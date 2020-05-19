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

import logging
import os
import re

import boto3
from lxml import etree
from tqdm import tqdm

from eodag.plugins.download.base import Download
from eodag.utils import urlparse
from eodag.utils.exceptions import DownloadError

logger = logging.getLogger("eodag.plugins.download.aws")


class AwsDownload(Download):
    """Download on AWS using S3 protocol
    """

    def download(self, product, auth=None, progress_callback=None, **kwargs):
        """Download method for AWS S3 API.

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

        product_local_path, record_filename = self._prepare_download(product)
        if not product_local_path or not record_filename:
            return product_local_path

        product_local_path = product_local_path.replace(".zip", "")

        # remove existing incomplete file
        if os.path.isfile(product_local_path):
            os.remove(product_local_path)
        # create product dest dir
        if not os.path.isdir(product_local_path):
            os.makedirs(product_local_path)

        bucket_name, prefix = self.get_bucket_name_and_prefix(product)
        access_key, access_secret = auth
        s3 = boto3.resource(
            "s3", aws_access_key_id=access_key, aws_secret_access_key=access_secret
        )
        bucket = s3.Bucket(bucket_name)

        prefixes = [prefix]

        # SAFE product build using complementary files
        build_safe = getattr(product.downloader.config, "build_safe", False)
        safe_complementary_url_keys = getattr(
            product.downloader.config, "safe_complementary_url_key", None
        )
        if build_safe and safe_complementary_url_keys:
            safe_complementary_urls = [
                product.properties[k] for k in safe_complementary_url_keys
            ]
            prefixes += safe_complementary_urls

        with tqdm(
            total=len(prefixes), unit="parts", desc="Downloading product parts"
        ) as bar:

            for prefix in prefixes:
                total_size = sum(
                    [
                        p.size
                        for p in bucket.objects.filter(
                            Prefix=prefix, RequestPayer="requester"
                        )
                    ]
                )
                progress_callback.max_size = total_size
                for product_chunk in bucket.objects.filter(
                    Prefix=prefix, RequestPayer="requester"
                ):
                    chunck_rel_path = self.get_chunck_path(
                        product, product_chunk, build_safe=build_safe
                    )
                    chunck_abs_path = os.path.join(product_local_path, chunck_rel_path)
                    chunck_abs_path_dir = os.path.dirname(chunck_abs_path)
                    if not os.path.isdir(chunck_abs_path_dir):
                        os.makedirs(chunck_abs_path_dir)

                    if not os.path.isfile(chunck_abs_path):
                        bucket.download_file(
                            product_chunk.key,
                            chunck_abs_path,
                            ExtraArgs={"RequestPayer": "requester"},
                            Callback=progress_callback,
                        )
                bar.update(1)

        # finalize safe product
        if build_safe:
            self.finalize_safe_product(product_local_path)

        # save hash/record file
        with open(record_filename, "w") as fh:
            fh.write(product.remote_location)
        logger.debug("Download recorded in %s", record_filename)

        return product_local_path

    def get_bucket_name_and_prefix(self, product):
        """Extract bucket name and prefix from product URL

        :param product: The EO product to download
        :type product: :class:`~eodag.api.product.EOProduct`
        :return: bucket_name and prefix as str
        :rtype: tuple
        """
        bucket, prefix = None, None
        # Assume the bucket is encoded into the product location as a URL or given as the 'associated_bucket' config
        # param
        scheme, netloc, path, params, query, fragment = urlparse(product.location)
        if scheme == "s3":
            bucket, prefix = self.config.associated_bucket, path.strip("/")
        elif scheme in ("http", "https", "ftp"):
            parts = path.split("/")
            bucket, prefix = parts[1], "/{}".format("/".join(parts[2:]))
        return bucket, prefix

    def finalize_safe_product(self, product_path):
        """Add missing dirs to downloaded product
        """
        try:
            logger.debug("Finalize SAFE product")
            manifest_path = [
                os.path.join(d, x)
                for d, _, f in os.walk(product_path)
                for x in f
                if x == "manifest.safe"
            ][0]
            safe_path = os.path.dirname(manifest_path)

            # create empty missing dirs
            auxdata_path = os.path.join(safe_path, "AUX_DATA")
            if not os.path.isdir(auxdata_path):
                os.makedirs(auxdata_path)
            html_path = os.path.join(safe_path, "HTML")
            if not os.path.isdir(html_path):
                os.makedirs(html_path)
            repinfo_path = os.path.join(safe_path, "rep_info")
            if not os.path.isdir(repinfo_path):
                os.makedirs(repinfo_path)

            # granule tile dirname
            root = etree.parse(os.path.join(safe_path, "manifest.safe")).getroot()
            tile_id = os.path.basename(
                os.path.dirname(
                    root.xpath("//fileLocation[contains(@href,'MTD_TL.xml')]")[0].get(
                        "href"
                    )
                )
            )
            os.rename(
                os.path.join(safe_path, "GRANULE/0"),
                os.path.join(safe_path, "GRANULE", tile_id),
            )
        except Exception as e:
            logger.exception("Could not finalize SAFE product from downloaded data")
            raise DownloadError(e)

    def get_chunck_path(self, product, chunk, build_safe=False):
        """Get chunck destination path
        """
        title_date1_search = re.search(
            r"^\w+_\w+_(\w+)_\w+_\w+_\w+_\w+$", product.properties["title"]
        )
        title_date1 = title_date1_search.group(1) if title_date1_search else None
        ds_dir_search = re.search(
            r"^.+_(DS_\w+_+\w+_\w+)_\w+.\w+$", product.properties["originalSceneID"]
        )
        ds_dir = ds_dir_search.group(1) if ds_dir_search else None

        # S2 Tile files
        S2_TILE_IMG_REGEX = re.compile(
            r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
            + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/(?P<file>[A-Z0-9_]+\.jp2)$"
        )
        S2_TILE_PREVIEW_DIR_REGEX = re.compile(
            r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
            + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/preview/(?P<file>.+)$"
        )
        S2_TILE_AUX_DIR_REGEX = re.compile(
            r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
            + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/auxiliary/(?P<file>.+)$"
        )
        S2_TILE_QI_DIR_REGEX = re.compile(
            r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
            + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/qi/(?P<file>.+)$"
        )
        S2_TILE_THUMBNAIL_REGEX = re.compile(
            r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
            + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/(?P<file>preview\.\w+)$"
        )
        S2_TILE_MTD_REGEX = re.compile(
            r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
            + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/(?P<file>metadata\.xml)$"
        )
        # S2 Tile generic
        S2_TILE_REGEX = re.compile(
            r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
            + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/(?P<file>.+)$"
        )
        # S2 Product files
        S2_PROD_REGEX = re.compile(
            r"^products/(?P<year>[0-9]+)/(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<title>[A-Z0-9_]+)/(?P<file>.+)$"
        )
        S2_PROD_DS_MTD_REGEX = re.compile(
            r"^products/(?P<year>[0-9]+)/(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<title>[A-Z0-9_]+)/datastrip/"
            + r"(?P<num>.+)/(?P<file>metadata\.xml)$"
        )
        S2_PROD_DS_QI_REGEX = re.compile(
            r"^products/(?P<year>[0-9]+)/(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<title>[A-Z0-9_]+)/datastrip/"
            + r"(?P<num>.+)/qi/(?P<file>.+)$"
        )
        S2_PROD_INSPIRE_REGEX = re.compile(
            r"^products/(?P<year>[0-9]+)/(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<title>[A-Z0-9_]+)/"
            + r"(?P<file>inspire\.xml)$"
        )
        # S2 Product generic
        S2_PROD_MTD_REGEX = re.compile(
            r"^products/(?P<year>[0-9]+)/(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<title>[A-Z0-9_]+)/"
            + r"(?P<file>metadata\.xml)$"
        )

        if build_safe:
            # S2 Tile files
            if S2_TILE_PREVIEW_DIR_REGEX.match(chunk.key):
                s2_tile_dict = S2_TILE_PREVIEW_DIR_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/GRANULE/%s/preview/%s" % (
                    product.properties["title"],
                    s2_tile_dict["num"],
                    s2_tile_dict["file"],
                )
            elif S2_TILE_IMG_REGEX.match(chunk.key):
                s2_tile_dict = S2_TILE_IMG_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/GRANULE/%s/IMG_DATA/T%s%s%s_%s_%s" % (
                    product.properties["title"],
                    s2_tile_dict["num"],
                    s2_tile_dict["tile1"],
                    s2_tile_dict["tile2"],
                    s2_tile_dict["tile3"],
                    title_date1,
                    s2_tile_dict["file"],
                )
            elif S2_TILE_THUMBNAIL_REGEX.match(chunk.key):
                s2_tile_dict = S2_TILE_THUMBNAIL_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/GRANULE/%s/%s" % (
                    product.properties["title"],
                    s2_tile_dict["num"],
                    s2_tile_dict["file"],
                )
            elif S2_TILE_MTD_REGEX.match(chunk.key):
                s2_tile_dict = S2_TILE_MTD_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/GRANULE/%s/MTD_TL.xml" % (
                    product.properties["title"],
                    s2_tile_dict["num"],
                )
            elif S2_TILE_AUX_DIR_REGEX.match(chunk.key):
                s2_tile_dict = S2_TILE_AUX_DIR_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/GRANULE/%s/AUX_DATA/AUX_%s" % (
                    product.properties["title"],
                    s2_tile_dict["num"],
                    s2_tile_dict["file"],
                )
            elif S2_TILE_QI_DIR_REGEX.match(chunk.key):
                s2_tile_dict = S2_TILE_QI_DIR_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/GRANULE/%s/QI_DATA/%s" % (
                    product.properties["title"],
                    s2_tile_dict["num"],
                    s2_tile_dict["file"],
                )
            # S2 Tiles generic
            elif S2_TILE_REGEX.match(chunk.key):
                s2_tile_dict = S2_TILE_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/GRANULE/%s/%s" % (
                    product.properties["title"],
                    s2_tile_dict["num"],
                    s2_tile_dict["file"],
                )
            # S2 Product files
            elif S2_PROD_DS_MTD_REGEX.match(chunk.key):
                s2_tile_dict = S2_PROD_DS_MTD_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/DATASTRIP/%s/MTD_DS.xml" % (
                    product.properties["title"],
                    ds_dir,
                )
            elif S2_PROD_DS_QI_REGEX.match(chunk.key):
                s2_tile_dict = S2_PROD_DS_QI_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/DATASTRIP/%s/QI_DATA/%s" % (
                    product.properties["title"],
                    ds_dir,
                    s2_tile_dict["file"],
                )
            elif S2_PROD_INSPIRE_REGEX.match(chunk.key):
                s2_tile_dict = S2_PROD_INSPIRE_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/INSPIRE.xml" % (product.properties["title"],)
            elif S2_PROD_MTD_REGEX.match(chunk.key):
                s2_tile_dict = S2_PROD_MTD_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/MTD_MSIL1C.xml" % (product.properties["title"],)
            # S2 Product generic
            elif S2_PROD_REGEX.match(chunk.key):
                s2_tile_dict = S2_PROD_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/%s" % (
                    product.properties["title"],
                    s2_tile_dict["file"],
                )
        else:
            # S2 Tiles generic
            if S2_TILE_REGEX.match(chunk.key):
                s2_tile_dict = S2_TILE_REGEX.match(chunk.key).groupdict()
                product_path = "%s" % (s2_tile_dict["file"])
        logger.debug("Downloading %s to %s" % (chunk.key, product_path))
        return product_path

    def download_all(self, products, auth=None, progress_callback=None, **kwargs):
        """
        download_all using parent (base plugin) method
        """
        super(AwsDownload, self).download_all(
            products, auth=auth, progress_callback=progress_callback
        )
