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
import os.path
from typing import TYPE_CHECKING, Dict, Optional, Union
from xml.dom import minidom
from xml.parsers.expat import ExpatError

import requests
from requests import RequestException
from requests.auth import AuthBase

from eodag.api.product.metadata_mapping import OFFLINE_STATUS, ONLINE_STATUS
from eodag.plugins.download.base import Download
from eodag.plugins.download.http import HTTPDownload
from eodag.utils import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    DEFAULT_STREAM_REQUESTS_TIMEOUT,
    HTTP_REQ_TIMEOUT,
    USER_AGENT,
    ProgressCallback,
    get_bucket_name_and_prefix,
    path_to_uri,
    unquote,
    urljoin,
)
from eodag.utils.exceptions import (
    AuthenticationError,
    DownloadError,
    MisconfiguredError,
    NotAvailableError,
    RequestError,
)

if TYPE_CHECKING:
    from eodag.api.product import EOProduct
    from eodag.config import PluginConfig
    from eodag.types.download_args import DownloadConf
    from eodag.utils import Unpack

logger = logging.getLogger("eodag.download.s3rest")


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
        * ``config.order_status`` (:class:`~eodag.config.PluginConfig.OrderStatus`) - Order status handling

    :type config: :class:`~eodag.config.PluginConfig`
    """

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(S3RestDownload, self).__init__(provider, config)
        self.http_download_plugin = HTTPDownload(self.provider, self.config)

    def download(
        self,
        product: EOProduct,
        auth: Optional[Union[AuthBase, Dict[str, str]]] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: int = DEFAULT_DOWNLOAD_WAIT,
        timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Unpack[DownloadConf],
    ) -> Optional[str]:
        """Download method for S3 REST API.

        :param product: The EO product to download
        :type product: :class:`~eodag.api.product._product.EOProduct`
        :param auth: (optional) authenticated object
        :type auth: Optional[Union[AuthBase, Dict[str, str]]]
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
        if auth is not None and not isinstance(auth, AuthBase):
            raise MisconfiguredError(f"Incompatible auth plugin: {type(auth)}")

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
            self.http_download_plugin.orderDownload(product=product, auth=auth)

        @self._download_retry(product, wait, timeout)
        def download_request(
            product: EOProduct,
            auth: AuthBase,
            progress_callback: ProgressCallback,
            ordered_message: str,
            **kwargs: Unpack[DownloadConf],
        ):
            # check order status
            if product.properties.get("orderStatusLink", None):
                self.http_download_plugin.orderDownloadStatus(
                    product=product, auth=auth
                )

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

            ssl_verify = getattr(self.config, "ssl_verify", True)

            bucket_contents = requests.get(
                nodes_list_url,
                auth=auth,
                headers=USER_AGENT,
                timeout=HTTP_REQ_TIMEOUT,
                verify=ssl_verify,
            )
            try:
                bucket_contents.raise_for_status()
            except requests.RequestException as err:
                # check if error is identified as auth_error in provider conf
                auth_errors = getattr(self.config, "auth_error_code", [None])
                if not isinstance(auth_errors, list):
                    auth_errors = [auth_errors]
                if err.response and err.response.status_code in auth_errors:
                    raise AuthenticationError(
                        "HTTP Error %s returned, %s\nPlease check your credentials for %s"
                        % (
                            err.response.status_code,
                            err.response.text.strip(),
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
                        if ordered_message
                        and err.response
                        and not err.response.text.strip()
                        else err.response and err.response.text.strip()
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
                    raise RequestError(str(err))
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
            record_filename = os.path.join(
                download_records_dir, self.generate_record_hash(product)
            )
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

                with requests.get(
                    node_url,
                    stream=True,
                    auth=auth,
                    headers=USER_AGENT,
                    timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
                    verify=ssl_verify,
                ) as stream:
                    try:
                        stream.raise_for_status()
                    except RequestException:
                        import traceback as tb

                        logger.error(
                            "Error while getting resource :\n%s", tb.format_exc()
                        )
                    else:
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
            auth,
            progress_callback,
            ordered_message,
            **kwargs,
        )
