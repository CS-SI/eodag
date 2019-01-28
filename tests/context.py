# -*- coding: utf-8 -*-
# Copyright 2018, CS Systemes d'Information, http://www.c-s.fr
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
"""Explicitly import here everything you want to use from the eodag package"""
import sys
import os

from tests import TEST_RESOURCES_PATH


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from eodag import api, config
from eodag import EODataAccessGateway
from eodag.cli import eodag, list_pt, search_crunch, download
from eodag.api.product import EOProduct
from eodag.api.search_result import SearchResult
from eodag.api.product.drivers import DRIVERS
from eodag.api.product.drivers.base import NoDriver
from eodag.api.product.drivers.sentinel2_l1c import Sentinel2L1C

from eodag.rest import settings
settings.EODAG_CFG_FILE = os.path.join(TEST_RESOURCES_PATH, 'file_config_override.yml')
from eodag.rest import server as eodag_http_server
from eodag.rest.server import _get_date

from eodag.plugins.authentication.base import Authentication
from eodag.plugins.download.base import Download
from eodag.plugins.search.base import Search

from eodag.utils import DEFAULT_PROJ
from eodag.utils.exceptions import (
    AddressNotFound, UnsupportedDatasetAddressScheme, UnsupportedProvider, ValidationError, DownloadError
)
