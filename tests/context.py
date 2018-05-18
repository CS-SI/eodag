# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
"""Explicitly import here everything you want to use from the eodag package"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from eodag import api, config
from eodag import SatImagesAPI
from eodag.cli import eodag, list_pt, search_crunch, download
from eodag.api.product import EOProduct
from eodag.api.search_result import SearchResult
from eodag.api.product.drivers import DRIVERS
from eodag.api.product.drivers.base import NoDriver
from eodag.api.product.drivers.sentinel2 import Sentinel2

from eodag.plugins.authentication.base import Authentication
from eodag.plugins.download.base import Download
from eodag.plugins.search.base import Search

from eodag.utils.exceptions import AddressNotFound, UnsupportedDatasetAddressScheme, UnsupportedProvider
