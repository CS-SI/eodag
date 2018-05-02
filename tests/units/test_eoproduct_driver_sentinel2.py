# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

import os
import unittest
from contextlib import contextmanager

from shapely import wkt

from tests import RESOURCES_PATH
from .context import AddressNotFound, EOProduct, Sentinel2, UnsupportedDatasetAddressScheme


class TestEOProductDriverSentinel2(unittest.TestCase):

    def setUp(self):
        self.provider = 'eocloud'
        self.download_url = ('https://static.eocloud.eu/v1/AUTH_8f07679eeb0a43b19b33669a4c888c45/eorepo/Sentinel-2/MSI/'
                             'L1C/2018/01/01/S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911.SAFE.zip')
        self.local_filename = 'S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911.SAFE'
        # A good valid geometry of a sentinel 2 product around Toulouse
        self.geometry = wkt.loads('POLYGON((0.495928592903789 44.22596415476343, 1.870237286761489 44.24783068396879, '
                                  '1.888683014192297 43.25939191053712, 0.536772323136669 43.23826255332707, '
                                  '0.495928592903789 44.22596415476343))')
        # The footprint requested
        self.footprint = {
            'lonmin': 0.495928592903789, 'latmin': 44.22596415476343,
            'lonmax': 1.888683014192297, 'latmax': 44.24783068396879
        }
        self.product_type = 'L1C'
        self.platform = 'S2A'
        self.instrument = 'MSI'
        self.provider_id = '318837e4-bc83-5c2b-9511-53592350f3e1'
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
            RESOURCES_PATH,
            'products', 'S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911.SAFE'
        )
        self.sentinel2_driver = Sentinel2()

    def test_driver_get_local_dataset_address_bad_band(self):
        """Driver must raise AddressNotFound if non existent band is requested"""
        with self.__filesystem_product() as product:
            driver = Sentinel2()
            band = 'B02'
            self.assertRaises(AddressNotFound, driver.get_dataset_address, product, band)

    def test_driver_get_local_dataset_address_ok(self):
        """Driver returns a good address for an existing band"""
        with self.__filesystem_product() as product:
            band = 'B01'
            address = self.sentinel2_driver.get_dataset_address(product, band)
            self.assertEqual(
                address,
                os.path.join(
                    RESOURCES_PATH, 'products', 'S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911.SAFE',
                    'GRANULE', 'L1C_T31TDH_A013204_20180101T105435', 'IMG_DATA', 'T31TDH_20180101T105441_B01.jp2'
                ))

    def test_driver_get_remote_dataset_address_fail(self):
        """Driver must raise UnsupportedDatasetAddressScheme if location scheme is different from 'file://'"""
        band = 'B01'
        self.assertRaises(UnsupportedDatasetAddressScheme,
                          self.sentinel2_driver.get_dataset_address, self.product, band)

    @contextmanager
    def __filesystem_product(self):
        original = self.product.location_url_tpl
        try:
            self.product.location_url_tpl = 'file://{}'.format(self.product.properties['productIdentifier'])
            yield self.product
        finally:
            self.product.location_url_tpl = original
