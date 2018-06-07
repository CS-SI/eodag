# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

import os
from contextlib import contextmanager

from tests import EODagTestCase, TEST_RESOURCES_PATH
from tests.context import AddressNotFound, EOProduct, Sentinel2, UnsupportedDatasetAddressScheme


class TestEOProductDriverSentinel2(EODagTestCase):

    def setUp(self):
        super(TestEOProductDriverSentinel2, self).setUp()
        self.product = EOProduct(
            self.provider,
            self.download_url,
            self.local_filename,
            self.geometry,
            self.footprint,
            self.product_type,
            instrument=self.instrument,
            platform=self.platform
        )
        self.product.properties['productIdentifier'] = os.path.join(
            TEST_RESOURCES_PATH,
            'products', 'S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911.SAFE'
        )
        self.sentinel2_driver = Sentinel2()

    def test_driver_get_local_dataset_address_bad_band(self):
        """Driver must raise AddressNotFound if non existent band is requested"""
        with self.__filesystem_product() as product:
            driver = Sentinel2()
            band = 'B02'
            self.assertRaises(AddressNotFound, driver.get_data_address, product, band)

    def test_driver_get_local_dataset_address_ok(self):
        """Driver returns a good address for an existing band"""
        with self.__filesystem_product() as product:
            band = 'B01'
            address = self.sentinel2_driver.get_data_address(product, band)
            self.assertEqual(address, self.local_band_file)

    def test_driver_get_remote_dataset_address_fail(self):
        """Driver must raise UnsupportedDatasetAddressScheme if location scheme is different from 'file://'"""
        band = 'B01'
        self.assertRaises(UnsupportedDatasetAddressScheme,
                          self.sentinel2_driver.get_data_address, self.product, band)

    @contextmanager
    def __filesystem_product(self):
        original = self.product.location
        try:
            self.product.location = 'file://{}'.format(self.product.properties['productIdentifier'])
            yield self.product
        finally:
            self.product.location = original
