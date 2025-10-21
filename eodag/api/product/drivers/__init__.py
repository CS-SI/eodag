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

from eodag.api.product.drivers.base import DatasetDriver
from eodag.api.product.drivers.generic import GenericDriver
from eodag.api.product.drivers.sentinel1 import Sentinel1Driver
from eodag.api.product.drivers.sentinel2 import Sentinel2Driver


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
            if (prod.collection or "").startswith("S2_MSI_")
            else False
        ],
        "driver": Sentinel2Driver(),
    },
    {
        "criteria": [
            lambda prod: True
            if (prod.collection or "").startswith("S1_SAR_")
            else False
        ],
        "driver": Sentinel1Driver(),
    },
    {
        "criteria": [lambda prod: True],
        "driver": GenericDriver(),
    },
]


# exportable content
__all__ = ["DRIVERS", "DatasetDriver", "GenericDriver", "Sentinel2Driver"]
