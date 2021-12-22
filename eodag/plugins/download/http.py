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
from datetime import datetime, timedelta
from time import sleep

import requests
from requests import HTTPError

from eodag.api.product.metadata_mapping import OFFLINE_STATUS, ONLINE_STATUS
from eodag.plugins.download.base import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    DEFAULT_STREAM_REQUESTS_TIMEOUT,
    Download,
)
from eodag.utils import ProgressCallback, path_to_uri
from eodag.utils.exceptions import (
    AuthenticationError,
    MisconfiguredError,
    NotAvailableError,
)
from eodag.utils.notebook import NotebookWidgets

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
        **kwargs
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
                **kwargs
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
                except HTTPError as e:
                    logger.warning(
                        "%s could not be ordered, request returned %s",
                        product.properties["title"],
                        e,
                    )

        # initiate retry loop
        start_time = datetime.now()
        stop_time = datetime.now() + timedelta(minutes=timeout)
        product.next_try = start_time
        retry_count = 0
        not_available_info = "The product could not be downloaded"
        # another output for notebooks
        nb_info = NotebookWidgets()

        while "Loop until products download succeeds or timeout is reached":

            if datetime.now() >= product.next_try:
                product.next_try += timedelta(minutes=wait)
                try:
                    params = kwargs.pop("dl_url_params", None) or getattr(
                        self.config, "dl_url_params", {}
                    )
                    with requests.get(
                        url,
                        stream=True,
                        auth=auth,
                        params=params,
                        timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
                    ) as stream:
                        try:
                            stream.raise_for_status()
                        except HTTPError as e:
                            # check if error is identified as auth_error in provider conf
                            auth_errors = getattr(
                                self.config, "auth_error_code", [None]
                            )
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
                            stream_size = int(stream.headers.get("content-length", 0))
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
                                        stream.reason,
                                    )
                                )
                            progress_callback.reset(total=stream_size)
                            with open(fs_path, "wb") as fhandle:
                                for chunk in stream.iter_content(chunk_size=64 * 1024):
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

                except NotAvailableError as e:
                    if not getattr(self.config, "order_enabled", False):
                        raise NotAvailableError(
                            "Product is not available for download and order is not supported for %s, %s"
                            % (self.provider, e)
                        )
                    not_available_info = e
                    pass

            if datetime.now() < product.next_try and datetime.now() < stop_time:
                wait_seconds = (product.next_try - datetime.now()).seconds
                retry_count += 1
                retry_info = (
                    "[Retry #%s] Waiting %ss until next download try (retry every %s' for %s')"
                    % (retry_count, wait_seconds, wait, timeout)
                )
                logger.debug(not_available_info)
                # Retry-After info from Response header
                retry_server_info = stream.headers.get("Retry-After", "")
                if retry_server_info:
                    logger.debug(
                        "[%s response] Retry-After: %s"
                        % (self.provider, retry_server_info)
                    )
                logger.info(retry_info)
                nb_info.display_html(retry_info)
                sleep(wait_seconds + 1)
            elif datetime.now() >= stop_time and timeout > 0:
                if "storageStatus" not in product.properties:
                    product.properties["storageStatus"] = "N/A status"
                logger.info(not_available_info)
                raise NotAvailableError(
                    "%s is not available (%s) and could not be downloaded, timeout reached"
                    % (product.properties["title"], product.properties["storageStatus"])
                )
            elif datetime.now() >= stop_time:
                raise NotAvailableError(not_available_info)

    def _download_assets(
        self,
        product,
        fs_dir_path,
        record_filename,
        auth=None,
        progress_callback=None,
        **kwargs
    ):
        """Download product assets if they exist"""
        assets_urls = [
            a["href"] for a in getattr(product, "assets", {}).values() if "href" in a
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

        # get total size using header[Content-length] of each asset
        total_size = sum(
            [
                int(
                    requests.head(asset_url, auth=auth).headers.get("Content-length", 0)
                )
                for asset_url in assets_urls
            ]
        )
        if total_size == 0:
            # alternative: get total size using header[content-disposition][size] of each asset
            total_size = sum(
                [
                    int(
                        parse_header(
                            requests.head(asset_url, auth=auth).headers.get(
                                "content-disposition", ""
                            )
                        )[-1].get("size", 0)
                    )
                    for asset_url in assets_urls
                ]
            )
        progress_callback.reset(total=total_size)
        error_messages = set()

        for asset_url in assets_urls:

            # get asset filename from header
            asset_content_disposition = requests.head(asset_url, auth=auth).headers.get(
                "content-disposition", None
            )
            if asset_content_disposition:
                asset_filename = parse_header(asset_content_disposition)[-1]["filename"]
            else:
                asset_filename = None

            # get extra parameters to pass to the query
            params = kwargs.pop("dl_url_params", None) or getattr(
                self.config, "dl_url_params", {}
            )

            with requests.get(
                asset_url,
                stream=True,
                auth=auth,
                params=params,
                timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
            ) as stream:
                try:
                    stream.raise_for_status()
                except HTTPError as e:
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
                        logger.warning("Skipping %s" % asset_url)
                    error_messages.add(str(e))
                else:
                    if asset_filename is not None:
                        asset_rel_path = asset_filename
                    else:
                        asset_rel_path = (
                            asset_url.replace(product.location, "")
                            .replace("https://", "")
                            .replace("http://", "")
                            .strip("/")
                        )
                    asset_abs_path = os.path.join(fs_dir_path, asset_rel_path)
                    asset_abs_path_dir = os.path.dirname(asset_abs_path)
                    if not os.path.isdir(asset_abs_path_dir):
                        os.makedirs(asset_abs_path_dir)

                    if not os.path.isfile(asset_abs_path):
                        with open(asset_abs_path, "wb") as fhandle:
                            for chunk in stream.iter_content(chunk_size=64 * 1024):
                                if chunk:
                                    fhandle.write(chunk)
                                    progress_callback(len(chunk))

        # could not download any file
        if len(os.listdir(fs_dir_path)) == 0:
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
        **kwargs
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
            **kwargs
        )
