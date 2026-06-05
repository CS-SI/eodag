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
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from eodag.api.product import EOProduct
from eodag.api.search_result import RawSearchResult
from eodag.plugins.search.qssearch import QueryStringSearch

if TYPE_CHECKING:
    from eodag.config import PluginConfig

logger = logging.getLogger("eodag.search.geodes")


class EumetsatDsSearch(QueryStringSearch):
    """``EumetsatDsSearch`` is an extension of :class:`~eodag.plugins.search.qssearch.QueryStringSearch`."""

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(EumetsatDsSearch, self).__init__(provider, config)

    def normalize_results(
        self, results: RawSearchResult, **kwargs: Any
    ) -> list[EOProduct]:
        """Build EOProducts from provider results"""
        # Post process assets
        processed_results: list[EOProduct] = super().normalize_results(
            results, **kwargs
        )
        for index in range(0, len(processed_results)):
            result = processed_results[index]
            if hasattr(result, "assets"):
                for name, asset in result.assets.items():
                    if "type" in asset:
                        asset["eumesat_ds:type"] = asset["type"]
                        del asset["type"]
                    if "mediaType" in asset:
                        asset["type"] = asset["mediaType"]
                        del asset["mediaType"]
                    result.assets[name] = asset
            processed_results[index] = result

        return processed_results
