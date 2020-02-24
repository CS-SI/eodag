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

import hashlib
import logging
import os
import os.path
from xml.dom import minidom
from xml.parsers.expat import ExpatError

import requests
from requests import HTTPError

from eodag.plugins.download.aws import AwsDownload
from eodag.plugins.download.http import HTTPDownload
from eodag.utils import urljoin
from eodag.utils.exceptions import DownloadError, RequestError

logger = logging.getLogger("eodag.plugins.download.s3rest")


class S3RestDownload(AwsDownload):
    """Http download on S3-like object storage location
    for example using Mundi REST API (free account)
    https://mundiwebservices.com/keystoneapi/uploads/documents/CWS-DATA-MUT-087-EN-Mundi_Download_v1.1.pdf#page=13

    Re-use AwsDownload bucket some handling methods
    """

    def download(self, product, auth=None, progress_callback=None):
        """Download method for S3 REST API.

        :param product: The EO product to download
        :type product: :class:`~eodag.api.product.EOProduct`
        :param auth: (optional) The configuration of a plugin of type Authentication
        :type auth: :class:`~eodag.config.PluginConfig`
        :param progress_callback: (optional) A method or a callable object
                                  which takes a current size and a maximum
                                  size as inputs and handle progress bar
                                  creation and update to give the user a
                                  feedback on the download progress
        :type progress_callback: :class:`~eodag.utils.ProgressCallback` or None
        :return: The absolute path to the downloaded product in the local filesystem
        :rtype: str or unicode
        """
        # get bucket urls
        bucket_name, prefix = self.get_bucket_name_and_prefix(product)

        bucket_url = urljoin(
            product.downloader.config.base_uri.strip("/") + "/", bucket_name
        )
        nodes_list_url = bucket_url + "?prefix=" + prefix.strip("/")

        # get nodes/files list contained in the bucket
        logger.debug("Retrieving product content from %s", nodes_list_url)
        bucket_contents = requests.get(nodes_list_url, auth=auth)
        try:
            bucket_contents.raise_for_status()
        except requests.HTTPError as err:
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
        elif len(nodes_xml_list) == 1:
            # single file download
            product.remote_location = urljoin(
                bucket_url.strip("/") + "/", prefix.strip("/")
            )
            return HTTPDownload(self.provider, self.config).download(
                product=product, auth=auth, progress_callback=progress_callback
            )

        # destination product path
        abs_outputs_prefix = os.path.abspath(self.config.outputs_prefix)
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

        # download each node key
        for node_xml in nodes_xml_list:
            node_key = node_xml.getElementsByTagName("Key")[0].firstChild.nodeValue
            # As "Key", "Size" and "ETag" (md5 hash) can also be retrieved from node_xml
            node_url = urljoin(bucket_url.strip("/") + "/", node_key.strip("/"))
            # output file location
            local_filename = os.path.join(
                self.config.outputs_prefix, "/".join(node_key.split("/")[6:])
            )
            local_filename_dir = os.path.dirname(os.path.realpath(local_filename))
            if not os.path.isdir(local_filename_dir):
                os.makedirs(local_filename_dir)

            with requests.get(node_url, stream=True, auth=auth) as stream:
                try:
                    stream.raise_for_status()
                except HTTPError:
                    import traceback as tb

                    logger.error("Error while getting resource :\n%s", tb.format_exc())
                else:
                    with open(local_filename, "wb") as fhandle:
                        for chunk in stream.iter_content(chunk_size=64 * 1024):
                            if chunk:
                                fhandle.write(chunk)
                                progress_callback(len(chunk), total_size)

            # TODO: check md5 hash ?

        with open(record_filename, "w") as fh:
            fh.write(product.remote_location)
        logger.debug("Download recorded in %s", record_filename)

        return product_local_path
