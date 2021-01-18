# -*- coding: utf-8 -*-
# Copyright 2020, CS GROUP - France, http://www.c-s.fr
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
import re
import shutil

import boto3
import requests
from botocore.exceptions import ClientError
from lxml import etree
from tqdm import tqdm

from eodag.api.product.metadata_mapping import mtd_cfg_as_jsonpath, properties_from_json
from eodag.plugins.download.base import Download
from eodag.utils import urlparse
from eodag.utils.exceptions import DownloadError

logger = logging.getLogger("eodag.plugins.download.aws")

# AWS chunck path identify patterns

# S2 L2A Tile files -----------------------------------------------------------
S2L2A_TILE_IMG_REGEX = re.compile(
    r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
    + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/R(?P<res>[0-9]+m)/(?P<file>[A-Z0-9_]+)\.jp2$"
)
S2L2A_TILE_AUX_DIR_REGEX = re.compile(
    r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
    + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/auxiliary/(?P<file>AUX_.+)$"
)
# S2 Tile files ---------------------------------------------------------------
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
# S1 files --------------------------------------------------------------------
S1_CALIB_REGEX = re.compile(
    r"^GRD/(?P<year>[0-9]+)/(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<beam>[A-Z0-9]+)/(?P<prod_pol>[A-Z0-9]+)/"
    + r"(?P<title>[A-Z0-9_]+)/annotation/calibration/"
    + r"(?P<file_prefix>[a-z]+)-(?P<file_beam>[a-z]+)-(?P<file_pol>.+)\.xml$"
)
S1_ANNOT_REGEX = re.compile(
    r"^GRD/(?P<year>[0-9]+)/(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<beam>[A-Z0-9]+)/(?P<prod_pol>[A-Z0-9]+)/"
    + r"(?P<title>[A-Z0-9_]+)/annotation/"
    + r"(?P<file_beam>[a-z]+)-(?P<file_pol>.+)\.xml$"
)
S1_MEAS_REGEX = re.compile(
    r"^GRD/(?P<year>[0-9]+)/(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<beam>[A-Z0-9]+)/(?P<prod_pol>[A-Z0-9]+)/"
    + r"(?P<title>[A-Z0-9_]+)/measurement/"
    + r"(?P<file_beam>[a-z]+)-(?P<file_pol>.+)\.(?P<file_ext>[a-z0-9]+)$"
)
S1_REPORT_REGEX = re.compile(
    r"^GRD/(?P<year>[0-9]+)/(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<beam>[A-Z0-9]+)/(?P<prod_pol>[A-Z0-9]+)/"
    + r"(?P<title>[A-Z0-9_]+)/(?P<file>report-\w+\.pdf)$"
)
# S1 generic
S1_REGEX = re.compile(
    r"^GRD/[0-9]{4}/[0-9]+/[0-9]+/[A-Z0-9]+/[A-Z0-9]+/(?P<title>S1[A-Z0-9_]+)/(?P<file>.+)$"
)
# CBERS4 generic
CBERS4_REGEX = re.compile(
    r"^GRD/[0-9]{4}/[0-9]+/[0-9]+/[A-Z0-9]+/[A-Z0-9]+/(?P<title>S1[A-Z0-9_]+)/(?P<file>.+)$"
)

# S1 image number conf per polarization ---------------------------------------
S1_IMG_NB_PER_POLAR = {
    "SH": {"HH": 1},
    "SV": {"VV": 1},
    "DH": {"HH": 1, "VV": 2},
    "DV": {"VV": 1, "VH": 2},
    "HH": {"HH": 1},
    "HV": {"HV": 1},
    "VV": {"VV": 1},
    "VH": {"VH": 1},
}


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
        :rtype: str
        """
        product_conf = getattr(self.config, "products", {}).get(
            product.product_type, {}
        )

        build_safe = product_conf.get("build_safe", False)

        # product conf overrides provider conf for "flatten_top_dirs"
        flatten_top_dirs = product_conf.get(
            "flatten_top_dirs", getattr(self.config, "flatten_top_dirs", False)
        )

        # xtra metadata needed for SAFE product
        if build_safe and "fetch_metadata" in product_conf.keys():
            fetch_format = product_conf["fetch_metadata"]["fetch_format"]
            update_metadata = product_conf["fetch_metadata"]["update_metadata"]
            fetch_url = product_conf["fetch_metadata"]["fetch_url"].format(
                **product.properties
            )
            if fetch_format == "json":
                logger.info("Fetching extra metadata from %s" % fetch_url)
                resp = requests.get(fetch_url)
                json_resp = resp.json()
                update_metadata = mtd_cfg_as_jsonpath(update_metadata)
                update_metadata = properties_from_json(json_resp, update_metadata)
                product.properties.update(update_metadata)
            else:
                logger.warning(
                    "SAFE metadata fetch format %s not implemented" % fetch_format
                )
        # if assets are defined, use them instead of scanning product.location
        if hasattr(product, "assets"):
            bucket_names_and_prefixes = []
            for complementary_url in getattr(product, "assets", {}).values():
                bucket_names_and_prefixes.append(
                    self.get_bucket_name_and_prefix(
                        product, complementary_url.get("href", "")
                    )
                )
        else:
            bucket_names_and_prefixes = [self.get_bucket_name_and_prefix(product)]

        # add complementary urls
        for complementary_url_key in product_conf.get("complementary_url_key", []):
            bucket_names_and_prefixes.append(
                self.get_bucket_name_and_prefix(
                    product, product.properties[complementary_url_key]
                )
            )

        # prepare download & create dirs
        product_local_path, record_filename = self._prepare_download(product, **kwargs)
        if not product_local_path or not record_filename:
            return product_local_path
        product_local_path = product_local_path.replace(".zip", "")
        # remove existing incomplete file
        if os.path.isfile(product_local_path):
            os.remove(product_local_path)
        # create product dest dir
        if not os.path.isdir(product_local_path):
            os.makedirs(product_local_path)

        with tqdm(
            total=len(bucket_names_and_prefixes),
            unit="parts",
            desc="Downloading product parts",
        ) as bar:

            for bucket_name, prefix in bucket_names_and_prefixes:
                try:
                    # connect to aws s3
                    access_key, access_secret = auth
                    s3 = boto3.resource(
                        "s3",
                        aws_access_key_id=access_key,
                        aws_secret_access_key=access_secret,
                    )
                    bucket = s3.Bucket(bucket_name)

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
                        chunck_rel_path = self.get_chunck_dest_path(
                            product,
                            product_chunk,
                            build_safe=build_safe,
                            dir_prefix=prefix,
                        )
                        chunck_abs_path = os.path.join(
                            product_local_path, chunck_rel_path
                        )
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
                except ClientError as e:
                    logger.warning("Unexpected error: %s" % e)
                    logger.warning("Skipping %s/%s" % (bucket_name, prefix))
                bar.update(1)

        # finalize safe product
        if build_safe and "S2_MSI" in product.product_type:
            self.finalize_s2_safe_product(product_local_path)
        # flatten directory structure
        elif flatten_top_dirs:
            tmp_product_local_path = "%s-tmp" % product_local_path
            for d, dirs, files in os.walk(product_local_path):
                if len(files) != 0:
                    shutil.copytree(d, tmp_product_local_path)
                    shutil.rmtree(product_local_path)
                    os.rename(tmp_product_local_path, product_local_path)
                    break

        # save hash/record file
        with open(record_filename, "w") as fh:
            fh.write(product.remote_location)
        logger.debug("Download recorded in %s", record_filename)

        return product_local_path

    def get_bucket_name_and_prefix(self, product, url=None):
        """Extract bucket name and prefix from product URL

        :param product: The EO product to download
        :type product: :class:`~eodag.api.product.EOProduct`
        :param url: URL to use as product.location
        :type url: str
        :return: bucket_name and prefix as str
        :rtype: tuple
        """
        if not url:
            url = product.location
        bucket, prefix = None, None
        # Assume the bucket is encoded into the product location as a URL or given as the 'default_bucket' config
        # param
        scheme, netloc, path, params, query, fragment = urlparse(url)
        if not scheme or scheme == "s3":
            bucket = (
                netloc
                if netloc
                else getattr(self.config, "products", {})
                .get(product.product_type, {})
                .get("default_bucket", "")
            )
            prefix = path.strip("/")
        elif scheme in ("http", "https", "ftp"):
            parts = path.split("/")
            bucket, prefix = parts[1], "/{}".format("/".join(parts[2:]))
        return bucket, prefix

    def finalize_s2_safe_product(self, product_path):
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

    def get_chunck_dest_path(self, product, chunk, dir_prefix, build_safe=False):
        """Get chunck destination path
        """
        if build_safe:
            # S2 common
            if "S2_MSI" in product.product_type:
                title_date1_search = re.search(
                    r"^\w+_\w+_(\w+)_\w+_\w+_\w+_\w+$", product.properties["title"]
                )
                title_date1 = (
                    title_date1_search.group(1) if title_date1_search else None
                )
                ds_dir_search = re.search(
                    r"^.+_(DS_\w+_+\w+_\w+)_\w+.\w+$",
                    product.properties.get("originalSceneID", ""),
                )
                ds_dir = ds_dir_search.group(1) if ds_dir_search else None
                s2_processing_level = product.product_type.split("_")[-1]
            # S1 common
            elif product.product_type == "S1_SAR_GRD":
                s1_title_suffix_search = re.search(
                    r"^.+_([A-Z0-9_]+_[A-Z0-9_]+_[A-Z0-9_]+_[A-Z0-9_]+)_\w+$",
                    product.properties["title"],
                )
                s1_title_suffix = (
                    s1_title_suffix_search.group(1).lower().replace("_", "-")
                    if s1_title_suffix_search
                    else None
                )

            # S2 L2A Tile files -----------------------------------------------
            if S2L2A_TILE_IMG_REGEX.match(chunk.key):
                found_dict = S2L2A_TILE_IMG_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/GRANULE/%s/IMG_DATA/%s/T%s%s%s_%s_%s_%s.jp2" % (
                    product.properties["title"],
                    found_dict["num"],
                    found_dict["res"],
                    found_dict["tile1"],
                    found_dict["tile2"],
                    found_dict["tile3"],
                    title_date1,
                    found_dict["file"],
                    found_dict["res"],
                )
            elif S2L2A_TILE_AUX_DIR_REGEX.match(chunk.key):
                found_dict = S2L2A_TILE_AUX_DIR_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/GRANULE/%s/AUX_DATA/%s" % (
                    product.properties["title"],
                    found_dict["num"],
                    found_dict["file"],
                )
            # S2 Tile files ---------------------------------------------------
            elif S2_TILE_PREVIEW_DIR_REGEX.match(chunk.key):
                found_dict = S2_TILE_PREVIEW_DIR_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/GRANULE/%s/preview/%s" % (
                    product.properties["title"],
                    found_dict["num"],
                    found_dict["file"],
                )
            elif S2_TILE_IMG_REGEX.match(chunk.key):
                found_dict = S2_TILE_IMG_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/GRANULE/%s/IMG_DATA/T%s%s%s_%s_%s" % (
                    product.properties["title"],
                    found_dict["num"],
                    found_dict["tile1"],
                    found_dict["tile2"],
                    found_dict["tile3"],
                    title_date1,
                    found_dict["file"],
                )
            elif S2_TILE_THUMBNAIL_REGEX.match(chunk.key):
                found_dict = S2_TILE_THUMBNAIL_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/GRANULE/%s/%s" % (
                    product.properties["title"],
                    found_dict["num"],
                    found_dict["file"],
                )
            elif S2_TILE_MTD_REGEX.match(chunk.key):
                found_dict = S2_TILE_MTD_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/GRANULE/%s/MTD_TL.xml" % (
                    product.properties["title"],
                    found_dict["num"],
                )
            elif S2_TILE_AUX_DIR_REGEX.match(chunk.key):
                found_dict = S2_TILE_AUX_DIR_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/GRANULE/%s/AUX_DATA/AUX_%s" % (
                    product.properties["title"],
                    found_dict["num"],
                    found_dict["file"],
                )
            elif S2_TILE_QI_DIR_REGEX.match(chunk.key):
                found_dict = S2_TILE_QI_DIR_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/GRANULE/%s/QI_DATA/%s" % (
                    product.properties["title"],
                    found_dict["num"],
                    found_dict["file"],
                )
            # S2 Tiles generic
            elif S2_TILE_REGEX.match(chunk.key):
                found_dict = S2_TILE_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/GRANULE/%s/%s" % (
                    product.properties["title"],
                    found_dict["num"],
                    found_dict["file"],
                )
            # S2 Product files
            elif S2_PROD_DS_MTD_REGEX.match(chunk.key):
                found_dict = S2_PROD_DS_MTD_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/DATASTRIP/%s/MTD_DS.xml" % (
                    product.properties["title"],
                    ds_dir,
                )
            elif S2_PROD_DS_QI_REGEX.match(chunk.key):
                found_dict = S2_PROD_DS_QI_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/DATASTRIP/%s/QI_DATA/%s" % (
                    product.properties["title"],
                    ds_dir,
                    found_dict["file"],
                )
            elif S2_PROD_INSPIRE_REGEX.match(chunk.key):
                found_dict = S2_PROD_INSPIRE_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/INSPIRE.xml" % (product.properties["title"],)
            elif S2_PROD_MTD_REGEX.match(chunk.key):
                found_dict = S2_PROD_MTD_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/MTD_MSI%s.xml" % (
                    product.properties["title"],
                    s2_processing_level,
                )
            # S2 Product generic
            elif S2_PROD_REGEX.match(chunk.key):
                found_dict = S2_PROD_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/%s" % (
                    product.properties["title"],
                    found_dict["file"],
                )
            # S1 --------------------------------------------------------------
            elif S1_CALIB_REGEX.match(chunk.key):
                found_dict = S1_CALIB_REGEX.match(chunk.key).groupdict()
                product_path = (
                    "%s.SAFE/annotation/calibration/%s-%s-%s-grd-%s-%s-%03d.xml"
                    % (
                        product.properties["title"],
                        found_dict["file_prefix"],
                        product.properties["platformSerialIdentifier"].lower(),
                        found_dict["file_beam"],
                        found_dict["file_pol"],
                        s1_title_suffix,
                        S1_IMG_NB_PER_POLAR.get(
                            product.properties["polarizationMode"], {}
                        ).get(found_dict["file_pol"].upper(), 1),
                    )
                )
            elif S1_ANNOT_REGEX.match(chunk.key):
                found_dict = S1_ANNOT_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/annotation/%s-%s-grd-%s-%s-%03d.xml" % (
                    product.properties["title"],
                    product.properties["platformSerialIdentifier"].lower(),
                    found_dict["file_beam"],
                    found_dict["file_pol"],
                    s1_title_suffix,
                    S1_IMG_NB_PER_POLAR.get(
                        product.properties["polarizationMode"], {}
                    ).get(found_dict["file_pol"].upper(), 1),
                )
            elif S1_MEAS_REGEX.match(chunk.key):
                found_dict = S1_MEAS_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/measurement/%s-%s-grd-%s-%s-%03d.%s" % (
                    product.properties["title"],
                    product.properties["platformSerialIdentifier"].lower(),
                    found_dict["file_beam"],
                    found_dict["file_pol"],
                    s1_title_suffix,
                    S1_IMG_NB_PER_POLAR.get(
                        product.properties["polarizationMode"], {}
                    ).get(found_dict["file_pol"].upper(), 1),
                    found_dict["file_ext"],
                )
            elif S1_REPORT_REGEX.match(chunk.key):
                found_dict = S1_REPORT_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/%s.SAFE-%s" % (
                    product.properties["title"],
                    product.properties["title"],
                    found_dict["file"],
                )
            # S1 generic
            elif S1_REGEX.match(chunk.key):
                found_dict = S1_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/%s" % (
                    product.properties["title"],
                    found_dict["file"],
                )
        # no SAFE format
        else:
            product_path = chunk.key.split(dir_prefix.strip("/") + "/")[-1]
        logger.debug("Downloading %s to %s" % (chunk.key, product_path))
        return product_path

    def download_all(self, products, auth=None, progress_callback=None, **kwargs):
        """
        download_all using parent (base plugin) method
        """
        super(AwsDownload, self).download_all(
            products, auth=auth, progress_callback=progress_callback, **kwargs
        )
