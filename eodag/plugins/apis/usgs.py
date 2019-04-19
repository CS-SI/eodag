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
import re
import zipfile

import requests
from requests import HTTPError
from shapely import geometry
from tqdm import tqdm
from usgs import USGSError, api

from eodag.api.product import EOProduct
from eodag.api.product.metadata_mapping import properties_from_json
from eodag.plugins.apis.base import Api

logger = logging.getLogger("eodag.plugins.apis.usgs")


class UsgsApi(Api):
    """A plugin that enables to query and download data on the USGS catalogues"""

    def query(self, product_type=None, **kwargs):
        """Search for data on USGS catalogues

        .. versionchanged::
            1.0

                * ``product_type`` is no longer mandatory
        """
        product_type = kwargs.get("productType")
        if product_type is None:
            return [], 0
        api.login(
            self.config.credentials["username"],
            self.config.credentials["password"],
            save=True,
        )
        usgs_dataset = self.config.products[product_type]["dataset"]
        usgs_catalog_node = self.config.products[product_type]["catalog_node"]
        start_date = kwargs.pop("startTimeFromAscendingNode", None)
        end_date = kwargs.pop("completionTimeFromAscendingNode", None)
        footprint = kwargs.pop("geometry", None)

        # Configuration to generate the download url of search results
        result_summary_pattern = re.compile(
            r"^Entity ID: .+, Acquisition Date: .+, Path: (?P<path>\d+), Row: (?P<row>\d+)$"  # noqa
        )
        # See https://pyformat.info/, on section "Padding and aligning strings" to
        # understand {path:0>3} and {row:0>3}.
        # It roughly means: 'if the string that will be passed as "path" has length < 3,
        # prepend as much "0"s as needed to reach length 3' and same for "row"
        dl_url_pattern = "{base_url}/L8/{path:0>3}/{row:0>3}/{entity}.tar.bz"

        final = []
        if footprint and len(footprint.keys()) == 4:  # a rectangle (or bbox)
            lower_left = {
                "longitude": footprint["lonmin"],
                "latitude": footprint["latmin"],
            }
            upper_right = {
                "longitude": footprint["lonmax"],
                "latitude": footprint["latmax"],
            }
        else:
            lower_left, upper_right = None, None
        try:
            results = api.search(
                usgs_dataset,
                usgs_catalog_node,
                start_date=start_date,
                end_date=end_date,
                ll=lower_left,
                ur=upper_right,
            )

            for result in results["data"]["results"]:
                r_lower_left = result["lowerLeftCoordinate"]
                r_upper_right = result["upperRightCoordinate"]
                summary_match = result_summary_pattern.match(
                    result["summary"]
                ).groupdict()
                result["geometry"] = geometry.box(
                    r_lower_left["longitude"],
                    r_lower_left["latitude"],
                    r_upper_right["longitude"],
                    r_upper_right["latitude"],
                )
                result["productType"] = usgs_dataset
                final.append(
                    EOProduct(
                        product_type,
                        self.provider,
                        dl_url_pattern.format(base_url="file://")
                        if self.config.product_location_scheme == "file"
                        else dl_url_pattern.format(
                            base_url=self.config.google_base_url.rstrip("/"),
                            entity=result["entityId"],
                            **summary_match
                        ),
                        properties_from_json(result, self.config.metadata_mapping),
                        searched_bbox=footprint,
                    )
                )
        except USGSError as e:
            logger.debug(
                "Product type %s does not exist on catalogue %s",
                usgs_dataset,
                usgs_catalog_node,
            )
            logger.debug("Skipping error: %s", e)
        api.logout()
        return final, len(final)

    def download(self, product, auth=None, progress_callback=None):
        """Download data from USGS catalogues"""
        url = product.remote_location
        if not url:
            logger.debug(
                "Unable to get download url for %s, skipping download", product
            )
            return
        logger.info("Download url: %s", url)

        filename = product.properties["title"] + ".tar.bz"
        local_file_path = os.path.join(self.config.outputs_prefix, filename)
        download_records = os.path.join(self.config.outputs_prefix, ".downloaded")
        if not os.path.exists(download_records):
            os.makedirs(download_records)
        url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
        record_filename = os.path.join(download_records, url_hash)
        if os.path.isfile(record_filename) and os.path.isfile(local_file_path):
            logger.info(
                "Product already downloaded. Retrieve it at %s", local_file_path
            )
            return local_file_path
        # Remove the record file if local_file_path is absent (e.g. it was deleted
        # while record wasn't)
        elif os.path.isfile(record_filename):
            logger.debug(
                "Record file found (%s) but not the actual file", record_filename
            )
            logger.debug("Removing record file : %s", record_filename)
            os.remove(record_filename)

        with requests.get(
            url,
            stream=True,
            auth=auth,
            params=getattr(self.config, "dl_url_params", {}),
            verify=False,
            hooks={"response": lambda r, *args, **kwargs: print("\n", r.url)},
        ) as stream:
            stream_size = int(stream.headers.get("content-length", 0))
            with open(local_file_path, "wb") as fhandle:
                for chunk in stream.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        fhandle.write(chunk)
                        progress_callback(len(chunk), stream_size)
            try:
                stream.raise_for_status()
            except HTTPError:
                import traceback

                logger.error(
                    "Error while getting resource : %s", traceback.format_exc()
                )
            else:
                with open(record_filename, "w") as fh:
                    fh.write(url)
                logger.debug("Download recorded in %s", record_filename)
                if self.config.extract and zipfile.is_zipfile(local_file_path):
                    logger.info("Extraction activated")
                    with zipfile.ZipFile(local_file_path, "r") as zfile:
                        fileinfos = zfile.infolist()
                        with tqdm(
                            fileinfos,
                            unit="file",
                            desc="Extracting files from {}".format(local_file_path),
                        ) as progressbar:
                            for fileinfo in progressbar:
                                zfile.extract(
                                    fileinfo, path=self.config["outputs_prefix"]
                                )
                    return local_file_path[: local_file_path.index(".tar.bz")]
                else:
                    return local_file_path
