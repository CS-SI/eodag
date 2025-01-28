# -*- coding: utf-8 -*-
# Copyright 2021, CS GROUP - France, http://www.c-s.fr
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

from eodag.api.product.drivers.base import AssetPatterns, DatasetDriver

if TYPE_CHECKING:
    from eodag.api.product._product import EOProduct


class Sentinel2Driver(DatasetDriver):
    """Driver for Sentinel2 products"""

    #: Band keys associated with their default Ground Sampling Distance (GSD)
    BANDS_DEFAULT_GSD = {
        "10M": ("B02", "B03", "B04", "B08", "TCI"),
        "20M": ("B05", "B06", "B07", "B11", "B12", "B8A"),
        "60M": ("B01", "B09", "B10"),
    }

    #: list of patterns to match asset keys and roles
    ASSET_KEYS_PATTERNS_ROLES: list[AssetPatterns] = [
        # masks
        {
            "pattern": re.compile(r"^.*?(MSK_[^/\\]+)\.(?:jp2|tiff?)$", re.IGNORECASE),
            "roles": ["data-mask"],
        },
        # visual
        {
            "pattern": re.compile(
                r"^.*?(TCI)(_[0-9]+m)?\.(?:jp2|tiff?)$", re.IGNORECASE
            ),
            "roles": ["visual"],
        },
        # bands
        {
            "pattern": re.compile(
                r"^.*?([A-Z]+[0-9]*[A-Z]?)(_[0-9]+m)?\.(?:jp2|tiff?)$", re.IGNORECASE
            ),
            "roles": ["data"],
        },
        # metadata
        {
            "pattern": re.compile(
                r"^(?:.*[/\\])?([^/\\]+)(\.xml|\.xsd|\.safe|\.json)$", re.IGNORECASE
            ),
            "roles": ["metadata"],
        },
        # thumbnail
        {
            "pattern": re.compile(
                r"^(?:.*[/\\])?(thumbnail)(\.jpe?g|\.png)$", re.IGNORECASE
            ),
            "roles": ["thumbnail"],
        },
        # quicklook
        {
            "pattern": re.compile(
                r"^(?:.*[/\\])?[^/\\]+(-ql|preview|quick-?look)(\.jpe?g|\.png)$",
                re.IGNORECASE,
            ),
            "roles": ["overview"],
        },
        # default
        {"pattern": re.compile(r"^(?:.*[/\\])?([^/\\]+)$"), "roles": ["auxiliary"]},
    ]

    def _normalize_key(self, key: str, eo_product: EOProduct) -> str:
        upper_key = key.upper()
        # check if key matched any normalized
        for res in self.BANDS_DEFAULT_GSD:
            if res in upper_key:
                for norm_key in self.BANDS_DEFAULT_GSD[res]:
                    if norm_key in upper_key:
                        return norm_key

        return super()._normalize_key(key, eo_product)
