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
import shutil
import tarfile
import zipfile
from datetime import datetime
from email.message import Message
from itertools import chain
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
    TypedDict,
    Union,
    cast,
)
from urllib.parse import parse_qs, urlparse

import geojson
import requests
from lxml import etree
from requests import RequestException
from requests.auth import AuthBase
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
)

if TYPE_CHECKING:
    from requests import Response

    from eodag.api.product import Asset, EOProduct  # type: ignore
    from eodag.api.search_result import SearchResult
    from eodag.config import PluginConfig
    from eodag.types.download_args import DownloadConf
    from eodag.utils import DownloadedCallback, Unpack

logger = logging.getLogger("eodag.download.http")


class HTTPDownload(Download):
    """HTTPDownload plugin. Handles product download over HTTP protocol

    :param provider: provider name
    :type provider: str
    :param config: Download plugin configuration:

        * ``config.base_uri`` (str) - default endpoint url
        * ``config.extract`` (bool) - (optional) extract downloaded archive or not
        * ``config.auth_error_code`` (int) - (optional) authentication error code
        * ``config.dl_url_params`` (dict) - (optional) attitional parameters to send in the request
        * ``config.archive_depth`` (int) - (optional) level in extracted path tree where to find data
        * ``config.flatten_top_dirs`` (bool) - (optional) flatten directory structure
        * ``config.ignore_assets`` (bool) - (optional) ignore assets and download using downloadLink
        * ``config.order_enabled`` (bool) - (optional) wether order is enabled or not if product is `OFFLINE`
        * ``config.order_method`` (str) - (optional) HTTP request method, GET (default) or POST
        * ``config.order_headers`` (dict) - (optional) order request headers
        * ``config.order_on_response`` (dict) - (optional) edit or add new product properties
        * ``config.order_status`` (:class:`~eodag.config.PluginConfig.OrderStatus`) - Order status handling


    :type config: :class:`~eodag.config.PluginConfig`

    """

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(HTTPDownload, self).__init__(provider, config)
        if not hasattr(self.config, "base_uri"):
            raise MisconfiguredError(
                "{} plugin require a base_uri configuration key".format(
                    type(self).__name__
                )
            )

    def orderDownload(
        self,
        product: EOProduct,
        auth: Optional[AuthBase] = None,
        **kwargs: Unpack[DownloadConf],
    ) -> Optional[Dict[str, Any]]:
        """Send product order request.

        It will be executed once before the download retry loop, if the product is OFFLINE
        and has `orderLink` in its properties.
        Product ordering can be configured using the following download plugin parameters:

            - **order_enabled**: Wether order is enabled or not (may not use this method
              if no `orderLink` exists)

            - **order_method**: (optional) HTTP request method, GET (default) or POST

            - **order_on_response**: (optional) things to do with obtained order response:

              - *metadata_mapping*: edit or add new product propoerties properties

        Product properties used for order:

            - **orderLink**: order request URL

        :param product: The EO product to order
        :type product: :class:`~eodag.api.product._product.EOProduct`
        :param auth: (optional) authenticated object
        :type auth: Optional[AuthBase]
        :param kwargs: download additional kwargs
        :type kwargs: Union[str, bool, dict]
        :returns: the returned json status response
        :rtype: dict
        """
        product.properties["storageStatus"] = STAGING_STATUS

        order_method = getattr(self.config, "order_method", "GET").upper()
        ssl_verify = getattr(self.config, "ssl_verify", True)
        timeout = getattr(self.config, "timeout", HTTP_REQ_TIMEOUT)
        OrderKwargs = TypedDict(
            "OrderKwargs", {"json": Dict[str, Union[Any, List[str]]]}, total=False
        )
        order_kwargs: OrderKwargs = {}
        if order_method == "POST":
            # separate url & parameters
            parts = urlparse(str(product.properties["orderLink"]))
            query_dict = parse_qs(parts.query)
            if not query_dict and parts.query:
                query_dict = geojson.loads(parts.query)
            order_url = parts._replace(query=None).geturl()
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
                    if e.response and hasattr(e.response, "content"):
                        error_message = f"{e.response.content.decode('utf-8')} - {e}"
                    else:
                        error_message = str(e)
                    logger.warning(
                        "%s could not be ordered, request returned %s",
                        product.properties["title"],
                        error_message,
                    )
                    self._check_auth_exception(e)
                return self.order_response_process(response, product)
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(exc, timeout=timeout) from exc

    def order_response_process(
        self, response: Response, product: EOProduct
    ) -> Optional[Dict[str, Any]]:
        """Process order response

        :param response: The order response
        :type response: :class:`~requests.Response`
        :param product: The orderd EO product
        :type product: :class:`~eodag.api.product._product.EOProduct`
        :returns: the returned json status response
        :rtype: dict
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
        if "downloadLink" in product.properties:
            product.remote_location = product.location = product.properties[
                "downloadLink"
            ]
            logger.debug(f"Product location updated to {product.location}")

        return json_response

    def orderDownloadStatus(
        self,
        product: EOProduct,
        auth: Optional[AuthBase] = None,
    ) -> None:
        """Send product order status request.

        It will be executed before each download retry.
        Product order status request can be configured using the following download plugin parameters:

            - **order_status**: :class:`~eodag.config.PluginConfig.OrderStatus`

        Product properties used for order status:

            - **orderStatusLink**: order status request URL

        :param product: The ordered EO product
        :type product: :class:`~eodag.api.product._product.EOProduct`
        :param auth: (optional) authenticated object
        :type auth: Optional[AuthBase]
        :param kwargs: download additional kwargs
        :type kwargs: Union[str, bool, dict]
        """

        status_config = getattr(self.config, "order_status", {})
        success_code: Optional[int] = status_config.get("success", {}).get("http_code")

        timeout = getattr(self.config, "timeout", HTTP_REQ_TIMEOUT)

        def _request(
            url: str,
            method: str = "GET",
            headers: Optional[Dict[str, Any]] = None,
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

        status_request: Dict[str, Any] = status_config.get("request", {})
        status_request_method = str(status_request.get("method", "GET")).upper()

        if status_request_method == "POST":
            # separate url & parameters
            parts = urlparse(str(product.properties["orderStatusLink"]))
            status_url = parts._replace(query=None).geturl()
            query_dict = parse_qs(parts.query)
            if not query_dict and parts.query:
                query_dict = geojson.loads(parts.query)
            json_data = query_dict if query_dict else None
        else:
            status_url = product.properties["orderStatusLink"]
            json_data = None

        # check header for success before full status request
        skip_parsing_status_response = False
        status_dict: Dict[str, Any] = {}
        config_on_success: Dict[str, Any] = status_config.get("on_success", {})
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
                raise DownloadError(
                    "%s order status could not be checked, request returned %s"
                    % (
                        product.properties["title"],
                        e,
                    )
                ) from e

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

            status_message = status_dict.get("message")
            product.properties["orderStatus"] = status_dict.get("status")

            # handle status error
            errors: Dict[str, Any] = status_config.get("error", {})
            if errors and errors.items() <= status_dict.items():
                raise DownloadError(
                    f"Provider {product.provider} returned: {status_dict.get('error_message', status_message)}"
                )

        success_status: Dict[str, Any] = status_config.get("success", {}).get("status")
        # if not success
        if (success_status and success_status != status_dict.get("status")) or (
            success_code and success_code != response.status_code
        ):
            error = NotAvailableError(status_message)
            raise error

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
                return None

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
        auth: Optional[Union[AuthBase, Dict[str, str]]] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: int = DEFAULT_DOWNLOAD_WAIT,
        timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
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

        outputs_extension = getattr(self.config, "products", {}).get(
            product.product_type, {}
        ).get("outputs_extension", None) or getattr(
            self.config, "outputs_extension", ".zip"
        )
        kwargs["outputs_extension"] = kwargs.get("outputs_extension", outputs_extension)

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
        if len(product.assets) > 0 and not getattr(self.config, "ignore_assets", False):
            try:
                fs_path = self._download_assets(
                    product,
                    fs_path.replace(".zip", ""),
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

        @self._download_retry(product, wait, timeout)
        def download_request(
            product: EOProduct,
            auth: AuthBase,
            progress_callback: ProgressCallback,
            wait: int,
            timeout: int,
            **kwargs: Unpack[DownloadConf],
        ) -> None:
            chunks = self._stream_download(product, auth, progress_callback, **kwargs)
            is_empty = True

            with open(fs_path, "wb") as fhandle:
                for chunk in chunks:
                    is_empty = False
                    fhandle.write(chunk)

            if is_empty:
                raise DownloadError(f"product {product.properties['id']} is empty")

        download_request(product, auth, progress_callback, wait, timeout, **kwargs)

        with open(record_filename, "w") as fh:
            fh.write(url)
        logger.debug("Download recorded in %s", record_filename)

        # Check that the downloaded file is really a zip file
        if not zipfile.is_zipfile(fs_path) and outputs_extension == ".zip":
            logger.warning(
                "Downloaded product is not a Zip File. Please check its file type before using it"
            )
            new_fs_path = os.path.join(
                os.path.dirname(fs_path),
                sanitize(product.properties["title"]),
            )
            if os.path.isfile(fs_path) and not tarfile.is_tarfile(fs_path):
                if not os.path.isdir(new_fs_path):
                    os.makedirs(new_fs_path)
                shutil.move(fs_path, new_fs_path)
                file_path = os.path.join(new_fs_path, os.path.basename(fs_path))
                new_file_path = file_path[: file_path.index(".zip")]
                shutil.move(file_path, new_file_path)
            # in the case where the outputs extension has not been set
            # to ".tar" in the product type nor provider configuration
            elif tarfile.is_tarfile(fs_path):
                if not new_fs_path.endswith(".tar"):
                    new_fs_path += ".tar"
                shutil.move(fs_path, new_fs_path)
                kwargs["outputs_extension"] = ".tar"
                product_path = self._finalize(
                    new_fs_path,
                    progress_callback=progress_callback,
                    **kwargs,
                )
                product.location = path_to_uri(product_path)
                return product_path
            else:
                # not a file (dir with zip extension)
                shutil.move(fs_path, new_fs_path)
            product.location = path_to_uri(new_fs_path)
            return new_fs_path

        if os.path.isfile(fs_path) and not (
            zipfile.is_zipfile(fs_path) or tarfile.is_tarfile(fs_path)
        ):
            new_fs_path = os.path.join(
                os.path.dirname(fs_path),
                sanitize(product.properties["title"]),
            )
            if not os.path.isdir(new_fs_path):
                os.makedirs(new_fs_path)
            shutil.move(fs_path, new_fs_path)
            product.location = path_to_uri(new_fs_path)
            return new_fs_path
        product_path = self._finalize(
            fs_path,
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
                else:
                    outputs_extension: Optional[str] = (
                        getattr(self.config, "products", {})
                        .get(product.product_type, {})
                        .get("outputs_extension")
                    )
                    if outputs_extension:
                        filename += outputs_extension

        return filename

    def _stream_download_dict(
        self,
        product: EOProduct,
        auth: Optional[Union[AuthBase, Dict[str, str]]] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: int = DEFAULT_DOWNLOAD_WAIT,
        timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Unpack[DownloadConf],
    ) -> StreamResponse:
        r"""
        Returns dictionnary of :class:`~fastapi.responses.StreamingResponse` keyword-arguments.
        It contains a generator to streamed download chunks and the response headers.

        :param product: The EO product to download
        :type product: :class:`~eodag.api.product._product.EOProduct`
        :param auth: (optional) authenticated object
        :type auth: Optional[Union[AuthBase, Dict[str, str]]]
        :param progress_callback: (optional) A progress callback
        :type progress_callback: :class:`~eodag.utils.ProgressCallback`
        :param wait: (optional) If download fails, wait time in minutes between two download tries
        :type wait: int
        :param timeout: (optional) If download fails, maximum time in minutes before stop retrying
                        to download
        :type timeout: int
        :param kwargs: `outputs_prefix` (str), `extract` (bool), `delete_archive` (bool)
                        and `dl_url_params` (dict) can be provided as additional kwargs
                        and will override any other values defined in a configuration
                        file or with environment variables.
        :type kwargs: Union[str, bool, dict]
        :returns: Dictionnary of :class:`~fastapi.responses.StreamingResponse` keyword-arguments
        :rtype: dict
        """
        if auth is not None and not isinstance(auth, AuthBase):
            raise MisconfiguredError(f"Incompatible auth plugin: {type(auth)}")

        # download assets if exist instead of remote_location
        if len(product.assets) > 0 and not getattr(self.config, "ignore_assets", False):
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
                    outputs_filename = (
                        sanitize(product.properties["title"])
                        if "title" in product.properties
                        else sanitize(product.properties.get("id", "download"))
                    )
                    return StreamResponse(
                        content=stream_zip(chunks_tuples),
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

        chunks = self._stream_download(product, auth, progress_callback, **kwargs)
        # start reading chunks to set product.headers
        try:
            first_chunk = next(chunks)
        except StopIteration:
            # product is empty file
            logger.error("product %s is empty", product.properties["id"])
            raise NotAvailableError(f"product {product.properties['id']} is empty")

        return StreamResponse(
            content=chain(iter([first_chunk]), chunks),
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
                "HTTP Error %s returned, %s\nPlease check your credentials for %s"
                % (
                    e.response.status_code,
                    response_text,
                    self.provider,
                )
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

    def _stream_download(
        self,
        product: EOProduct,
        auth: Optional[AuthBase] = None,
        progress_callback: Optional[ProgressCallback] = None,
        **kwargs: Unpack[DownloadConf],
    ) -> Iterator[Any]:
        """
        fetches a zip file containing the assets of a given product as a stream
        and returns a generator yielding the chunks of the file
        :param product: product for which the assets should be downloaded
        :type product: :class:`~eodag.api.product._product.EOProduct`
        :param auth: The configuration of a plugin of type Authentication
        :type auth: Optional[Union[AuthBase, Dict[str, str]]]
        :param progress_callback: A method or a callable object
                                  which takes a current size and a maximum
                                  size as inputs and handle progress bar
                                  creation and update to give the user a
                                  feedback on the download progress
        :type progress_callback: :class:`~eodag.utils.ProgressCallback`
        :param kwargs: additional arguments
        :type kwargs: dict
        """
        if progress_callback is None:
            logger.info("Progress bar unavailable, please call product.download()")
            progress_callback = ProgressCallback(disable=True)

        ordered_message = ""
        if (
            "orderLink" in product.properties
            and product.properties.get("storageStatus") == OFFLINE_STATUS
            and not product.properties.get("orderStatus")
        ):
            self.orderDownload(product=product, auth=auth)

        if (
            product.properties.get("orderStatusLink", None)
            and product.properties.get("storageStatus") != ONLINE_STATUS
        ):
            self.orderDownloadStatus(product=product, auth=auth)

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
            req_url = parts._replace(query=None).geturl()
            req_kwargs: Dict[str, Any] = {"json": query_dict} if query_dict else {}
        else:
            req_url = url
            req_kwargs = {}

        if req_url.startswith(NOT_AVAILABLE):
            raise NotAvailableError("Download link is not available")

        s = requests.Session()
        with s.request(
            req_method,
            req_url,
            stream=True,
            auth=auth,
            params=params,
            headers=USER_AGENT,
            timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
            **req_kwargs,
        ) as self.stream:
            try:
                self.stream.raise_for_status()
            except requests.exceptions.Timeout as exc:
                raise TimeOutError(
                    exc, timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT
                ) from exc
            except RequestException as e:
                self._process_exception(e, product, ordered_message)
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
                filename = self._check_product_filename(product) or None
                product.headers[
                    "content-disposition"
                ] = f"attachment; filename={filename}"
                content_type = product.headers.get("Content-Type")
                if filename and not content_type:
                    product.headers["Content-Type"] = guess_file_type(filename)

                progress_callback.reset(total=stream_size)
                for chunk in self.stream.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        progress_callback(len(chunk))
                        yield chunk

    def _stream_download_assets(
        self,
        product: EOProduct,
        auth: Optional[AuthBase] = None,
        progress_callback: Optional[ProgressCallback] = None,
        assets_values: List[Asset] = [],
        **kwargs: Unpack[DownloadConf],
    ) -> Iterator[Tuple[str, datetime, int, Any, Iterator[Any]]]:
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
            "flatten_top_dirs", getattr(self.config, "flatten_top_dirs", False)
        )
        ssl_verify = getattr(self.config, "ssl_verify", True)

        # loop for assets download
        for asset in assets_values:

            if not asset["href"] or asset["href"].startswith("file:"):
                logger.info(
                    f"Local asset detected. Download skipped for {asset['href']}"
                )
                continue

            with requests.get(
                asset["href"],
                stream=True,
                auth=auth,
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
                    raise_errors = True if len(assets_values) == 1 else False
                    self._handle_asset_exception(e, asset, raise_errors=raise_errors)
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
            "flatten_top_dirs", getattr(self.config, "flatten_top_dirs", False)
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
            chunks_tuples = [(assets_values[0].rel_path, None, None, None, chunks)]

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
        # several local assets
        elif local_assets_count == len(assets_urls) and local_assets_count > 0:
            common_path = os.path.commonpath([uri_to_path(uri) for uri in assets_urls])
            # remove empty {fs_dir_path}
            shutil.rmtree(fs_dir_path)
            # and return assets_urls common path
            fs_dir_path = common_path
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

    def _handle_asset_exception(
        self, e: RequestException, asset: Asset, raise_errors: bool = False
    ) -> None:
        # check if error is identified as auth_error in provider conf
        auth_errors = getattr(self.config, "auth_error_code", [None])
        if not isinstance(auth_errors, list):
            auth_errors = [auth_errors]
        if e.response is not None and e.response.status_code in auth_errors:
            raise AuthenticationError(
                "HTTP Error %s returned, %s\nPlease check your credentials for %s"
                % (
                    e.response.status_code,
                    e.response.text.strip(),
                    self.provider,
                )
            )
        elif raise_errors:
            raise DownloadError(e)
        else:
            logger.warning("Unexpected error: %s" % e)
            logger.warning("Skipping %s" % asset["href"])

    def _get_asset_sizes(
        self,
        assets_values: List[Asset],
        auth: Optional[AuthBase],
        params: Optional[Dict[str, str]],
        zipped: bool = False,
    ) -> int:
        total_size = 0

        timeout = getattr(self.config, "timeout", HTTP_REQ_TIMEOUT)
        ssl_verify = getattr(self.config, "ssl_verify", True)
        # loop for assets size & filename
        for asset in assets_values:
            if asset["href"] and not asset["href"].startswith("file:"):
                # HEAD request for size & filename
                asset_headers = requests.head(
                    asset["href"],
                    auth=auth,
                    headers=USER_AGENT,
                    timeout=timeout,
                ).headers

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
        auth: Optional[Union[AuthBase, Dict[str, str]]] = None,
        downloaded_callback: Optional[DownloadedCallback] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: int = DEFAULT_DOWNLOAD_WAIT,
        timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
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
