# -*- coding: utf-8 -*-
# Copyright 2021, CS GROUP - France, http://www.c-s.fr
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
import copy
import logging
import shutil
import tarfile

import requests
from jsonpath_ng.ext import parse
from requests import HTTPError
from usgs import USGSError, api

from eodag.api.product import EOProduct
from eodag.api.product.metadata_mapping import (
    DEFAULT_METADATA_MAPPING,
    mtd_cfg_as_jsonpath,
    properties_from_json,
)
from eodag.plugins.apis.base import Api
from eodag.plugins.download.base import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    Download,
)
from eodag.utils import GENERIC_PRODUCT_TYPE, format_dict_items, get_progress_callback
from eodag.utils.exceptions import AuthenticationError, NotAvailableError

logger = logging.getLogger("eodag.plugins.apis.usgs")


class UsgsApi(Api, Download):
    """A plugin that enables to query and download data on the USGS catalogues"""

    def query(
        self, product_type=None, items_per_page=None, page=None, count=True, **kwargs
    ):
        """Search for data on USGS catalogues

        .. versionchanged::
           2.2.0

                * Based on usgs library v0.3.0 which now uses M2M API. The library
                  is used for both search & download

        .. versionchanged::
            1.0

                * ``product_type`` is no longer mandatory
        """
        product_type = kwargs.get("productType")
        if product_type is None:
            return [], 0
        try:
            api.login(
                self.config.credentials["username"],
                self.config.credentials["password"],
                save=True,
            )
        except USGSError:
            raise AuthenticationError("Please check your USGS credentials.") from None

        product_type_def_params = self.config.products.get(
            product_type, self.config.products[GENERIC_PRODUCT_TYPE]
        )
        usgs_dataset = format_dict_items(product_type_def_params, **kwargs)["dataset"]
        start_date = kwargs.pop("startTimeFromAscendingNode", None)
        end_date = kwargs.pop("completionTimeFromAscendingNode", None)
        geom = kwargs.pop("geometry", None)
        footprint = {}
        if hasattr(geom, "bounds"):
            (
                footprint["lonmin"],
                footprint["latmin"],
                footprint["lonmax"],
                footprint["latmax"],
            ) = geom.bounds
        else:
            footprint = geom

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
            results = api.scene_search(
                usgs_dataset,
                start_date=start_date,
                end_date=end_date,
                ll=lower_left,
                ur=upper_right,
                max_results=items_per_page,
                starting_number=(1 + (page - 1) * items_per_page),
            )

            # Same method as in base.py, Search.__init__()
            # Prepare the metadata mapping
            # Do a shallow copy, the structure is flat enough for this to be sufficient
            metas = DEFAULT_METADATA_MAPPING.copy()
            # Update the defaults with the mapping value. This will add any new key
            # added by the provider mapping that is not in the default metadata.
            # A deepcopy is done to prevent self.config.metadata_mapping from being modified when metas[metadata]
            # is a list and is modified
            metas.update(copy.deepcopy(self.config.metadata_mapping))
            metas = mtd_cfg_as_jsonpath(metas)

            for result in results["data"]["results"]:

                result["productType"] = usgs_dataset

                product_properties = properties_from_json(result, metas)

                final.append(
                    EOProduct(
                        productType=product_type,
                        provider=self.provider,
                        properties=product_properties,
                        geometry=footprint,
                    )
                )
        except USGSError as e:
            logger.warning(
                "Product type %s does not exist on USGS EE catalog",
                usgs_dataset,
            )
            logger.warning("Skipping error: %s", e)
        api.logout()

        if final:
            # parse total_results
            path_parsed = parse(self.config.pagination["total_items_nb_key_path"])
            total_results = path_parsed.find(results["data"])[0].value
        else:
            total_results = 0

        return final, total_results

    def download(self, product, auth=None, progress_callback=None, **kwargs):
        """Download data from USGS catalogues"""

        fs_path, record_filename = self._prepare_download(
            product, outputs_extension=".tar.gz", **kwargs
        )
        if not fs_path or not record_filename:
            return fs_path

        # progress bar init
        if progress_callback is None:
            progress_callback = get_progress_callback()
        progress_callback.desc = product.properties.get("id", "")
        progress_callback.position = 1

        try:
            api.login(
                self.config.credentials["username"],
                self.config.credentials["password"],
                save=True,
            )
        except USGSError:
            raise AuthenticationError("Please check your USGS credentials.") from None

        download_options = api.download_options(
            product.properties["productType"], product.properties["id"]
        )

        try:
            product_ids = [
                p["id"]
                for p in download_options["data"]
                if p["downloadSystem"] == "dds"
            ]
        except KeyError as e:
            raise NotAvailableError(
                "%s not found in %s's products" % (e, product.properties["id"])
            )

        if not product_ids:
            raise NotAvailableError(
                "No USGS products found for %s" % product.properties["id"]
            )

        req_urls = []
        for product_id in product_ids:
            download_request = api.download_request(
                product.properties["productType"], product.properties["id"], product_id
            )
            try:
                req_urls.extend(
                    [x["url"] for x in download_request["data"]["preparingDownloads"]]
                )
            except KeyError as e:
                raise NotAvailableError(
                    "%s not found in %s download_request"
                    % (e, product.properties["id"])
                )

        if len(req_urls) > 1:
            logger.warning(
                "%s usgs products found for %s. Only first will be downloaded"
                % (len(req_urls), product.properties["id"])
            )
        elif not req_urls:
            raise NotAvailableError(
                "No usgs request url was found for %s" % product.properties["id"]
            )

        req_url = req_urls[0]
        progress_callback.reset()
        with requests.get(
            req_url,
            stream=True,
        ) as stream:
            try:
                stream.raise_for_status()
            except HTTPError:
                import traceback as tb

                logger.error(
                    "Error while getting resource :\n%s",
                    tb.format_exc(),
                )
            else:
                stream_size = int(stream.headers.get("content-length", 0))
                progress_callback.max_size = stream_size
                progress_callback.reset()
                with open(fs_path, "wb") as fhandle:
                    for chunk in stream.iter_content(chunk_size=64 * 1024):
                        if chunk:
                            fhandle.write(chunk)
                            progress_callback(len(chunk), stream_size)

        with open(record_filename, "w") as fh:
            fh.write(product.properties["downloadLink"])
        logger.debug("Download recorded in %s", record_filename)

        api.logout()

        # Check that the downloaded file is really a tar file
        if not tarfile.is_tarfile(fs_path):
            logger.warning(
                "Downloaded product is not a tar File. Please check its file type before using it"
            )
            new_fs_path = fs_path[: fs_path.index(".tar.gz")]
            shutil.move(fs_path, new_fs_path)
            return new_fs_path
        return self._finalize(fs_path, outputs_extension=".tar.gz", **kwargs)

    def download_all(
        self,
        products,
        auth=None,
        progress_callback=None,
        wait=DEFAULT_DOWNLOAD_WAIT,
        timeout=DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs
    ):
        """
        download_all using parent (base plugin) method
        """
        return super(UsgsApi, self).download_all(
            products,
            auth=auth,
            progress_callback=progress_callback,
            wait=wait,
            timeout=timeout,
            **kwargs
        )
