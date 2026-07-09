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
from eodag.utils.exceptions import MisconfiguredError

if TYPE_CHECKING:
    from eodag.config import PluginConfig

logger = logging.getLogger("eodag.search.oar")


class OARSearch(QueryStringSearch):
    """OGC API - Records Core search plugin.

    Search requests use the standard query-string GET implementation from
    :class:`~eodag.plugins.search.qssearch.QueryStringSearch`, while queryables
    discovery reuses :class:`~eodag.plugins.search.qssearch.StacSearch`.

    .. seealso::
        - OGC API - Records Core specification: https://docs.ogc.org/is/20-004r1/20-004r1.html
    """

    @classmethod
    def normalize_config(cls, provider: str, config: "PluginConfig") -> "PluginConfig":
        """Normalize and validate the plugin configuration for an OGC API Records provider."""
        if not hasattr(config, "api_endpoint"):
            raise MisconfiguredError(
                f"Missing required configuration 'api_endpoint' for provider '{provider}'"
            )
        if not config.api_endpoint.rstrip("/").endswith("/items"):
            api_root_endpoint = config.api_endpoint.rstrip("/")
            config.api_endpoint = api_root_endpoint + "/collections/{_collection}/items"
        else:
            try:
                api_root_endpoint = config.api_endpoint.rstrip("/").rsplit("/", 3)[0]
            except IndexError:
                raise MisconfiguredError(
                    f"Invalid 'api_endpoint' configuration for provider '{provider}'"
                )

        # Plugin default configuration
        config.__dict__.setdefault("result_type", "json")
        config.__dict__.setdefault("results_entry", "features")

        # Pagination
        config.__dict__.setdefault("pagination", {})
        config.pagination.setdefault(
            "next_page_url_tpl", "{url}?{search}&limit={limit}&offset={next_page_token}"
        )
        config.pagination.setdefault("total_items_nb_key_path", "$.numberMatched")
        config.pagination.setdefault("start_page", 0)
        config.pagination.setdefault("next_page_token_key", "skip")

        # Discover metadata
        config.__dict__.setdefault("discover_metadata", {})
        config.discover_metadata.setdefault("auto_discovery", True)
        config.discover_metadata.setdefault(
            "metadata_pattern", r"^(?!collection)[a-zA-Z0-9_]+$"
        )
        config.discover_metadata.setdefault("search_param", "{metadata}={{{metadata}}}")
        config.discover_metadata.setdefault("metadata_path", "$.properties.*")

        # Discover collections
        config.__dict__.setdefault("discover_collections", {})
        config.discover_collections.setdefault(
            "fetch_url", api_root_endpoint + "/collections"
        )
        config.discover_collections.setdefault("result_type", "json")
        config.discover_collections.setdefault("results_entry", "$.collections[*]")
        config.discover_collections.setdefault("generic_collection_id", "$.id")
        config.discover_collections.setdefault(
            "generic_collection_parsable_properties", {}
        )
        config.discover_collections[
            "generic_collection_parsable_properties"
        ].setdefault("_collection", "$.id")
        config.discover_collections.setdefault(
            "generic_collection_parsable_metadata", {}
        )
        config.discover_collections["generic_collection_parsable_metadata"].setdefault(
            "description", "$.description"
        )
        config.discover_collections["generic_collection_parsable_metadata"].setdefault(
            "keywords", "$.keywords"
        )
        config.discover_collections["generic_collection_parsable_metadata"].setdefault(
            "title", "$.title"
        )
        config.discover_collections["generic_collection_parsable_metadata"].setdefault(
            "extent", "$.extent"
        )

        # Discover queryables
        config.__dict__.setdefault("discover_queryables", {})
        config.discover_queryables.setdefault(
            "fetch_url", api_root_endpoint + "/queryables"
        )
        config.discover_queryables.setdefault(
            "collection_fetch_url",
            api_root_endpoint + "/collections/{provider_collection}/queryables",
        )
        config.discover_queryables.setdefault("result_type", "json")
        config.discover_queryables.setdefault("results_entry", "$.properties[*]")

        # Metadata mapping
        config.__dict__.setdefault("metadata_mapping", {})
        config.metadata_mapping.setdefault("title", "$.properties.title")
        config.metadata_mapping.setdefault("datetime", "$.properties.datetime")
        config.metadata_mapping.setdefault("updated", "$.properties.updated")
        config.metadata_mapping.setdefault(
            "start_datetime",
            [
                None,
                "$.null",
            ],
        )
        config.metadata_mapping.setdefault(
            "end_datetime",
            [
                "datetime={start_datetime#to_iso_utc_datetime}/{end_datetime#to_iso_utc_datetime}",
                "$.null",
            ],
        )
        config.metadata_mapping.setdefault("id", ["null", "$.id"])
        config.metadata_mapping.setdefault(
            "geometry",
            [
                "bbox={geometry#to_bounds_str}",
                "($.geometry.`str()`.`sub(/^None$/, POLYGON((180 -90, 180 90, "
                "-180 90, -180 -90, 180 -90)))`)|($.geometry[*])",
            ],
        )

        return config

    def __init__(self, provider: str, config: "PluginConfig") -> None:
        config = self.normalize_config(provider, config)

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
