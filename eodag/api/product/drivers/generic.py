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
from pathlib import Path
from typing import TYPE_CHECKING

import rasterio

from eodag.api.product.drivers.base import DatasetDriver
from eodag.utils import uri_to_path
from eodag.utils.exceptions import AddressNotFound, UnsupportedDatasetAddressScheme

if TYPE_CHECKING:
    from eodag.api.product._product import EOProduct

logger = logging.getLogger("eodag.driver.generic")


# File extensions to accept on top of those known to rasterio/GDAL
EXTRA_ALLOWED_FILE_EXTENSIONS = [".grib", ".grib2"]


class GenericDriver(DatasetDriver):
    """Generic Driver for products that need to be downloaded"""

    def get_data_address(self, eo_product: EOProduct, band: str) -> str:
        """Get the address of a product subdataset.

        :param eo_product: The product whom underlying dataset address is to be retrieved
        :type eo_product: :class:`~eodag.api.product._product.EOProduct`
        :param band: The band to retrieve (e.g: 'B01')
        :type band: str
        :returns: An address for the dataset
        :rtype: str
        :raises: :class:`~eodag.utils.exceptions.AddressNotFound`
        :raises: :class:`~eodag.utils.exceptions.UnsupportedDatasetAddressScheme`
        """
        product_location_scheme = eo_product.location.split("://")[0]
        if product_location_scheme == "file":

            p = re.compile(rf"{band}", re.IGNORECASE)
            matching_files = []
            for f_path in Path(uri_to_path(eo_product.location)).glob("**/*"):
                f_str = str(f_path.resolve())
                if f_path.suffix in EXTRA_ALLOWED_FILE_EXTENSIONS:
                    matching_files.append(f_str)
                elif p.search(f_str):
                    try:
                        # files readable by rasterio
                        rasterio.drivers.driver_from_extension(f_path)
                        matching_files.append(f_str)
                        logger.debug(f"Matching band: {f_str}")
                    except ValueError:
                        pass

            if len(matching_files) == 1:
                return matching_files[0]

            raise AddressNotFound(
                rf"Please adapt given band parameter ('{band}') to match only file: "
                rf"{len(matching_files)} files found matching {p}"
            )

        raise UnsupportedDatasetAddressScheme(
            "eo product {} is accessible through a location scheme that is not yet "
            "supported by eodag: {}".format(eo_product, product_location_scheme)
        )
