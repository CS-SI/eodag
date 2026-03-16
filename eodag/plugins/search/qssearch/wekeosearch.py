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
from typing import TYPE_CHECKING, Any

from .postjsonsearch import PostJsonSearch
from .stacsearch import StacSearch

if TYPE_CHECKING:
    from eodag.config import PluginConfig

logger = logging.getLogger("eodag.search.qssearch.wekeosearch")


class WekeoSearch(StacSearch, PostJsonSearch):
    """A specialisation of a :class:`~eodag.plugins.search.qssearch.PostJsonSearch` that uses
    generic STAC configuration for queryables (inherited from :class:`~eodag.plugins.search.qssearch.StacSearch`).
    """

    def __init__(self, provider: str, config: PluginConfig) -> None:
        PostJsonSearch.__init__(self, provider, config)

    def build_query_string(
        self, collection: str, query_dict: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        """Build The query string using the search parameters"""
        return PostJsonSearch.build_query_string(self, collection, query_dict)


__all__ = ["WekeoSearch"]
