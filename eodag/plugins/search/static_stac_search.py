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

import geojson

from eodag.api.search_result import SearchResult
from eodag.plugins.crunch.filter_date import FilterDate
from eodag.plugins.crunch.filter_overlap import FilterOverlap
from eodag.plugins.crunch.filter_property import FilterProperty
from eodag.plugins.search.qssearch import StacSearch
from eodag.utils import MockResponse
from eodag.utils.stac_reader import HTTP_REQ_TIMEOUT, fetch_stac_items

logger = logging.getLogger("eodag.plugins.search.static_stac_search")


class StaticStacSearch(StacSearch):
    """Static STAC Catalog search plugin

    The available configuration parameters for this plugin are
    (to be set in provider configuration):

        - **api_endpoint**: (mandatory) path to the catalog (url or local system path)

        - **max_connections**: (optional) Maximum number of connections for HTTP requests,
          defaut is 100.

        - **timeout**: (mandatory) Timeout in seconds for each internal HTTP request,
          default is 5.

    This plugin first loads all STAC items found in the catalog, and converts them to
    EOProducts using StacSearch.
    Then it uses crunchers to only keep products matching query parameters.
    """

    def __init__(self, provider, config):
        super(StaticStacSearch, self).__init__(provider, config)
        self.config.__dict__.setdefault("max_connections", 100)
        self.config.__dict__.setdefault("timeout", HTTP_REQ_TIMEOUT)

    def query(self, items_per_page=None, page=None, count=True, **kwargs):
        """Perform a search on a static STAC Catalog"""

        features = fetch_stac_items(
            self.config.api_endpoint,
            recursive=True,
            max_connections=self.config.max_connections,
            timeout=self.config.timeout,
        )
        nb_features = len(features)
        feature_collection = geojson.FeatureCollection(features)
        feature_collection["context"] = {
            "limit": nb_features,
            "matched": nb_features,
            "returned": nb_features,
        }

        # save StaticStacSearch._request and mock it to make return loaded static results
        stacapi_request = self._request
        self._request = (
            lambda url, info_message=None, exception_message=None: MockResponse(
                feature_collection, 200
            )
        )

        # query on mocked StacSearch
        eo_products, _ = super(StaticStacSearch, self).query(
            items_per_page=nb_features, page=1, count=True, **kwargs
        )

        # filter using query params
        search_result = SearchResult(eo_products)

        # Filter by date
        if "startTimeFromAscendingNode" in kwargs:
            kwargs["start"] = kwargs.pop("startTimeFromAscendingNode")
        if "completionTimeFromAscendingNode" in kwargs:
            kwargs["end"] = kwargs.pop("completionTimeFromAscendingNode")
        if any(k in ["start", "end"] for k in kwargs.keys()):
            search_result = search_result.crunch(
                FilterDate({k: kwargs[k] for k in ["start", "end"] if k in kwargs})
            )

        # Filter by geometry
        if "geometry" in kwargs.keys():
            search_result = search_result.crunch(
                FilterOverlap({"intersects": True}), geometry=kwargs.pop("geometry")
            )
        # Filter by cloudCover
        if "cloudCover" in kwargs.keys():
            search_result = search_result.crunch(
                FilterProperty(
                    {"cloudCover": kwargs.pop("cloudCover"), "operator": "lt"}
                )
            )
        # Filter by other properties
        skip_eodag_internal_parameters = [
            "auth",
            "raise_errors",
            "productType",
            "locations",
            "start",
            "end",
            "geom",
        ]
        for property_key, property_value in kwargs.items():
            if property_key not in skip_eodag_internal_parameters:
                search_result = search_result.crunch(
                    FilterProperty({property_key: property_value, "operator": "eq"})
                )

        # restore plugin._request
        self._request = stacapi_request

        return search_result.data, len(search_result)
