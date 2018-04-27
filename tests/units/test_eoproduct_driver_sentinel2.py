# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

import os
import unittest

import numpy as np

from shapely import wkt

from eodag.utils.exceptions import AddressNotFound
from .context import EOProduct, Sentinel2


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
            os.path.dirname(__file__),
            '..', 'resources', 'products', 'S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911.SAFE'
        )

    def test_driver_get_local_dataset_address_bad_band(self):
        """Driver must raise AddressNotFound if non existent band is requested"""
        driver = Sentinel2()
        band = 'B02'
        self.assertRaises(AddressNotFound, driver.get_dataset_address, self.product, band)

    def test_driver_get_local_dataset_address_ok(self):
        """Driver returns a good address for an existing band"""
        driver = Sentinel2()
        band = 'B01'
        address = driver.get_dataset_address(self.product, band)
        self.assertEqual(
            address,
            os.path.join(
                os.path.dirname(__file__), '..', 'resources', 'products',
                'S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911.SAFE', 'GRANULE',
                'L1C_T31TDH_A013204_20180101T105435', 'IMG_DATA', 'T31TDH_20180101T105441_B01.jp2'
            ))
