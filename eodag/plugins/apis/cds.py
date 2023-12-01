# -*- coding: utf-8 -*-
# Copyright 2022, CS GROUP - France, https://www.csgroup.eu/
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
from datetime import datetime

import cdsapi
import geojson
import requests

from eodag.api.product.request_splitter import RequestSplitter
from eodag.plugins.apis.base import Api
from eodag.plugins.download.base import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    Download,
)
from eodag.plugins.search.base import Search
from eodag.plugins.search.build_search_result import BuildPostSearchResult
from eodag.rest.stac import DEFAULT_MISSION_START_DATE
from eodag.utils import datetime_range, get_geometry_from_various, path_to_uri, urlsplit
from eodag.utils.exceptions import AuthenticationError, DownloadError, RequestError
from eodag.utils.logging import get_logging_verbose

logger = logging.getLogger("eodag.apis.cds")

CDS_KNOWN_FORMATS = {"grib": "grib", "netcdf": "nc"}


class CdsApi(Download, Api, BuildPostSearchResult):
    """A plugin that enables to build download-request and download data on CDS API.

    Builds a single ready-to-download :class:`~eodag.api.product._product.EOProduct`
    during the search stage.

    This class inherits from :class:`~eodag.plugins.apis.base.Api` for compatibility,
    :class:`~eodag.plugins.download.base.Download` for download methods, and
    :class:`~eodag.plugins.search.qssearch.QueryStringSearch` for metadata-mapping and
    query build methods.
    """

    def __init__(self, provider, config):
        # init self.config.metadata_mapping using Search Base plugin
        Search.__init__(self, provider, config)

        # needed by QueryStringSearch.build_query_string / format_free_text_search
        self.config.__dict__.setdefault("free_text_search_operations", {})
        # needed for compatibility
        self.config.__dict__.setdefault("pagination", {"next_page_query_obj": "{{}}"})

    def do_search(self, *args, **kwargs):
        """Should perform the actual search request."""
        return [{}]

    def query(
        self,
        product_type=None,
        items_per_page=None,
        page=None,
        count=True,
        **kwargs,
    ):
        """Build ready-to-download SearchResult"""
        # check productType, dates, geometry, use defaults if not specified
        # productType
        if not kwargs.get("productType"):
            kwargs["productType"] = kwargs.get("dataset", None)

        if (
            kwargs["productType"] in getattr(self.config, "products", {})
            and "multi_select_values"
            in getattr(self.config, "products", {})[kwargs["productType"]]
        ):
            self.config.multi_select_values = getattr(self.config, "products", {})[
                kwargs["productType"]
            ]["multi_select_values"]
        else:
            self.config.multi_select_values = ""
        if (
            kwargs["productType"] in getattr(self.config, "products", {})
            and "constraints_file_path"
            in getattr(self.config, "products", {})[kwargs["productType"]]
        ):
            self.config.constraints_file_path = getattr(self.config, "products", {})[
                kwargs["productType"]
            ]["constraints_file_path"]
        else:
            self.config.constraints_file_path = ""
        if (
            kwargs["productType"] in getattr(self.config, "products", {})
            and "constraints_file_url"
            in getattr(self.config, "products", {})[kwargs["productType"]]
        ):
            self.config.constraints_file_url = getattr(self.config, "products", {})[
                kwargs["productType"]
            ]["constraints_file_url"]
        elif not getattr(self.config, "constraints_file_url", None):
            self.config.constraints_file_url = ""
        # start date
        if "startTimeFromAscendingNode" not in kwargs and "id" not in kwargs:
            kwargs["startTimeFromAscendingNode"] = (
                getattr(self.config, "product_type_config", {}).get(
                    "missionStartDate", None
                )
                or DEFAULT_MISSION_START_DATE
            )
        # end date
        if "completionTimeFromAscendingNode" not in kwargs and "id" not in kwargs:
            kwargs["completionTimeFromAscendingNode"] = getattr(
                self.config, "product_type_config", {}
            ).get("missionEndDate", None) or datetime.utcnow().isoformat(
                timespec="seconds"
            )
        # geometry
        if not kwargs.get("geometry", None):
            kwargs["geometry"] = [
                -180,
                -90,
                180,
                90,
            ]
        kwargs["geometry"] = get_geometry_from_various(geometry=kwargs["geometry"])

        products = []
        if (
            getattr(self.config, "products_split_timedelta", None)
            and "id" not in kwargs
        ):
            product_type_conf = getattr(self.config, "products", {}).get(
                kwargs["productType"], None
            )
            if product_type_conf and "dataset" in product_type_conf:
                provider_product_type = product_type_conf["dataset"]
            else:
                provider_product_type = ""
            request_splitter = RequestSplitter(
                self.config,
                self.config.metadata_mapping,
                provider_product_type=provider_product_type,
            )
            slices, num_items = request_splitter.get_time_slices(
                kwargs["startTimeFromAscendingNode"],
                kwargs["completionTimeFromAscendingNode"],
            )
            kwargs.pop("startTimeFromAscendingNode")
            kwargs.pop("completionTimeFromAscendingNode")
            for time_slice in slices:
                for key, value in time_slice.items():
                    if key == "start_date":
                        if isinstance(value, str):
                            kwargs["startTimeFromAscendingNode"] = value
                        else:
                            kwargs["startTimeFromAscendingNode"] = value.strftime(
                                "%Y-%m-%dT%H:%M:%SZ"
                            )
                    elif key == "end_date":
                        if isinstance(value, str):
                            kwargs["completionTimeFromAscendingNode"] = value
                        else:
                            kwargs["completionTimeFromAscendingNode"] = value.strftime(
                                "%Y-%m-%dT%H:%M:%SZ"
                            )
                    else:
                        kwargs[key] = value
                result = BuildPostSearchResult.query(
                    self,
                    items_per_page=items_per_page,
                    page=page,
                    count=count,
                    **kwargs,
                )
                products += result[0]
        else:
            products, num_items = BuildPostSearchResult.query(
                self, items_per_page=items_per_page, page=page, count=count, **kwargs
            )
        return products, num_items

    def normalize_results(self, results, **kwargs):
        """Build EOProducts from provider results"""

        products = super(CdsApi, self).normalize_results(results, **kwargs)

        # move assets from properties to product's attr
        for product in products:
            assets = {}
            if "downloadLinks" in product.properties and (
                "server_mode" not in kwargs or not kwargs["server_mode"]
            ):
                for param, link in product.properties["downloadLinks"].items():
                    asset = {
                        "title": "Download " + param,
                        "href": link,
                        "roles": ["data"],
                    }
                    assets[param] = asset
                product.assets = assets

        return products

    def _get_cds_client(self, **auth_dict):
        """Returns cdsapi client."""
        # eodag logging info
        eodag_verbosity = get_logging_verbose()
        eodag_logger = logging.getLogger("eodag")

        client = cdsapi.Client(
            # disable cdsapi default logging and handle it on eodag side
            # until https://github.com/ecmwf/cdsapi/pull/47 is merged
            quiet=True,
            verify=True,
            **auth_dict,
        )

        if eodag_verbosity is None or eodag_verbosity == 1:
            client.logger.setLevel(logging.WARNING)
        elif eodag_verbosity == 2:
            client.logger.setLevel(logging.INFO)
        elif eodag_verbosity == 3:
            client.logger.setLevel(logging.DEBUG)
        else:
            client.logger.setLevel(logging.WARNING)

        if len(eodag_logger.handlers) > 0:
            client.logger.addHandler(eodag_logger.handlers[0])

        return client

    def authenticate(self):
        """Returns information needed for auth

        :returns: {key, url} dictionary
        :rtype: dict
        :raises: :class:`~eodag.utils.exceptions.AuthenticationError`
        :raises: :class:`~eodag.utils.exceptions.RequestError`
        """
        # Get credentials from eodag or using cds conf
        uid = getattr(self.config, "credentials", {}).get("username", None)
        api_key = getattr(self.config, "credentials", {}).get("password", None)
        url = getattr(self.config, "api_endpoint", None)
        if not all([uid, api_key, url]):
            raise AuthenticationError("Missing authentication informations")

        auth_dict = {"key": f"{uid}:{api_key}", "url": url}

        client = self._get_cds_client(**auth_dict)
        try:
            client.status()
            logger.debug("Connection checked on CDS API")
        except requests.exceptions.ConnectionError as e:
            logger.error(e)
            raise RequestError(f"Could not connect to the CDS API '{url}'")
        except requests.exceptions.HTTPError as e:
            logger.error(e)
            raise RequestError("The CDS API has returned an unexpected error")

        return auth_dict

    def download(self, product, auth=None, progress_callback=None, **kwargs):
        """Download data from providers using CDS API"""

        product_extension = CDS_KNOWN_FORMATS[product.properties.get("format", "grib")]
        auth_dict = self.authenticate()

        # Prepare download
        fs_path, record_filename = self._prepare_download(
            product,
            progress_callback=progress_callback,
            outputs_extension=f".{product_extension}",
            **kwargs,
        )

        if not fs_path or not record_filename:
            if fs_path:
                product.location = path_to_uri(fs_path)
            return fs_path

        assets = getattr(product, "assets", {})
        if assets and "downloadLink" not in assets:
            self._download_assets(product, fs_path, record_filename, auth_dict)
        else:
            # get download request dict from product.location/downloadLink url query string
            # separate url & parameters
            query_str = "".join(urlsplit(product.location).fragment.split("?", 1)[1:])
            download_request = self._create_download_request(
                query_str, product.product_type
            )

            dataset_name = download_request.pop("dataset")

            # Send download request to CDS web API
            logger.info(
                "Request download on CDS API: dataset=%s, request=%s",
                dataset_name,
                download_request,
            )
            try:
                client = self._get_cds_client(**auth_dict)
                client.retrieve(
                    name=dataset_name, request=download_request, target=fs_path
                )
            except Exception as e:
                logger.error(e)
                raise DownloadError(e)

            with open(record_filename, "w") as fh:
                fh.write(product.properties["downloadLink"])
            logger.debug("Download recorded in %s", record_filename)

        # do not try to extract or delete grib/netcdf
        kwargs["extract"] = False

        product_path = self._finalize(
            fs_path,
            progress_callback=progress_callback,
            outputs_extension=f".{product_extension}",
            **kwargs,
        )
        product.location = path_to_uri(product_path)
        return product_path

    def _create_download_request(self, query_str, product_type):
        download_request = geojson.loads(query_str)
        # remove string quotes within values
        for param, param_value in download_request.items():
            if isinstance(param_value, str):
                download_request[param] = param_value.replace('"', "").replace("'", "")
            elif isinstance(param_value, list):
                for i, value in enumerate(param_value):
                    if isinstance(value, str):
                        param_value[i] = value.replace('"', "").replace("'", "")

        date_range = download_request.pop("date_range", False)
        if date_range:
            date_value = download_request.pop("date", None)
            if not date_value:
                date_value = date_range
            if isinstance(date_value, str):
                date = date_value.replace('"', "").replace("'", "")
            else:
                date = date_value[0].replace('"', "").replace("'", "")
            start, end, *_ = date.split("/")
            if getattr(self.config, "products_split_timedelta", None):
                product_type_conf = getattr(self.config, "products", {})[product_type]
                if "dataset" in product_type_conf:
                    provider_product_type = product_type_conf["dataset"]
                else:
                    provider_product_type = ""
                request_splitter = RequestSplitter(
                    self.config, self.config.metadata_mapping, provider_product_type
                )
                time_params = request_splitter.get_time_slices(start, end)[0]
                download_request["year"] = time_params[0]["year"]
                download_request["month"] = time_params[0]["month"]
                download_request["day"] = time_params[0]["day"]
            else:
                _start = datetime.fromisoformat(start)
                _end = datetime.fromisoformat(end)
                d_range = [d for d in datetime_range(_start, _end)]
                download_request["year"] = [*{str(d.year) for d in d_range}]
                download_request["month"] = [*{str(d.month) for d in d_range}]
                download_request["day"] = [*{str(d.day) for d in d_range}]
        return download_request

    def _download_assets(self, product, fs_path, record_filename, auth_dict):
        for key, asset in product.assets.items():
            query_str = "".join(urlsplit(asset["href"]).fragment.split("?", 1)[1:])
            download_request = self._create_download_request(
                query_str, product.product_type
            )
            if not os.path.isdir(fs_path):
                os.mkdir(fs_path)
            asset_path = fs_path + "/" + key

            asset_file_name = record_filename + "/" + key
            dataset_name = download_request.pop("dataset")

            # Send download request to CDS web API
            logger.info(
                "Request download on CDS API: dataset=%s, request=%s, asset=%s",
                dataset_name,
                download_request,
                key,
            )
            try:
                client = self._get_cds_client(**auth_dict)
                client.retrieve(
                    name=dataset_name, request=download_request, target=asset_path
                )
            except Exception as e:
                logger.error(e)
                raise DownloadError(e)

            if not os.path.isdir(record_filename):
                os.mkdir(record_filename)
            with open(asset_file_name, "w") as fh:
                fh.write(product.properties["downloadLink"])
            logger.debug("Download recorded in %s", asset_file_name)

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
        return super(CdsApi, self).download_all(
            products,
            auth=auth,
            downloaded_callback=downloaded_callback,
            progress_callback=progress_callback,
            wait=wait,
            timeout=timeout,
            **kwargs,
        )
