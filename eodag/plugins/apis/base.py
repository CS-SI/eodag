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

from typing import TYPE_CHECKING

from eodag.plugins.download.base import Download
from eodag.plugins.search.base import Search

if TYPE_CHECKING:
    from eodag.config import PluginConfig


class Api(Search, Download):
    """Plugins API Base plugin

    An Api plugin inherits the methods from Search and Download plugins.

    There are three methods that it must implement:

    - ``query``: search for products
    - ``download``: download a single :class:`~eodag.api.product._product.EOProduct`
    - ``download_all``: download multiple products from a :class:`~eodag.api.search_result.SearchResult`

    Download methods follow the asset selection, output layout and cache contract
    of :class:`~eodag.plugins.download.base.Download`. Store remote URLs in asset
    ``href`` fields and downloaded filesystem paths in ``file:local_path``. Persist
    per-asset JSON statements through ``set_statements`` rather than writing legacy
    product records or updating deprecated product location properties.

    :param provider: An EODAG provider name
    :type provider: str
    :param config: An EODAG plugin configuration
    :type config: dict[str, Any]
    """

    @classmethod
    def normalize_config(cls, provider: str, config: PluginConfig) -> PluginConfig:
        """Normalize API plugin config defaults."""
        return Download.normalize_config(provider, config)
