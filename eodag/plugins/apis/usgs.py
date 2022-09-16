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
import copy
import logging
import shutil
import tarfile
import zipfile

import requests
from jsonpath_ng.ext import parse
from requests import RequestException
from usgs import USGSAuthExpiredError, USGSError, api

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
from eodag.utils import (
    GENERIC_PRODUCT_TYPE,
    ProgressCallback,
    format_dict_items,
    path_to_uri,
)
from eodag.utils.exceptions import AuthenticationError, NotAvailableError

logger = logging.getLogger("eodag.plugins.apis.usgs")


class UsgsApi(Download, Api):
    """A plugin that enables to query and download data on the USGS catalogues"""

    def authenticate(self):
        """Login to usgs api

        :raises: :class:`~eodag.utils.exceptions.AuthenticationError`
        """
        for i in range(2):
            try:
                api.login(
                    getattr(self.config, "credentials", {}).get("username", ""),
                    getattr(self.config, "credentials", {}).get("password", ""),
                    save=True,
                )
                break
            # if API key expired, retry to login once after logout
            except USGSAuthExpiredError:
                api.logout()
                continue
            except USGSError:
                raise AuthenticationError(
                    "Please check your USGS credentials."
                ) from None

    def query(
        self, product_type=None, items_per_page=None, page=None, count=True, **kwargs
    ):
        """Search for data on USGS catalogues"""
        product_type = kwargs.get("productType")
        if product_type is None:
            return [], 0

        self.authenticate()

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
            api_search_kwargs = dict(
                start_date=start_date,
                end_date=end_date,
                ll=lower_left,
                ur=upper_right,
                max_results=items_per_page,
                starting_number=(1 + (page - 1) * items_per_page),
            )
            logger.info(
                f"Sending search request for {usgs_dataset} with {api_search_kwargs}"
            )

            results = api.scene_search(usgs_dataset, **api_search_kwargs)

            # update results with storage info from download_options()
            results_by_entity_id = {
                res["entityId"]: res for res in results["data"]["results"]
            }
            logger.debug(
                f"Adapting {len(results_by_entity_id)} plugin results to eodag product representation"
            )
            download_options = api.download_options(
                usgs_dataset, list(results_by_entity_id.keys())
            )
            if download_options.get("data", None) is not None:
                for download_option in download_options["data"]:
                    if "dds" in download_option["downloadSystem"]:
                        results_by_entity_id[download_option["entityId"]].update(
                            download_option
                        )
            results["data"]["results"] = list(results_by_entity_id.values())

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
                f"Product type {usgs_dataset} does not exist on USGS EE catalog"
            )
            logger.warning(f"Skipping error: {e}")
        api.logout()

        if final:
            # parse total_results
            path_parsed = parse(self.config.pagination["total_items_nb_key_path"])
            total_results = path_parsed.find(results["data"])[0].value
        else:
            total_results = 0

        return final, total_results

    def download(
        self,
        product,
        auth=None,
        progress_callback=None,
        wait=DEFAULT_DOWNLOAD_WAIT,
        timeout=DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs,
    ):
        """Download data from USGS catalogues"""

        if progress_callback is None:
            logger.info(
                "Progress bar unavailable, please call product.download() instead of plugin.download()"
            )
            progress_callback = ProgressCallback(disable=True)

        outputs_extension = self.config.products.get(
            product.product_type, self.config.products[GENERIC_PRODUCT_TYPE]
        ).get("outputs_extension", ".tar.gz")

        fs_path, record_filename = self._prepare_download(
            product,
            progress_callback=progress_callback,
            outputs_extension=outputs_extension,
            **kwargs,
        )
        if not fs_path or not record_filename:
            if fs_path:
                product.location = path_to_uri(fs_path)
            return fs_path

        self.authenticate()

        if "dds" in product.properties.get("downloadSystem", ""):
            raise NotAvailableError(
                f"No USGS products found for {product.properties['id']}"
            )

        download_request = api.download_request(
            product.properties["productType"],
            product.properties["entityId"],
            product.properties["productId"],
        )

        req_urls = []
        try:
            if len(download_request["data"]["preparingDownloads"]) > 0:
                req_urls.extend(
                    [x["url"] for x in download_request["data"]["preparingDownloads"]]
                )
            else:
                req_urls.extend(
                    [x["url"] for x in download_request["data"]["availableDownloads"]]
                )
        except KeyError as e:
            raise NotAvailableError(
                f"{e} not found in {product.properties['id']} download_request"
            )

        if len(req_urls) > 1:
            logger.warning(
                f"{len(req_urls)} usgs products found for {product.properties['id']}. Only first will be downloaded"
            )
        elif not req_urls:
            raise NotAvailableError(
                f"No usgs request url was found for {product.properties['id']}"
            )

        req_url = req_urls[0]
        progress_callback.reset()
        logger.debug(f"Downloading {req_url}")

        @self._download_retry(product, wait, timeout)
        def download_request(product, fs_path, progress_callback, **kwargs):
            try:
                with requests.get(
                    req_url,
                    stream=True,
                    timeout=wait * 60,
                ) as stream:
                    try:
                        stream.raise_for_status()
                    except RequestException:
                        import traceback as tb

                        logger.error(
                            f"Error while getting resource :\n{tb.format_exc()}",
                        )
                    else:
                        stream_size = int(stream.headers.get("content-length", 0))
                        progress_callback.reset(total=stream_size)
                        with open(fs_path, "wb") as fhandle:
                            for chunk in stream.iter_content(chunk_size=64 * 1024):
                                if chunk:
                                    fhandle.write(chunk)
                                    progress_callback(len(chunk))
            except requests.exceptions.Timeout as e:
                raise NotAvailableError(str(e))

        download_request(product, fs_path, progress_callback, **kwargs)

        with open(record_filename, "w") as fh:
            fh.write(product.properties["downloadLink"])
        logger.debug(f"Download recorded in {record_filename}")

        api.logout()

        # Check downloaded file format
        if (outputs_extension == ".tar.gz" and tarfile.is_tarfile(fs_path)) or (
            outputs_extension == ".zip" and zipfile.is_zipfile(fs_path)
        ):
            product_path = self._finalize(
                fs_path,
                progress_callback=progress_callback,
                outputs_extension=outputs_extension,
                **kwargs,
            )
            product.location = path_to_uri(product_path)
            return product_path
        elif tarfile.is_tarfile(fs_path):
            logger.info(
                "Downloaded product detected as a tar File, but was was expected to be a zip file"
            )
            new_fs_path = fs_path[: fs_path.index(outputs_extension)] + ".tar.gz"
            shutil.move(fs_path, new_fs_path)
            product.location = path_to_uri(new_fs_path)
            return new_fs_path
        elif zipfile.is_zipfile(fs_path):
            logger.info(
                "Downloaded product detected as a zip File, but was was expected to be a tar file"
            )
            new_fs_path = fs_path[: fs_path.index(outputs_extension)] + ".zip"
            shutil.move(fs_path, new_fs_path)
            product.location = path_to_uri(new_fs_path)
            return new_fs_path
        else:
            logger.warning(
                "Downloaded product is not a tar or a zip File. Please check its file type before using it"
            )
            new_fs_path = fs_path[: fs_path.index(outputs_extension)]
            shutil.move(fs_path, new_fs_path)
            product.location = path_to_uri(new_fs_path)
            return new_fs_path

    def download_all(
        self,
        products,
        auth=None,
        downloaded_callback=None,
        progress_callback=None,
        wait=DEFAULT_DOWNLOAD_WAIT,
        timeout=DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs,
    ):
        """
        Download all using parent (base plugin) method
        """
        return super(UsgsApi, self).download_all(
            products,
            auth=auth,
            downloaded_callback=downloaded_callback,
            progress_callback=progress_callback,
            wait=wait,
            timeout=timeout,
            **kwargs,
        )
