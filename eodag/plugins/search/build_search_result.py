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
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus, unquote_plus

import geojson
import orjson
from jsonpath_ng import Fields

from eodag.api.product import EOProduct
from eodag.api.product.metadata_mapping import properties_from_json
from eodag.plugins.search.qssearch import PostJsonSearch
from eodag.utils import dict_items_recursive_sort

logger = logging.getLogger("eodag.search.build_search_result")


class BuildPostSearchResult(PostJsonSearch):
    """BuildPostSearchResult search plugin.

    This plugin, which inherits from :class:`~eodag.plugins.search.qssearch.PostJsonSearch`,
    performs a POST request and uses its result to build a single :class:`~eodag.api.search_result.SearchResult`
    object.

    The available configuration parameters inherits from parent classes, with particularly
    for this plugin:

        - **api_endpoint**: (mandatory) The endpoint of the provider's search interface

        - **pagination**: The configuration of how the pagination is done
          on the provider. It is a tree with the following nodes:

          - *next_page_query_obj*: (optional) The additional parameters needed to perform
            search. These paramaters won't be included in result. This must be a json dict
            formatted like `{{"foo":"bar"}}` because it will be passed to a `.format()`
            method before being loaded as json.

    :param provider: An eodag providers configuration dictionary
    :type provider: dict
    :param config: Path to the user configuration file
    :type config: str
    """

    def count_hits(
        self, count_url: Optional[str] = None, result_type: Optional[str] = None
    ) -> int:
        """Count method that will always return 1."""
        return 1

    def collect_search_urls(
        self,
        page: Optional[int] = None,
        items_per_page: Optional[int] = None,
        count: bool = True,
        **kwargs: Any,
    ) -> Tuple[List[str], int]:
        """Wraps PostJsonSearch.collect_search_urls to force product count to 1"""
        urls, _ = super(BuildPostSearchResult, self).collect_search_urls(
            page=page, items_per_page=items_per_page, count=count, **kwargs
        )
        return urls, 1

    def do_search(self, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        """Perform the actual search request, and return result in a single element."""
        search_url = self.search_urls[0]
        response = self._request(
            search_url,
            info_message=f"Sending search request: {search_url}",
            exception_message=f"Skipping error while searching for {self.provider} "
            f"{self.__class__.__name__} instance:",
        )
        return [response.json()]

    def normalize_results(
        self, results: List[Dict[str, Any]], **kwargs: Any
    ) -> List[EOProduct]:
        """Build :class:`~eodag.api.product._product.EOProduct` from provider result

        :param results: Raw provider result as single dict in list
        :type results: list
        :param kwargs: Search arguments
        :type kwargs: Union[int, str, bool, dict, list]
        :returns: list of single :class:`~eodag.api.product._product.EOProduct`
        :rtype: list
        """
        product_type = kwargs.get("productType")

        result = results[0]

        # datacube query string got from previous search
        _dc_qs = kwargs.pop("_dc_qs", None)
        if _dc_qs is not None:
            qs = unquote_plus(unquote_plus(_dc_qs))
            unpaginated_query_params = sorted_unpaginated_query_params = geojson.loads(
                qs
            )
        else:
            # update result with query parameters without pagination (or search-only params)
            if isinstance(
                self.config.pagination["next_page_query_obj"], str
            ) and hasattr(self, "query_params_unpaginated"):
                unpaginated_query_params = self.query_params_unpaginated
            elif isinstance(self.config.pagination["next_page_query_obj"], str):
                next_page_query_obj = orjson.loads(
                    self.config.pagination["next_page_query_obj"].format()
                )
                unpaginated_query_params = {
                    k: v[0] if (isinstance(v, list) and len(v) == 1) else v
                    for k, v in self.query_params.items()
                    if (k, v) not in next_page_query_obj.items()
                }
            else:
                unpaginated_query_params = self.query_params

            # query hash, will be used to build a product id
            sorted_unpaginated_query_params = dict_items_recursive_sort(
                unpaginated_query_params
            )
            qs = geojson.dumps(sorted_unpaginated_query_params)

        query_hash = hashlib.sha1(str(qs).encode("UTF-8")).hexdigest()

        result = dict(result, **unpaginated_query_params)

        # update result with search args if not None (and not auth)
        kwargs.pop("auth", None)
        result = dict(result, **{k: v for k, v in kwargs.items() if v is not None})

        # parse porperties
        parsed_properties = properties_from_json(
            result,
            self.config.metadata_mapping,
            discovery_config=getattr(self.config, "discover_metadata", {}),
        )

        if not product_type:
            product_type = parsed_properties.get("productType", None)

        # build product id
        id_prefix = (product_type or self.provider).upper()
        product_id = "%s_%s_%s" % (
            id_prefix,
            parsed_properties["startTimeFromAscendingNode"]
            .split("T")[0]
            .replace("-", ""),
            query_hash,
        )
        parsed_properties["id"] = parsed_properties["title"] = product_id

        # update downloadLink
        parsed_properties["downloadLink"] += f"?{qs}"
        parsed_properties["_dc_qs"] = quote_plus(qs)

        # parse metadata needing downloadLink
        for param, mapping in self.config.metadata_mapping.items():
            if Fields("downloadLink") in mapping:
                parsed_properties.update(
                    properties_from_json(parsed_properties, {param: mapping})
                )

        # use product_type_config as default properties
        parsed_properties = dict(
            getattr(self.config, "product_type_config", {}),
            **parsed_properties,
        )

        product = EOProduct(
            provider=self.provider,
            productType=product_type,
            properties=parsed_properties,
        )

        return [
            product,
        ]
