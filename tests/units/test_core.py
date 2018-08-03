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
from __future__ import unicode_literals

import unittest

from tests.context import SatImagesAPI, UnsupportedProvider


class TestCore(unittest.TestCase):
    SUPPORTED_PRODUCT_TYPES = {
        'S3_SLSTR_L1RBT': ['peps'],
        'PLD_REFLECTANCETOA': ['theia-landsat'],
        'S2_MSI_L2A': ['theia'],
        'S3_LAN': ['peps', 'airbus-ds'],
        'S2_MSI_L1C': ['AmazonWS', 'peps', 'airbus-ds'],
        'S3_ERR': ['peps'],
        'L7_L1G': [],
        'S1_SAR_SLC': ['peps', 'airbus-ds'],
        'ES_FRS': [],
        'S3_SRA': ['airbus-ds'],
        'S3_WAT': [],
        'S3_OLCI_L2LFR': ['peps'],
        'L5_L1GT': [],
        'S3_SLSTR_L2LST': ['peps'],
        'L5_L1T': [],
        'LS_REFLECTANCE': ['theia-landsat'],
        'S1_SAR_RAW': ['airbus-ds'],
        'S1_SAR_GRD': ['peps', 'airbus-ds'],
        'S1_SAR_OCN': ['peps', 'airbus-ds'],
        'L8_L1T': [],
        'S3_SRA_BS': ['airbus-ds'],
        'S3_SRA_A_BS': ['airbus-ds'],
        'S3_EFR': ['peps'],
        'L8_LC8': ['USGS'],
        'L7_L1T': [],
        'S3_OLCI_L2LRR': ['peps'],
        'PLD_REFLECTANCE': ['theia-landsat'],
        'L5_L1G': [],
        'L8_L1GT': [],
        'LS_REFLECTANCETOA': ['theia-landsat'],
        'L7_L1GT': [],
    }
    SUPPORTED_PROVIDERS = [
        'peps',
        'AmazonWS',
        'USGS',
        'theia',
        'theia-landsat',
        'airbus-ds',
    ]

    def setUp(self):
        super(TestCore, self).setUp()
        self.dag = SatImagesAPI()

    def test_supported_providers_in_unit_test(self):
        """Every provider must be referenced in the core unittest SUPPORTED_PROVIDERS class attribute"""
        for provider in self.dag.available_providers():
            self.assertIn(provider, self.SUPPORTED_PROVIDERS)

    def test_supported_product_types_in_unit_test(self):
        """Every product type must be referenced in the core unit test SUPPORTED_PRODUCT_TYPES class attribute"""
        for product_type in self.dag.list_product_types():
            self.assertIn(product_type['ID'], self.SUPPORTED_PRODUCT_TYPES.keys())

    def test_list_product_types_ok(self):
        """Core api must correctly return the list of supported product types"""
        product_types = self.dag.list_product_types()
        self.assertIsInstance(product_types, list)
        for product_type in product_types:
            self.assertListProductTypesRightStructure(product_type)

    def test_list_product_types_for_provider_ok(self):
        """Core api must correctly return the list of supported product types for a given provider"""
        for provider in self.SUPPORTED_PROVIDERS:
            product_types = self.dag.list_product_types(provider=provider)
            self.assertIsInstance(product_types, list)
            for product_type in product_types:
                self.assertListProductTypesRightStructure(product_type)
                self.assertIn(provider, self.SUPPORTED_PRODUCT_TYPES[product_type['ID']])

    def test_list_product_types_for_unsupported_provider(self):
        """Core api must raise UnsupportedProvider error for list_product_types with unsupported provider"""
        unsupported_provider = 'a'
        self.assertRaises(UnsupportedProvider, self.dag.list_product_types, provider=unsupported_provider)

    def assertListProductTypesRightStructure(self, structure):
        """Helper method to verify that the structure given is a good result of SatImagesAPI.list_product_types"""
        self.assertIsInstance(structure, dict)
        self.assertIn('ID', structure)
        self.assertIn('desc', structure)
        self.assertIn('meta', structure)
        self.assertIn(structure['ID'], self.SUPPORTED_PRODUCT_TYPES)
