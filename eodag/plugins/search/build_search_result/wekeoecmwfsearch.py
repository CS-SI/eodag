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
from typing import Any
from urllib.parse import quote_plus

import orjson

from eodag.api.product import EOProduct
from eodag.api.search_result import RawSearchResult

from ..preparesearch import PreparedSearch
from ..qssearch import QueryStringSearch
from ._utils import ecmwf_format
from .ecmwfsearch import ECMWFSearch

logger = logging.getLogger("eodag.search.build_search_result.wekeoecmwfsearch")


class WekeoECMWFSearch(ECMWFSearch):
    """
    WekeoECMWFSearch search plugin.

    This plugin, which inherits from :class:`~eodag.plugins.search.build_search_result.ECMWFSearch`,
    performs a POST request and uses its result to build a single :class:`~eodag.api.search_result.SearchResult`
    object. In contrast to ECMWFSearch or MeteoblueSearch, the products are only build with information
    returned by the provider.

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

    def normalize_results(
        self, results: RawSearchResult, **kwargs: Any
    ) -> list[EOProduct]:
        """Build :class:`~eodag.api.product._product.EOProduct` from provider result

        :param results: Raw provider result as single dict in list
        :param kwargs: Search arguments
        :returns: list of single :class:`~eodag.api.product._product.EOProduct`
        """

        if kwargs.get("id") and "ORDERABLE" not in kwargs["id"]:
            # id is order id (only letters and numbers) -> use parent normalize results
            return super().normalize_results(results, **kwargs)

        # formating of eodag:order_link requires access to the collection value.
        results.data = [
            {**result, **results.collection_def_params} for result in results
        ]

        normalized = QueryStringSearch.normalize_results(self, results, **kwargs)

        if not normalized:
            return normalized

        # remove unwanted query params
        excluded_query_params = getattr(self.config, "remove_from_query", [])
        filtered_query_params = {
            k: v
            for k, v in results.query_params.items()
            if k not in excluded_query_params
        }
        for product in normalized:
            properties = {**product.properties, **results.query_params}
            properties["_dc_qs"] = quote_plus(orjson.dumps(filtered_query_params))
            product.properties = {ecmwf_format(k): v for k, v in properties.items()}

            # update product and title the same way as in parent class
            splitted_id = product.properties.get("title", "").split("-")
            dataset = "_".join(splitted_id[:-1])
            query_hash = splitted_id[-1]
            product.properties["title"] = product.properties["id"] = (
                (product.collection or dataset or self.provider).upper()
                + "_ORDERABLE_"
                + query_hash
            )

        return normalized

    def do_search(
        self, prep: PreparedSearch = PreparedSearch(limit=None), **kwargs: Any
    ) -> RawSearchResult:
        """Should perform the actual search request.

        :param args: arguments to be used in the search
        :param kwargs: keyword arguments to be used in the search
        :return: list containing the results from the provider in json format
        """
        if "id" in kwargs and "ORDERABLE" not in kwargs["id"]:
            # id is order id (only letters and numbers) -> use parent normalize results.
            # No real search. We fake it all, then check order status using given id
            raw_search_results = RawSearchResult([{}])
            raw_search_results.search_params = kwargs
            raw_search_results.query_params = (
                prep.query_params if hasattr(prep, "query_params") else {}
            )
            raw_search_results.collection_def_params = (
                prep.collection_def_params
                if hasattr(prep, "collection_def_params")
                else {}
            )
            return raw_search_results
        else:
            return QueryStringSearch.do_search(self, prep, **kwargs)
