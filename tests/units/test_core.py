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

from tests.context import EODataAccessGateway, UnsupportedProvider


class TestCore(unittest.TestCase):
    SUPPORTED_PRODUCT_TYPES = {
        'LS_REFLECTANCE': ['theia_landsat'],
        'LS_REFLECTANCETOA': ['theia_landsat'],
        'L5_L1T': [],
        'L5_L1G': [],
        'L5_L1GT': [],
        'L7_L1G': [],
        'L7_L1T': [],
        'L7_L1GT': [],
        'L8_L1T': ['onda'],
        'L8_L1GT': ['onda'],
        'L8_OLI_TIRS_C1L1': ['usgs'],
        'S1_SAR_GRD': ['peps', 'sobloo', 'onda', 'wekeo', 'mundi', 'creodias'],
        'S1_SAR_OCN': ['peps', 'sobloo', 'onda', 'mundi', 'creodias'],
        'S1_SAR_RAW': ['sobloo', 'onda', 'mundi', 'creodias'],
        'S1_SAR_SLC': ['peps', 'sobloo', 'onda', 'wekeo', 'mundi', 'creodias'],
        'S2_MSI_L2A': ['theia', 'onda', 'mundi', 'creodias'],
        'S2_MSI_L1C': ['aws_s3_sentinel2_l1c', 'peps', 'sobloo', 'onda', 'wekeo', 'mundi', 'creodias'],
        'S3_ERR': ['peps', 'onda', 'wekeo', 'creodias'],
        'S3_EFR': ['peps', 'onda', 'wekeo', 'creodias'],
        'S3_LAN': ['peps', 'sobloo', 'onda', 'wekeo', 'creodias'],
        'S3_SRA': ['sobloo', 'onda', 'wekeo', 'creodias'],
        'S3_SRA_BS': ['sobloo', 'onda', 'wekeo', 'creodias'],
        'S3_SRA_A_BS': ['sobloo', 'onda', 'creodias'],
        'S3_WAT': ['onda', 'wekeo', 'creodias'],
        'S3_OLCI_L2LFR': ['peps', 'onda', 'wekeo', 'creodias'],
        'S3_OLCI_L2LRR': ['peps', 'onda', 'wekeo', 'creodias'],
        'S3_SLSTR_L1RBT': ['peps', 'onda', 'wekeo', 'creodias'],
        'S3_SLSTR_L2LST': ['peps', 'onda', 'wekeo', 'creodias'],
        'PLD_BUNDLE': ['theia_landsat'],
        'PLD_REFLECTANCE': ['theia_landsat'],
        'PLD_REFLECTANCETOA': ['theia_landsat'],
        'ES_FRS': [],
    }
    SUPPORTED_PROVIDERS = [
        'peps',
        'aws_s3_sentinel2_l1c',
        'usgs',
        'theia',
        'theia_landsat',
        'sobloo',
        'creodias',
        'mundi',
        'onda',
        'wekeo'
    ]

    def setUp(self):
        super(TestCore, self).setUp()
        self.dag = EODataAccessGateway()

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
        # There should be no repeated product type in the output
        self.assertEqual(len(product_types), len(set(pt['ID'] for pt in product_types)))

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
        """Helper method to verify that the structure given is a good result of
        EODataAccessGateway.list_product_types
        """
        self.assertIsInstance(structure, dict)
        self.assertIn('ID', structure)
        self.assertIn('desc', structure)
        self.assertIn('meta', structure)
        self.assertIn(structure['ID'], self.SUPPORTED_PRODUCT_TYPES)
