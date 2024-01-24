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
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING

import geojson
from ecmwfapi import ECMWFDataServer, ECMWFService
from ecmwfapi.api import APIException, Connection, get_apikey_values

from eodag.plugins.apis.base import Api
from eodag.plugins.download.base import Download
from eodag.plugins.search.base import Search
from eodag.plugins.search.build_search_result import BuildPostSearchResult
from eodag.rest.stac import DEFAULT_MISSION_START_DATE
from eodag.utils import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    DEFAULT_ITEMS_PER_PAGE,
    DEFAULT_PAGE,
    get_geometry_from_various,
    path_to_uri,
    sanitize,
    urlsplit,
)
from eodag.utils.exceptions import AuthenticationError, DownloadError
from eodag.utils.logging import get_logging_verbose

if TYPE_CHECKING:
    from typing import Any, Dict, List, Optional, Tuple, Union

    from requests.auth import AuthBase

    from eodag.api.product import EOProduct
    from eodag.api.search_result import SearchResult
    from eodag.config import PluginConfig
    from eodag.utils import DownloadedCallback, ProgressCallback

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

    def __init__(self, provider: str, config: PluginConfig) -> None:
        # init self.config.metadata_mapping using Search Base plugin
        Search.__init__(self, provider, config)

        # needed by QueryStringSearch.build_query_string / format_free_text_search
        self.config.__dict__.setdefault("free_text_search_operations", {})
        # needed for compatibility
        self.config.__dict__.setdefault("pagination", {"next_page_query_obj": "{{}}"})

    def do_search(self, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        """Should perform the actual search request."""
        return [{}]

    def query(
        self,
        product_type: Optional[str] = None,
        items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
        page: int = DEFAULT_PAGE,
        count: bool = True,
        **kwargs: Any,
    ) -> Tuple[List[EOProduct], Optional[int]]:
        """Build ready-to-download SearchResult"""

        # check productType, dates, geometry, use defaults if not specified
        # productType
        if not kwargs.get("productType"):
            kwargs["productType"] = "%s_%s_%s" % (
                kwargs.get("dataset", "mars"),
                kwargs.get("type", ""),
                kwargs.get("levtype", ""),
            )
        # start date
        if "startTimeFromAscendingNode" not in kwargs:
            kwargs["startTimeFromAscendingNode"] = (
                getattr(self.config, "product_type_config", {}).get(
                    "missionStartDate", None
                )
                or DEFAULT_MISSION_START_DATE
            )
        # end date
        if "completionTimeFromAscendingNode" not in kwargs:
            kwargs["completionTimeFromAscendingNode"] = getattr(
                self.config, "product_type_config", {}
            ).get("missionEndDate", None) or datetime.utcnow().isoformat(
                timespec="seconds"
            )

        # geometry
        if "geometry" in kwargs:
            kwargs["geometry"] = get_geometry_from_various(geometry=kwargs["geometry"])

        return BuildPostSearchResult.query(
            self, items_per_page=items_per_page, page=page, count=count, **kwargs
        )

    def authenticate(self) -> Dict[str, Optional[str]]:
        """Check credentials and returns information needed for auth

        :returns: {key, url, email} dictionary
        :rtype: dict
        :raises: :class:`~eodag.utils.exceptions.AuthenticationError`
        """
        # Get credentials from eodag or using ecmwf conf
        email = getattr(self.config, "credentials", {}).get("username", None)
        key = getattr(self.config, "credentials", {}).get("password", None)
        url = getattr(self.config, "api_endpoint", None)
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

    def download(
        self,
        product: EOProduct,
        auth: Optional[Union[AuthBase, Dict[str, str]]] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: int = DEFAULT_DOWNLOAD_WAIT,
        timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Any,
    ) -> Optional[str]:
        """Download data from ECMWF MARS"""
        product_format = product.properties.get("format", "grib")
        product_extension = ECMWF_MARS_KNOWN_FORMATS.get(product_format, product_format)

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

        new_fs_path = os.path.join(
            os.path.dirname(fs_path), sanitize(product.properties["title"])
        )
        if not os.path.isdir(new_fs_path):
            os.makedirs(new_fs_path)
        fs_path = os.path.join(new_fs_path, os.path.basename(fs_path))

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
                download_request.pop("dataset", None)
                ecmwf_server.execute(download_request, fs_path)
        except APIException as e:
            logger.error(e)
            raise DownloadError(e)

        with open(record_filename, "w") as fh:
            fh.write(product.properties["downloadLink"])
        logger.debug("Download recorded in %s", record_filename)

        # do not try to extract a directory
        kwargs["extract"] = False

        product_path = self._finalize(
            new_fs_path,
            progress_callback=progress_callback,
            outputs_extension=f".{product_extension}",
            **kwargs,
        )
        product.location = path_to_uri(product_path)
        return product_path

    def download_all(
        self,
        products: SearchResult,
        auth: Optional[Union[AuthBase, Dict[str, str]]] = None,
        downloaded_callback: Optional[DownloadedCallback] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: int = DEFAULT_DOWNLOAD_WAIT,
        timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Any,
    ) -> List[str]:
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
