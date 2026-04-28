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

import hashlib
import logging
from typing import Any
from urllib.parse import quote_plus, unquote_plus

import geojson
import orjson

from eodag.api.product import EOProduct
from eodag.api.product.metadata_mapping import NOT_AVAILABLE, properties_from_json
from eodag.api.search_result import RawSearchResult
from eodag.utils import dict_items_recursive_sort

from ..preparesearch import PreparedSearch
from ..qssearch import QueryStringSearch
from ._utils import END, START, ecmwf_format
from .ecmwfsearch import ECMWFSearch

logger = logging.getLogger("eodag.search.build_search_result.meteobluesearch")


class MeteoblueSearch(ECMWFSearch):
    """MeteoblueSearch search plugin.

    This plugin, which inherits from :class:`~eodag.plugins.search.build_search_result.ECMWFSearch`,
    performs a POST request and uses its result to build a single :class:`~eodag.api.search_result.SearchResult`
    object.

    The available configuration parameters are inherited from parent classes, with some a particularity
    for pagination for this plugin.

    :param provider: An eodag providers configuration dictionary
    :param config: Search plugin configuration:

        * :attr:`~eodag.config.PluginConfig.pagination` (:class:`~eodag.config.PluginConfig.Pagination`)
          (**mandatory**): The configuration of how the pagination is done on the provider. For
          this plugin it has the node:

          * :attr:`~eodag.config.PluginConfig.Pagination.next_page_query_obj` (``str``): The
            additional parameters needed to perform search. These parameters won't be included in
            the result. This must be a json dict formatted like ``{{"foo":"bar"}}`` because it
            will be passed to a :meth:`str.format` method before being loaded as json.
    """

    def collect_search_urls(
        self,
        prep: PreparedSearch = PreparedSearch(),
        **kwargs: Any,
    ) -> tuple[list[str], int]:
        """Wraps PostJsonSearch.collect_search_urls to force product count to 1

        :param prep: :class:`~eodag.plugins.search.PreparedSearch` object containing information for the search
        :param kwargs: keyword arguments used in the search
        :return: list of search url and number of results
        """
        urls, _ = super().collect_search_urls(prep, **kwargs)
        return urls, 1

    def do_search(
        self, prep: PreparedSearch = PreparedSearch(limit=None), **kwargs: Any
    ) -> RawSearchResult:
        """Perform the actual search request, and return result in a single element.

        :param prep: :class:`~eodag.plugins.search.PreparedSearch` object containing information for the search
        :param kwargs: keyword arguments to be used in the search
        :return: list containing the results from the provider in json format
        """

        prep.url = prep.search_urls[0]
        prep.info_message = f"Sending search request: {prep.url}"
        prep.exception_message = (
            f"Skipping error while searching for {self.provider}"
            f" {self.__class__.__name__} instance"
        )
        response = self._request(prep)
        raw_search_results = RawSearchResult([response.json()])
        raw_search_results.search_params = kwargs

        raw_search_results.query_params = prep.query_params
        raw_search_results.collection_def_params = prep.collection_def_params
        return raw_search_results

    def build_query_string(
        self, collection: str, query_dict: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        """Build The query string using the search parameters

        :param collection: collection id
        :param query_dict: keyword arguments to be used in the query string
        :return: formatted query params and encode query string
        """
        return QueryStringSearch.build_query_string(self, collection, query_dict)

    def normalize_results(self, results, **kwargs):
        """Build :class:`~eodag.api.product._product.EOProduct` from provider result

        :param results: Raw provider result as single dict in list
        :param kwargs: Search arguments
        :returns: list of single :class:`~eodag.api.product._product.EOProduct`
        """

        collection = kwargs.get("collection")

        result = results[0]

        # datacube query string got from previous search
        _dc_qs = kwargs.pop("_dc_qs", None)
        if _dc_qs is not None:
            qs = unquote_plus(unquote_plus(_dc_qs))
            sorted_unpaginated_query_params = geojson.loads(qs)
        else:
            next_page_query_obj = orjson.loads(
                self.config.pagination["next_page_query_obj"].format()
            )
            unpaginated_query_params = {
                k: v
                for k, v in results.query_params.items()
                if (k, v) not in next_page_query_obj.items()
            }
            # query hash, will be used to build a product id
            sorted_unpaginated_query_params = dict_items_recursive_sort(
                unpaginated_query_params
            )

        # use all available query_params to parse properties
        result = dict(
            result,
            **sorted_unpaginated_query_params,
            qs=sorted_unpaginated_query_params,
        )

        qs = geojson.dumps(sorted_unpaginated_query_params)

        query_hash = hashlib.sha1(str(qs).encode("UTF-8")).hexdigest()

        # update result with collection_def_params and search args if not None (and not auth)
        kwargs.pop("auth", None)
        result.update(results.collection_def_params)
        result = dict(result, **{k: v for k, v in kwargs.items() if v is not None})

        # parse properties
        parsed_properties = properties_from_json(
            result,
            self.config.metadata_mapping,
            discovery_config=getattr(self.config, "discover_metadata", {}),
        )

        properties = {ecmwf_format(k): v for k, v in parsed_properties.items()}
        # collection alias (required by opentelemetry-instrumentation-eodag)
        if alias := getattr(self.config, "collection_config", {}).get("alias"):
            collection = alias

        def slugify(date_str: str) -> str:
            return date_str.split("T")[0].replace("-", "")

        # build product id
        product_id = (collection or self.provider).upper()

        start = properties.get(START, NOT_AVAILABLE)
        end = properties.get(END, NOT_AVAILABLE)

        if start != NOT_AVAILABLE:
            product_id += f"_{slugify(start)}"
            if end != NOT_AVAILABLE:
                product_id += f"_{slugify(end)}"

        product_id += f"_{query_hash}"

        properties["id"] = properties["title"] = product_id

        # used by server mode to generate eodag:download_link href
        properties["_dc_qs"] = quote_plus(qs)

        product = EOProduct(
            provider=self.provider,
            collection=collection,
            properties=properties,
        )
        product.assets.update(
            self.get_assets_from_mapping(results, product, collection)
        )

        return [
            product,
        ]


__all__ = ["MeteoblueSearch"]
