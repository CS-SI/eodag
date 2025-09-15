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
from typing import TYPE_CHECKING, Annotated, Any, Optional
from unittest import mock

import geojson
from pydantic.fields import FieldInfo

from eodag.api.product.metadata_mapping import get_metadata_path_value
from eodag.api.search_result import SearchResult
from eodag.plugins.crunch.filter_date import FilterDate
from eodag.plugins.crunch.filter_overlap import FilterOverlap
from eodag.plugins.crunch.filter_property import FilterProperty
from eodag.plugins.search import PreparedSearch
from eodag.plugins.search.qssearch import StacSearch
from eodag.types.queryables import Queryables
from eodag.utils import HTTP_REQ_TIMEOUT, MockResponse
from eodag.utils.stac_reader import fetch_stac_collections, fetch_stac_items

if TYPE_CHECKING:
    from eodag.api.product import EOProduct
    from eodag.config import PluginConfig


logger = logging.getLogger("eodag.search.static_stac_search")


class StaticStacSearch(StacSearch):
    """Static STAC Catalog search plugin

    This plugin first loads all STAC items found in the catalog (or item), and converts them to
    EOProducts using :class:`~eodag.plugins.search.qssearch.StacSearch`.
    Then it uses crunchers to only keep products matching query parameters.

    The plugin inherits the configuration parameters from :class:`~eodag.plugins.search.qssearch.PostJsonSearch`
    (via the :class:`~eodag.plugins.search.qssearch.StacSearch` inheritance) with the following particularities:

    :param provider: provider name
    :param config: Search plugin configuration:

        * :attr:`~eodag.config.PluginConfig.api_endpoint` (``str``) (**mandatory**): path to the catalog or item;
          in contrast to the api_endpoint for other plugin types this can be a url or local system path.
        * :attr:`~eodag.config.PluginConfig.max_connections` (``int``): Maximum number of concurrent
          connections for HTTP requests; default: ``100``
        * :attr:`~eodag.config.PluginConfig.timeout` (``int``): Timeout in seconds for each
          internal HTTP request; default: ``5``

    """

    def __init__(self, provider: str, config: PluginConfig) -> None:
        # prevent search parameters from being queried when they are known in the configuration or not
        for param, mapping in config.metadata_mapping.items():
            # only keep one queryable to allow the mock search request
            if param != "productType":
                config.metadata_mapping[param] = get_metadata_path_value(mapping)
        config.discover_metadata["auto_discovery"] = False
        # there is no endpoint for fetching queryables with a static search
        config.discover_queryables["fetch_url"] = None
        config.discover_queryables["product_type_fetch_url"] = None

        super(StaticStacSearch, self).__init__(provider, config)
        self.config.__dict__.setdefault("max_connections", 100)
        self.config.__dict__.setdefault("timeout", HTTP_REQ_TIMEOUT)
        self.config.__dict__.setdefault("ssl_verify", True)
        self.config.__dict__.setdefault("pagination", {})
        self.config.__dict__["pagination"].setdefault(
            "total_items_nb_key_path", "$.null"
        )
        self.config.__dict__["pagination"].setdefault("max_items_per_page", -1)
        # disable product types discovery by default (if endpoints equals to STAC API default)
        if (
            getattr(self.config, "discover_product_types", {}).get("fetch_url")
            == "{api_endpoint}/../collections"
        ):
            self.config.discover_product_types = {}

    def discover_product_types(self, **kwargs: Any) -> Optional[dict[str, Any]]:
        """Fetch product types list from a static STAC Catalog provider using `discover_product_types` conf

        :returns: configuration dict containing fetched product types information
        """
        unformatted_fetch_url = self.config.discover_product_types.get("fetch_url")
        if unformatted_fetch_url is None:
            return None
        fetch_url = unformatted_fetch_url.format(**self.config.__dict__)

        collections = fetch_stac_collections(
            fetch_url,
            collection=kwargs.get("q"),
            max_connections=self.config.max_connections,
            timeout=int(self.config.timeout),
            ssl_verify=self.config.ssl_verify,
        )
        if "q" in kwargs:
            collections = [c for c in collections if c["id"] == kwargs["q"]]
        collections_mock_response = {"collections": collections}

        # discover_product_types on mocked QueryStringSearch._request
        with mock.patch(
            "eodag.plugins.search.qssearch.QueryStringSearch._request",
            autospec=True,
            return_value=MockResponse(collections_mock_response, 200),
        ):
            conf_update_dict = super(StaticStacSearch, self).discover_product_types(
                **kwargs
            )

        return conf_update_dict

    def discover_queryables(
        self, **kwargs: Any
    ) -> dict[str, Annotated[Any, FieldInfo]]:
        """Set static available queryables for :class:`~eodag.plugins.search.static_stac_search.StaticStacSearch`
        search plugin

        :param kwargs: additional filters for queryables (`productType` and other search
                       arguments)
        :returns: queryable parameters dict
        """
        return {
            "productType": Queryables.get_with_default(
                "productType", kwargs.get("productType")
            ),
            "id": Queryables.get_with_default("id", kwargs.get("id")),
            "start": Queryables.get_with_default(
                "start", kwargs.get("start") or kwargs.get("startTimeFromAscendingNode")
            ),
            "end": Queryables.get_with_default(
                "end",
                kwargs.get("end") or kwargs.get("completionTimeFromAscendingNode"),
            ),
            "geom": Queryables.get_with_default(
                "geom",
                kwargs.get("geom") or kwargs.get("geometry") or kwargs.get("area"),
            ),
        }

    def query(
        self,
        prep: PreparedSearch = PreparedSearch(),
        **kwargs: Any,
    ) -> tuple[list[EOProduct], Optional[int]]:
        """Perform a search on a static STAC Catalog"""

        # only return 1 page if pagination is disabled
        if (
            prep.page
            and prep.page > 1
            and prep.items_per_page is not None
            and prep.items_per_page <= 0
        ):
            return ([], 0) if prep.count else ([], None)

        product_type = kwargs.get("productType", prep.product_type)
        # provider product type specific conf
        self.product_type_def_params = (
            self.get_product_type_def_params(product_type, format_variables=kwargs)
            if product_type is not None
            else {}
        )

        for collection in self.get_collections(prep, **kwargs):
            # skip empty collection if one is required in api_endpoint
            if "{collection}" in self.config.api_endpoint and not collection:
                continue
            search_endpoint = self.config.api_endpoint.rstrip("/").format(
                collection=collection
            )

        features = fetch_stac_items(
            search_endpoint,
            recursive=True,
            max_connections=self.config.max_connections,
            timeout=int(self.config.timeout),
            ssl_verify=self.config.ssl_verify,
        )
        nb_features = len(features)
        feature_collection = geojson.FeatureCollection(features)

        # query on mocked StacSearch._request
        with mock.patch(
            "eodag.plugins.search.qssearch.StacSearch._request",
            autospec=True,
            return_value=MockResponse(feature_collection, 200),
        ):
            eo_products, _ = super(StaticStacSearch, self).query(
                PreparedSearch(items_per_page=nb_features, page=1, count=True), **kwargs
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
        geometry = kwargs.pop("geometry", None)
        if geometry:
            search_result = search_result.crunch(
                FilterOverlap({"intersects": True}), geometry=geometry
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

        return (
            (search_result.data, len(search_result))
            if prep.count
            else (search_result.data, None)
        )
