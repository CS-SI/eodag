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
from cgi import parse_header
from urllib.parse import urlparse

import requests
from requests import HTTPError, RequestException

from eodag.api.product.metadata_mapping import OFFLINE_STATUS, ONLINE_STATUS
from eodag.plugins.download.base import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    DEFAULT_STREAM_REQUESTS_TIMEOUT,
    Download,
)
from eodag.utils import ProgressCallback, path_to_uri, uri_to_path
from eodag.utils.exceptions import (
    AuthenticationError,
    MisconfiguredError,
    NotAvailableError,
)
from eodag.utils.stac_reader import HTTP_REQ_TIMEOUT

logger = logging.getLogger("eodag.plugins.download.http")


class HTTPDownload(Download):
    """HTTPDownload plugin. Handles product download over HTTP protocol"""

    def __init__(self, provider, config):
        super(HTTPDownload, self).__init__(provider, config)
        if not hasattr(self.config, "base_uri"):
            raise MisconfiguredError(
                "{} plugin require a base_uri configuration key".format(self.__name__)
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
        try:
            fs_path = self._download_assets(
                product,
                fs_path.replace(".zip", ""),
                record_filename,
                auth,
                progress_callback,
                **kwargs,
            )
            product.location = path_to_uri(fs_path)
            return fs_path
        except NotAvailableError:
            pass

        url = product.remote_location

        # order product if it is offline
        ordered_message = ""
        if (
            "orderLink" in product.properties
            and "storageStatus" in product.properties
            and product.properties["storageStatus"] == OFFLINE_STATUS
        ):
            order_method = getattr(self.config, "order_method", "GET")
            with requests.request(
                method=order_method,
                url=product.properties["orderLink"],
                auth=auth,
                headers=getattr(self.config, "order_headers", {}),
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
                        e,
                    )

        @self._download_retry(product, wait, timeout)
        def download_request(
            product,
            fs_path,
            record_filename,
            auth,
            progress_callback,
            ordered_message,
            **kwargs,
        ):
            params = kwargs.pop("dl_url_params", None) or getattr(
                self.config, "dl_url_params", {}
            )
            with requests.get(
                url,
                stream=True,
                auth=auth,
                params=params,
                timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
            ) as self.stream:
                try:
                    self.stream.raise_for_status()

                except RequestException as e:
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
                    elif (
                        product.properties.get("storageStatus", ONLINE_STATUS)
                        != ONLINE_STATUS
                    ):
                        msg = (
                            ordered_message
                            if ordered_message and not e.response.text
                            else e.response.text
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
                            "Error while getting resource :\n%s",
                            tb.format_exc(),
                        )
                else:
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
                    progress_callback.reset(total=stream_size)
                    with open(fs_path, "wb") as fhandle:
                        for chunk in self.stream.iter_content(chunk_size=64 * 1024):
                            if chunk:
                                fhandle.write(chunk)
                                progress_callback(len(chunk))

                    with open(record_filename, "w") as fh:
                        fh.write(url)
                    logger.debug("Download recorded in %s", record_filename)

                    # Check that the downloaded file is really a zip file
                    if not zipfile.is_zipfile(fs_path):
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

        return download_request(
            product,
            fs_path,
            record_filename,
            auth,
            progress_callback,
            ordered_message,
            **kwargs,
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
        """Download product assets if they exist"""
        assets_urls = [
            a["href"] for a in getattr(product, "assets", {}).values() if "href" in a
        ]
        assets_values = [
            a for a in getattr(product, "assets", {}).values() if "href" in a
        ]

        if not assets_urls:
            raise NotAvailableError("No assets available for %s" % product)

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

        # get extra parameters to pass to the query
        params = kwargs.pop("dl_url_params", None) or getattr(
            self.config, "dl_url_params", {}
        )

        total_size = 0
        # loop for assets size & filename
        for asset in assets_values:
            if not asset["href"].startswith("file:"):
                # HEAD request for size & filename
                asset_headers = requests.head(
                    asset["href"], auth=auth, timeout=HTTP_REQ_TIMEOUT
                ).headers
                header_content_disposition_dict = {}

                if not asset.get("size", 0):
                    # size from HEAD header / Content-length
                    asset["size"] = int(asset_headers.get("Content-length", 0))

                if not asset.get("size", 0) or not asset.get("filename", 0):
                    # header content-disposition
                    header_content_disposition_dict = parse_header(
                        asset_headers.get("content-disposition", "")
                    )[-1]
                if not asset.get("size", 0):
                    # size from HEAD header / content-disposition / size
                    asset["size"] = int(header_content_disposition_dict.get("size", 0))
                if not asset.get("filename", 0):
                    # filename from HEAD header / content-disposition / size
                    asset["filename"] = header_content_disposition_dict.get(
                        "filename", None
                    )

                if not asset.get("size", 0):
                    # GET request for size
                    with requests.get(
                        asset["href"],
                        stream=True,
                        auth=auth,
                        params=params,
                        timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
                    ) as stream:
                        # size from GET header / Content-length
                        asset["size"] = int(stream.headers.get("Content-length", 0))
                        if not asset.get("size", 0):
                            # size from GET header / content-disposition / size
                            asset["size"] = int(
                                parse_header(
                                    stream.headers.get("content-disposition", "")
                                )[-1].get("size", 0)
                            )

                total_size += asset["size"]

        progress_callback.reset(total=total_size)
        error_messages = set()

        local_assets_count = 0

        # loop for assets download
        for asset in assets_values:

            if asset["href"].startswith("file:"):
                logger.info(
                    f"Local asset detected. Download skipped for {asset['href']}"
                )
                local_assets_count += 1
                continue

            with requests.get(
                asset["href"],
                stream=True,
                auth=auth,
                params=params,
                timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
            ) as stream:
                try:
                    stream.raise_for_status()
                except RequestException as e:
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
                    error_messages.add(str(e))
                else:
                    asset_rel_path = urlparse(asset["href"]).path.strip("/")
                    asset_rel_dir = os.path.dirname(asset_rel_path)

                    if not asset.get("filename", None):
                        # try getting filename in GET header if was not found in HEAD result
                        asset_content_disposition_dict = stream.headers.get(
                            "content-disposition", None
                        )
                        if asset_content_disposition_dict:
                            asset["filename"] = parse_header(
                                asset_content_disposition_dict
                            )[-1].get("filename", None)

                    if not asset.get("filename", None):
                        # default filename extracted from path
                        asset["filename"] = os.path.basename(asset_rel_path)

                    asset_abs_path = os.path.join(
                        fs_dir_path, asset_rel_dir, asset["filename"]
                    )
                    asset_abs_path_dir = os.path.dirname(asset_abs_path)
                    if not os.path.isdir(asset_abs_path_dir):
                        os.makedirs(asset_abs_path_dir)

                    if not os.path.isfile(asset_abs_path):
                        with open(asset_abs_path, "wb") as fhandle:
                            for chunk in stream.iter_content(chunk_size=64 * 1024):
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
            raise HTTPError(", ".join(error_messages))

        # flatten directory structure
        if flatten_top_dirs:
            tmp_product_local_path = "%s-tmp" % fs_dir_path
            for d, dirs, files in os.walk(fs_dir_path):
                if len(files) != 0:
                    shutil.copytree(d, tmp_product_local_path)
                    shutil.rmtree(fs_dir_path)
                    os.rename(tmp_product_local_path, fs_dir_path)
                    break

        # save hash/record file
        with open(record_filename, "w") as fh:
            fh.write(product.remote_location)
        logger.debug("Download recorded in %s", record_filename)

        return fs_dir_path

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
