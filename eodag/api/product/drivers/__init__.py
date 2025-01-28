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
"""EODAG drivers package"""
from __future__ import annotations

from typing import Callable, TypedDict

from eodag.api.product.drivers.base import DatasetDriver, NoDriver
from eodag.api.product.drivers.generic import GenericDriver
from eodag.api.product.drivers.sentinel1 import Sentinel1Driver
from eodag.api.product.drivers.sentinel2 import Sentinel2Driver

try:
    # import from eodag-cube if installed
    from eodag_cube.api.product.drivers.generic import (  # pyright: ignore[reportMissingImports]; isort: skip
        GenericDriver as GenericDriver_cube,
    )
    from eodag_cube.api.product.drivers.sentinel2_l1c import (  # pyright: ignore[reportMissingImports]; isort: skip
        Sentinel2L1C as Sentinel2L1C_cube,
    )
    from eodag_cube.api.product.drivers.stac_assets import (  # pyright: ignore[reportMissingImports]; isort: skip
        StacAssets as StacAssets_cube,
    )
except ImportError:
    GenericDriver_cube = NoDriver
    Sentinel2L1C_cube = NoDriver
    StacAssets_cube = NoDriver


class DriverCriteria(TypedDict):
    """Driver criteria definition"""

    #: Function that returns True if the driver is suitable for the given :class:`~eodag.api.product._product.EOProduct`
    criteria: list[Callable[..., bool]]
    #: driver to use
    driver: DatasetDriver


#: list of drivers and their criteria
DRIVERS: list[DriverCriteria] = [
    {
        "criteria": [
            lambda prod: True
            if (prod.product_type or "").startswith("S2_MSI_")
            else False
        ],
        "driver": Sentinel2Driver(),
    },
    {
        "criteria": [
            lambda prod: True
            if (prod.product_type or "").startswith("S1_SAR_")
            else False
        ],
        "driver": Sentinel1Driver(),
    },
    {
        "criteria": [lambda prod: True],
        "driver": GenericDriver(),
    },
]


#: list of legacy drivers and their criteria
LEGACY_DRIVERS: list[DriverCriteria] = [
    {
        "criteria": [
            lambda prod: True if len(getattr(prod, "assets", {})) > 0 else False
        ],
        "driver": StacAssets_cube(),
    },
    {
        "criteria": [lambda prod: True if "assets" in prod.properties else False],
        "driver": StacAssets_cube(),
    },
    {
        "criteria": [
            lambda prod: True
            if getattr(prod, "product_type") == "S2_MSI_L1C"
            else False
        ],
        "driver": Sentinel2L1C_cube(),
    },
    {
        "criteria": [lambda prod: True],
        "driver": GenericDriver_cube(),
    },
]

# exportable content
__all__ = ["DRIVERS", "DatasetDriver", "GenericDriver", "NoDriver", "Sentinel2Driver"]
