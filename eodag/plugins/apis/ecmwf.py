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
from datetime import datetime

import geojson
from ecmwfapi import ECMWFDataServer, ECMWFService
from ecmwfapi.api import APIException, Connection, get_apikey_values

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
from eodag.utils import get_geometry_from_various, path_to_uri, urlsplit
from eodag.utils.exceptions import AuthenticationError, DownloadError
from eodag.utils.logging import get_logging_verbose

logger = logging.getLogger("eodag.apis.ecmwf")

ECMWF_MARS_KNOWN_FORMATS = {"grib": "grib", "netcdf": "nc"}


class EcmwfApi(Download, Api, BuildPostSearchResult):
    """A plugin that enables to build download-request and download data on ECMWF MARS.

    Builds a single ready-to-download :class:`~eodag.api.product._product.EOProduct`
    during the search stage.

    Download will then be performed on ECMWF Public Datasets (if ``dataset`` parameter
    is in query), or on MARS Operational Archive (if ``dataset`` parameter is not in
    query).

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
        self, product_type=None, items_per_page=None, page=None, count=True, **kwargs
    ):
        """Build ready-to-download SearchResult"""

        # check productType, dates, geometry, use defaults if not specified
        # productType
        if not kwargs.get("productType"):
            kwargs["productType"] = "%s_%s_%s" % (
                kwargs.get("dataset", "mars"),
                kwargs.get("type", ""),
                kwargs.get("levtype", ""),
            )

        if not product_type:
            product_type = kwargs["productType"]
        self.config.constraints_file_path = getattr(self.config, "products", {})[
            product_type
        ]["constraints_file_path"]

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
        num_items = 0
        if (
            getattr(self.config, "products_split_timedelta", None)
            and "id" not in kwargs
        ):
            request_splitter = RequestSplitter(self.config)
            slices = request_splitter.get_time_slices(
                kwargs["startTimeFromAscendingNode"],
                kwargs["completionTimeFromAscendingNode"],
            )
            for slice in slices:
                kwargs["startTimeFromAscendingNode"] = slice["start_date"].strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
                kwargs["completionTimeFromAscendingNode"] = slice["end_date"].strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
                print("ecmwf")
                print(kwargs)
                result = BuildPostSearchResult.query(
                    self,
                    items_per_page=items_per_page,
                    page=page,
                    count=count,
                    **kwargs,
                )
                products += result[0]
                num_items += result[1]
        else:
            print("ecmwf")
            print(kwargs)
            products, num_items = BuildPostSearchResult.query(
                self,
                items_per_page=items_per_page,
                page=page,
                count=count,
                **kwargs,
            )

        return products, num_items

    def authenticate(self):
        """Check credentials and returns information needed for auth

        :returns: {key, url, email} dictionary
        :rtype: dict
        :raises: :class:`~eodag.utils.exceptions.AuthenticationError`
        """
        # Get credentials from eodag or using ecmwf conf
        print("auth")
        print(getattr(self.config, "credentials", {}))
        email = getattr(self.config, "credentials", {}).get("username", None)
        key = getattr(self.config, "credentials", {}).get("password", None)
        url = getattr(self.config, "api_endpoint", None)
        print(url)
        if not all([email, key, url]):
            key, url, email = get_apikey_values()

        # APIRequest to check credentials
        ecmwf_connection = Connection(
            url=url,
            email=email,
            key=key,
        )
        try:
            ecmwf_connection.call("{}/{}".format(url, "who-am-i"))
            logger.debug("Credentials checked on ECMWF")
        except APIException as e:
            logger.error(e)
            raise AuthenticationError("Please check your ECMWF credentials.")

        return {"key": key, "url": url, "email": email}

    def download(self, product, auth=None, progress_callback=None, **kwargs):
        """Download data from ECMWF MARS"""

        if "format" in product.properties and product.properties["format"] is not None:
            product_extension = ECMWF_MARS_KNOWN_FORMATS[
                product.properties.get("format")
            ]
        else:
            product_extension = ECMWF_MARS_KNOWN_FORMATS["grib"]

        print(product.location)
        # Prepare download
        fs_path, record_filename = self._prepare_download(
            product,
            progress_callback=progress_callback,
            outputs_extension=f".{product_extension}",
            **kwargs,
        )
        print(fs_path, record_filename)

        if not fs_path or not record_filename:
            if fs_path:
                product.location = path_to_uri(fs_path)
            return fs_path

        # get download request dict from product.location/downloadLink url query string
        # separate url & parameters
        download_request = geojson.loads(urlsplit(product.location).query)

        # Set verbosity
        eodag_verbosity = get_logging_verbose()
        if eodag_verbosity is not None and eodag_verbosity >= 3:
            # debug verbosity
            ecmwf_verbose = True
            ecmwf_log = logger.debug
        else:
            # default verbosity
            ecmwf_verbose = False
            ecmwf_log = logger.info

        auth_dict = self.authenticate()
        print(auth_dict)

        # Send download request to ECMWF web API
        logger.info("Request download on ECMWF: %s" % download_request)
        try:
            if "dataset" in download_request and not download_request[
                "dataset"
            ].startswith("mars_"):
                # Public dataset
                ecmwf_server = ECMWFDataServer(
                    verbose=ecmwf_verbose, log=ecmwf_log, **auth_dict
                )
                ecmwf_server.retrieve(dict(download_request, **{"target": fs_path}))
            else:
                # Operational Archive
                ecmwf_server = ECMWFService(
                    service="mars", verbose=ecmwf_verbose, log=ecmwf_log, **auth_dict
                )
                print(ecmwf_server)
                download_request.pop("dataset", None)
                ecmwf_server.execute(download_request, fs_path)
        except APIException as e:
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
        return super(EcmwfApi, self).download_all(
            products,
            auth=auth,
            downloaded_callback=downloaded_callback,
            progress_callback=progress_callback,
            wait=wait,
            timeout=timeout,
            **kwargs,
        )
