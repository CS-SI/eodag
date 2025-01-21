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
from typing import TYPE_CHECKING, Optional

from eodag.api.product.drivers.base import AssetPatterns, DatasetDriver
from eodag.utils.exceptions import AddressNotFound

if TYPE_CHECKING:
    from eodag.api.product._product import EOProduct


class Sentinel2L1C(DatasetDriver):
    """Driver for Sentinel2 L1C product"""

    BAND_FILE_PATTERN_TPL = r"^.+_{band}\.jp2$"
    SPATIAL_RES_PER_BANDS = {
        "10m": ("B02", "B03", "B04", "B08"),
        "20m": ("B05", "B06", "B07", "B11", "B12", "B8A"),
        "60m": ("B01", "B09", "B10"),
        "TCI": ("TCI",),
    }
    BANDS_DEFAULT_GSD = {
        "10m": ("B02", "B03", "B04", "B08", "TCI"),
        "20m": ("B05", "B06", "B07", "B11", "B12", "B8A"),
        "60m": ("B01", "B09", "B10"),
    }

    ASSET_KEYS_PATTERNS_ROLES: list[AssetPatterns] = [
        # masks
        {
            "pattern": re.compile(r"^.*?(MSK_[^/\\]+)\.jp2$", re.IGNORECASE),
            "roles": ["data-mask"],
        },
        # visual
        {
            "pattern": re.compile(r"^.*?(TCI)(_[0-9]+m)?\.jp2$", re.IGNORECASE),
            "roles": ["visual"],
        },
        # bands
        {
            "pattern": re.compile(
                r"^.*?([A-Z]+[0-9]*[A-Z]?)(_[0-9]+m)?\.jp2$", re.IGNORECASE
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
        # quicklook
        {
            "pattern": re.compile(
                r"^(?:.*[/\\])?([^/\\]+-ql|preview)(\.jpg)$", re.IGNORECASE
            ),
            "roles": ["overview"],
        },
        # default
        {"pattern": re.compile(r"^(?:.*[/\\])?([^/\\]+)$"), "roles": ["auxiliary"]},
    ]

    STRIP_SPECIAL_PATTERN = DatasetDriver.STRIP_SPECIAL_PATTERN

    def _normalize_key(self, key, eo_product):
        upper_key = key.upper()
        # check if key matched any normalized
        for res in self.BANDS_DEFAULT_GSD:
            if res in upper_key:
                for norm_key in self.BANDS_DEFAULT_GSD[res]:
                    if norm_key in upper_key:
                        return norm_key

        # default cleanup
        norm_key = key.replace(eo_product.properties.get("id", ""), "")
        norm_key = re.sub(self.STRIP_SPECIAL_PATTERN, "", norm_key)

        return norm_key

    def guess_asset_key_and_roles(
        self, href: str, eo_product: EOProduct
    ) -> tuple[Optional[str], Optional[list[str]]]:
        """Guess the asset key and roles from the given href.

        :param href: The asset href
        :param eo_product: The product to which the asset belongs
        :returns: The asset key and roles
        """
        for pattern_dict in self.ASSET_KEYS_PATTERNS_ROLES:
            if matched := pattern_dict["pattern"].match(href):
                extracted_key, roles = (
                    "".join([m for m in matched.groups() if m is not None]),
                    pattern_dict.get("roles"),
                )
                normalized_key = self._normalize_key(extracted_key, eo_product)
                return normalized_key or extracted_key, roles
        return None, None

    def _get_data_address(self, eo_product: EOProduct, band: str) -> str:
        """Compute the address of a subdataset for a Sentinel2 L1C product.

        This method should not be called as ``get_data_address()`` is only expected to be
        called from ``eodag-cube``.

        :param eo_product: The product whom underlying dataset address is to be retrieved
        :type eo_product: :class:`~eodag.api.product._product.EOProduct`
        :param band: The band to retrieve (e.g: 'B01')
        :type band: str
        :returns: An address for the dataset
        :rtype: str
        :raises: :class:`~eodag.utils.exceptions.AddressNotFound`
        :raises: :class:`~eodag.utils.exceptions.UnsupportedDatasetAddressScheme`
        """
        # legacy driver usage if defined
        if legacy_driver := getattr(self, "legacy", None):
            return legacy_driver.get_data_address(eo_product, band)

        raise AddressNotFound("eodag-cube required for this feature")

    try:
        # import from eodag-cube if installed
        from eodag_cube.api.product.drivers.sentinel2_l1c import (  # pyright: ignore[reportMissingImports]; isort: skip
            Sentinel2L1C as Sentinel2L1C_cube,
        )

        get_data_address = Sentinel2L1C_cube.get_data_address
    except ImportError:
        get_data_address = _get_data_address
