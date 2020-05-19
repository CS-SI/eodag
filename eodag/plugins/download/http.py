# -*- coding: utf-8 -*-
# Copyright 2018, CS Systemes d'Information, http://www.c-s.fr
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
from __future__ import absolute_import, print_function, unicode_literals

# import hashlib
import logging
import shutil
import zipfile
from datetime import datetime, timedelta
from time import sleep

import requests
from requests import HTTPError

from eodag.api.product.metadata_mapping import OFFLINE_STATUS, ONLINE_STATUS
from eodag.plugins.download.base import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    Download,
)
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
    ):
        """Download a product using HTTP protocol.

        The downloaded product is assumed to be a Zip file. If it is not,
        the user is warned, it is renamed to remove the zip extension and
        no further treatment is done (no extraction)
        """
        fs_path, record_filename = self._prepare_download(product)
        if not fs_path or not record_filename:
            return fs_path

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
        # another output for notbooks
        nb_info = NotebookWidgets()

        while "Loop until products download succeeds or timeout is reached":

            if datetime.now() >= product.next_try:
                product.next_try += timedelta(minutes=wait)
                try:
                    with requests.get(
                        url,
                        stream=True,
                        auth=auth,
                        params=getattr(self.config, "dl_url_params", {}),
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
                            with open(fs_path, "wb") as fhandle:
                                for chunk in stream.iter_content(chunk_size=64 * 1024):
                                    if chunk:
                                        fhandle.write(chunk)
                                        progress_callback(len(chunk), stream_size)

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
                                return new_fs_path
                            return self._finalize(fs_path)

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

    def download_all(
        self,
        products,
        auth=None,
        progress_callback=None,
        wait=DEFAULT_DOWNLOAD_WAIT,
        timeout=DEFAULT_DOWNLOAD_TIMEOUT,
    ):
        """
        download_all using parent (base plugin) method
        """
        super(HTTPDownload, self).download_all(
            products,
            auth=auth,
            progress_callback=progress_callback,
            wait=wait,
            timeout=timeout,
        )
