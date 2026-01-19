# -*- coding: utf-8 -*-
# Copyright 2025, CS GROUP - France, http://www.c-s.fr
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

import re
from typing import TYPE_CHECKING

from .base import AssetPatterns, DatasetDriver

if TYPE_CHECKING:
    from eodag.api.product._product import EOProduct


class Sentinel1Driver(DatasetDriver):
    """Driver for Sentinel1 products"""

    #: pattern to match data-role keys
    DATA_PATTERN = re.compile(r"[vh]{2}", re.IGNORECASE)

    #: list of patterns to replace in asset keys
    REPLACE_PATTERNS = [
        (re.compile(r"s1a?", re.IGNORECASE), ""),
        (re.compile(r"grd", re.IGNORECASE), ""),
        (re.compile(r"slc", re.IGNORECASE), ""),
        (re.compile(r"ocn", re.IGNORECASE), ""),
        (re.compile(r"(?<![A-Za-z])iw(?![A-Za-z])", re.IGNORECASE), ""),
        (re.compile(r"(?<![A-Za-z])ew(?![A-Za-z])", re.IGNORECASE), ""),
        (re.compile(r"wv", re.IGNORECASE), ""),
        (re.compile(r"(?<![A-Za-z])sm(?![A-Za-z])", re.IGNORECASE), ""),
        (re.compile(r"(?<![A-Za-z])raw([-_]s)?(?![A-Za-z])", re.IGNORECASE), ""),
        (re.compile(r"[t?0-9]{3,}", re.IGNORECASE), ""),
        (re.compile(r"\b[0-9A-F]{3,}\b", re.IGNORECASE), ""),
        (re.compile(r"-+"), "-"),
        (re.compile(r"-+\."), "."),
        (re.compile(r"_+"), "_"),
        (re.compile(r"_+\."), "."),
    ]

    #: list of patterns to match asset keys and roles
    ASSET_KEYS_PATTERNS_ROLES: list[AssetPatterns] = [
        # data
        {
            "pattern": re.compile(
                r"^.*?([vh]{2}).*\.(?:jp2|tiff?|dat)(?:\?.*)?$", re.IGNORECASE
            ),
            "roles": ["data"],
        },
        # metadata
        {
            "pattern": re.compile(
                r"^(?:.*[/\\])?([^/\\]+)(\.xml|\.xsd|\.safe|\.json)(?:\?.*)?$",
                re.IGNORECASE,
            ),
            "roles": ["metadata"],
        },
        # thumbnail
        {
            "pattern": re.compile(
                r"^(?:.*[/\\])?(thumbnail)(\.jpe?g|\.png)(?:\?.*)?$", re.IGNORECASE
            ),
            "roles": ["thumbnail"],
        },
        # quicklook
        {
            "pattern": re.compile(
                r"^(?:.*[/\\])?([^/\\]+-ql|preview|quick-?look)(\.jpe?g|\.png)(?:\?.*)?$",
                re.IGNORECASE,
            ),
            "roles": ["overview"],
        },
        # default
        {
            "pattern": re.compile(r"^(?:.*[/\\])?([^/\\?]+)(?:\?.*)?$"),
            "roles": ["auxiliary"],
        },
    ]

    def _normalize_key(self, key: str, eo_product: EOProduct) -> str:
        if self.DATA_PATTERN.fullmatch(key):
            return key.upper()

        key = super()._normalize_key(key, eo_product)

        for pattern, replacement in self.REPLACE_PATTERNS:
            key = pattern.sub(replacement, key)

        return super()._normalize_key(key, eo_product)

    @staticmethod
    def match(product: EOProduct, by: str = "*") -> bool:
        """
        Resolve if given product matches with current driver.

        :param  product: product as reference use to extract criteria
        :param  by: specific criteria match
        :return: ``True`` if given product matches with current driver, else ``False``
        """
        if (
            by == "collection"
            and hasattr(product, "collection")
            and isinstance(product.collection, str)
        ):
            collection = product.collection.lower()
            if collection.startswith("s1_sar_"):
                return True

        if (
            by == "properties"
            and hasattr(product, "properties")
            and isinstance(product.properties, dict)
        ):

            constellation = product.properties.get("constellation", None)
            if isinstance(constellation, str):
                constellation = re.sub(r"([^a-z0-9]+)", "", constellation.lower())
                if constellation == "sentinel1":
                    return True

            platform = product.properties.get("platform", None)
            if platform is not None:
                platform = re.sub(r"([^a-z0-9]+)", "", platform.lower())
                if re.match("s1[a-z]", platform):
                    return True

        return False
