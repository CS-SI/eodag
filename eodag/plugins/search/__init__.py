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
""" Plugin search module """
from .base import MappingInterpretor, Search
from .build_search_result import (
    ALLOWED_KEYWORDS,
    ECMWF_PREFIX,
    END,
    START,
    ECMWFSearch,
    MeteoblueSearch,
    WekeoECMWFSearch,
    ecmwf_format,
    ecmwf_mtd,
    ecmwf_temporal_to_eodag,
    update_properties_from_element,
)
from .cop_ghsl import CopGhslSearch
from .cop_marine import CopMarineSearch
from .creodias_s3 import CreodiasS3Search
from .csw import CSWSearch
from .preparesearch import PreparedSearch
from .qssearch import (
    GeodesSearch,
    ODataV4Search,
    PostJsonSearch,
    QueryStringSearch,
    StacSearch,
    WekeoSearch,
)
from .stac_list_assets import StacListAssets
from .static_stac_search import StaticStacSearch

__all__ = [
    "Search",
    "MappingInterpretor",
    "PreparedSearch",
    "ECMWFSearch",
    "MeteoblueSearch",
    "WekeoECMWFSearch",
    "CopMarineSearch",
    "CopGhslSearch",
    "ODataV4Search",
    "PostJsonSearch",
    "QueryStringSearch",
    "StacSearch",
    "WekeoSearch",
    "CreodiasS3Search",
    "CSWSearch",
    "GeodesSearch",
    "StacListAssets",
    "StaticStacSearch",
    "ecmwf_mtd",
    "update_properties_from_element",
    "ecmwf_format",
    "ecmwf_temporal_to_eodag",
    "ECMWF_PREFIX",
    "ALLOWED_KEYWORDS",
    "END",
    "START",
]
