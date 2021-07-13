# -*- coding: utf-8 -*-
# Copyright 2021, CS GROUP - France, https://www.csgroup.eu/
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
from pathlib import Path

import boto3
import requests
from botocore.exceptions import ClientError, ProfileNotFound
from botocore.handlers import disable_signing
from lxml import etree

from eodag.api.product.metadata_mapping import (
    mtd_cfg_as_jsonpath,
    properties_from_json,
    properties_from_xml,
)
from eodag.plugins.download.base import Download
from eodag.utils import ProgressCallback, path_to_uri, urlparse
from eodag.utils.exceptions import AuthenticationError, DownloadError

logger = logging.getLogger("eodag.plugins.download.aws")

# AWS chunk path identify patterns

# S2 L2A Tile files -----------------------------------------------------------
S2L2A_TILE_IMG_REGEX = re.compile(
    r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
    + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/R(?P<res>[0-9]+m)/(?P<file>[A-Z0-9_]+)\.jp2$"
)
S2L2A_TILE_AUX_DIR_REGEX = re.compile(
    r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
    + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/auxiliary/(?P<file>AUX_.+)$"
)
# S2 L2A QI Masks
S2_TILE_QI_MSK_REGEX = re.compile(
    r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
    + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/qi/(?P<file_base>.+)_(?P<file_suffix>[0-9]+m\.jp2)$"
)
# S2 L2A QI PVI
S2_TILE_QI_PVI_REGEX = re.compile(
    r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
    + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/qi/L2A_PVI\.jp2$"
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
S2_PROD_DS_QI_REPORT_REGEX = re.compile(
    r"^products/(?P<year>[0-9]+)/(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<title>[A-Z0-9_]+)/datastrip/"
    + r"(?P<num>.+)/qi/(?P<filename>.+)_report\.xml$"
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
    "DH": {"HH": 1, "HV": 2},
    "DV": {"VV": 1, "VH": 2},
    "HH": {"HH": 1},
    "HV": {"HV": 1},
    "VV": {"VV": 1},
    "VH": {"VH": 1},
}


class AwsDownload(Download):
    """Download on AWS using S3 protocol"""

    def download(self, product, auth=None, progress_callback=None, **kwargs):
        """Download method for AWS S3 API.

        The product can be downloaded as it is, or as SAFE-formatted product.
        SAFE-build is configured for a given provider and product type.
        If the product title is configured to be updated during download and
        SAFE-formatted, its destination path will be:
        `{outputs_prefix}/{title}/{updated_title}.SAFE`

        :param product: The EO product to download
        :type product: :class:`~eodag.api.product._product.EOProduct`
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
        if progress_callback is None:
            logger.info(
                "Progress bar unavailable, please call product.download() instead of plugin.download()"
            )
            progress_callback = ProgressCallback(disable=True)

        # prepare download & create dirs (before updating metadata)
        product_local_path, record_filename = self._prepare_download(
            product, progress_callback=progress_callback, **kwargs
        )
        if not product_local_path or not record_filename:
            if product_local_path:
                product.location = path_to_uri(product_local_path)
            return product_local_path
        product_local_path = product_local_path.replace(".zip", "")
        # remove existing incomplete file
        if os.path.isfile(product_local_path):
            os.remove(product_local_path)
        # create product dest dir
        if not os.path.isdir(product_local_path):
            os.makedirs(product_local_path)

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
            logger.info("Fetching extra metadata from %s" % fetch_url)
            resp = requests.get(fetch_url)
            update_metadata = mtd_cfg_as_jsonpath(update_metadata)
            if fetch_format == "json":
                json_resp = resp.json()
                update_metadata = properties_from_json(json_resp, update_metadata)
                product.properties.update(update_metadata)
            elif fetch_format == "xml":
                update_metadata = properties_from_xml(resp.content, update_metadata)
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

        # authenticate
        authenticated_objects = {}
        auth_error_messages = set()
        for idx, pack in enumerate(bucket_names_and_prefixes):
            try:
                bucket_name, prefix = pack
                if bucket_name not in authenticated_objects:
                    # get Prefixes longest common base path
                    common_prefix = ""
                    prefix_split = prefix.split("/")
                    prefixes_in_bucket = len(
                        [p for b, p in bucket_names_and_prefixes if b == bucket_name]
                    )
                    for i in range(1, len(prefix_split)):
                        common_prefix = "/".join(prefix_split[0:i])
                        if (
                            len(
                                [
                                    p
                                    for b, p in bucket_names_and_prefixes
                                    if b == bucket_name and common_prefix in p
                                ]
                            )
                            < prefixes_in_bucket
                        ):
                            common_prefix = "/".join(prefix_split[0 : i - 1])
                            break
                    # connect to aws s3 and get bucket auhenticated objects
                    s3_objects = self.get_authenticated_objects(
                        bucket_name, common_prefix, auth
                    )
                    authenticated_objects[bucket_name] = s3_objects
                else:
                    s3_objects = authenticated_objects[bucket_name]

            except AuthenticationError as e:
                logger.warning("Unexpected error: %s" % e)
                logger.warning("Skipping %s/%s" % (bucket_name, prefix))
                auth_error_messages.add(str(e))
            except ClientError as e:
                err = e.response["Error"]
                auth_messages = [
                    "AccessDenied",
                    "InvalidAccessKeyId",
                    "SignatureDoesNotMatch",
                ]
                if err["Code"] in auth_messages and "key" in err["Message"].lower():
                    raise AuthenticationError(
                        "HTTP error {} returned\n{}: {}\nPlease check your credentials for {}".format(
                            e.response["ResponseMetadata"]["HTTPStatusCode"],
                            err["Code"],
                            err["Message"],
                            self.provider,
                        )
                    )
                logger.warning("Unexpected error: %s" % e)
                logger.warning("Skipping %s/%s" % (bucket_name, prefix))
                auth_error_messages.add(str(e))

        # could not auth on any bucket
        if not authenticated_objects:
            raise AuthenticationError(", ".join(auth_error_messages))

        # downloadable files
        product_chunks = []
        for bucket_name, prefix in bucket_names_and_prefixes:
            # unauthenticated items filtered out
            if bucket_name in authenticated_objects.keys():
                product_chunks.extend(
                    authenticated_objects[bucket_name].filter(Prefix=prefix)
                )

        unique_product_chunks = set(product_chunks)

        total_size = sum([p.size for p in unique_product_chunks])

        # download
        progress_callback.reset(total=total_size)
        try:
            for product_chunk in unique_product_chunks:
                chunk_rel_path = self.get_chunk_dest_path(
                    product,
                    product_chunk,
                    build_safe=build_safe,
                    dir_prefix=prefix,
                )
                chunk_abs_path = os.path.join(product_local_path, chunk_rel_path)
                chunk_abs_path_dir = os.path.dirname(chunk_abs_path)
                if not os.path.isdir(chunk_abs_path_dir):
                    os.makedirs(chunk_abs_path_dir)

                if not os.path.isfile(chunk_abs_path):
                    product_chunk.Bucket().download_file(
                        product_chunk.key,
                        chunk_abs_path,
                        ExtraArgs=getattr(s3_objects, "_params", {}),
                        Callback=progress_callback,
                    )

        except AuthenticationError as e:
            logger.warning("Unexpected error: %s" % e)
            logger.warning("Skipping %s/%s" % (bucket_name, prefix))
        except ClientError as e:
            err = e.response["Error"]
            auth_messages = [
                "AccessDenied",
                "InvalidAccessKeyId",
                "SignatureDoesNotMatch",
            ]
            if err["Code"] in auth_messages and "key" in err["Message"].lower():
                raise AuthenticationError(
                    "HTTP error {} returned\n{}: {}\nPlease check your credentials for {}".format(
                        e.response["ResponseMetadata"]["HTTPStatusCode"],
                        err["Code"],
                        err["Message"],
                        self.provider,
                    )
                )
            logger.warning("Unexpected error: %s" % e)
            logger.warning("Skipping %s/%s" % (bucket_name, prefix))

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

        if build_safe:
            self.check_manifest_file_list(product_local_path)

        # save hash/record file
        with open(record_filename, "w") as fh:
            fh.write(product.remote_location)
        logger.debug("Download recorded in %s", record_filename)

        product.location = path_to_uri(product_local_path)
        return product_local_path

    def get_rio_env(self, bucket_name, prefix, auth_dict):
        """Get rasterio environment variables needed for data access authentication.

        :param bucket_name: bucket containg objects
        :type bucket_name: str
        :param prefix: prefix used to try auth
        :type prefix: str
        :param auth_dict: dictionnary containing authentication keys
        :type auth_dict: dict

        :return: The rasterio environement variables
        :rtype: dict
        """
        if hasattr(self, "s3_session"):
            return {"session": self.s3_session, "requester_pays": True}

        _ = self.get_authenticated_objects(bucket_name, prefix, auth_dict)
        if hasattr(self, "s3_session"):
            return {"session": self.s3_session, "requester_pays": True}
        else:
            return {"aws_unsigned": True}

    def get_authenticated_objects(self, bucket_name, prefix, auth_dict):
        """Get boto3 authenticated objects for the given bucket using
        the most adapted auth strategy.
        Also expose ``s3_session`` as class variable if available.

        :param bucket_name: bucket containg objects
        :type bucket_name: str
        :param prefix: prefix used to filter objects on auth try
                       (not used to filter returned objects)
        :type prefix: str
        :param auth_dict: dictionnary containing authentication keys
        :type auth_dict: dict
        :return: boto3 authenticated objects
        :rtype: :class:`~boto3.resources.collection.s3.Bucket.objectsCollection`
        """
        auth_methods = [
            self._get_authenticated_objects_unsigned,
            self._get_authenticated_objects_from_auth_profile,
            self._get_authenticated_objects_from_auth_keys,
            self._get_authenticated_objects_from_env,
        ]
        # skip _get_authenticated_objects_from_env if credentials were filled in eodag conf
        if auth_dict:
            del auth_methods[-1]

        for try_auth_method in auth_methods:
            try:
                s3_objects = try_auth_method(bucket_name, prefix, auth_dict)
                if s3_objects:
                    logger.debug("Auth using %s succeeded", try_auth_method.__name__)
                    return s3_objects
            except ClientError as e:
                if e.response.get("Error", {}).get("Code", {}) in [
                    "AccessDenied",
                    "InvalidAccessKeyId",
                    "SignatureDoesNotMatch",
                ]:
                    pass
                else:
                    raise e
            except ProfileNotFound:
                pass
            logger.debug("Auth using %s failed", try_auth_method.__name__)

        raise AuthenticationError(
            "Unable do authenticate on s3://%s using any available credendials configuration"
            % bucket_name
        )

    def _get_authenticated_objects_unsigned(self, bucket_name, prefix, auth_dict):
        """Auth strategy using no-sign-request"""

        s3_resource = boto3.resource("s3")
        s3_resource.meta.client.meta.events.register(
            "choose-signer.s3.*", disable_signing
        )
        objects = s3_resource.Bucket(bucket_name).objects
        list(objects.filter(Prefix=prefix).limit(1))
        return objects

    def _get_authenticated_objects_from_auth_profile(
        self, bucket_name, prefix, auth_dict
    ):
        """Auth strategy using RequestPayer=requester and ``aws_profile`` from provided credentials"""

        if "profile_name" in auth_dict.keys():
            s3_session = boto3.session.Session(profile_name=auth_dict["profile_name"])
            s3_resource = s3_session.resource("s3")
            objects = s3_resource.Bucket(bucket_name).objects.filter(
                RequestPayer="requester"
            )
            list(objects.filter(Prefix=prefix).limit(1))
            self.s3_session = s3_session
            return objects
        else:
            return None

    def _get_authenticated_objects_from_auth_keys(self, bucket_name, prefix, auth_dict):
        """Auth strategy using RequestPayer=requester and ``aws_access_key_id``/``aws_secret_access_key``
        from provided credentials"""

        if all(k in auth_dict for k in ("aws_access_key_id", "aws_secret_access_key")):
            s3_session = boto3.session.Session(
                aws_access_key_id=auth_dict["aws_access_key_id"],
                aws_secret_access_key=auth_dict["aws_secret_access_key"],
            )
            s3_resource = s3_session.resource("s3")
            objects = s3_resource.Bucket(bucket_name).objects.filter(
                RequestPayer="requester"
            )
            list(objects.filter(Prefix=prefix).limit(1))
            self.s3_session = s3_session
            return objects
        else:
            return None

    def _get_authenticated_objects_from_env(self, bucket_name, prefix, auth_dict):
        """Auth strategy using RequestPayer=requester and current environment"""

        s3_session = boto3.session.Session()
        s3_resource = s3_session.resource("s3")
        objects = s3_resource.Bucket(bucket_name).objects.filter(
            RequestPayer="requester"
        )
        list(objects.filter(Prefix=prefix).limit(1))
        self.s3_session = s3_session
        return objects

    def get_bucket_name_and_prefix(self, product, url=None):
        """Extract bucket name and prefix from product URL

        :param product: The EO product to download
        :type product: :class:`~eodag.api.product._product.EOProduct`
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

    def check_manifest_file_list(self, product_path):
        """Checks if products listed in manifest.safe exist"""
        manifest_path = [
            os.path.join(d, x)
            for d, _, f in os.walk(product_path)
            for x in f
            if x == "manifest.safe"
        ][0]
        safe_path = os.path.dirname(manifest_path)

        root = etree.parse(os.path.join(safe_path, "manifest.safe")).getroot()
        for safe_file in root.xpath("//fileLocation"):
            safe_file_path = os.path.join(safe_path, safe_file.get("href"))
            if not os.path.isfile(safe_file_path) and "HTML" in safe_file.get("href"):
                # add empty files for missing HTML/*
                Path(safe_file_path).touch()
            elif not os.path.isfile(safe_file_path):
                logger.warning("SAFE build: %s is missing" % safe_file.get("href"))

    def finalize_s2_safe_product(self, product_path):
        """Add missing dirs to downloaded product"""
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

            # datastrip scene dirname
            scene_id = os.path.basename(
                os.path.dirname(
                    root.xpath("//fileLocation[contains(@href,'MTD_DS.xml')]")[0].get(
                        "href"
                    )
                )
            )
            datastrip_folder = os.path.join(safe_path, "DATASTRIP/0")
            if os.path.isdir(datastrip_folder):
                os.rename(
                    os.path.join(safe_path, "DATASTRIP/0"),
                    os.path.join(safe_path, "DATASTRIP", scene_id),
                )
        except Exception as e:
            logger.exception("Could not finalize SAFE product from downloaded data")
            raise DownloadError(e)

    def get_chunk_dest_path(self, product, chunk, dir_prefix, build_safe=False):
        """Get chunk destination path"""
        if build_safe:
            # S2 common
            if "S2_MSI" in product.product_type:
                title_search = re.search(
                    r"^\w+_\w+_(\w+)_(\w+)_(\w+)_(\w+)_(\w+)$",
                    product.properties["title"],
                )
                title_date1 = title_search.group(1) if title_search else None
                title_part3 = title_search.group(4) if title_search else None
                ds_dir_search = re.search(
                    r"^.+_(DS_\w+_+\w+_\w+)_\w+.\w+$",
                    product.properties.get("originalSceneID", ""),
                )
                ds_dir = ds_dir_search.group(1) if ds_dir_search else 0
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
                product_path = (
                    "%s.SAFE/GRANULE/%s/IMG_DATA/R%s/T%s%s%s_%s_%s_%s.jp2"
                    % (
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
                )
            elif S2L2A_TILE_AUX_DIR_REGEX.match(chunk.key):
                found_dict = S2L2A_TILE_AUX_DIR_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/GRANULE/%s/AUX_DATA/%s" % (
                    product.properties["title"],
                    found_dict["num"],
                    found_dict["file"],
                )
            # S2 L2A QI Masks
            elif S2_TILE_QI_MSK_REGEX.match(chunk.key):
                found_dict = S2_TILE_QI_MSK_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/GRANULE/%s/QI_DATA/MSK_%sPRB_%s" % (
                    product.properties["title"],
                    found_dict["num"],
                    found_dict["file_base"],
                    found_dict["file_suffix"],
                )
            # S2 L2A QI PVI
            elif S2_TILE_QI_PVI_REGEX.match(chunk.key):
                found_dict = S2_TILE_QI_PVI_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/GRANULE/%s/QI_DATA/%s_%s_PVI.jp2" % (
                    product.properties["title"],
                    found_dict["num"],
                    title_part3,
                    title_date1,
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
            elif S2_PROD_DS_QI_REPORT_REGEX.match(chunk.key):
                found_dict = S2_PROD_DS_QI_REPORT_REGEX.match(chunk.key).groupdict()
                product_path = "%s.SAFE/DATASTRIP/%s/QI_DATA/%s.xml" % (
                    product.properties["title"],
                    ds_dir,
                    found_dict["filename"],
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
        return super(AwsDownload, self).download_all(
            products, auth=auth, progress_callback=progress_callback, **kwargs
        )
