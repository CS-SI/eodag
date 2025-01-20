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
from typing import TYPE_CHECKING

from eodag.api.product.drivers.base import DatasetDriver
from eodag.utils.exceptions import AddressNotFound

if TYPE_CHECKING:
    from eodag.api.product._product import EOProduct

logger = logging.getLogger("eodag.driver.generic")


# File extensions to accept on top of those known to rasterio/GDAL
EXTRA_ALLOWED_FILE_EXTENSIONS = [".grib", ".grib2"]


class GenericDriver(DatasetDriver):
    """Generic Driver for products that need to be downloaded"""

    def _get_data_address(self, eo_product: EOProduct, band: str) -> str:
        """Get the address of a product subdataset.

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
        from eodag_cube.api.product.drivers.generic import (  # pyright: ignore[reportMissingImports] ; isort: skip
            GenericDriver as GenericDriver_cube,
        )

        get_data_address = GenericDriver_cube.get_data_address
    except ImportError:
        get_data_address = _get_data_address
