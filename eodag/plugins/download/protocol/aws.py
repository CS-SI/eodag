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
import re
import shutil
import urllib
from typing import TYPE_CHECKING, Any, Optional, Union, cast

import boto3
import requests
from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ClientError
from lxml import etree
from mypy_boto3_s3 import S3ServiceResource

from eodag.api.product.metadata_mapping import (
    mtd_cfg_as_conversion_and_querypath,
    properties_from_json,
    properties_from_xml,
)
from eodag.utils import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    HTTP_REQ_TIMEOUT,
    USER_AGENT,
    Mime,
    Processor,
    ProgressCallback,
    flatten_top_directories,
    format_string,
    rename_subfolder,
)
from eodag.utils.exceptions import (
    DownloadError,
    MisconfiguredError,
    NotAvailableError,
    TimeOutError,
)

from ..contentiterator import FileContentIterator, S3ObjectContentIterator
from ..streamresponse import StreamResponse
from ._aws_consts import (
    S1_ANNOT_REGEX,
    S1_CALIB_REGEX,
    S1_IMG_NB_PER_POLAR,
    S1_MEAS_REGEX,
    S1_REGEX,
    S1_REPORT_REGEX,
    S2_PROD_DS_MTD_REGEX,
    S2_PROD_DS_QI_REGEX,
    S2_PROD_DS_QI_REPORT_REGEX,
    S2_PROD_INSPIRE_REGEX,
    S2_PROD_MTD_REGEX,
    S2_PROD_REGEX,
    S2_TILE_AUX_DIR_REGEX,
    S2_TILE_IMG_REGEX,
    S2_TILE_MTD_REGEX,
    S2_TILE_PREVIEW_DIR_REGEX,
    S2_TILE_QI_DIR_REGEX,
    S2_TILE_QI_MSK_REGEX,
    S2_TILE_QI_PVI_REGEX,
    S2_TILE_REGEX,
    S2_TILE_THUMBNAIL_REGEX,
    S2L2A_TILE_AUX_DIR_REGEX,
    S2L2A_TILE_IMG_REGEX,
)
from .base import Download

if TYPE_CHECKING:
    from eodag.api.product import Asset
    from eodag.config import PluginConfig
    from eodag.types.download_args import DownloadConf
    from eodag.utils import Unpack

logger = logging.getLogger("eodag.download.aws")


class AwsDownload(Download):
    """AWS plugin. Handles asset download on AWS using S3 protocol"""

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(AwsDownload, self).__init__(provider, config)

    def download(  # type: ignore
        self,
        asset: Asset,
        auth: Optional[S3ServiceResource] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        no_cache: bool = False,
        stream: bool = False,
        **kwargs: Unpack[DownloadConf],
    ) -> Union[Optional[str], StreamResponse]:
        """Inherits from .base:download"""

        # Force create progress_callback
        if not isinstance(progress_callback, ProgressCallback):
            logger.info("Progress bar unavailable")
            progress_callback = ProgressCallback(disable=True)
        progress_callback = cast(ProgressCallback, progress_callback)

        # Check authenticator and auth
        downloader, authenticator = asset.get_downloader_and_auth()

        # Check if auth is a S3 resource by verifying it has the meta.client attribute.
        if not (
            auth is not None and hasattr(auth, "meta") and hasattr(auth.meta, "client")
        ):
            auth = boto3.resource(
                service_name="s3",
                endpoint_url=getattr(self.config, "s3_endpoint", None),
            )

        # Expect instanceof boto3.resources.factory.s3.ServiceResource
        # but boto3.resources.factory is a lazy loader, boto3.resources.factory.s3.ServiceResource is not loaded
        if auth.__class__.__name__ != "s3.ServiceResource":
            raise MisconfiguredError(
                "Authentication plugin (AwsAuth) have to serve s3.ServiceResource object"
            )
        cast(S3ServiceResource, auth)

        # Get asset statements
        statements = self.get_statements(asset, **kwargs)

        # Already downloaded ? (cache)
        if not no_cache:
            cache = self.get_cache(asset, statements, stream)
            if cache is not None:
                progress_callback.reset()
                return cache

        # Build safe preparation
        self._update_product_metadata(asset)

        # List [Bucket / Key] endpoints from asset
        paths: list[dict[str, str]] = self._get_s3_paths(
            asset, auth, authenticator.config
        )
        logger.debug("Asset {} s3 resolve {} paths".format(asset.key, len(paths)))

        shared: dict[str, Any] = {}
        if len(paths) == 0:
            # Nothing matching
            if not stream:
                return None
            else:
                raise NotAvailableError("No file asset found")

        elif len(paths) == 1:

            # One file: direct serve
            local_path = statements["local_path"]
            if os.path.isfile(local_path):
                os.remove(local_path)

            # Stream object
            s3 = authenticator.get_s3_client()
            max_workers = getattr(self.config, "max_workers", os.cpu_count())

            # Use processor to manage concurrency of call instead of:
            _ = """
            obj: dict = s3.get_object(Bucket=paths[0]["bucket"], Key=paths[0]["key"])  # type: ignore
            """
            shared = {"obj": None, "error": None}

            def get_object_callback(obj: dict, error: Exception):
                shared["obj"] = obj  # type: ignore
                if error is not None:
                    shared["error"] = error  # type: ignore
                    Processor.stop()  # type: ignore

            taskid = Processor.queue(
                s3.get_object,
                Bucket=paths[0]["bucket"],
                Key=paths[0]["key"],
                q_timeout=int(timeout * 60),
                q_parallelize=max_workers,
                q_callback=get_object_callback,
            )
            Processor.wait(taskid)

            if shared["error"] is not None:
                raise shared["error"]
            if shared["obj"] is None:
                raise DownloadError("Download fails")
            obj = shared["obj"]

            # Update asset from s3 object and prepare serve
            self.asset_metadata_from_s3object(asset, obj)
            s3ci = S3ObjectContentIterator(obj, progress_callback)

            if not stream:

                # Conflict with previous cache
                if os.path.isdir(local_path):
                    shutil.rmtree(local_path)

                # Stream stream into local file
                with open(local_path, "wb") as fd:
                    for chunk in s3ci:
                        fd.write(chunk)

                # File has no extension ?
                filename = os.path.basename(local_path)
                pos = filename.rfind(".")
                if pos < 0:
                    ext = Mime.guess_extension_from_fileheaders(local_path)
                    if ext is not None:
                        new_file_path = "{}.{}".format(local_path, ext)
                        os.rename(local_path, new_file_path)
                        local_path = new_file_path

                # Post process archive
                local_path = self.unpack_archive(
                    asset, local_path, progress_callback, **kwargs
                )
                self._post_process_archive(asset, local_path)
                self.asset_metadata_from_file(asset, local_path)

                # Update cache location
                statements["local_path"] = local_path
                statements["href"] = asset.get("href")
                self.set_statements(asset, statements, **kwargs)

                logger.debug("Download results served as file {}".format(local_path))
                return local_path

            else:

                # if allow cache, intercept served chunks to generate local cache
                if not no_cache:

                    # During stream service, intercept chunks to save a cache
                    passthrough_data = {
                        "fp": open(local_path, "wb"),
                        "asset": asset,
                        "local_path": local_path,
                        "progress_callback": progress_callback,
                        "statements": statements,
                        "kwargs": kwargs,
                    }

                    # Trigger when stream succedfully finished
                    def on_complete():
                        passthrough_data["fp"].close()
                        # Post process archive
                        local_path = self.unpack_archive(
                            passthrough_data["asset"],
                            passthrough_data["local_path"],
                            passthrough_data["progress_callback"],
                            **passthrough_data["kwargs"],
                        )

                        # File has no extension ?
                        filename = os.path.basename(local_path)
                        pos = filename.rfind(".")
                        if pos < 0:
                            ext = Mime.guess_extension_from_fileheaders(local_path)
                            if ext is not None:
                                new_file_path = "{}.{}".format(local_path, ext)
                                os.rename(local_path, new_file_path)
                                local_path = new_file_path

                        # Update cache location
                        logger.debug(
                            "Download stream complete, save cache at: {}".format(
                                local_path
                            )
                        )
                        passthrough_data["statements"]["local_path"] = local_path
                        passthrough_data["statements"]["href"] = passthrough_data[
                            "asset"
                        ].get("href")
                        self.set_statements(
                            passthrough_data["asset"],
                            passthrough_data["statements"],
                            **kwargs,
                        )

                    s3ci.on("complete", on_complete)

                    # Trigger when stream chunk is transfered
                    def on_chunk(chunk: bytes):
                        passthrough_data["fp"].write(chunk)

                    s3ci.on("chunk", on_chunk)

                    # Trigger when stream transfer fails
                    def on_error(error: Exception):
                        logger.debug("Download stream error: {}".format(str(error)))
                        passthrough_data["fp"].close()
                        os.remove(passthrough_data["local_path"])

                    s3ci.on("error", on_error)

                logger.debug("Download results served as stream")
                return StreamResponse(
                    content=s3ci,
                    filename=asset.filename,
                    size=asset.size,
                    headers={
                        "Content-Length": str(asset.size),
                        "Content-Type": asset.get("type", Mime.DEFAULT),
                    },
                    media_type=asset.get("type", Mime.DEFAULT),
                    status_code=200,
                    arcname=None,
                )

        else:

            # Many files, have to download and pack in archive
            local_path = statements["local_path"]
            if os.path.isdir(local_path):
                # Remove previous download
                shutil.rmtree(local_path)

            # Prepare destination directories
            if not os.path.isdir(local_path):
                os.makedirs(local_path)
            for i in range(0, len(paths)):
                paths[i]["path"] = os.path.join(
                    local_path, paths[i]["rel_path"].replace("/\\", os.path.sep)
                )
                dir_path = os.path.dirname(paths[i]["path"])
                if not os.path.isdir(dir_path):
                    os.makedirs(dir_path)

            # Download all files (parallelized)
            progress_callback.reset(total=len(paths))
            max_workers = getattr(self.config, "max_workers", os.cpu_count())

            passthrough_data = {
                "error": None,
                "progress_callback": progress_callback,
            }

            def callback(
                _, error, bucket: Optional[str] = None, key: Optional[str] = None
            ):
                # interrupt parallelized download on error
                if error is not None:
                    error_message = "AWS error on {}:{} : {}".format(
                        bucket, key, str(error)
                    )
                    if isinstance(error, ClientError):
                        error_code = error.response["Error"]["Code"]
                        error_message = ""
                        if error_code == "404":
                            error_message = "Object {}:{} not found".format(bucket, key)
                        elif error_code == "AccessDenied":
                            error_message = "Access denied on {}:{}".format(bucket, key)
                    elif isinstance(error, TimeoutError):
                        error_message = "Object {}:{} download timeout".format(
                            bucket, key
                        )
                    # An error will interrupt paralellized download
                    passthrough_data["error"] = DownloadError(error_message)  # type: ignore
                    Processor.stop()  # type: ignore

                passthrough_data["progress_callback"](1)  # type: ignore

            logger.debug(
                "Download paralellized (files: {}, workers: {})".format(
                    len(paths), max_workers
                )
            )
            ids: list = []
            for i in range(0, len(paths)):

                # Exclude directories
                if not paths[i]["path"].endswith("/"):
                    dir_path = os.path.dirname(paths[i]["path"]).rstrip("/\\")
                    if not os.path.isdir(dir_path):
                        os.makedirs(dir_path)

                    taskid = Processor.queue(
                        auth.Bucket(paths[i]["bucket"]).download_file,  # type: ignore
                        Key=paths[i]["key"],
                        Filename=paths[i]["path"],
                        ExtraArgs={},
                        Config=TransferConfig(use_threads=False),
                        q_timeout=int(timeout * 60),
                        q_parallelize=max_workers,
                        q_callback=callback,
                        q_callback_kwargs={
                            "bucket": paths[i]["bucket"],
                            "key": paths[i]["key"],
                        },
                    )
                    ids.append(taskid)
            # Wait for my own task
            Processor.wait(ids)

            if passthrough_data["error"] is not None:
                raise passthrough_data["error"]  # type: ignore

            self._post_process_archive(asset, local_path)

            # Save statements
            statements["local_path"] = local_path
            statements["href"] = asset.get("href")
            self.set_statements(asset, statements, **kwargs)

            if not stream:
                self.asset_metadata_from_file(asset, local_path)
                return local_path
            else:

                # Pack directory to archive before return it's stream
                shared = {"remove_file": False, "file_path": local_path}
                if os.path.isdir(shared["file_path"]):
                    shared["file_path"] = self.pack_archive(asset, shared["file_path"])
                    # Archive is temporary generated
                    shared["remove_file"] = True

                fci = FileContentIterator(shared["file_path"])

                # Trigger when stream finished, remove archived results
                def post_download(error: Optional[Exception] = None):
                    if shared["remove_file"] and os.path.isfile(shared["file_path"]):
                        os.remove(shared["file_path"])

                fci.on("complete", post_download)
                fci.on("error", post_download)

                return StreamResponse(
                    content=fci,
                    filename=asset.filename,
                    size=asset.size,
                    headers={
                        "Content-Length": str(asset.size),
                        "Content-Type": asset.get("type", Mime.DEFAULT),
                    },
                    media_type=asset.get("type", Mime.DEFAULT),
                    status_code=200,
                    arcname=None,
                )

    def _update_product_metadata(self, asset: Asset):
        """Triggers when configuration describe an external metadata
        used by build_safe. So, download it and integrate new data to prepare
        path mapping required by build_safe mode
        """
        # configuration download.products only concerns asset download_link
        if asset.key == "download_link":

            collection_config: dict = getattr(self.config, "products", {}).get(
                asset.product.collection, {}
            )
            build_safe = collection_config.get("build_safe", False)
            fetch_metadata = collection_config.get("fetch_metadata", None)

            if build_safe and fetch_metadata is not None:

                # Pull external metadata given by provider
                ssl_verify = getattr(self.config, "ssl_verify", True)
                timeout = getattr(self.config, "timeout", HTTP_REQ_TIMEOUT)
                fetch_format = fetch_metadata.get("fetch_format")
                update_metadata = fetch_metadata.get("update_metadata")
                fetch_url = fetch_metadata.get("fetch_url")
                if fetch_url is not None:
                    fetch_url = format_string(None, fetch_url, **asset.as_dict())
                    logger.info("Fetching extra metadata from %s" % fetch_url)
                    try:
                        resp = requests.get(
                            fetch_url,
                            headers=USER_AGENT,
                            timeout=timeout,
                            verify=ssl_verify,
                        )
                    except requests.exceptions.Timeout as exc:
                        raise TimeOutError(exc, timeout=timeout) from exc
                    update_metadata = mtd_cfg_as_conversion_and_querypath(
                        update_metadata
                    )
                    if fetch_format == "json":
                        json_resp = resp.json()
                        update_metadata = properties_from_json(
                            json_resp, update_metadata
                        )
                    elif fetch_format == "xml":
                        update_metadata = properties_from_xml(
                            resp.content, update_metadata
                        )
                    else:
                        logger.warning(
                            "SAFE metadata fetch format %s not implemented"
                            % fetch_format
                        )
                        update_metadata = None

                # metadata mapping update product
                for key in update_metadata:
                    asset[key] = update_metadata[key]

    def _get_s3_paths(
        self,
        asset: Asset,
        auth: S3ServiceResource,
        config: Optional[PluginConfig] = None,
    ) -> list[dict[str, str]]:
        """Gather all s3 path matching with current asset
        and map corresponding output path
        """

        def get_bucket_prefix_from_url(url: str):
            if url == "":
                return []
            results = []
            bucket_path_level = getattr(self.config, "bucket_path_level", None)
            bucket, prefix = None, None
            parse_result = urllib.parse.urlsplit(url)
            scheme: str = parse_result.scheme
            netloc: str = parse_result.netloc
            path: str = parse_result.path
            subdomain = netloc.split(".")[0]
            path = path.strip("/")
            if (
                "/" in path
                and scheme
                and subdomain == "s3"
                and bucket_path_level is None
            ):
                bucket, prefix = path.split("/", 1)
            elif scheme and bucket_path_level is None:
                bucket = subdomain
                prefix = path
            elif not scheme and bucket_path_level is None:
                prefix = path
            elif bucket_path_level is not None:
                parts = path.split("/")
                bucket, prefix = (
                    parts[bucket_path_level],
                    "/".join(parts[(bucket_path_level + 1) :]),
                )
            if bucket is None or bucket == "":
                bucket = (
                    getattr(self.config, "products", {})
                    .get(asset.product.collection, {})
                    .get("default_bucket", "")
                )
            if prefix is not None:
                results.append({"bucket": bucket, "prefix": prefix})
            return results

        sources = get_bucket_prefix_from_url(asset.get("href", ""))

        collection_config: dict = getattr(self.config, "products", {}).get(
            asset.product.collection, {}
        )
        for url in collection_config.get("complementary_url_key", []):
            url = format_string(None, url, **asset.product.properties)
            sources += get_bucket_prefix_from_url(url)

        # Scan all sources
        paths = []
        for source in sources:
            objects = auth.Bucket(source["bucket"]).objects  # type: ignore
            filters: dict[str, str] = {"Prefix": source["prefix"]}
            if config is not None and config.requester_pays:
                filters["RequestPayer"] = "requester"
            results = list(objects.filter(**filters))  # type: ignore
            for result in results:
                rel_path = result.key[len(source["prefix"]) :].lstrip("/")
                # Build safe can have special rel_path mapping
                paths.append(
                    {
                        "bucket": result.bucket_name,
                        "key": result.key,
                        "rel_path": self._path_mapping(asset, result.key, rel_path),
                    }
                )

        return paths

    def _path_mapping(
        self,
        asset: Asset,
        s3_key: str,
        rel_path: str,
    ) -> str:
        """Path path mapping from remote location to local location considering build safe"""

        collection = getattr(asset.product, "collection")
        if collection is None:
            return rel_path
        cast(str, collection)

        collection_config: dict = getattr(self.config, "products", {}).get(
            collection, {}
        )
        build_safe = collection_config.get("build_safe", False)
        if not build_safe:
            return rel_path

        # Extract parmeters from product properties and asset values
        parameters: dict[str, Any] = {}
        for key in asset.product.properties:
            parameters[key] = asset.product.properties[key]
        for key in asset.as_dict():
            parameters[key] = asset.get(key)

        """Get SAFE destination path"""
        title_date1: Optional[str] = None
        title_part3: Optional[str] = None
        ds_dir: Any = 0
        s2_processing_level: str = ""
        s1_title_suffix: Optional[str] = None

        # S2 common
        if "S2_MSI" in collection:
            title_search: Optional[re.Match[str]] = re.search(
                r"^\w+_\w+_(\w+)_(\w+)_(\w+)_(\w+)_(\w+)$",
                parameters.get("title", ""),
            )
            title_date1 = title_search.group(1) if title_search else None
            title_part3 = title_search.group(4) if title_search else None
            ds_dir_search = re.search(
                r"^.+_(DS_\w+_+\w+_\w+)_\w+.\w+$",
                parameters.get("originalSceneID", ""),
            )
            ds_dir = ds_dir_search.group(1) if ds_dir_search else 0
            s2_processing_level = collection.split("_")[-1]
        # S1 common
        elif collection == "S1_SAR_GRD":
            s1_title_suffix_search = re.search(
                r"^.+_([A-Z0-9_]+_[A-Z0-9_]+_[A-Z0-9_]+_[A-Z0-9_]+)_\w+$",
                parameters.get("title", ""),
            )
            s1_title_suffix = (
                s1_title_suffix_search.group(1).lower().replace("_", "-")
                if s1_title_suffix_search
                else None
            )

        # S1 polarization mode
        if product_title := parameters.get("title", ""):
            polarization_mode = re.sub(r".{14}([A-Z]{2}).*", r"\1", product_title)
        else:
            polarization_mode = None

        # S2 L2A Tile files -----------------------------------------------
        if matched := S2L2A_TILE_IMG_REGEX.match(s3_key):
            found_dict = matched.groupdict()
            product_path = "GRANULE/%s/IMG_DATA/R%s/T%s%s%s_%s_%s_%s.jp2" % (
                found_dict["num"],
                found_dict["res"],
                found_dict["tile1"],
                found_dict["tile2"],
                found_dict["tile3"],
                title_date1,
                found_dict["file"],
                found_dict["res"],
            )
        elif matched := S2L2A_TILE_AUX_DIR_REGEX.match(s3_key):
            found_dict = matched.groupdict()
            product_path = "GRANULE/%s/AUX_DATA/%s" % (
                found_dict["num"],
                found_dict["file"],
            )
        # S2 L2A QI Masks
        elif matched := S2_TILE_QI_MSK_REGEX.match(s3_key):
            found_dict = matched.groupdict()
            product_path = "GRANULE/%s/QI_DATA/MSK_%sPRB_%s" % (
                found_dict["num"],
                found_dict["file_base"],
                found_dict["file_suffix"],
            )
        # S2 L2A QI PVI
        elif matched := S2_TILE_QI_PVI_REGEX.match(s3_key):
            found_dict = matched.groupdict()
            product_path = "GRANULE/%s/QI_DATA/%s_%s_PVI.jp2" % (
                found_dict["num"],
                title_part3,
                title_date1,
            )
        # S2 Tile files ---------------------------------------------------
        elif matched := S2_TILE_PREVIEW_DIR_REGEX.match(s3_key):
            found_dict = matched.groupdict()
            product_path = "GRANULE/%s/preview/%s" % (
                found_dict["num"],
                found_dict["file"],
            )
        elif matched := S2_TILE_IMG_REGEX.match(s3_key):
            found_dict = matched.groupdict()
            product_path = "GRANULE/%s/IMG_DATA/T%s%s%s_%s_%s" % (
                found_dict["num"],
                found_dict["tile1"],
                found_dict["tile2"],
                found_dict["tile3"],
                title_date1,
                found_dict["file"],
            )
        elif matched := S2_TILE_THUMBNAIL_REGEX.match(s3_key):
            found_dict = matched.groupdict()
            product_path = "GRANULE/%s/%s" % (
                found_dict["num"],
                found_dict["file"],
            )
        elif matched := S2_TILE_MTD_REGEX.match(s3_key):
            found_dict = matched.groupdict()
            product_path = "GRANULE/%s/MTD_TL.xml" % found_dict["num"]
        elif matched := S2_TILE_AUX_DIR_REGEX.match(s3_key):
            found_dict = matched.groupdict()
            product_path = "GRANULE/%s/AUX_DATA/AUX_%s" % (
                found_dict["num"],
                found_dict["file"],
            )
        elif matched := S2_TILE_QI_DIR_REGEX.match(s3_key):
            found_dict = matched.groupdict()
            product_path = "GRANULE/%s/QI_DATA/%s" % (
                found_dict["num"],
                found_dict["file"],
            )
        # S2 Tiles generic
        elif matched := S2_TILE_REGEX.match(s3_key):
            found_dict = matched.groupdict()
            product_path = "GRANULE/%s/%s" % (
                found_dict["num"],
                found_dict["file"],
            )
        # S2 Product files
        elif matched := S2_PROD_DS_MTD_REGEX.match(s3_key):
            found_dict = matched.groupdict()
            product_path = "DATASTRIP/%s/MTD_DS.xml" % ds_dir
        elif matched := S2_PROD_DS_QI_REPORT_REGEX.match(s3_key):
            found_dict = matched.groupdict()
            product_path = "DATASTRIP/%s/QI_DATA/%s.xml" % (
                ds_dir,
                found_dict["filename"],
            )
        elif matched := S2_PROD_DS_QI_REGEX.match(s3_key):
            found_dict = matched.groupdict()
            product_path = "DATASTRIP/%s/QI_DATA/%s" % (
                ds_dir,
                found_dict["file"],
            )
        elif matched := S2_PROD_INSPIRE_REGEX.match(s3_key):
            found_dict = matched.groupdict()
            product_path = "INSPIRE.xml"
        elif matched := S2_PROD_MTD_REGEX.match(s3_key):
            found_dict = matched.groupdict()
            product_path = "MTD_MSI%s.xml" % s2_processing_level
        # S2 Product generic
        elif matched := S2_PROD_REGEX.match(s3_key):
            found_dict = matched.groupdict()
            product_path = "%s" % found_dict["file"]
        # S1 --------------------------------------------------------------
        elif (
            matched := S1_CALIB_REGEX.match(s3_key)
        ) and polarization_mode is not None:
            found_dict = matched.groupdict()
            product_path = "annotation/calibration/%s-%s-%s-grd-%s-%s-%03d.xml" % (
                found_dict["file_prefix"],
                parameters.get("platform", "").lower(),
                found_dict["file_beam"],
                found_dict["file_pol"],
                s1_title_suffix,
                S1_IMG_NB_PER_POLAR.get(polarization_mode, {}).get(
                    found_dict["file_pol"].upper(), 1
                ),
            )
        elif (
            matched := S1_ANNOT_REGEX.match(s3_key)
        ) and polarization_mode is not None:
            found_dict = matched.groupdict()
            product_path = "annotation/%s-%s-grd-%s-%s-%03d.xml" % (
                parameters.get("platform", "").lower(),
                found_dict["file_beam"],
                found_dict["file_pol"],
                s1_title_suffix,
                S1_IMG_NB_PER_POLAR.get(polarization_mode, {}).get(
                    found_dict["file_pol"].upper(), 1
                ),
            )
        elif (matched := S1_MEAS_REGEX.match(s3_key)) and polarization_mode is not None:
            found_dict = matched.groupdict()
            product_path = "measurement/%s-%s-grd-%s-%s-%03d.%s" % (
                parameters.get("platform", "").lower(),
                found_dict["file_beam"],
                found_dict["file_pol"],
                s1_title_suffix,
                S1_IMG_NB_PER_POLAR.get(polarization_mode, {}).get(
                    found_dict["file_pol"].upper(), 1
                ),
                found_dict["file_ext"],
            )
        elif matched := S1_REPORT_REGEX.match(s3_key):
            found_dict = matched.groupdict()
            product_path = "%s.SAFE-%s" % (
                parameters.get("title", ""),
                found_dict["file"],
            )
        # S1 generic
        elif matched := S1_REGEX.match(s3_key):
            found_dict = matched.groupdict()
            product_path = "%s" % found_dict["file"]
        # out of SAFE format
        else:
            logger.warning(f"Ignored {s3_key} out of SAFE matching pattern")

        logger.debug(f"Map s3_key {s3_key} to rel_path {product_path}")
        return product_path

    def _post_process_archive(self, asset: Asset, local_path: str):
        if os.path.isdir(local_path):
            collection_config: dict = getattr(self.config, "products", {}).get(
                asset.product.collection, {}
            )
            build_safe = collection_config.get("build_safe", False)
            flatten_top_dirs = collection_config.get(
                "flatten_top_dirs", getattr(self.config, "flatten_top_dirs", False)
            )
            collection = getattr(asset.product, "collection")
            if build_safe and collection is not None and "S2_MSI" in collection:
                self._finalize_s2_safe_product(local_path)
            elif flatten_top_dirs:
                flatten_top_directories(local_path)
            if build_safe:
                self._check_manifest_file_list(local_path)

    def _finalize_s2_safe_product(self, asset_path: str) -> None:
        """Add missing dirs to downloaded product"""
        try:
            logger.debug("Finalize SAFE product")
            manifest_path_list = [
                os.path.join(d, x)
                for d, _, f in os.walk(asset_path)
                for x in f
                if x == "manifest.safe"
            ]
            if len(manifest_path_list) == 0:
                raise FileNotFoundError(
                    f"No manifest.safe could be found in {asset_path}"
                )
            else:
                safe_path = os.path.dirname(manifest_path_list[0])

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
            nodes = root.xpath("//fileLocation[contains(@href,'MTD_TL.xml')]")
            tile_id = None
            if len(nodes) > 0:
                path = nodes[0].get("href")
                tile_id = cast(str, os.path.basename(os.path.dirname(path)))

            granule_folder = os.path.join(safe_path, "GRANULE")
            if os.path.isdir(granule_folder) and tile_id is not None:
                rename_subfolder(granule_folder, tile_id)

            # datastrip scene dirname
            nodes = root.xpath("//fileLocation[contains(@href,'MTD_DS.xml')]")
            scene_id = None
            if len(nodes) > 0:
                path = nodes[0].get("href")
                scene_id = cast(str, os.path.basename(os.path.dirname(path)))

            datastrip_folder = os.path.join(safe_path, "DATASTRIP")
            if os.path.isdir(datastrip_folder) and scene_id is not None:
                rename_subfolder(datastrip_folder, scene_id)

        except Exception as e:
            logger.exception("Could not finalize SAFE product from downloaded data")
            raise DownloadError(e)

    def _check_manifest_file_list(self, asset_path: str) -> None:

        """Checks if products listed in manifest.safe exist"""
        manifest_path_list = [
            os.path.join(d, x)
            for d, _, f in os.walk(asset_path)
            for x in f
            if x == "manifest.safe"
        ]

        if len(manifest_path_list) == 0:
            raise FileNotFoundError(f"No manifest.safe could be found in {asset_path}")
        else:
            safe_path = os.path.dirname(manifest_path_list[0])

        root = etree.parse(os.path.join(safe_path, "manifest.safe")).getroot()

        # Extract files
        files: list[dict[str, str]] = []
        for dataobject in root.xpath("//dataObjectSection/dataObject"):
            files.append(
                {
                    "id": dataobject.attrib["ID"],
                    "mimetype": dataobject.find("./byteStream").attrib["mimeType"],
                    "size": dataobject.find("./byteStream").attrib["size"],
                    "path": dataobject.find("./byteStream/fileLocation")
                    .attrib["href"]
                    .lstrip("./"),
                }
            )

        for file in files:
            full_path = os.path.normpath(
                os.path.join(asset_path, safe_path, file["path"])
            )
            if not os.path.isfile(full_path):
                if "HTML" in file["path"]:
                    dir = os.path.dirname(full_path)
                    if not os.path.isdir(dir):
                        os.makedirs(dir)
                    # add empty files for missing HTML/*
                    open(full_path, "w+").close()
                else:
                    logger.warning("SAFE build: {} is missing".format(file["path"]))

        logger.debug("SAFE build: complete")


__all__ = ["AwsDownload"]
