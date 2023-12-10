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
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from urllib.parse import unquote_plus

import cdsapi
import geojson
import requests

from eodag.api.product._assets import Asset
from eodag.plugins.apis.base import Api
from eodag.plugins.download.http import HTTPDownload
from eodag.plugins.search.base import Search
from eodag.plugins.search.build_search_result import BuildPostSearchResult
from eodag.rest.stac import DEFAULT_MISSION_START_DATE
from eodag.utils import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    DEFAULT_ITEMS_PER_PAGE,
    DEFAULT_PAGE,
    datetime_range,
    get_geometry_from_various,
    path_to_uri,
    urlsplit,
)
from eodag.utils.exceptions import AuthenticationError, DownloadError, RequestError
from eodag.utils.logging import get_logging_verbose

if TYPE_CHECKING:
    from eodag.api.product import EOProduct
    from eodag.api.search_result import SearchResult
    from eodag.config import PluginConfig
    from eodag.utils import DownloadedCallback, ProgressCallback

logger = logging.getLogger("eodag.apis.cds")

CDS_KNOWN_FORMATS = {"grib": "grib", "netcdf": "nc"}


class CdsApi(HTTPDownload, Api, BuildPostSearchResult):
    """A plugin that enables to build download-request and download data on CDS API.

    Builds a single ready-to-download :class:`~eodag.api.product._product.EOProduct`
    during the search stage.

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

    def get_product_type_cfg(self, key: str, default: Any = None) -> Any:
        """
        Get the value of a configuration option specific to the current product type.

        This method retrieves the value of a configuration option from the
        `_product_type_config` attribute. If the option is not found, the provided
        default value is returned.

        :param key: The configuration option key.
        :type key: str
        :param default: The default value to be returned if the option is not found (default is None).
        :type default: Any

        :return: The value of the specified configuration option or the default value.
        :rtype: Any
        """
        product_type_cfg = getattr(self.config, "product_type_config", {})
        non_none_cfg = {k: v for k, v in product_type_cfg.items() if v}

        return non_none_cfg.get(key, default)

    def _preprocess_search_params(self, params: Dict[Any]) -> None:
        """Preprocess search parameters before making a request to the CDS API.

        This method is responsible for checking and updating the provided search parameters
        to ensure that required parameters like 'productType', 'startTimeFromAscendingNode',
        'completionTimeFromAscendingNode', and 'geometry' are properly set. If not specified
        in the input parameters, default values or values from the configuration are used.

        :param params: Search parameters to be preprocessed.
        :type params: dict
        """
        _dc_qs = params.get("_dc_qs", None)
        if _dc_qs is not None:
            # if available, update search params using datacube query-string
            _dc_qp = geojson.loads(unquote_plus(unquote_plus(_dc_qs)))
            if "/" in _dc_qp.get("date", ""):
                (
                    params["startTimeFromAscendingNode"],
                    params["completionTimeFromAscendingNode"],
                ) = _dc_qp["date"].split("/")
            else:
                params["startTimeFromAscendingNode"] = params[
                    "completionTimeFromAscendingNode"
                ] = _dc_qp["date"]

            if "/" in _dc_qp.get("area", ""):
                params["geometry"] = _dc_qp["area"].split("/")

        non_none_params = {k: v for k, v in params.items() if v}

        # productType
        dataset = params.get("dataset", None)
        params["productType"] = non_none_params.get("productType", dataset)

        # dates
        default_start_str = DEFAULT_MISSION_START_DATE.replace(
            "Z", "+00:00"
        )  # before 3.11
        mission_start_dt = datetime.fromisoformat(
            self.get_product_type_cfg("missionStartDate", default_start_str)
        )

        default_end_str = (
            datetime.utcnow()
            if params.get("startTimeFromAscendingNode")
            else mission_start_dt + timedelta(days=1)
        ).isoformat()
        mission_end_str = self.get_product_type_cfg("missionEndDate", default_end_str)

        params["startTimeFromAscendingNode"] = non_none_params.get(
            "startTimeFromAscendingNode", mission_start_dt.isoformat()
        )
        params["completionTimeFromAscendingNode"] = non_none_params.get(
            "completionTimeFromAscendingNode", mission_end_str
        )

        # geometry
        if "geometry" in params:
            params["geometry"] = get_geometry_from_various(geometry=params["geometry"])

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

        self._preprocess_search_params(kwargs)

        return BuildPostSearchResult.query(
            self, items_per_page=items_per_page, page=page, count=count, **kwargs
        )

    def _get_cds_client(self, **auth_dict: Any) -> cdsapi.Client:
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

    def authenticate(self) -> Dict[str, str]:
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
            raise AuthenticationError("Missing authentication information")

        auth_dict: Dict[str, str] = {"key": f"{uid}:{api_key}", "url": url}

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

    def _prepare_download_link(self, product):
        """Update product download link with http url obtained from cds api"""
        # get download request dict from product.location/downloadLink url query string
        # separate url & parameters
        query_str = "".join(urlsplit(product.location).fragment.split("?", 1)[1:])
        download_request = geojson.loads(query_str)

        date_range = download_request.pop("date_range", False)
        if date_range:
            date = download_request.pop("date")
            start, end, *_ = date.split("/")
            _start = datetime.fromisoformat(start)
            _end = datetime.fromisoformat(end)
            d_range = [d for d in datetime_range(_start, _end)]
            download_request["year"] = [*{str(d.year) for d in d_range}]
            download_request["month"] = [*{str(d.month) for d in d_range}]
            download_request["day"] = [*{str(d.day) for d in d_range}]

        auth_dict = self.authenticate()
        dataset_name = download_request.pop("dataset")

        # Send download request to CDS web API
        logger.info(
            "Request download on CDS API: dataset=%s, request=%s",
            dataset_name,
            download_request,
        )
        try:
            client = self._get_cds_client(**auth_dict)
            result = client._api(
                "%s/resources/%s" % (client.url, dataset_name), download_request, "POST"
            )
            # update product download link through a new asset
            product.assets["data"] = Asset(product, "data", {"href": result.location})
        except Exception as e:
            logger.error(e)
            raise DownloadError(e)

    def download(
        self,
        product: EOProduct,
        auth: Optional[PluginConfig] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: int = DEFAULT_DOWNLOAD_WAIT,
        timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Any,
    ) -> Optional[str]:
        """Download data from providers using CDS API"""

        product_extension = CDS_KNOWN_FORMATS[product.properties.get("format", "grib")]

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

        self._prepare_download_link(product)

        try:
            return super(CdsApi, self).download(
                product,
                progress_callback=progress_callback,
                **kwargs,
            )
        except Exception as e:
            logger.error(e)
            raise DownloadError(e)

    def _stream_download_dict(
        self,
        product: EOProduct,
        auth: Optional[PluginConfig] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: int = DEFAULT_DOWNLOAD_WAIT,
        timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Union[str, bool, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Returns dictionnary of :class:`~fastapi.responses.StreamingResponse` keyword-arguments.
        It contains a generator to streamed download chunks and the response headers."""

        self._prepare_download_link(product)
        return super(CdsApi, self)._stream_download_dict(
            product,
            auth=auth,
            progress_callback=progress_callback,
            wait=wait,
            timeout=timeout,
            **kwargs,
        )

    def download_all(
        self,
        products: SearchResult,
        auth: Optional[PluginConfig] = None,
        downloaded_callback: Optional[DownloadedCallback] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: int = DEFAULT_DOWNLOAD_WAIT,
        timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Any,
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
