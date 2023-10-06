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

import hashlib
import logging
import os
import os.path
from xml.dom import minidom
from xml.parsers.expat import ExpatError

from eodag.api.product.metadata_mapping import OFFLINE_STATUS, ONLINE_STATUS
from eodag.plugins.download.base import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    DEFAULT_STREAM_REQUESTS_TIMEOUT,
    Download,
)
from eodag.plugins.download.http import HTTPDownload
from eodag.utils import (
    ProgressCallback,
    get_bucket_name_and_prefix,
    path_to_uri,
    unquote,
    urljoin,
)
from eodag.utils.exceptions import DownloadError, NotAvailableError, RequestError
from eodag.utils.http import HttpResponse

logger = logging.getLogger("eodag.plugins.download.s3rest")


class S3RestDownload(Download):
    """Http download on S3-like object storage location
    for example using Mundi REST API (free account)
    https://mundiwebservices.com/keystoneapi/uploads/documents/CWS-DATA-MUT-087-EN-Mundi_Download_v1.1.pdf#page=13

    Re-use AwsDownload bucket some handling methods

    :param provider: provider name
    :type provider: str
    :param config: Download plugin configuration:

        * ``config.base_uri`` (str) - default endpoint url
        * ``config.extract`` (bool) - (optional) extract downloaded archive or not
        * ``config.auth_error_code`` (int) - (optional) authentication error code
        * ``config.bucket_path_level`` (int) - (optional) bucket location index in path.split('/')
        * ``config.order_enabled`` (bool) - (optional) wether order is enabled or not if product is `OFFLINE`
        * ``config.order_method`` (str) - (optional) HTTP request method, GET (default) or POST
        * ``config.order_headers`` (dict) - (optional) order request headers
        * ``config.order_on_response`` (dict) - (optional) edit or add new product properties
        * ``config.order_status_method`` (str) - (optional) status HTTP request method, GET (default) or POST
        * ``config.order_status_percent`` (str) - (optional) progress percentage key in obtained status response
        * ``config.order_status_success`` (dict) - (optional) key/value identifying an error success
        * ``config.order_status_on_success`` (dict) - (optional) edit or add new product properties

    :type config: :class:`~eodag.config.PluginConfig`
    """

    def __init__(self, provider, config):
        super(S3RestDownload, self).__init__(provider, config)
        self.http_download_plugin = HTTPDownload(self.provider, self.config)

    def download(
        self,
        product,
        progress_callback=None,
        wait=DEFAULT_DOWNLOAD_WAIT,
        timeout=DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs,
    ):
        """Download method for S3 REST API.

        :param product: The EO product to download
        :type product: :class:`~eodag.api.product._product.EOProduct`
        :param progress_callback: (optional) A method or a callable object
                                  which takes a current size and a maximum
                                  size as inputs and handle progress bar
                                  creation and update to give the user a
                                  feedback on the download progress
        :type progress_callback: :class:`~eodag.utils.ProgressCallback` or None
        :param kwargs: `outputs_prefix` (str), `extract` (bool), `delete_archive` (bool)
                        and `dl_url_params` (dict) can be provided as additional kwargs
                        and will override any other values defined in a configuration
                        file or with environment variables.
        :type kwargs: Union[str, bool, dict]
        :returns: The absolute path to the downloaded product in the local filesystem
        :rtype: str
        """
        if progress_callback is None:
            logger.info(
                "Progress bar unavailable, please call product.download() instead of plugin.download()"
            )
            progress_callback = ProgressCallback(disable=True)

        # order product if it is offline
        ordered_message = ""
        if (
            "orderLink" in product.properties
            and "storageStatus" in product.properties
            and product.properties["storageStatus"] != ONLINE_STATUS
        ):
            self.http_download_plugin.orderDownload(product)

        @self._download_retry(product, wait, timeout)
        def download_request(
            product,
            progress_callback,
            ordered_message,
            **kwargs,
        ):
            # check order status
            if product.properties.get("orderStatusLink", None):
                self.http_download_plugin.orderDownloadStatus(product=product)

            # get bucket urls
            bucket_name, prefix = get_bucket_name_and_prefix(
                url=product.location, bucket_path_level=self.config.bucket_path_level
            )

            if (
                bucket_name is None
                and "storageStatus" in product.properties
                and product.properties["storageStatus"] == OFFLINE_STATUS
            ):
                raise NotAvailableError(
                    "%s is not available for download on %s (status = %s)"
                    % (
                        product.properties["title"],
                        self.provider,
                        product.properties["storageStatus"],
                    )
                )

            bucket_url = urljoin(
                product.downloader.config.base_uri.strip("/") + "/", bucket_name
            )
            nodes_list_url = bucket_url + "?prefix=" + prefix.strip("/")

            # get nodes/files list contained in the bucket
            logger.debug("Retrieving product content from %s", nodes_list_url)
            bucket_contents = self.http.get(nodes_list_url)
            try:
                bucket_contents.raise_for_status()
            except RequestError as err:
                # product not available
                if (
                    product.properties.get("storageStatus", ONLINE_STATUS)
                    != ONLINE_STATUS
                ):
                    msg = (
                        ordered_message
                        if ordered_message and not err.response.text.strip()
                        else err.response.text.strip()
                    )
                    raise NotAvailableError(
                        "%s(initially %s) requested, returned: %s"
                        % (
                            product.properties["title"],
                            product.properties["storageStatus"],
                            msg,
                        )
                    )
                # other error
                else:
                    logger.exception(
                        "Could not get content from %s (provider:%s, plugin:%s)\n%s",
                        nodes_list_url,
                        self.provider,
                        self.__class__.__name__,
                        bucket_contents.text,
                    )
                    raise err
            try:
                xmldoc = minidom.parseString(bucket_contents.text)
            except ExpatError as err:
                logger.exception("Could not parse xml data from %s", bucket_contents)
                raise DownloadError(str(err))
            nodes_xml_list = xmldoc.getElementsByTagName("Contents")

            if len(nodes_xml_list) == 0:
                logger.warning("Could not load any content from %s", nodes_list_url)

            # destination product path
            outputs_prefix = (
                kwargs.pop("outputs_prefix", None) or self.config.outputs_prefix
            )
            abs_outputs_prefix = os.path.abspath(outputs_prefix)
            product_local_path = os.path.join(abs_outputs_prefix, prefix.split("/")[-1])

            # .downloaded cache record directory
            download_records_dir = os.path.join(abs_outputs_prefix, ".downloaded")
            try:
                os.makedirs(download_records_dir)
            except OSError as exc:
                import errno

                if exc.errno != errno.EEXIST:  # Skip error if dir exists
                    import traceback as tb

                    logger.warning(
                        "Unable to create records directory. Got:\n%s", tb.format_exc()
                    )
            # check if product has already been downloaded
            url_hash = hashlib.md5(product.remote_location.encode("utf-8")).hexdigest()
            record_filename = os.path.join(download_records_dir, url_hash)
            if os.path.isfile(record_filename) and os.path.exists(product_local_path):
                product.location = path_to_uri(product_local_path)
                return product_local_path
            # Remove the record file if product_local_path is absent (e.g. it was deleted while record wasn't)
            elif os.path.isfile(record_filename):
                logger.debug(
                    "Record file found (%s) but not the actual file", record_filename
                )
                logger.debug("Removing record file : %s", record_filename)
                os.remove(record_filename)

            # total size for progress_callback
            total_size = sum(
                [
                    int(node.firstChild.nodeValue)
                    for node in xmldoc.getElementsByTagName("Size")
                ]
            )
            progress_callback.reset(total=total_size)

            # download each node key
            for node_xml in nodes_xml_list:
                node_key = unquote(
                    node_xml.getElementsByTagName("Key")[0].firstChild.nodeValue
                )
                # As "Key", "Size" and "ETag" (md5 hash) can also be retrieved from node_xml
                node_url = urljoin(bucket_url.strip("/") + "/", node_key.strip("/"))
                # output file location
                local_filename_suffix_list = node_key.split("/")[6:]
                if local_filename_suffix_list[0] == os.path.basename(
                    product_local_path
                ):
                    local_filename_suffix_list.pop(0)
                # single file: remove nested sub dirs
                if len(nodes_xml_list) == 1:
                    local_filename_suffix_list = [local_filename_suffix_list[-1]]
                local_filename = os.path.join(
                    product_local_path, *local_filename_suffix_list
                )
                local_filename_dir = os.path.dirname(os.path.realpath(local_filename))
                if not os.path.isdir(local_filename_dir):
                    os.makedirs(local_filename_dir)

                stream: HttpResponse
                with self.http.get(
                    node_url,
                    stream=True,
                    timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
                ) as stream:
                    with open(local_filename, "wb") as fhandle:
                        for chunk in stream.iter_content(chunk_size=64 * 1024):
                            if chunk:
                                fhandle.write(chunk)
                                progress_callback(len(chunk))

            with open(record_filename, "w") as fh:
                fh.write(product.remote_location)
            logger.debug("Download recorded in %s", record_filename)

            product.location = path_to_uri(product_local_path)
            return product_local_path

        return download_request(
            product,
            progress_callback,
            ordered_message,
            **kwargs,
        )
