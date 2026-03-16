# -*- coding: utf-8 -*-
# Copyright 2018, CS GROUP - France, https://www.csgroup.eu/
#
# This file is part of EODAG project
#     https://www.github.com/CS-SI/EODAG
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import datetime
import logging
import os
import shutil
import time
from json import JSONDecodeError
from typing import TYPE_CHECKING, Any, Optional, Union, cast
from urllib.parse import parse_qs, urlparse

import geojson
import requests
from lxml import etree
from requests import RequestException, Response
from requests.auth import AuthBase

from eodag.api.product.metadata_mapping import (
    NOT_AVAILABLE,
    OFFLINE_STATUS,
    ONLINE_STATUS,
    STAGING_STATUS,
    mtd_cfg_as_conversion_and_querypath,
    properties_from_json,
    properties_from_xml,
)
from eodag.utils import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    HTTP_REQ_TIMEOUT,
    USER_AGENT,
    Mime,
    Processor,
    ProgressCallback,
    string_to_jsonpath,
)
from eodag.utils.exceptions import (
    AuthenticationError,
    DownloadError,
    MisconfiguredError,
    NotAvailableError,
    QuotaExceededError,
    TimeOutError,
    ValidationError,
)

from ..contentiterator import ResponseContentIterator
from ..httputils import HttpUtils
from ..streamresponse import StreamResponse
from .base import Download

if TYPE_CHECKING:
    from jsonpath_ng import JSONPath

    from eodag.api.product import Asset
    from eodag.config import PluginConfig
    from eodag.types.download_args import DownloadConf
    from eodag.utils import Unpack

logger = logging.getLogger("eodag.download.http")


class HTTPDownload(Download):
    """HTTPDownload plugin. Handles product download over HTTP protocol"""

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(HTTPDownload, self).__init__(provider, config)

    def now(self) -> datetime.datetime:
        """return now datetime"""
        return datetime.datetime.now(datetime.timezone.utc)

    def download(  # type: ignore
        self,
        asset: Asset,
        auth: Optional[AuthBase] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        no_cache: bool = False,
        stream: bool = False,
        **kwargs: Unpack[DownloadConf],
    ) -> Union[Optional[str], StreamResponse]:
        """Inherits from .base:download"""

        # Check auth
        if auth is not None and not isinstance(auth, AuthBase):
            raise MisconfiguredError(f"Incompatible auth plugin: {type(auth)}")
        auth = cast(AuthBase, auth)

        # Force create progress_callback
        if not isinstance(progress_callback, ProgressCallback):
            logger.info("Progress bar unavailable")
            progress_callback = ProgressCallback(disable=True)
        progress_callback = cast(ProgressCallback, progress_callback)

        # Gather current asset statements
        statements = self.get_statements(asset, **kwargs)

        # Already downloaded ? (cache)
        if not no_cache:
            cache = self.get_cache(asset, statements, stream)
            if cache is not None:
                progress_callback.reset()
                return cache

        # Check if need order
        max_workers = getattr(self.config, "max_workers", os.cpu_count())

        # Use processor to manage concurrency of call instead of:
        _ = """
        self._order(
            asset,
            statements,
            auth,
            wait,
            timeout,
            no_cache
        )
        """
        shared = {"error": None}

        def order_callback(_, error: Exception):
            if error is not None:
                shared["error"] = error  # type: ignore
                Processor.stop()  # type: ignore

        taskid = Processor.queue(
            self._order,
            asset,
            statements,
            auth,
            wait,
            timeout,
            no_cache,
            q_timeout=int(timeout * 60),
            q_parallelize=max_workers,
            q_callback=order_callback,
            **kwargs,
        )
        if taskid is not None:
            Processor.wait(taskid)
        if shared["error"] is not None:
            raise shared["error"]

        # Use processor to manage concurrency of call instead of:
        _ = """
        response = self._download(
            asset,
            statements,
            auth,
            progress_callback,
            wait,
            timeout,
            **kwargs
        )
        """
        shared = {"response": None, "error": None}

        def download_callback(response, error: Exception):
            shared["response"] = response
            if error is not None:
                shared["error"] = error  # type: ignore
                Processor.stop()  # type: ignore

        taskid = Processor.queue(
            self._download,
            asset,
            statements,
            auth,
            progress_callback,
            wait,
            timeout,
            q_timeout=int(timeout * 60),
            q_parallelize=max_workers,
            q_callback=download_callback,
            **kwargs,
        )
        if taskid is not None:
            Processor.wait(taskid)
        if shared["error"] is not None:
            raise shared["error"]

        response: Optional[Response] = shared["response"]
        if response is None:
            if stream:
                raise DownloadError("Download fails")
            else:
                return None
        response = cast(Response, response)

        # Fill asset fields from retreives data
        self.asset_metadata_from_response(asset, response)

        # Rewrite response iterator to include progress_bar display
        sci = ResponseContentIterator(
            response, progress_callback, asset.filename, asset.size
        )

        # Remove previous download
        local_path = statements.get("local_path", None)
        if local_path is None:
            raise DownloadError("Fail to locate download local_file")
        if os.path.isfile(local_path):
            os.remove(local_path)
        elif os.path.isdir(local_path):
            shutil.rmtree(local_path)

        if not stream:

            # Flat download response to local file
            #   even if no_cache is True
            #   must write a file to return a path
            try:
                with open(local_path, "wb") as fd:
                    for chunk in sci:
                        fd.write(chunk)

                # File has no extension ?
                filename = os.path.basename(local_path)
                pos = filename.rfind(".")
                if pos < 0:
                    ext = Mime.guess_extension_from_fileheaders(local_path)
                    if ext is not None:
                        new_file_path = "{}.{}".format(local_path, ext)
                        os.rename(local_path, new_file_path)
                        local_path = new_file_path

                # Post process archive
                local_path = self.unpack_archive(
                    asset, local_path, progress_callback, **kwargs
                )
                self.asset_metadata_from_file(asset, local_path)

                # Update cache location
                statements["local_path"] = local_path
                statements["href"] = asset.get("href")
                self.set_statements(asset, statements, **kwargs)

                return local_path
            except Exception as e:
                # Not allow corrumpted download file
                if os.path.isfile(local_path):
                    os.remove(local_path)
                raise e

        else:

            # if allow cache, intercept served chunks to generate local cache
            if not no_cache:

                # During stream service, intercept chunks to save a cache
                passthrough_data = {
                    "fp": open(local_path, "wb"),
                    "asset": asset,
                    "local_path": local_path,
                    "progress_callback": progress_callback,
                    "statements": statements,
                    "kwargs": kwargs,
                }

                # Trigger when stream succedfully finished
                def on_complete():
                    passthrough_data["fp"].close()

                    # Post process archive
                    local_path = self.unpack_archive(
                        passthrough_data["asset"],
                        passthrough_data["local_path"],
                        passthrough_data["progress_callback"],
                        **passthrough_data["kwargs"],
                    )

                    # File has no extension ?
                    if os.path.isfile(local_path):
                        filename = os.path.basename(local_path)
                        pos = filename.rfind(".")
                        if pos < 0:
                            ext = Mime.guess_extension_from_fileheaders(local_path)
                            if ext is not None:
                                new_file_path = "{}.{}".format(local_path, ext)
                                os.rename(local_path, new_file_path)
                                local_path = new_file_path

                    # Update cache location
                    passthrough_data["statements"]["local_path"] = local_path
                    passthrough_data["statements"]["href"] = passthrough_data[
                        "asset"
                    ].get("href")
                    self.set_statements(
                        passthrough_data["asset"],
                        passthrough_data["statements"],
                        **kwargs,
                    )

                sci.on("complete", on_complete)

                # Trigger when stream chunk is transfered
                def on_chunk(chunk: bytes):
                    passthrough_data["fp"].write(chunk)

                sci.on("chunk", on_chunk)

                # Trigger when stream transfer fails
                def on_error(error: Exception):
                    passthrough_data["fp"].close()
                    os.remove(passthrough_data["local_path"])

                sci.on("error", on_error)

            # Stream response
            return StreamResponse(
                content=sci,
                filename=asset.filename,
                size=asset.size,
                headers=HttpUtils.format_headers(response.headers),
                media_type=asset.get("type", Mime.DEFAULT),
                status_code=response.status_code,
                arcname=None,
            )

    def _order(
        self,
        asset: Asset,
        statements: dict[str, Any],
        auth: AuthBase,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        no_cache: bool = False,
        **kwargs,
    ):
        """Manage asset orderbehaviour if needed, update asset and statements

        It will be executed once before the download, if the asset is orderable.
        Product ordering can be configured using the following download plugin parameters:
            - :attr:`~eodag.config.PluginConfig.order_enabled`: Wether order is enabled or not (may not use this method
              if no ``eodag:order_link`` exists)
            - :attr:`~eodag.config.PluginConfig.order_method`: (optional) HTTP request method, GET (default) or POST
            - :attr:`~eodag.config.PluginConfig.order_on_response`: (optional) things to do with obtained order
              response:
              - *metadata_mapping*: edit or add new asset propoerties properties
        Asset properties used for order:
            - **order_link**: order request URL
        :param asset: Asset to order
        :param statements: Asset statements
        :param auth: (optional) authenticated object
        :param wait: (optional) time to wait before retry a request
        :param timeout: (optional) time limit of process
        """

        if not no_cache:

            # If a previous run do some step, restore it's context
            for field in ["status_link", "search_link", "order_id"]:
                value = statements.get(field, "")
                if value != "":
                    asset["eodag:{}".format(field)] = value

            # Check if order was not aleready done
            if statements.get("ordered", False):
                asset["href"] = statements["href"]
                asset["order:status"] = ONLINE_STATUS
                return

        # If order status is not online, request order
        order_status = asset.get("order:status", OFFLINE_STATUS)
        if order_status != ONLINE_STATUS:

            if not getattr(self.config, "order_enabled", False):
                raise NotAvailableError(
                    "Asset {} is not available for download and order is not supported for {}".format(
                        asset.key, asset.product.provider
                    )
                )

            timeout_at = self.now() + datetime.timedelta(minutes=max(timeout, 0))
            restart_at = self.now()
            completed = False

            while not completed and self.now() < timeout_at:

                if asset.get("order:status", ONLINE_STATUS) == ONLINE_STATUS:
                    completed = True
                elif self.now() < restart_at:
                    # Have to wait (restart_at - self.now()).total_seconds() before retru order
                    time.sleep(1)
                else:
                    status_link = asset.get("eodag:status_link", "")
                    if status_link == "":

                        # no status link ? request an order
                        try:
                            self._order_request(asset=asset, auth=auth)
                        except NotAvailableError as e:
                            raise NotAvailableError(
                                "Asset {} is not available for download and order is not supported for {}: {}",
                                asset.key,
                                asset.product.provider,
                                str(e),
                            )
                        except Exception as e:
                            raise e

                        status_link = asset.get("eodag:status_link", "")
                        if status_link == "":
                            raise NotAvailableError(
                                "Asset {} order fail, provider does not return status link",
                                asset.key,
                            )

                        # Save current statement
                        statements["search_link"] = asset.get("eodag:search_link", "")

                    else:

                        # wait for order complete
                        retry_after = None
                        try:
                            retry_after = self._order_status(asset=asset, auth=auth)
                        except Exception as e:
                            # Order could be gone, save current statement
                            statements["status_link"] = ""
                            statements["search_link"] = ""
                            statements["order_id"] = ""
                            self.set_statements(asset, statements, **kwargs)
                            raise e

                        if asset.get("order:status") != ONLINE_STATUS:
                            wait_offset = datetime.timedelta(minutes=wait)
                            if retry_after is not None:
                                wait_offset = datetime.timedelta(seconds=retry_after)

                            if self.now() + wait_offset < timeout_at:
                                logger.debug(
                                    "Asset {} order not ready, check again after: {} seconds".format(
                                        asset.key, wait_offset.total_seconds()
                                    )
                                )
                                restart_at = self.now() + wait_offset
                            else:
                                # No need to wait more if next try ll be timeouted
                                raise NotAvailableError(
                                    "Asset {} could not be downloaded: order timeout".format(
                                        asset.key
                                    )
                                )

            if not completed:
                asset["order:status"] = OFFLINE_STATUS
                raise NotAvailableError(
                    "Asset {} could not be downloaded: order timeout".format(asset.key)
                )
            else:
                logger.debug("Asset {} order completed".format(asset.key))

                statements["ordered"] = True
                statements["order_id"] = asset.get("eodag:order_id", "")
                statements["href"] = asset.get("href")
                self.set_statements(asset, statements, **kwargs)

    def _order_request(self, asset: Asset, auth: Optional[AuthBase] = None):
        """Send asset order request, and update asset with status_link
        It will be executed once before the download retry loop, if the product is orderable
        and has ``eodag:order_link`` in its properties.
        Product ordering can be configured using the following download plugin parameters:
            - :attr:`~eodag.config.PluginConfig.order_enabled`: Wether order is enabled or not (may not use this method
              if no ``eodag:order_link`` exists)
            - :attr:`~eodag.config.PluginConfig.order_method`: (optional) HTTP request method, GET (default) or POST
            - :attr:`~eodag.config.PluginConfig.order_on_response`: (optional) things to do with obtained order
              response:
              - *metadata_mapping*: edit or add new product propoerties properties
        Asset properties used for order:
            - **order_link**: order request URL
        :param asset: Asset to order
        :param auth: (optional) authenticated object
        :param kwargs: download additional kwargs
        :returns: the returned json status response
        """
        if asset["order:status"] == STAGING_STATUS:
            raise DownloadError("Asset {} order already in progress".format(asset.key))

        asset["order:status"] = STAGING_STATUS
        order_method = getattr(self.config, "order_method", "GET").upper()
        order_url = asset.get("order_link", "")
        ssl_verify = getattr(self.config, "ssl_verify", True)
        timeout = getattr(self.config, "timeout", HTTP_REQ_TIMEOUT)
        headers = {**getattr(self.config, "order_headers", {}), **USER_AGENT}
        order_kwargs: dict[str, Any] = {}

        order_response_mapping = getattr(self.config, "order_on_response", None)
        if order_response_mapping is None:
            raise DownloadError(
                "Provider {} configuration require download.order_on_response".format(
                    asset.product.provider
                )
            )
        order_response_mapping = order_response_mapping.get("metadata_mapping", None)
        if order_response_mapping is None:
            raise DownloadError(
                "Provider {} configuration require download.order_on_response.metadata_mapping".format(
                    asset.product.provider
                )
            )
        order_response_mapping = mtd_cfg_as_conversion_and_querypath(
            order_response_mapping
        )

        if order_url == "":
            asset["order:status"] = ONLINE_STATUS
            raise DownloadError("Asset {} order has no order_link".format(asset.key))

        if order_method == "POST":
            # separate url & parameters
            parts = urlparse(order_url)
            query_dict = {}
            # `parts.query` may be a JSON with query strings as one of values. If `parse_qs` is executed as first step,
            # the resulting `query_dict` would be erroneous.
            try:
                query_dict = geojson.loads(parts.query)
            except JSONDecodeError:
                try:
                    # due to the fact how metadata formatting works, there might be 2 {} around the string
                    query_dict = geojson.loads(parts.query[1:-1])
                except JSONDecodeError:
                    if parts.query:
                        query_dict = parse_qs(parts.query)
            order_url = parts._replace(query="").geturl()
            if query_dict:
                order_kwargs["json"] = query_dict

        try:
            logger.debug(
                "Asset {} order request {} {}".format(
                    asset.key, order_method, order_url
                )
            )
            with requests.request(
                method=order_method,
                url=order_url,
                auth=auth,
                timeout=timeout,
                headers=headers,
                verify=ssl_verify,
                **order_kwargs,
            ) as response:
                logger.debug(f"{order_method} {order_url} {headers} {order_kwargs}")
                try:
                    response.raise_for_status()
                    asset["order:status"] = STAGING_STATUS
                except RequestException as e:
                    self._check_auth_exception(e)
                    QuotaExceededError.raise_if_quota_exceeded(e, self.provider)
                    msg = "Asset {} could not be ordered".format(asset.key)
                    asset["order:status"] = OFFLINE_STATUS
                    if e.response is not None and e.response.status_code == 400:
                        raise ValidationError.from_error(e, msg) from e
                    else:
                        raise DownloadError.from_error(e, msg) from e

                json_response = response.json()
                properties_update = properties_from_json(
                    {"json": json_response, "headers": {**response.headers}},
                    order_response_mapping,
                )
                for name in properties_update:
                    if properties_update[name] not in [None, NOT_AVAILABLE]:
                        asset[name] = properties_update[name]

        except requests.exceptions.Timeout as exc:
            asset["order:status"] = OFFLINE_STATUS
            raise TimeOutError(exc, timeout=timeout) from exc

    def _order_status(
        self, asset: Asset, auth: Optional[AuthBase] = None
    ) -> Optional[int]:
        """Check asset order status, and update asset, if not ready, return delay to wait extracted from retry after

        It will be executed before each download retry.
        Product order status request can be configured using the following download plugin parameters:

            - :attr:`~eodag.config.PluginConfig.order_status`: :class:`~eodag.config.PluginConfig.OrderStatus`

        Product properties used for order status:

            - **eodag:status_link**: order status request URL

        :param product: The ordered EO product
        :param auth: (optional) authenticated object
        :param kwargs: download additional kwargs
        """

        retry_after: Optional[int] = None
        status_config = getattr(self.config, "order_status", None)
        if status_config is None:
            raise DownloadError(
                "Asset {} order_status fails: provider configuration require dowload.order_status"
            )

        status_metadata_mapping = status_config.get("metadata_mapping", None)
        if status_metadata_mapping is None:
            raise DownloadError(
                "Asset {} order_status fails: provider configuration require dowload.order_status.metadata_mapping"
            )
        status_metadata_mapping = mtd_cfg_as_conversion_and_querypath(
            status_metadata_mapping
        )

        order_response_mapping = getattr(self.config, "order_on_response", None)
        if order_response_mapping is None:
            raise DownloadError(
                "Provider {} configuration require download.order_on_response".format(
                    asset.product.provider
                )
            )
        order_response_mapping = order_response_mapping.get("metadata_mapping", None)
        if order_response_mapping is None:
            raise DownloadError(
                "Provider {} configuration require download.order_on_response.metadata_mapping".format(
                    asset.product.provider
                )
            )
        order_response_mapping = mtd_cfg_as_conversion_and_querypath(
            order_response_mapping
        )

        success_code: Optional[int] = status_config.get("success", {}).get(
            "http_code", None
        )
        timeout = getattr(self.config, "timeout", HTTP_REQ_TIMEOUT)
        response = None

        def _request(
            url: str,
            method: str = "GET",
            headers: Optional[dict[str, Any]] = None,
            json: Optional[Any] = None,
            timeout: int = HTTP_REQ_TIMEOUT,
        ) -> Response:
            """Send request and handle allow redirects"""
            try:
                logger.debug(
                    "Asset {} order status {} {}".format(asset.key, method, url)
                )
                response = requests.request(
                    method=method,
                    url=url,
                    auth=auth,
                    timeout=timeout,
                    headers={**(headers or {}), **USER_AGENT},
                    allow_redirects=False,  # Redirection is manually handled
                    json=json,
                )
                logger.debug(
                    "Asset {} order download status request responded with {}".format(
                        asset.key, response.status_code
                    )
                )

                response.raise_for_status()  # Raise an exception if status code indicates an error

                # Handle redirection (if needed)
                if (
                    300 <= response.status_code < 400
                    and response.status_code != success_code
                ):
                    # cf: https://www.rfc-editor.org/rfc/rfc9110.html#name-303-see-other
                    if response.status_code == 303:
                        method = "GET"
                    if new_url := response.headers.get("Location"):
                        return _request(new_url, method, headers, json, timeout)
                return response
            except requests.exceptions.Timeout as exc:
                raise TimeOutError(exc, timeout=timeout) from exc

        status_request: dict[str, Any] = status_config.get("request", {})
        status_request_method = str(status_request.get("method", "GET")).upper()

        status_url = asset.get("eodag:status_link", "")
        json_data = None
        if status_request_method == "POST":
            # separate url & parameters
            parts = urlparse(str(asset.get("eodag:status_link")))
            status_url = parts._replace(query="").geturl()
            query_dict = parse_qs(parts.query)
            if not query_dict and parts.query:
                query_dict = geojson.loads(parts.query)
            json_data = query_dict if query_dict else None

        if status_url == "":
            raise DownloadError(
                "Asset {} order status fail: no status_link found".format(asset.key)
            )

        # check header for success before full status request
        skip_parsing_status_response = False
        status_dict: dict[str, Any] = {}
        config_on_success: dict[str, Any] = status_config.get("on_success", {})
        on_success_mm = config_on_success.get("metadata_mapping", {})

        status_response_content_needed = (
            False
            if not any([v.startswith("$.json.") for v in on_success_mm.values()])
            else True
        )
        if success_code:
            try:
                response = _request(
                    status_url,
                    "HEAD",
                    status_request.get("headers"),
                    json_data,
                    timeout,
                )

                if response is not None:
                    headers = HttpUtils.format_headers(response.headers)
                    buffer = headers.get("Retry-After", None)
                    if buffer is not None and buffer.isnumeric():
                        retry_after = int(buffer)
                    if (
                        response.status_code == success_code
                        and not status_response_content_needed
                    ):
                        # success and no need to get status response content
                        skip_parsing_status_response = True

            except RequestException as e:
                logger.debug(e)

        if not skip_parsing_status_response:
            # status request
            try:
                response = _request(
                    status_url,
                    status_request_method,
                    status_request.get("headers"),
                    json_data,
                    timeout,
                )
                if response is not None:
                    headers = HttpUtils.format_headers(response.headers)
                    buffer = headers.get("Retry-After", None)
                    if buffer is not None and buffer.isnumeric():
                        retry_after = int(buffer)

                    if (
                        response.status_code == success_code
                        and not status_response_content_needed
                    ):
                        # success and no need to get status response content
                        skip_parsing_status_response = True
            except RequestException as e:
                msg = "Asset {} order status could not be checked".format(asset.key)
                if e.response is not None and e.response.status_code == 400:
                    raise ValidationError.from_error(e, msg) from e
                else:
                    raise DownloadError.from_error(e, msg) from e

        if not skip_parsing_status_response and response is not None:
            # status request
            json_response = response.json()
            if not isinstance(json_response, dict):
                raise RequestException("response content is not a dict")
            status_dict = json_response
            logger.debug("Asset {} parsing order status response".format(asset.key))
            status_dict = properties_from_json(
                {"json": response.json(), "headers": {**response.headers}},
                status_metadata_mapping,
            )
            # display progress percentage
            if "eodag:order_percent" in status_dict:
                status_percent = str(status_dict["eodag:order_percent"])
                if status_percent.isdigit():
                    status_percent += "%"
                logger.info(
                    "Asset {} order status: {}".format(asset.key, status_percent)
                )

            properties_update = {}
            for k, v in status_dict.items():
                if k == "eodag:order_status" or v not in [None, NOT_AVAILABLE]:
                    asset[k] = v
            status_message = status_dict.get("eodag:order_message")

            # handle status error
            errors: dict[str, Any] = status_config.get("error", {})
            if errors and errors.items() <= status_dict.items():
                raise DownloadError(
                    "Provider {} returned: {}".format(
                        asset.product.provider,
                        status_dict.get("error_message", status_message),
                    )
                )

        asset["order:status"] = STAGING_STATUS
        success_status: dict[str, Any] = status_config.get("success", {}).get(
            "eodag:order_status"
        )

        # if not success
        if (
            response is None
            or (
                success_status is not None
                and success_status != status_dict.get("eodag:order_status")
            )
            or (success_code is not None and success_code != response.status_code)
        ):
            # Remove the download link if the order has not been completed or was not successful
            asset["href"] = ""
            return retry_after

        asset["order:status"] = ONLINE_STATUS
        if not config_on_success:
            # Nothing left to do
            return retry_after

        # need search on success ?
        if config_on_success.get("need_search", False):
            search_link = asset.get("eodag:search_link", None)
            if search_link is None:
                raise DownloadError(
                    "Asset {} need_search fail: no search_link found".format(asset.key)
                )

            logger.debug("Search for new location: {}".format(search_link))
            try:
                response = _request(search_link, timeout=timeout)
            except RequestException as e:
                logger.warning(
                    "Asset {} order status could not be checked, request returned: {}".format(
                        asset.key, str(e)
                    )
                )
                msg = "Asset {} order status could not be checked".format(asset.key)
                if e.response is not None and e.response.status_code == 400:
                    raise ValidationError.from_error(e, msg) from e
                else:
                    raise DownloadError.from_error(e, msg) from e

        result_type = config_on_success.get("result_type", "json")
        result_entry = config_on_success.get("results_entry")

        on_success_mm_querypath = (
            # append product.properties as input for on success response parsing
            mtd_cfg_as_conversion_and_querypath(on_success_mm)
            if on_success_mm
            else {}
        )
        try:
            if result_type == "xml":
                if not result_entry:
                    raise MisconfiguredError(
                        '"result_entry" is required with "result_type" "xml"'
                        'in "order_status.on_success"'
                    )
                root_node = etree.fromstring(response.content)
                namespaces = {k or "ns": v for k, v in root_node.nsmap.items()}
                results = [
                    etree.tostring(entry)
                    for entry in root_node.xpath(
                        result_entry,
                        namespaces=namespaces,
                    )
                ]
                if len(results) != 1:
                    raise DownloadError(
                        "Could not get a single result after order success for "
                        f"{asset.get('eodag:search_link')} request. "
                        f"Please search and download again"
                    )
                assert isinstance(results, list), "results must be in a list"
                # single result
                result = results[0]
                if on_success_mm_querypath:
                    properties_update = properties_from_xml(
                        result,
                        on_success_mm_querypath,
                    )
                else:
                    properties_update = {}
            else:
                json_response = (
                    response.json()
                    if "application/json" in response.headers.get("Content-Type", "")
                    or "application/geo+json"
                    in response.headers.get("Content-Type", "")
                    else {}
                )
                if result_entry:
                    entry_jsonpath: JSONPath = string_to_jsonpath(
                        result_entry, force=True
                    )
                    json_response = entry_jsonpath.find(json_response)
                    raise NotImplementedError(
                        'result_entry in config.on_success is not yet supported for result_type "json"'
                    )
                if on_success_mm_querypath:
                    logger.debug(
                        "Parsing on-success metadata-mapping using order status response"
                    )
                    properties_update = properties_from_json(
                        {"json": json_response, "headers": {**response.headers}},
                        on_success_mm_querypath,
                    )
                    # only keep properties to update (remove product.properties added for parsing)
                    properties_update = {
                        k: v for k, v in properties_update.items() if k in on_success_mm
                    }
                else:
                    properties_update = {}
        except Exception as e:
            if isinstance(e, DownloadError):
                raise
            logger.debug(e)
            raise DownloadError(
                "Asset {} could not parse result after order success. Please search and download again".format(
                    asset.key
                )
            ) from e

        # update product
        if "href" in properties_update:
            asset["href"] = properties_update["href"]
        else:
            json_response = response.json()
            properties_update = properties_from_json(
                {"json": json_response, "headers": {**response.headers}},
                order_response_mapping,
            )
            for name in properties_update:
                if properties_update[name] not in [None, NOT_AVAILABLE]:
                    asset[name] = properties_update[name]

        return retry_after

    def _download(
        self,
        asset: Asset,
        statements: dict[str, Any],
        auth: Optional[AuthBase],
        progress_callback: ProgressCallback,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Unpack[DownloadConf],
    ) -> Response:

        href = asset.get("href", "")
        if href == "":
            href = statements.get("href", "")
            if href == "":
                raise DownloadError(
                    "Asset {} has no href to download".format(asset.key)
                )

        ssl_verify = getattr(self.config, "ssl_verify", True)
        params = kwargs.pop("dl_url_params", getattr(self.config, "dl_url_params", {}))
        req_method = asset.get(
            "eodag:download_method", getattr(self.config, "method", "GET")
        ).lower()

        req_url: str = href
        req_kwargs: dict[str, Any] = {}
        if req_method == "post":
            # separate url & parameters
            parts = urlparse(href)
            query_dict = parse_qs(parts.query)
            if not query_dict and parts.query:
                query_dict = geojson.loads(parts.query)
            req_url = parts._replace(query="").geturl()
            req_kwargs = {"json": query_dict} if query_dict else {}

        if req_url.startswith(NOT_AVAILABLE):
            raise NotAvailableError("Download link is not available")

        if getattr(self.config, "no_auth_download", False):
            auth = None

        session = requests.Session()
        response = None
        try:
            timeout_at = self.now() + datetime.timedelta(minutes=max(timeout, 0))
            restart_at = self.now()
            wait_offset = datetime.timedelta(minutes=wait)
            completed = False
            response = None

            while not completed and self.now() < timeout_at:
                if self.now() < restart_at:
                    # Have to wait (restart_at - self.now()).total_seconds() before retru order
                    time.sleep(1)
                else:
                    try:
                        response = session.request(
                            req_method,
                            req_url,
                            stream=True,
                            auth=auth,
                            params=params,
                            headers=USER_AGENT,
                            timeout=timeout,
                            verify=ssl_verify,
                            **req_kwargs,
                        )
                        if response.status_code == 202:
                            # Content not yet ready
                            restart_at = self.now() + wait_offset
                            logger.debug(
                                "Asset {} download not ready yet, check again after: {} seconds".format(
                                    asset.key, wait_offset.total_seconds()
                                )
                            )
                        elif response.status_code == 429:
                            # Too many requests
                            raise QuotaExceededError()

                        elif response.status_code == 422:
                            # HTTP GONE
                            raise NotAvailableError(
                                "Asset {} not avaible anymore".format(asset.key)
                            )
                        else:
                            response.raise_for_status()
                            completed = True
                    except requests.exceptions.Timeout as e:
                        restart_at = self.now() + wait_offset
                        if restart_at < timeout_at:
                            logger.debug(
                                "Asset {} download timeout, check again after: {} seconds".format(
                                    asset.key, wait_offset.total_seconds()
                                )
                            )
                        else:
                            raise e
        except requests.exceptions.MissingSchema:
            # location is not a valid url -> asset is not available yet
            raise NotAvailableError("Asset {} not avaible anymore".format(asset.key))
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(exc, timeout=timeout) from exc
        except RequestException as e:

            # Order could be gone, save current statement
            statements["status_link"] = ""
            statements["search_link"] = ""
            statements["order_id"] = ""
            self.set_statements(asset, statements, **kwargs)

            self._check_auth_exception(e)
            if response is not None:
                if response.status_code == 410:  # HTTP Gone
                    raise DownloadError(
                        "Asset {} is no more avaible (http: 410)".format(asset.key)
                    ) from e
                if response.status_code == 404:
                    raise DownloadError(
                        "Asset {} not found (http: 404)".format(asset.key)
                    ) from e

            raise DownloadError("Asset {} download is empty".format(asset.key)) from e

        if response is None:
            raise DownloadError("Asset {} download is empty".format(asset.key))

        asset["href"] = href
        return response

    def _check_auth_exception(self, e: Optional[RequestException]) -> None:
        # check if error is identified as auth_error in provider conf
        auth_errors = getattr(self.config, "auth_error_code", [None])
        if not isinstance(auth_errors, list):
            auth_errors = [auth_errors]
        response_text = (
            e.response.text.strip() if e is not None and e.response is not None else ""
        )
        if (
            e is not None
            and e.response is not None
            and e.response.status_code in auth_errors
        ):
            raise AuthenticationError(
                f"Please check your credentials for {self.provider}.",
                f"HTTP Error {e.response.status_code} returned.",
                response_text,
            )


__all__ = ["HTTPDownload"]
