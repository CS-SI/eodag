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
import re
from typing import TYPE_CHECKING, Optional, TypedDict

from eodag.utils import _deprecated

if TYPE_CHECKING:
    from eodag.api.product import EOProduct


class AssetPatterns(TypedDict):
    """Asset patterns definition"""

    #: pattern to match and extract asset key
    pattern: re.Pattern
    #: roles associated to the asset key
    roles: list[str]


logger = logging.getLogger("eodag.driver.base")


class DatasetDriver(metaclass=type):
    """Parent class for all dataset drivers.

    Drivers will provide methods adapted to a given :class:`~eodag.api.product._product.EOProduct` related to predefined
    criteria.
    """

    #: legacy driver for deprecated :meth:`~eodag_cube.api.product._product.EOProduct.get_data` method usage
    legacy: DatasetDriver

    #: list of patterns to match asset keys and roles
    ASSET_KEYS_PATTERNS_ROLES: list[AssetPatterns] = []

    #: strip non-alphanumeric characters at the beginning and end of the key
    STRIP_SPECIAL_PATTERN = re.compile(r"^[^A-Z0-9]+|[^A-Z0-9]+$", re.IGNORECASE)

    def _normalize_key(self, key, eo_product):
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
        logger.debug(f"No key & roles could be guessed for {href}")
        return None, None

    @_deprecated(reason="Method used by deprecated get_data", version="3.1.0")
    def get_data_address(self, eo_product: EOProduct, band: str) -> str:
        """Retrieve the address of the dataset represented by `eo_product`.

        :param eo_product: The product whom underlying dataset address is to be retrieved
        :param band: The band to retrieve (e.g: 'B01')
        :returns: An address for the dataset
        :raises: :class:`~eodag.utils.exceptions.AddressNotFound`
        :raises: :class:`~eodag.utils.exceptions.UnsupportedDatasetAddressScheme`

        .. deprecated:: 3.1.0
           Method used by deprecated :meth:`~eodag_cube.api.product._product.EOProduct.get_data`
        """
        raise NotImplementedError


class NoDriver(DatasetDriver):
    """A default :attr:`~eodag.api.product.drivers.base.DatasetDriver.legacy` driver that does not implement any of the
    methods it should implement, used for all product types for  which the deprecated
    :meth:`~eodag_cube.api.product._product.EOProduct.get_data` method is not implemented. Expect a
    :exc:`NotImplementedError` when trying to get the data in that case.
    """
