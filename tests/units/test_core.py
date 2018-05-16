# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

import unittest

from tests.context import SatImagesAPI, UnsupportedProvider


class TestCore(unittest.TestCase):
    SUPPORTED_PRODUCT_TYPES = {
        'S3_RBT': ['eocloud', 'peps'],
        'PLD_REFLECTANCETOA': ['theia-landsat'],
        'S2_MSI_L2Ap': [],
        'S3_LAN': ['eocloud', 'peps'],
        'S2_MSI_L1C': ['AmazonWS', 'eocloud', 'peps'],
        'S3_ERR': ['eocloud', 'peps'],
        'L7_L1G': ['eocloud'],
        'S1_SLC': ['eocloud', 'peps'],
        'ES_FRS': ['eocloud'],
        'S3_SRA': ['eocloud'],
        'S3_WAT': ['eocloud'],
        'S3_LFR': ['peps'],
        'L5_L1GT': ['eocloud'],
        'S3_LST': ['peps', 'eocloud'],
        'L5_L1T': ['eocloud'],
        'LS_REFLECTANCE': ['theia-landsat'],
        'S1_RAW': ['eocloud'],
        'S1_GRD': ['peps', 'eocloud'],
        'S1_OCN': ['peps', 'eocloud'],
        'L8_L1T': ['eocloud'],
        'S3_EFR': ['peps', 'eocloud'],
        'L8_LC8': ['USGS'],
        'L7_L1T': ['eocloud'],
        'S2_REFLECTANCE': ['theia'],
        'S3_LRR': ['peps'],
        'PLD_REFLECTANCE': ['theia-landsat'],
        'L5_L1G': ['eocloud'],
        'L8_L1GT': ['eocloud'],
        'LS_REFLECTANCETOA': ['theia-landsat'],
        'L7_L1GT': ['eocloud'],
    }
    SUPPORTED_PROVIDERS = [
        'eocloud',
        'peps',
        'AmazonWS',
        'USGS',
        'theia',
        'theia-landsat',
        'scihub',
        'geostorm-ce'
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
