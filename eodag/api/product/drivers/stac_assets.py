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

import logging
import re
from typing import TYPE_CHECKING

from eodag.api.product.drivers.base import DatasetDriver
from eodag.utils.exceptions import AddressNotFound

if TYPE_CHECKING:
    from eodag.api.product._product import EOProduct

logger = logging.getLogger("eodag.driver.stac_assets")


class StacAssets(DatasetDriver):
    """Driver for Stac Assets"""

    def get_data_address(self, eo_product: EOProduct, band: str) -> str:
        """Get the address of a subdataset for a STAC provider product.

        :param eo_product: The product whom underlying dataset address is to be retrieved
        :type eo_product: :class:`~eodag.api.product._product.EOProduct`
        :param band: The band to retrieve (e.g: 'B01')
        :type band: str
        :returns: An address for the dataset
        :rtype: str
        :raises: :class:`~eodag.utils.exceptions.AddressNotFound`
        :raises: :class:`~eodag.utils.exceptions.UnsupportedDatasetAddressScheme`
        """
        p = re.compile(rf"{band}", re.IGNORECASE)
        matching_keys = []
        for s in eo_product.assets.keys():
            if (
                (
                    "roles" in eo_product.assets[s]
                    and "data" in eo_product.assets[s]["roles"]
                )
                or ("roles" not in eo_product.assets[s])
            ) and p.search(s):
                matching_keys.append(s)
                logger.debug(f"Matching asset key: {s}")

        if len(matching_keys) == 1:
            return str(eo_product.assets[matching_keys[0]]["href"])

        raise AddressNotFound(
            rf"Please adapt given band parameter ('{band}') to match only one asset: "
            rf"{len(matching_keys)} assets keys found matching {p}"
        )
