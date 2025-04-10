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

import logging
import os
import re
import shutil
import tarfile
import zipfile
from datetime import datetime
from email.message import Message
from itertools import chain
from json import JSONDecodeError
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator, Optional, TypedDict, Union, cast
from urllib.parse import parse_qs, urlparse

import geojson
import requests
from lxml import etree
from requests import RequestException
from requests.auth import AuthBase
from requests.structures import CaseInsensitiveDict
from stream_zip import ZIP_AUTO, stream_zip

from eodag.api.product.metadata_mapping import (
    NOT_AVAILABLE,
    OFFLINE_STATUS,
    ONLINE_STATUS,
    STAGING_STATUS,
    mtd_cfg_as_conversion_and_querypath,
    properties_from_json,
    properties_from_xml,
)
from eodag.plugins.download.base import Download
from eodag.utils import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    DEFAULT_STREAM_REQUESTS_TIMEOUT,
    HTTP_REQ_TIMEOUT,
    USER_AGENT,
    ProgressCallback,
    StreamResponse,
    flatten_top_directories,
    guess_extension,
    guess_file_type,
    parse_header,
    path_to_uri,
    rename_with_version,
    sanitize,
    string_to_jsonpath,
    uri_to_path,
)
from eodag.utils.exceptions import (
    AuthenticationError,
    DownloadError,
    MisconfiguredError,
    NotAvailableError,
    TimeOutError,
    ValidationError,
)

if TYPE_CHECKING:
    from requests import Response

    from eodag.api.product import Asset, EOProduct  # type: ignore
    from eodag.api.search_result import SearchResult
    from eodag.config import PluginConfig
    from eodag.types import S3SessionKwargs
    from eodag.types.download_args import DownloadConf
    from eodag.utils import DownloadedCallback, Unpack

logger = logging.getLogger("eodag.download.http")


class HTTPDownload(Download):
    """HTTPDownload plugin. Handles product download over HTTP protocol

    :param provider: provider name
    :param config: Download plugin configuration:

        * :attr:`~eodag.config.PluginConfig.type` (``str``) (**mandatory**): ``HTTPDownload``
        * :attr:`~eodag.config.PluginConfig.base_uri` (``str``): default endpoint url
        * :attr:`~eodag.config.PluginConfig.method` (``str``): HTTP request method for the download request (``GET`` or
          ``POST``); default: ``GET``
        * :attr:`~eodag.config.PluginConfig.extract` (``bool``): if the content of the downloaded file should be
          extracted; default: ``True``
        * :attr:`~eodag.config.PluginConfig.auth_error_code` (``int``): which error code is returned in case of an
          authentication error
        * :attr:`~eodag.config.PluginConfig.dl_url_params` (``dict[str, Any]``): parameters to be
          added to the query params of the request
        * :attr:`~eodag.config.PluginConfig.archive_depth` (``int``): level in extracted path tree where to find data;
          default: ``1``
        * :attr:`~eodag.config.PluginConfig.flatten_top_dirs` (``bool``): if the directory structure should be
          flattened; default: ``True``
        * :attr:`~eodag.config.PluginConfig.ignore_assets` (``bool``): ignore assets and download using downloadLink;
          default: ``False``
        * :attr:`~eodag.config.PluginConfig.timeout` (``int``): time to wait until request timeout in seconds;
          default: ``5``
        * :attr:`~eodag.config.PluginConfig.ssl_verify` (``bool``): if the ssl certificates should be verified in
          requests; default: ``True``
        * :attr:`~eodag.config.PluginConfig.no_auth_download` (``bool``): if the download should be done without
          authentication; default: ``True``
        * :attr:`~eodag.config.PluginConfig.order_enabled` (``bool``): if the product has to be ordered to download it;
          if this parameter is set to true, a mapping for the orderLink has to be added to the metadata mapping of
          the search plugin used for the provider; default: ``False``
        * :attr:`~eodag.config.PluginConfig.order_method` (``str``): HTTP request method for the order request (``GET``
          or ``POST``); default: ``GET``
        * :attr:`~eodag.config.PluginConfig.order_headers` (``[dict[str, str]]``): headers to be added to the order
          request
        * :attr:`~eodag.config.PluginConfig.order_on_response` (:class:`~eodag.config.PluginConfig.OrderOnResponse`):
          a typed dictionary containing the key ``metadata_mapping`` which can be used to add new product properties
          based on the data in response to the order request
        * :attr:`~eodag.config.PluginConfig.order_status` (:class:`~eodag.config.PluginConfig.OrderStatus`):
          configuration to handle the order status; contains information which method to use, how the response data is
          interpreted, which status corresponds to success, ordered and error and what should be done on success.
        * :attr:`~eodag.config.PluginConfig.products` (``dict[str, dict[str, Any]``): product type specific config; the
          keys are the product types, the values are dictionaries which can contain the key
          :attr:`~eodag.config.PluginConfig.extract` to overwrite the provider config for a specific product type

    """

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(HTTPDownload, self).__init__(provider, config)

    def _order(
        self,
        product: EOProduct,
        auth: Optional[AuthBase] = None,
        **kwargs: Unpack[DownloadConf],
    ) -> Optional[dict[str, Any]]:
        """Send product order request.

        It will be executed once before the download retry loop, if the product is OFFLINE
        and has `orderLink` in its properties.
        Product ordering can be configured using the following download plugin parameters:

            - :attr:`~eodag.config.PluginConfig.order_enabled`: Wether order is enabled or not (may not use this method
              if no `orderLink` exists)

            - :attr:`~eodag.config.PluginConfig.order_method`: (optional) HTTP request method, GET (default) or POST

            - :attr:`~eodag.config.PluginConfig.order_on_response`: (optional) things to do with obtained order
              response:

              - *metadata_mapping*: edit or add new product propoerties properties

        Product properties used for order:

            - **orderLink**: order request URL

        :param product: The EO product to order
        :param auth: (optional) authenticated object
        :param kwargs: download additional kwargs
        :returns: the returned json status response
        """
        product.properties["storageStatus"] = STAGING_STATUS

        order_method = getattr(self.config, "order_method", "GET").upper()
        ssl_verify = getattr(self.config, "ssl_verify", True)
        timeout = getattr(self.config, "timeout", HTTP_REQ_TIMEOUT)
        OrderKwargs = TypedDict(
            "OrderKwargs", {"json": dict[str, Union[Any, list[str]]]}, total=False
        )
        order_kwargs: OrderKwargs = {}
        if order_method == "POST":
            # separate url & parameters
            parts = urlparse(str(product.properties["orderLink"]))
            query_dict = {}
            # `parts.query` may be a JSON with query strings as one of values. If `parse_qs` is executed as first step,
            # the resulting `query_dict` would be erroneous.
            try:
                query_dict = geojson.loads(parts.query)
            except JSONDecodeError:
                if parts.query:
                    query_dict = parse_qs(parts.query)
            order_url = parts._replace(query="").geturl()
            if query_dict:
                order_kwargs["json"] = query_dict
        else:
            order_url = product.properties["orderLink"]
            order_kwargs = {}

        headers = {**getattr(self.config, "order_headers", {}), **USER_AGENT}
        try:
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
                    ordered_message = response.text
                    logger.debug(ordered_message)
                    product.properties["storageStatus"] = STAGING_STATUS
                except RequestException as e:
                    self._check_auth_exception(e)
                    msg = f"{product.properties['title']} could not be ordered"
                    if e.response is not None and e.response.status_code == 400:
                        raise ValidationError.from_error(e, msg) from e
                    else:
                        raise DownloadError.from_error(e, msg) from e

                return self.order_response_process(response, product)
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(exc, timeout=timeout) from exc

    def order_response_process(
        self, response: Response, product: EOProduct
    ) -> Optional[dict[str, Any]]:
        """Process order response

        :param response: The order response
        :param product: The orderd EO product
        :returns: the returned json status response
        """
        on_response_mm = getattr(self.config, "order_on_response", {}).get(
            "metadata_mapping", {}
        )
        if not on_response_mm:
            return None

        logger.debug("Parsing order response to update product metada-mapping")
        on_response_mm_jsonpath = mtd_cfg_as_conversion_and_querypath(
            on_response_mm,
        )

        json_response = response.json()

        properties_update = properties_from_json(
            {"json": json_response, "headers": {**response.headers}},
            on_response_mm_jsonpath,
        )
        product.properties.update(
            {k: v for k, v in properties_update.items() if v != NOT_AVAILABLE}
        )
        # the job id becomes the product id for EcmwfSearch products
        if "ORDERABLE" in product.properties.get("id", ""):
            product.properties["id"] = product.properties.get(
                "orderId", product.properties["id"]
            )
            product.properties["title"] = (
                (product.product_type or product.provider).upper()
                + "_"
                + product.properties["id"]
            )
        if "downloadLink" in product.properties:
            product.remote_location = product.location = product.properties[
                "downloadLink"
            ]
            logger.debug(f"Product location updated to {product.location}")

        return json_response

    def _order_status(
        self,
        product: EOProduct,
        auth: Optional[AuthBase] = None,
    ) -> None:
        """Send product order status request.

        It will be executed before each download retry.
        Product order status request can be configured using the following download plugin parameters:

            - :attr:`~eodag.config.PluginConfig.order_status`: :class:`~eodag.config.PluginConfig.OrderStatus`

        Product properties used for order status:

            - **orderStatusLink**: order status request URL

        :param product: The ordered EO product
        :param auth: (optional) authenticated object
        :param kwargs: download additional kwargs
        """

        status_config = getattr(self.config, "order_status", {})
        success_code: Optional[int] = status_config.get("success", {}).get("http_code")

        timeout = getattr(self.config, "timeout", HTTP_REQ_TIMEOUT)

        def _request(
            url: str,
            method: str = "GET",
            headers: Optional[dict[str, Any]] = None,
            json: Optional[Any] = None,
            timeout: int = HTTP_REQ_TIMEOUT,
        ) -> Response:
            """Send request and handle allow redirects"""

            logger.debug(f"{method} {url} {headers} {json}")
            try:
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
                    f"Order download status request responded with {response.status_code}"
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

        if status_request_method == "POST":
            # separate url & parameters
            parts = urlparse(str(product.properties["orderStatusLink"]))
            status_url = parts._replace(query="").geturl()
            query_dict = parse_qs(parts.query)
            if not query_dict and parts.query:
                query_dict = geojson.loads(parts.query)
            json_data = query_dict if query_dict else None
        else:
            status_url = product.properties["orderStatusLink"]
            json_data = None

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
                if (
                    response.status_code == success_code
                    and not status_response_content_needed
                ):
                    # success and no need to get status response content
                    skip_parsing_status_response = True
            except RequestException as e:
                msg = (
                    f"{product.properties.get('title') or product.properties.get('id') or product} "
                    "order status could not be checked"
                )
                if e.response is not None and e.response.status_code == 400:
                    raise ValidationError.from_error(e, msg) from e
                else:
                    raise DownloadError.from_error(e, msg) from e

        if not skip_parsing_status_response:
            # status request
            json_response = response.json()
            if not isinstance(json_response, dict):
                raise RequestException("response content is not a dict")
            status_dict = json_response

            status_mm = status_config.get("metadata_mapping", {})
            status_mm_jsonpath = (
                mtd_cfg_as_conversion_and_querypath(
                    status_mm,
                )
                if status_mm
                else {}
            )
            logger.debug("Parsing order status response")
            status_dict = properties_from_json(
                {"json": response.json(), "headers": {**response.headers}},
                status_mm_jsonpath,
            )

            # display progress percentage
            if "percent" in status_dict:
                status_percent = str(status_dict["percent"])
                if status_percent.isdigit():
                    status_percent += "%"
                logger.info(
                    f"{product.properties['title']} order status: {status_percent}"
                )

            product.properties.update(
                {k: v for k, v in status_dict.items() if v != NOT_AVAILABLE}
            )

            product.properties["orderStatus"] = status_dict.get("status")

            status_message = status_dict.get("message")

            # handle status error
            errors: dict[str, Any] = status_config.get("error", {})
            if errors and errors.items() <= status_dict.items():
                raise DownloadError(
                    f"Provider {product.provider} returned: {status_dict.get('error_message', status_message)}"
                )

        product.properties["storageStatus"] = STAGING_STATUS

        success_status: dict[str, Any] = status_config.get("success", {}).get("status")
        # if not success
        if (success_status and success_status != status_dict.get("status")) or (
            success_code and success_code != response.status_code
        ):
            return None

        product.properties["storageStatus"] = ONLINE_STATUS

        if not config_on_success:
            # Nothing left to do
            return None

        # need search on success ?
        if config_on_success.get("need_search"):
            logger.debug(f"Search for new location: {product.properties['searchLink']}")
            try:
                response = _request(product.properties["searchLink"], timeout=timeout)
            except RequestException as e:
                logger.warning(
                    "%s order status could not be checked, request returned %s",
                    product.properties["title"],
                    e,
                )
                msg = f"{product.properties['title']} order status could not be checked"
                if e.response is not None and e.response.status_code == 400:
                    raise ValidationError.from_error(e, msg) from e
                else:
                    raise DownloadError.from_error(e, msg) from e

        result_type = config_on_success.get("result_type", "json")
        result_entry = config_on_success.get("results_entry")

        on_success_mm_querypath = (
            # append product.properties as input for on success response parsing
            mtd_cfg_as_conversion_and_querypath(
                dict(
                    {k: str(v) for k, v in product.properties.items()}, **on_success_mm
                ),
            )
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
                        f"{product.properties['searchLink']} request. "
                        f"Please search and download {product} again"
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
                    else {}
                )
                if result_entry:
                    entry_jsonpath = string_to_jsonpath(result_entry, force=True)
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
                f"Could not parse result after order success. Please search and download {product} again"
            ) from e

        # update product
        product.properties.update(properties_update)
        if "downloadLink" in properties_update:
            product.location = product.remote_location = product.properties[
                "downloadLink"
            ]
        else:
            self.order_response_process(response, product)

    def download(
        self,
        product: EOProduct,
        auth: Optional[Union[AuthBase, S3SessionKwargs]] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Unpack[DownloadConf],
    ) -> Optional[str]:
        """Download a product using HTTP protocol.

        The downloaded product is assumed to be a Zip file. If it is not,
        the user is warned, it is renamed to remove the zip extension and
        no further treatment is done (no extraction)
        """
        if auth is not None and not isinstance(auth, AuthBase):
            raise MisconfiguredError(f"Incompatible auth plugin: {type(auth)}")

        if progress_callback is None:
            logger.info(
                "Progress bar unavailable, please call product.download() instead of plugin.download()"
            )
            progress_callback = ProgressCallback(disable=True)

        fs_path, record_filename = self._prepare_download(
            product,
            progress_callback=progress_callback,
            **kwargs,
        )
        if not fs_path or not record_filename:
            if fs_path:
                product.location = path_to_uri(fs_path)
            return fs_path

        # download assets if exist instead of remote_location
        if len(product.assets) > 0 and (
            not getattr(self.config, "ignore_assets", False)
            or kwargs.get("asset", None) is not None
        ):
            try:
                fs_path = self._download_assets(
                    product,
                    fs_path,
                    record_filename,
                    auth,
                    progress_callback,
                    **kwargs,
                )
                if kwargs.get("asset", None) is None:
                    product.location = path_to_uri(fs_path)
                return fs_path
            except NotAvailableError as e:
                if kwargs.get("asset", None) is not None:
                    raise NotAvailableError(e).with_traceback(e.__traceback__)
                else:
                    pass

        url = product.remote_location

        @self._order_download_retry(product, wait, timeout)
        def download_request(
            product: EOProduct,
            auth: AuthBase,
            progress_callback: ProgressCallback,
            wait: float,
            timeout: float,
            **kwargs: Unpack[DownloadConf],
        ) -> os.PathLike:
            is_empty = True
            chunk_iterator = self._stream_download(
                product, auth, progress_callback, **kwargs
            )
            if fs_path is not None:
                ext = Path(product.filename).suffix
                path = Path(fs_path).with_suffix(ext)
                if "ORDERABLE" in path.stem and product.properties.get("title"):
                    path = path.with_stem(sanitize(product.properties["title"]))

                with open(path, "wb") as fhandle:
                    for chunk in chunk_iterator:
                        is_empty = False
                        progress_callback(len(chunk))
                        fhandle.write(chunk)
                self.stream.close()  # Closing response stream

                if is_empty:
                    raise DownloadError(f"product {product.properties['id']} is empty")

                return path
            else:
                raise DownloadError(
                    f"download of product {product.properties['id']} failed"
                )

        path = download_request(
            product, auth, progress_callback, wait, timeout, **kwargs
        )

        with open(record_filename, "w") as fh:
            fh.write(url)
        logger.debug("Download recorded in %s", record_filename)

        if os.path.isfile(path) and not (
            zipfile.is_zipfile(path) or tarfile.is_tarfile(path)
        ):
            new_fs_path = os.path.join(
                os.path.dirname(path),
                sanitize(product.properties["title"]),
            )
            if os.path.isfile(new_fs_path):
                rename_with_version(new_fs_path)
            if not os.path.isdir(new_fs_path):
                os.makedirs(new_fs_path)
            shutil.move(path, new_fs_path)
            product.location = path_to_uri(new_fs_path)
            return new_fs_path

        product_path = self._finalize(
            str(path),
            progress_callback=progress_callback,
            **kwargs,
        )
        product.location = path_to_uri(product_path)
        return product_path

    def _check_stream_size(self, product: EOProduct) -> int:
        stream_size = int(self.stream.headers.get("content-length", 0))
        if (
            stream_size == 0
            and "storageStatus" in product.properties
            and product.properties["storageStatus"] != ONLINE_STATUS
        ):
            raise NotAvailableError(
                "%s(initially %s) ordered, got: %s"
                % (
                    product.properties["title"],
                    product.properties["storageStatus"],
                    self.stream.reason,
                )
            )
        return stream_size

    def _check_product_filename(self, product: EOProduct) -> str:
        filename = None
        asset_content_disposition = self.stream.headers.get("content-disposition", None)
        if asset_content_disposition:
            filename = cast(
                Optional[str],
                parse_header(asset_content_disposition).get_param("filename", None),
            )
        if not filename:
            # default filename extracted from path
            filename = str(os.path.basename(self.stream.url))
            filename_extension = os.path.splitext(filename)[1]
            if not filename_extension:
                if content_type := getattr(product, "headers", {}).get("Content-Type"):
                    ext = guess_extension(content_type)
                    if ext:
                        filename += ext
        return filename

    def _stream_download_dict(
        self,
        product: EOProduct,
        auth: Optional[Union[AuthBase, S3SessionKwargs]] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Unpack[DownloadConf],
    ) -> StreamResponse:
        r"""
        Returns dictionary of :class:`~fastapi.responses.StreamingResponse` keyword-arguments.
        It contains a generator to streamed download chunks and the response headers.

        :param product: The EO product to download
        :param auth: (optional) authenticated object
        :param progress_callback: (optional) A progress callback
        :param wait: (optional) If download fails, wait time in minutes between two download tries
        :param timeout: (optional) If download fails, maximum time in minutes before stop retrying
                        to download
        :param kwargs: `output_dir` (str), `extract` (bool), `delete_archive` (bool)
                        and `dl_url_params` (dict) can be provided as additional kwargs
                        and will override any other values defined in a configuration
                        file or with environment variables.
        :returns: Dictionary of :class:`~fastapi.responses.StreamingResponse` keyword-arguments
        """
        if auth is not None and not isinstance(auth, AuthBase):
            raise MisconfiguredError(f"Incompatible auth plugin: {type(auth)}")

        # download assets if exist instead of remote_location
        if len(product.assets) > 0 and (
            not getattr(self.config, "ignore_assets", False)
            or kwargs.get("asset") is not None
        ):
            try:
                assets_values = product.assets.get_values(kwargs.get("asset", None))
                chunks_tuples = self._stream_download_assets(
                    product,
                    auth,
                    progress_callback,
                    assets_values=assets_values,
                    **kwargs,
                )

                if len(assets_values) == 1:
                    # start reading chunks to set asset.headers
                    first_chunks_tuple = next(chunks_tuples)

                    # update headers
                    assets_values[0].headers[
                        "content-disposition"
                    ] = f"attachment; filename={assets_values[0].filename}"
                    if assets_values[0].get("type", None):
                        assets_values[0].headers["content-type"] = assets_values[0][
                            "type"
                        ]

                    return StreamResponse(
                        content=chain(iter([first_chunks_tuple]), chunks_tuples),
                        headers=assets_values[0].headers,
                    )

                else:
                    # get first chunk to check if it does not contain an error (if it does, that error will be raised)
                    first_chunks_tuple = next(chunks_tuples)
                    outputs_filename = (
                        sanitize(product.properties["title"])
                        if "title" in product.properties
                        else sanitize(product.properties.get("id", "download"))
                    )
                    return StreamResponse(
                        content=stream_zip(
                            chain(iter([first_chunks_tuple]), chunks_tuples)
                        ),
                        media_type="application/zip",
                        headers={
                            "content-disposition": f"attachment; filename={outputs_filename}.zip",
                        },
                    )
            except NotAvailableError as e:
                if kwargs.get("asset", None) is not None:
                    raise NotAvailableError(e).with_traceback(e.__traceback__)
                else:
                    pass

        chunk_iterator = self._stream_download(
            product, auth, progress_callback, **kwargs
        )

        # start reading chunks to set product.headers
        try:
            first_chunk = next(chunk_iterator)
        except StopIteration:
            # product is empty file
            logger.error("product %s is empty", product.properties["id"])
            raise NotAvailableError(f"product {product.properties['id']} is empty")

        return StreamResponse(
            content=chain(iter([first_chunk]), chunk_iterator),
            headers=product.headers,
        )

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

    def _process_exception(
        self, e: Optional[RequestException], product: EOProduct, ordered_message: str
    ) -> None:
        self._check_auth_exception(e)
        response_text = (
            e.response.text.strip() if e is not None and e.response is not None else ""
        )
        # product not available
        if product.properties.get("storageStatus", ONLINE_STATUS) != ONLINE_STATUS:
            msg = (
                ordered_message
                if ordered_message and not response_text
                else response_text
            )

            raise NotAvailableError(
                "%s(initially %s) requested, returned: %s"
                % (
                    product.properties["title"],
                    product.properties["storageStatus"],
                    msg,
                )
            )
        else:
            import traceback as tb

            if e:
                logger.error(
                    "Error while getting resource :\n%s\n%s",
                    tb.format_exc(),
                    response_text,
                )
            else:
                logger.error("Error while getting resource :\n%s", tb.format_exc())

    def _order_request(
        self,
        product: EOProduct,
        auth: Optional[AuthBase],
    ) -> None:
        if (
            "orderLink" in product.properties
            and product.properties.get("storageStatus") == OFFLINE_STATUS
            and not product.properties.get("orderStatus")
        ):
            self._order(product=product, auth=auth)

        if (
            product.properties.get("orderStatusLink", None)
            and product.properties.get("storageStatus") != ONLINE_STATUS
        ):
            self._order_status(product=product, auth=auth)

    def order(
        self,
        product: EOProduct,
        auth: Optional[Union[AuthBase, S3SessionKwargs]] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
    ) -> None:
        """
        Order product and poll to check its status

        :param product: The EO product to download
        :param auth: (optional) authenticated object
        :param wait: (optional) Wait time in minutes between two order status check
        :param timeout: (optional) Maximum time in minutes before stop checking
                        order status
        """
        self._order_download_retry(product, wait, timeout)(self._order_request)(
            product, auth
        )

    def _stream_download(
        self,
        product: EOProduct,
        auth: Optional[AuthBase] = None,
        progress_callback: Optional[ProgressCallback] = None,
        **kwargs: Unpack[DownloadConf],
    ) -> Iterator[Any]:
        """
        Fetches a zip file containing the assets of a given product as a stream
        and returns a generator yielding the chunks of the file

        :param product: product for which the assets should be downloaded
        :param auth: The configuration of a plugin of type Authentication
        :param progress_callback: A method or a callable object
                                  which takes a current size and a maximum
                                  size as inputs and handle progress bar
                                  creation and update to give the user a
                                  feedback on the download progress
        :param kwargs: additional arguments
        """
        if progress_callback is None:
            logger.info("Progress bar unavailable, please call product.download()")
            progress_callback = ProgressCallback(disable=True)

        ssl_verify = getattr(self.config, "ssl_verify", True)

        ordered_message = ""
        # retry handled at download level
        self._order_request(product, auth)

        params = kwargs.pop("dl_url_params", None) or getattr(
            self.config, "dl_url_params", {}
        )

        req_method = (
            product.properties.get("downloadMethod", "").lower()
            or getattr(self.config, "method", "GET").lower()
        )
        url = product.remote_location
        if req_method == "post":
            # separate url & parameters
            parts = urlparse(url)
            query_dict = parse_qs(parts.query)
            if not query_dict and parts.query:
                query_dict = geojson.loads(parts.query)
            req_url = parts._replace(query="").geturl()
            req_kwargs: dict[str, Any] = {"json": query_dict} if query_dict else {}
        else:
            req_url = url
            req_kwargs = {}

        if req_url.startswith(NOT_AVAILABLE):
            raise NotAvailableError("Download link is not available")

        if getattr(self.config, "no_auth_download", False):
            auth = None

        s = requests.Session()
        try:
            self.stream = s.request(
                req_method,
                req_url,
                stream=True,
                auth=auth,
                params=params,
                headers=USER_AGENT,
                timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
                verify=ssl_verify,
                **req_kwargs,
            )
        except requests.exceptions.MissingSchema:
            # location is not a valid url -> product is not available yet
            raise NotAvailableError("Product is not available yet")
        try:
            self.stream.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(exc, timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT) from exc
        except RequestException as e:
            self._process_exception(e, product, ordered_message)
            raise DownloadError(
                f"download of {product.properties['id']} is empty"
            ) from e
        else:
            # check if product was ordered

            if getattr(
                self.stream, "status_code", None
            ) is not None and self.stream.status_code == getattr(
                self.config, "order_status", {}
            ).get(
                "ordered", {}
            ).get(
                "http_code"
            ):
                product.properties["storageStatus"] = "ORDERED"
                self._process_exception(None, product, ordered_message)
            stream_size = self._check_stream_size(product) or None

            product.headers = self.stream.headers
            filename = self._check_product_filename(product)
            product.headers["content-disposition"] = f"attachment; filename={filename}"
            content_type = product.headers.get("Content-Type")
            guessed_content_type = (
                guess_file_type(filename) if filename and not content_type else None
            )
            if guessed_content_type is not None:
                product.headers["Content-Type"] = guessed_content_type

            progress_callback.reset(total=stream_size)

            product.filename = filename
            return self.stream.iter_content(chunk_size=64 * 1024)

    def _stream_download_assets(
        self,
        product: EOProduct,
        auth: Optional[AuthBase] = None,
        progress_callback: Optional[ProgressCallback] = None,
        assets_values: list[Asset] = [],
        **kwargs: Unpack[DownloadConf],
    ) -> Iterator[Any]:
        if progress_callback is None:
            logger.info("Progress bar unavailable, please call product.download()")
            progress_callback = ProgressCallback(disable=True)

        assets_urls = [
            a["href"] for a in getattr(product, "assets", {}).values() if "href" in a
        ]

        if not assets_urls:
            raise NotAvailableError("No assets available for %s" % product)

        # get extra parameters to pass to the query
        params = kwargs.pop("dl_url_params", None) or getattr(
            self.config, "dl_url_params", {}
        )

        total_size = self._get_asset_sizes(assets_values, auth, params) or None

        progress_callback.reset(total=total_size)

        def get_chunks(stream: Response) -> Any:
            for chunk in stream.iter_content(chunk_size=64 * 1024):
                if chunk:
                    progress_callback(len(chunk))
                    yield chunk

        # zipped files properties
        modified_at = datetime.now()
        perms = 0o600

        # loop for assets paths and get common_subdir
        asset_rel_paths_list = []
        for asset in assets_values:
            asset_rel_path_parts = urlparse(asset["href"]).path.strip("/").split("/")
            asset_rel_path_parts_sanitized = [
                sanitize(part) for part in asset_rel_path_parts
            ]
            asset.rel_path = os.path.join(*asset_rel_path_parts_sanitized)
            asset_rel_paths_list.append(asset.rel_path)
        if asset_rel_paths_list:
            assets_common_subdir = os.path.commonpath(asset_rel_paths_list)

        # product conf overrides provider conf for "flatten_top_dirs"
        product_conf = getattr(self.config, "products", {}).get(
            product.product_type, {}
        )
        flatten_top_dirs = product_conf.get(
            "flatten_top_dirs", getattr(self.config, "flatten_top_dirs", True)
        )
        ssl_verify = getattr(self.config, "ssl_verify", True)
        matching_url = (
            getattr(product.downloader_auth.config, "matching_url", "")
            if product.downloader_auth
            else ""
        )
        matching_conf = (
            getattr(product.downloader_auth.config, "matching_conf", None)
            if product.downloader_auth
            else None
        )

        # loop for assets download
        for asset in assets_values:
            if not asset["href"] or asset["href"].startswith("file:"):
                logger.info(
                    f"Local asset detected. Download skipped for {asset['href']}"
                )
                continue
            if matching_conf or (
                matching_url and re.match(matching_url, asset["href"])
            ):
                auth_object = auth
            else:
                auth_object = None
            with requests.get(
                asset["href"],
                stream=True,
                auth=auth_object,
                params=params,
                headers=USER_AGENT,
                timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
                verify=ssl_verify,
            ) as stream:
                try:
                    stream.raise_for_status()
                except requests.exceptions.Timeout as exc:
                    raise TimeOutError(
                        exc, timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT
                    ) from exc
                except RequestException as e:
                    self._handle_asset_exception(e, asset)
                else:
                    asset_rel_path = (
                        asset.rel_path.replace(assets_common_subdir, "").strip(os.sep)
                        if flatten_top_dirs
                        else asset.rel_path
                    )
                    asset_rel_dir = os.path.dirname(asset_rel_path)

                    if not getattr(asset, "filename", None):
                        # try getting filename in GET header if was not found in HEAD result
                        asset_content_disposition = stream.headers.get(
                            "content-disposition", None
                        )
                        if asset_content_disposition:
                            asset.filename = cast(
                                Optional[str],
                                parse_header(asset_content_disposition).get_param(
                                    "filename", None
                                ),
                            )

                    if not getattr(asset, "filename", None):
                        # default filename extracted from path
                        asset.filename = os.path.basename(asset.rel_path)

                    asset.rel_path = os.path.join(
                        asset_rel_dir, cast(str, asset.filename)
                    )

                    if len(assets_values) == 1:
                        # apply headers to asset
                        product.assets[assets_values[0].key].headers = stream.headers
                        yield from get_chunks(stream)
                    else:
                        # several assets to zip
                        yield (
                            asset.rel_path,
                            modified_at,
                            perms,
                            ZIP_AUTO(asset.size),
                            get_chunks(stream),
                        )

    def _download_assets(
        self,
        product: EOProduct,
        fs_dir_path: str,
        record_filename: str,
        auth: Optional[AuthBase] = None,
        progress_callback: Optional[ProgressCallback] = None,
        **kwargs: Unpack[DownloadConf],
    ) -> str:
        """Download product assets if they exist"""
        if progress_callback is None:
            logger.info("Progress bar unavailable, please call product.download()")
            progress_callback = ProgressCallback(disable=True)

        assets_urls = [
            a["href"] for a in getattr(product, "assets", {}).values() if "href" in a
        ]
        if not assets_urls:
            raise NotAvailableError("No assets available for %s" % product)

        assets_values = product.assets.get_values(kwargs.get("asset", None))

        chunks_tuples = self._stream_download_assets(
            product, auth, progress_callback, assets_values=assets_values, **kwargs
        )

        # remove existing incomplete file
        if os.path.isfile(fs_dir_path):
            os.remove(fs_dir_path)
        # create product dest dir
        if not os.path.isdir(fs_dir_path):
            os.makedirs(fs_dir_path)

        # product conf overrides provider conf for "flatten_top_dirs"
        product_conf = getattr(self.config, "products", {}).get(
            product.product_type, {}
        )
        flatten_top_dirs = product_conf.get(
            "flatten_top_dirs", getattr(self.config, "flatten_top_dirs", True)
        )

        # count local assets
        local_assets_count = 0
        for asset in assets_values:
            if asset["href"].startswith("file:"):
                local_assets_count += 1
                continue

        if len(assets_values) == 1 and local_assets_count == 0:
            # start reading chunks to set asset.rel_path
            first_chunks_tuple = next(chunks_tuples)
            chunks = chain(iter([first_chunks_tuple]), chunks_tuples)
            chunks_tuples = iter(
                [(assets_values[0].rel_path, None, None, None, chunks)]
            )

        for chunk_tuple in chunks_tuples:
            asset_path = chunk_tuple[0]
            asset_chunks = chunk_tuple[4]
            asset_abs_path = os.path.join(fs_dir_path, asset_path)
            asset_abs_path_temp = asset_abs_path + "~"
            # create asset subdir if not exist
            asset_abs_path_dir = os.path.dirname(asset_abs_path)
            if not os.path.isdir(asset_abs_path_dir):
                os.makedirs(asset_abs_path_dir)
            # remove temporary file
            if os.path.isfile(asset_abs_path_temp):
                os.remove(asset_abs_path_temp)
            if not os.path.isfile(asset_abs_path):
                logger.debug("Downloading to temporary file '%s'", asset_abs_path_temp)
                with open(asset_abs_path_temp, "wb") as fhandle:
                    for chunk in asset_chunks:
                        if chunk:
                            fhandle.write(chunk)
                            progress_callback(len(chunk))
                logger.debug(
                    "Download completed. Renaming temporary file '%s' to '%s'",
                    os.path.basename(asset_abs_path_temp),
                    os.path.basename(asset_abs_path),
                )
                os.rename(asset_abs_path_temp, asset_abs_path)
        # only one local asset
        if local_assets_count == len(assets_urls) and local_assets_count == 1:
            # remove empty {fs_dir_path}
            shutil.rmtree(fs_dir_path)
            # and return assets_urls[0] path
            fs_dir_path = uri_to_path(assets_urls[0])
            # do not flatten dir
            flatten_top_dirs = False
        # several local assets
        elif local_assets_count == len(assets_urls) and local_assets_count > 0:
            common_path = os.path.commonpath([uri_to_path(uri) for uri in assets_urls])
            # remove empty {fs_dir_path}
            shutil.rmtree(fs_dir_path)
            # and return assets_urls common path
            fs_dir_path = common_path
            # do not flatten dir
            flatten_top_dirs = False
        # no assets downloaded but some should have been
        elif len(os.listdir(fs_dir_path)) == 0:
            raise NotAvailableError("No assets could be downloaded")

        # flatten directory structure
        if flatten_top_dirs:
            flatten_top_directories(fs_dir_path)

        if kwargs.get("asset", None) is None:
            # save hash/record file
            with open(record_filename, "w") as fh:
                fh.write(product.remote_location)
            logger.debug("Download recorded in %s", record_filename)

        return fs_dir_path

    def _handle_asset_exception(self, e: RequestException, asset: Asset) -> None:
        # check if error is identified as auth_error in provider conf
        auth_errors = getattr(self.config, "auth_error_code", [None])
        if not isinstance(auth_errors, list):
            auth_errors = [auth_errors]
        if e.response is not None and e.response.status_code in auth_errors:
            raise AuthenticationError(
                f"Please check your credentials for {self.provider}.",
                f"HTTP Error {e.response.status_code} returned.",
                e.response.text.strip(),
            )
        else:
            logger.error(
                "Unexpected error at download of asset %s: %s", asset["href"], e
            )
            raise DownloadError(e)

    def _get_asset_sizes(
        self,
        assets_values: list[Asset],
        auth: Optional[AuthBase],
        params: Optional[dict[str, str]],
        zipped: bool = False,
    ) -> int:
        total_size = 0

        timeout = getattr(self.config, "timeout", HTTP_REQ_TIMEOUT)
        ssl_verify = getattr(self.config, "ssl_verify", True)
        # loop for assets size & filename
        for asset in assets_values:
            if asset["href"] and not asset["href"].startswith("file:"):
                # HEAD request for size & filename
                try:
                    asset_headers = requests.head(
                        asset["href"],
                        auth=auth,
                        params=params,
                        headers=USER_AGENT,
                        timeout=timeout,
                        verify=ssl_verify,
                    ).headers
                except RequestException as e:
                    logger.debug(f"HEAD request failed: {str(e)}")
                    asset_headers = CaseInsensitiveDict()

                if not getattr(asset, "size", 0):
                    # size from HEAD header / Content-length
                    asset.size = int(asset_headers.get("Content-length", 0))

                header_content_disposition = Message()
                if not getattr(asset, "size", 0) or not getattr(asset, "filename", 0):
                    # header content-disposition
                    header_content_disposition = parse_header(
                        asset_headers.get("content-disposition", "")
                    )
                if not getattr(asset, "size", 0):
                    # size from HEAD header / content-disposition / size
                    size_str = str(header_content_disposition.get_param("size", 0))
                    asset.size = int(size_str) if size_str.isdigit() else 0
                if not getattr(asset, "filename", 0):
                    # filename from HEAD header / content-disposition / size
                    asset_filename = header_content_disposition.get_param(
                        "filename", None
                    )
                    asset.filename = str(asset_filename) if asset_filename else None

                if not getattr(asset, "size", 0):
                    # GET request for size
                    with requests.get(
                        asset["href"],
                        stream=True,
                        auth=auth,
                        params=params,
                        headers=USER_AGENT,
                        timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
                        verify=ssl_verify,
                    ) as stream:
                        # size from GET header / Content-length
                        asset.size = int(stream.headers.get("Content-length", 0))
                        if not getattr(asset, "size", 0):
                            # size from GET header / content-disposition / size
                            size_str = str(
                                parse_header(
                                    stream.headers.get("content-disposition", "")
                                ).get_param("size", 0)
                            )
                            asset.size = int(size_str) if size_str.isdigit() else 0

                total_size += asset.size
        return total_size

    def download_all(
        self,
        products: SearchResult,
        auth: Optional[Union[AuthBase, S3SessionKwargs]] = None,
        downloaded_callback: Optional[DownloadedCallback] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Unpack[DownloadConf],
    ):
        """
        Download all using parent (base plugin) method
        """
        return super(HTTPDownload, self).download_all(
            products,
            auth=auth,
            downloaded_callback=downloaded_callback,
            progress_callback=progress_callback,
            wait=wait,
            timeout=timeout,
            **kwargs,
        )
