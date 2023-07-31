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

import logging
import os
import shutil
import zipfile
from datetime import datetime
from itertools import chain
from urllib.parse import parse_qs, urlparse

import geojson
import requests
import requests_ftp
from lxml import etree
from requests import RequestException
from stream_zip import NO_COMPRESSION_64, stream_zip

from eodag.api.product.metadata_mapping import (
    OFFLINE_STATUS,
    ONLINE_STATUS,
    mtd_cfg_as_conversion_and_querypath,
    properties_from_json,
    properties_from_xml,
)
from eodag.plugins.download.base import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    DEFAULT_STREAM_REQUESTS_TIMEOUT,
    Download,
)
from eodag.utils import (
    USER_AGENT,
    ProgressCallback,
    flatten_top_directories,
    parse_header,
    path_to_uri,
    sanitize,
    uri_to_path,
)
from eodag.utils.exceptions import (
    AuthenticationError,
    DownloadError,
    MisconfiguredError,
    NotAvailableError,
)
from eodag.utils.stac_reader import HTTP_REQ_TIMEOUT

logger = logging.getLogger("eodag.plugins.download.http")


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
        * ``config.order_status_method`` (str) - (optional) status HTTP request method, GET (default) or POST
        * ``config.order_status_percent`` (str) - (optional) progress percentage key in obtained status response
        * ``config.order_status_error`` (dict) - (optional) key/value identifying an error status

    :type config: :class:`~eodag.config.PluginConfig`

    """

    def __init__(self, provider, config):
        super(HTTPDownload, self).__init__(provider, config)
        if not hasattr(self.config, "base_uri"):
            raise MisconfiguredError(
                "{} plugin require a base_uri configuration key".format(self.__name__)
            )

    def orderDownload(
        self,
        product,
        auth=None,
        **kwargs,
    ):
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
        :param auth: (optional) The configuration of a plugin of type Authentication
        :type auth: :class:`~eodag.config.PluginConfig`
        :param kwargs: download additional kwargs
        :type kwargs: Union[str, bool, dict]
        """
        order_method = getattr(self.config, "order_method", "GET").lower()
        if order_method == "post":
            # separate url & parameters
            parts = urlparse(product.properties["orderLink"])
            query_dict = parse_qs(parts.query)
            if not query_dict and parts.query:
                query_dict = geojson.loads(parts.query)
            order_url = parts._replace(query=None).geturl()
            order_kwargs = {"json": query_dict} if query_dict else {}
        else:
            order_url = product.properties["orderLink"]
            order_kwargs = {}

        with requests.request(
            method=order_method,
            url=order_url,
            auth=auth,
            headers=dict(getattr(self.config, "order_headers", {}), **USER_AGENT),
            **order_kwargs,
        ) as response:
            try:
                response.raise_for_status()
                ordered_message = response.text
                logger.debug(ordered_message)
                logger.info("%s was ordered", product.properties["title"])
            except RequestException as e:
                logger.warning(
                    "%s could not be ordered, request returned %s",
                    product.properties["title"],
                    f"{e.response.content} - {e}",
                )

        order_metadata_mapping = getattr(self.config, "order_on_response", {}).get(
            "metadata_mapping", {}
        )
        if order_metadata_mapping:
            logger.debug("Parsing order response to update product metada-mapping")
            order_metadata_mapping_jsonpath = {}
            order_metadata_mapping_jsonpath = mtd_cfg_as_conversion_and_querypath(
                order_metadata_mapping, order_metadata_mapping_jsonpath
            )
            properties_update = properties_from_json(
                response.json(),
                order_metadata_mapping_jsonpath,
            )
            product.properties.update(properties_update)
            if "downloadLink" in properties_update:
                product.remote_location = product.location = product.properties[
                    "downloadLink"
                ]
                logger.debug(f"Product location updated to {product.location}")

    def orderDownloadStatus(
        self,
        product,
        auth=None,
        **kwargs,
    ):
        """Send product order status request.

        It will be executed before each download retry.
        Product order status request can be configured using the following download plugin parameters:

            - **order_status_method**: (optional) HTTP request method, GET (default) or POST

            - **order_status_percent**: (optional) progress percentage key in obtained response

            - **order_status_error**: (optional) key/value identifying an error status

        Product properties used for order status:

            - **orderStatusLink**: order status request URL

        :param product: The ordered EO product
        :type product: :class:`~eodag.api.product._product.EOProduct`
        :param auth: (optional) The configuration of a plugin of type Authentication
        :type auth: :class:`~eodag.config.PluginConfig`
        :param kwargs: download additional kwargs
        :type kwargs: Union[str, bool, dict]
        """
        status_method = getattr(self.config, "order_status_method", "GET").lower()
        if status_method == "post":
            # separate url & parameters
            parts = urlparse(product.properties["orderStatusLink"])
            query_dict = parse_qs(parts.query)
            if not query_dict and parts.query:
                query_dict = geojson.loads(parts.query)
            status_url = parts._replace(query=None).geturl()
            status_kwargs = {"json": query_dict} if query_dict else {}
        else:
            status_url = product.properties["orderStatusLink"]
            status_kwargs = {}

        with requests.request(
            method=status_method,
            url=status_url,
            auth=auth,
            headers=dict(
                getattr(self.config, "order_status_headers", {}), **USER_AGENT
            ),
            **status_kwargs,
        ) as response:
            try:
                response.raise_for_status()
                status_message = response.text
                status_dict = response.json()
                # display progress percentage
                order_status_percent_key = getattr(
                    self.config, "order_status_percent", None
                )
                if order_status_percent_key and order_status_percent_key in status_dict:
                    order_status_value = str(status_dict[order_status_percent_key])
                    if order_status_value.isdigit():
                        order_status_value += "%"
                    logger.info(
                        f"{product.properties['title']} order status: {order_status_value}"
                    )
                # display error if any
                order_status_error_dict = getattr(self.config, "order_status_error", {})
                if (
                    order_status_error_dict
                    and order_status_error_dict.items() <= status_dict.items()
                ):
                    # order_status_error_dict is a subset of status_dict : error
                    logger.warning(status_message)
                else:
                    logger.debug(status_message)
                # check if succeeds and need search again
                order_status_success_dict = getattr(
                    self.config, "order_status_success", {}
                )
                if (
                    "status" in status_dict
                    and status_dict["status"] == order_status_success_dict["status"]
                    and "message" in status_dict
                    and status_dict["message"] == order_status_success_dict["message"]
                ):
                    product.properties["storageStatus"] = ONLINE_STATUS
                if (
                    order_status_success_dict
                    and order_status_success_dict.items() <= status_dict.items()
                    and getattr(self.config, "order_status_on_success", {}).get(
                        "need_search"
                    )
                ):
                    logger.debug(
                        f"Search for new location: {product.properties['searchLink']}"
                    )
                    # search again
                    response = requests.get(product.properties["searchLink"])
                    response.raise_for_status()
                    if (
                        self.config.order_status_on_success.get("result_type", "json")
                        == "xml"
                    ):
                        root_node = etree.fromstring(response.content)
                        namespaces = {k or "ns": v for k, v in root_node.nsmap.items()}
                        results = [
                            etree.tostring(entry)
                            for entry in root_node.xpath(
                                self.config.order_status_on_success["results_entry"],
                                namespaces=namespaces,
                            )
                        ]
                        if isinstance(results, list) and len(results) != 1:
                            raise DownloadError(
                                "Could not get a single result after order success for "
                                f"{product.properties['searchLink']} request. "
                                f"Please search and download {product} again"
                            )
                            return
                        try:
                            assert isinstance(
                                results, list
                            ), "results must be in a list"
                            # single result
                            result = results[0]
                            # parse result
                            new_search_metadata_mapping = (
                                self.config.order_status_on_success["metadata_mapping"]
                            )
                            order_metadata_mapping_jsonpath = {}
                            order_metadata_mapping_jsonpath = (
                                mtd_cfg_as_conversion_and_querypath(
                                    new_search_metadata_mapping,
                                    order_metadata_mapping_jsonpath,
                                )
                            )
                            properties_update = properties_from_xml(
                                result,
                                order_metadata_mapping_jsonpath,
                            )
                        except Exception as e:
                            logger.debug(e)
                            raise DownloadError(
                                f"Could not parse result after order success for {product.properties['searchLink']} "
                                f"request. Please search and download {product} again"
                            )
                        # update product
                        product.properties.update(properties_update)
                        product.location = product.remote_location = product.properties[
                            "downloadLink"
                        ]
                    else:
                        logger.warning(
                            "JSON response parsing is not implemented yet for new searches "
                            f"after order success. Please search and download {product} again"
                        )

            except RequestException as e:
                logger.warning(
                    "%s order status could not be checked, request returned %s",
                    product.properties["title"],
                    e,
                )

    def download(
        self,
        product,
        auth=None,
        progress_callback=None,
        wait=DEFAULT_DOWNLOAD_WAIT,
        timeout=DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs,
    ):
        """Download a product using HTTP protocol.

        The downloaded product is assumed to be a Zip file. If it is not,
        the user is warned, it is renamed to remove the zip extension and
        no further treatment is done (no extraction)
        """
        if progress_callback is None:
            logger.info(
                "Progress bar unavailable, please call product.download() instead of plugin.download()"
            )
            progress_callback = ProgressCallback(disable=True)

        fs_path, record_filename = self._prepare_download(
            product, progress_callback=progress_callback, **kwargs
        )
        if not fs_path or not record_filename:
            if fs_path:
                product.location = path_to_uri(fs_path)
            return fs_path

        # download assets if exist instead of remote_location
        if hasattr(product, "assets") and not getattr(
            self.config, "ignore_assets", False
        ):
            try:
                fs_path = self._download_assets(
                    product,
                    fs_path.replace(".zip", ""),
                    record_filename,
                    auth,
                    progress_callback,
                    **kwargs,
                )
                # product.location = path_to_uri(fs_path)
                return fs_path
            except NotAvailableError:
                pass

        url = product.remote_location

        @self._download_retry(product, wait, timeout)
        def download_request(product, auth, progress_callback, wait, timeout, **kwargs):
            chunks = self._stream_download(
                product, auth, progress_callback, wait, timeout, **kwargs
            )

            with open(fs_path, "wb") as fhandle:
                for chunk in chunks:
                    fhandle.write(chunk)

        download_request(product, auth, progress_callback, wait, timeout, **kwargs)

        with open(record_filename, "w") as fh:
            fh.write(url)
        logger.debug("Download recorded in %s", record_filename)

        # Check that the downloaded file is really a zip file
        outputs_extension = kwargs.get("outputs_extension", None) or getattr(
            self.config, "outputs_extension", ".zip"
        )
        if not zipfile.is_zipfile(fs_path) and outputs_extension == ".zip":
            logger.warning(
                "Downloaded product is not a Zip File. Please check its file type before using it"
            )
            new_fs_path = fs_path[: fs_path.index(".zip")]
            shutil.move(fs_path, new_fs_path)
            product.location = path_to_uri(new_fs_path)
            return new_fs_path
        product_path = self._finalize(
            fs_path, progress_callback=progress_callback, **kwargs
        )
        product.location = path_to_uri(product_path)
        return product_path

    def _check_stream_size(self, product):
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

    def _stream_download_dict(
        self,
        product,
        auth=None,
        progress_callback=None,
        wait=DEFAULT_DOWNLOAD_WAIT,
        timeout=DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs,
    ):
        r"""
        Returns dictionnary of :class:`~fastapi.responses.StreamingResponse` keyword-arguments.
        It contains a generator to streamed download chunks and the response headers.

        :param product: The EO product to download
        :type product: :class:`~eodag.api.product._product.EOProduct`
        :param auth: (optional) The configuration of a plugin of type Authentication
        :type auth: :class:`~eodag.config.PluginConfig`
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
        # download assets if exist instead of remote_location
        if hasattr(product, "assets") and not getattr(
            self.config, "ignore_assets", False
        ):
            try:
                chunks_tuples = self._stream_download_assets(
                    product, auth, progress_callback, **kwargs
                )

                outputs_filename = (
                    sanitize(product.properties["title"])
                    if "title" in product.properties
                    else sanitize(product.properties.get("id", "download"))
                )
                return dict(
                    content=stream_zip(chunks_tuples),
                    media_type="application/zip",
                    headers={
                        "content-disposition": f"attachment; filename={outputs_filename}.zip",
                    },
                )
            except NotAvailableError:
                pass

        chunks = self._stream_download(
            product, auth, progress_callback, wait, timeout, **kwargs
        )
        # start reading chunks to set product.headers
        first_chunk = next(chunks)

        return dict(
            content=chain(iter([first_chunk]), chunks),
            headers=product.headers,
        )

    def _process_exception(self, e, product, ordered_message):
        # check if error is identified as auth_error in provider conf
        auth_errors = getattr(self.config, "auth_error_code", [None])
        if not isinstance(auth_errors, list):
            auth_errors = [auth_errors]
        if e.response.status_code in auth_errors:
            raise AuthenticationError(
                "HTTP Error %s returned, %s\nPlease check your credentials for %s"
                % (
                    e.response.status_code,
                    e.response.text.strip(),
                    self.provider,
                )
            )
        # product not available
        elif product.properties.get("storageStatus", ONLINE_STATUS) != ONLINE_STATUS:
            msg = (
                ordered_message
                if ordered_message and not e.response.text.strip()
                else e.response.text.strip()
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

            logger.error(
                "Error while getting resource :\n%s\n%s",
                tb.format_exc(),
                e.response.text.strip(),
            )

    def _stream_download(
        self,
        product,
        auth=None,
        progress_callback=None,
        wait=DEFAULT_DOWNLOAD_WAIT,
        timeout=DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs,
    ):
        """
        fetches a zip file containing the assets of a given product as a stream
        and returns a generator yielding the chunks of the file
        :param product: product for which the assets should be downloaded
        :type product: :class:`~eodag.api.product._product.EOProduct`
        :param auth: The configuration of a plugin of type Authentication
        :type auth: :class:`~eodag.config.PluginConfig`
        :param progress_callback: A method or a callable object
                                  which takes a current size and a maximum
                                  size as inputs and handle progress bar
                                  creation and update to give the user a
                                  feedback on the download progress
        :type progress_callback: :class:`~eodag.utils.ProgressCallback`
        :param ordered_message: message to be used in case of error because
                                the product is unavailable
        :type ordered_message: str
        :param kwargs: additional arguments
        :type kwargs: dict
        """
        if progress_callback is None:
            logger.info("Progress bar unavailable, please call product.download()")
            progress_callback = ProgressCallback(disable=True)

        ordered_message = ""
        if (
            "orderLink" in product.properties
            and "storageStatus" in product.properties
            and product.properties["storageStatus"] == OFFLINE_STATUS
        ):
            self.orderDownload(product=product, auth=auth)

        if product.properties.get("orderStatusLink", None):
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
            req_kwargs = {"json": query_dict} if query_dict else {}
        else:
            req_url = url
            req_kwargs = {}

        # url where data is downloaded from can be ftp -> add ftp adapter
        requests_ftp.monkeypatch_session()
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

            except RequestException as e:
                self._process_exception(e, product, ordered_message)
            else:
                stream_size = self._check_stream_size(product)
                product.headers = self.stream.headers
                progress_callback.reset(total=stream_size)
                logger.debug(f"stream_zip: {stream_size}")
                for chunk in self.stream.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        progress_callback(len(chunk))
                        yield chunk

    def _stream_download_assets(
        self,
        product,
        auth=None,
        progress_callback=None,
        **kwargs,
    ):
        if progress_callback is None:
            logger.info("Progress bar unavailable, please call product.download()")
            progress_callback = ProgressCallback(disable=True)

        assets_urls = [
            a["href"] for a in getattr(product, "assets", {}).values() if "href" in a
        ]
        assets_values = [
            a for a in getattr(product, "assets", {}).values() if "href" in a
        ]

        if not assets_urls:
            raise NotAvailableError("No assets available for %s" % product)

        # get extra parameters to pass to the query
        params = kwargs.pop("dl_url_params", None) or getattr(
            self.config, "dl_url_params", {}
        )

        total_size = self._get_asset_sizes(assets_values, auth, params)

        progress_callback.reset(total=total_size)

        def get_chunks(stream):
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
            asset["rel_path"] = os.path.join(*asset_rel_path_parts_sanitized)
            asset_rel_paths_list.append(asset["rel_path"])
        assets_common_subdir = os.path.commonpath(asset_rel_paths_list)

        # product conf overrides provider conf for "flatten_top_dirs"
        product_conf = getattr(self.config, "products", {}).get(
            product.product_type, {}
        )
        flatten_top_dirs = product_conf.get(
            "flatten_top_dirs", getattr(self.config, "flatten_top_dirs", False)
        )

        # loop for assets download
        for asset in assets_values:

            if asset["href"].startswith("file:"):
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
            ) as stream:
                try:
                    stream.raise_for_status()
                except RequestException as e:
                    self._handle_asset_exception(e, asset)
                else:
                    asset_rel_path = (
                        asset["rel_path"]
                        .replace(assets_common_subdir, "")
                        .strip(os.sep)
                        if flatten_top_dirs
                        else asset["rel_path"]
                    )
                    asset_rel_dir = os.path.dirname(asset_rel_path)

                    if not asset.get("filename", None):
                        # try getting filename in GET header if was not found in HEAD result
                        asset_content_disposition = stream.headers.get(
                            "content-disposition", None
                        )
                        if asset_content_disposition:
                            asset["filename"] = parse_header(
                                asset_content_disposition
                            ).get_param("filename", None)

                    if not asset.get("filename", None):
                        # default filename extracted from path
                        asset["filename"] = os.path.basename(asset["rel_path"])

                    yield (
                        os.path.join(asset_rel_dir, asset["filename"]),
                        modified_at,
                        perms,
                        NO_COMPRESSION_64,
                        get_chunks(stream),
                    )

    def _download_assets(
        self,
        product,
        fs_dir_path,
        record_filename,
        auth=None,
        progress_callback=None,
        **kwargs,
    ):
        # """Download product assets if they exist"""
        assets_urls = [
            a["href"] for a in getattr(product, "assets", {}).values() if "href" in a
        ]
        assets_values = [
            a for a in getattr(product, "assets", {}).values() if "href" in a
        ]

        if not assets_urls:
            raise NotAvailableError("No assets available for %s" % product)

        chunks_tuples = self._stream_download_assets(
            product, auth, progress_callback, **kwargs
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

        for chunk_tuple in chunks_tuples:
            asset_path = chunk_tuple[0]
            asset_chunks = chunk_tuple[4]
            asset_abs_path = os.path.join(fs_dir_path, asset_path)
            # create asset subdir if not exist
            asset_abs_path_dir = os.path.dirname(asset_abs_path)
            if not os.path.isdir(asset_abs_path_dir):
                os.makedirs(asset_abs_path_dir)
            if not os.path.isfile(asset_abs_path):
                with open(asset_abs_path, "wb") as fhandle:
                    for chunk in asset_chunks:
                        if chunk:
                            fhandle.write(chunk)
                            progress_callback(len(chunk))

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

        # save hash/record file
        with open(record_filename, "w") as fh:
            fh.write(product.remote_location)
        logger.debug("Download recorded in %s", record_filename)

        return fs_dir_path

    def _handle_asset_exception(self, e, asset):
        # check if error is identified as auth_error in provider conf
        auth_errors = getattr(self.config, "auth_error_code", [None])
        if not isinstance(auth_errors, list):
            auth_errors = [auth_errors]
        if e.response.status_code in auth_errors:
            raise AuthenticationError(
                "HTTP Error %s returned, %s\nPlease check your credentials for %s"
                % (
                    e.response.status_code,
                    e.response.text.strip(),
                    self.provider,
                )
            )
        else:
            logger.warning("Unexpected error: %s" % e)
            logger.warning("Skipping %s" % asset["href"])

    def _get_asset_sizes(self, assets_values, auth, params, zipped=False):
        total_size = 0

        # loop for assets size & filename
        for asset in assets_values:
            if not asset["href"].startswith("file:"):
                # HEAD request for size & filename
                asset_headers = requests.head(
                    asset["href"],
                    auth=auth,
                    headers=USER_AGENT,
                    timeout=HTTP_REQ_TIMEOUT,
                ).headers

                if not asset.get("size", 0):
                    # size from HEAD header / Content-length
                    asset["size"] = int(asset_headers.get("Content-length", 0))

                if not asset.get("size", 0) or not asset.get("filename", 0):
                    # header content-disposition
                    header_content_disposition = parse_header(
                        asset_headers.get("content-disposition", "")
                    )
                if not asset.get("size", 0):
                    # size from HEAD header / content-disposition / size
                    asset["size"] = int(header_content_disposition.get_param("size", 0))
                if not asset.get("filename", 0):
                    # filename from HEAD header / content-disposition / size
                    asset["filename"] = header_content_disposition.get_param(
                        "filename", None
                    )

                if not asset.get("size", 0):
                    # GET request for size
                    with requests.get(
                        asset["href"],
                        stream=True,
                        auth=auth,
                        params=params,
                        headers=USER_AGENT,
                        timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
                    ) as stream:
                        # size from GET header / Content-length
                        asset["size"] = int(stream.headers.get("Content-length", 0))
                        if not asset.get("size", 0):
                            # size from GET header / content-disposition / size
                            asset["size"] = int(
                                parse_header(
                                    stream.headers.get("content-disposition", "")
                                ).get_param("size", 0)
                            )

                total_size += asset["size"]
        return total_size

    def _stream_assets(self, product, auth=None, progress_callback=None, **kwargs):
        assets_values = [
            a for a in getattr(product, "assets", {}).values() if "href" in a
        ]

        # get extra parameters to pass to the query
        params = kwargs.pop("dl_url_params", None) or getattr(
            self.config, "dl_url_params", {}
        )

        total_size = self._get_asset_sizes(assets_values, auth, params)
        progress_callback.reset(total_size)

        # zipped files properties
        modified_at = datetime.now()
        perms = 0o600

        def get_chunks(stream):
            for chunk in stream.iter_content(chunk_size=64 * 1024):
                if chunk:
                    progress_callback(len(chunk))
                    yield chunk

        for asset in assets_values:
            with requests.get(
                asset["href"],
                stream=True,
                auth=auth,
                params=params,
                headers=USER_AGENT,
                timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
            ) as stream:
                try:
                    stream.raise_for_status()
                except RequestException as e:
                    self._handle_asset_exception(e, asset)
                else:
                    asset_rel_path = urlparse(asset["href"]).path.strip("/")
                    # asset_rel_dir = os.path.dirname(asset_rel_path)

                    if not asset.get("filename", None):
                        # try getting filename in GET header if was not found in HEAD result
                        asset_content_disposition = stream.headers.get(
                            "content-disposition", None
                        )
                        if asset_content_disposition:
                            asset["filename"] = parse_header(
                                asset_content_disposition
                            ).get_param("filename", None)

                    if not asset.get("filename", None):
                        # default filename extracted from path
                        asset["filename"] = os.path.basename(asset_rel_path)

                    yield (
                        asset["filename"],
                        modified_at,
                        perms,
                        NO_COMPRESSION_64,
                        get_chunks(stream),
                    )

    def download_all(
        self,
        products,
        auth=None,
        downloaded_callback=None,
        progress_callback=None,
        wait=DEFAULT_DOWNLOAD_WAIT,
        timeout=DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs,
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
