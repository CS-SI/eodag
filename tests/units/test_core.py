# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

import unittest

from tests.context import SatImagesAPI, UnsupportedProvider


class TestCore(unittest.TestCase):
    SUPPORTED_PRODUCT_TYPES = {
        'S3_LAN': ['airbus-ds'],
        'S2_MSI_L1C': ['airbus-ds'],
        'S1_SLC': ['airbus-ds'],
        'S3_SRA': ['airbus-ds'],
        'S1_RAW': ['airbus-ds'],
        'S1_GRD': ['airbus-ds'],
        'S1_OCN': ['airbus-ds'],
        'S3_SRA_BS': ['airbus-ds'],
        'S3_SRA_A_BS': ['airbus-ds'],
    }
    SUPPORTED_PROVIDERS = [
        'airbus-ds'
    ]

    def setUp(self):
        super(TestCore, self).setUp()
        self.dag = SatImagesAPI()

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
