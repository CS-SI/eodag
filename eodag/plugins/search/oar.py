# -*- coding: utf-8 -*-
# Copyright 2026, CS GROUP - France, https://www.csgroup.eu/
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
from typing import TYPE_CHECKING, Any, Optional, cast

from eodag.plugins.search import PreparedSearch
from eodag.plugins.search.qssearch import QueryStringSearch, StacSearch

if TYPE_CHECKING:
    from eodag.config import PluginConfig

logger = logging.getLogger("eodag.search.oar")


class OARSearch(QueryStringSearch):
    """OGC API - Records search plugin.

    Search requests use the standard query-string GET implementation from
    :class:`~eodag.plugins.search.qssearch.QueryStringSearch`, while queryables
    discovery reuses :class:`~eodag.plugins.search.qssearch.StacSearch`.
    """

    def __init__(self, provider: str, config: "PluginConfig") -> None:
        # OGC API - Records defaults (20-004r1, Search): bbox, datetime, limit,
        # plus Records parameters q, type, ids and externalIds.
        config.__dict__.setdefault("result_type", "json")
        config.__dict__.setdefault("results_entry", "features")

        config.__dict__.setdefault("pagination", {})
        config.pagination.setdefault("total_items_nb_key_path", "$.numberMatched")

        config.__dict__.setdefault("sort", {})
        config.sort.setdefault("sort_by_tpl", "&sortby={sort_order}{sort_param}")
        config.sort.setdefault("sort_order_mapping", {})
        config.sort["sort_order_mapping"].setdefault("ascending", "+")
        config.sort["sort_order_mapping"].setdefault("descending", "-")

        config.__dict__.setdefault("discover_queryables", {})
        config.discover_queryables.setdefault(
            "fetch_url", "{api_endpoint}/../queryables"
        )
        config.discover_queryables.setdefault(
            "collection_fetch_url",
            "{api_endpoint}/../collections/{provider_collection}/queryables",
        )
        config.discover_queryables.setdefault("result_type", "json")
        config.discover_queryables.setdefault("results_entry", "$.properties[*]")

        config.__dict__.setdefault("metadata_mapping", {})
        config.metadata_mapping.setdefault("q", ["q={q}", "$.properties.title"])
        config.metadata_mapping.setdefault("type", ["type={type#csv_list}", "$.type"])
        config.metadata_mapping.setdefault("ids", ["ids={ids#csv_list}", "$.id"])
        config.metadata_mapping.setdefault(
            "externalIds",
            ["externalIds={externalIds#csv_list}", "$.properties.externalIds"],
        )
        config.metadata_mapping.setdefault("bbox", ["bbox={bbox}", "$.bbox"])
        config.metadata_mapping.setdefault(
            "datetime", ["datetime={datetime}", "$.properties.datetime"]
        )
        config.metadata_mapping.setdefault("limit", ["limit={limit}", "$.null"])

        super().__init__(provider, config)

    def collect_search_urls(
        self,
        prep: PreparedSearch = PreparedSearch(),
        **kwargs: Any,
    ) -> tuple[list[str], Optional[int]]:
        """Handle OGC API - Records specificities, then delegate collect_search_urls to
        :class:`~eodag.plugins.search.qssearch.QueryStringSearch`."""

        if "id" in kwargs and "collection" in kwargs:
            url = (
                self.config.api_endpoint.format(_collection=kwargs["collection"])
                + "/"
                + kwargs.pop("id")
            )
            return [url], None

        return super().collect_search_urls(prep, **kwargs)

    def extract_results_from_response(
        self, resp_as_json: dict[str, Any], **kwargs: Any
    ) -> list[Any]:
        """Extract results list from a JSON response using the ``results_entry`` configuration"""
        if "id" in kwargs and "collection" in kwargs:
            return [resp_as_json]
        return super().extract_results_from_response(resp_as_json, **kwargs)

    def discover_queryables(self, **kwargs: Any):
        """Delegate queryables discovery to :class:`~eodag.plugins.search.qssearch.StacSearch`."""

        return StacSearch.discover_queryables(cast(Any, self), **kwargs)
