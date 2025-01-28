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

from eodag.api.product.drivers.base import AssetPatterns, DatasetDriver

logger = logging.getLogger("eodag.driver.generic")


class GenericDriver(DatasetDriver):
    """Generic default Driver"""

    #: list of patterns to match asset keys and roles
    ASSET_KEYS_PATTERNS_ROLES: list[AssetPatterns] = [
        # data
        {
            "pattern": re.compile(
                r"^(?:.*[/\\])?([^/\\]+)(\.jp2|\.tiff?|\.dat|\.nc|\.grib2?)$",
                re.IGNORECASE,
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
                r"^(?:.*[/\\])?(thumbnail)(\.jpg|\.jpeg|\.png)$", re.IGNORECASE
            ),
            "roles": ["thumbnail"],
        },
        # quicklook
        {
            "pattern": re.compile(
                r"^(?:.*[/\\])?([^/\\]+-ql|preview|quick-?look)(\.jpg|\.jpeg|\.png)$",
                re.IGNORECASE,
            ),
            "roles": ["overview"],
        },
        # default
        {"pattern": re.compile(r"^(?:.*[/\\])?([^/\\]+)$"), "roles": ["auxiliary"]},
    ]
