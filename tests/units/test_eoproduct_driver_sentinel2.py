# -*- coding: utf-8 -*-
# Copyright 2021, CS GROUP - France, http://www.c-s.fr
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

import os
from contextlib import contextmanager

from tests import TEST_RESOURCES_PATH, EODagTestCase
from tests.context import AddressNotFound, EOProduct, Sentinel2Driver


class TestEOProductDriverSentinel2Driver(EODagTestCase):
    def setUp(self):
        super(TestEOProductDriverSentinel2Driver, self).setUp()
        self.product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        self.product.properties["title"] = os.path.join(
            TEST_RESOURCES_PATH,
            "products",
            "S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911",
        )

    def test_driver_s2_init(self):
        """The appropriate driver must have been set"""
        self.assertIsInstance(self.product.driver, Sentinel2Driver)

    def test_driver_s2_guess_asset_key_and_roles(self):
        """The driver must guess appropriate asset key and roles"""
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles("", self.product),
            (None, None),
        )
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles(
                "tiles/31/T/DJ/2018/1/28/0/bla_TCI.jp2", self.product
            ),
            ("TCI", ["visual"]),
        )
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles(
                "tiles/31/T/DJ/2018/1/28/0/B01.jp2", self.product
            ),
            ("B01", ["data"]),
        )
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles(
                "http://foo/1/28/0/bla_bla-B02_10m.tif", self.product
            ),
            ("B02", ["data"]),
        )
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles(
                "s3://foo/1/28/0/bla_bla-B02_20m.tiff", self.product
            ),
            ("B02_20m", ["data"]),
        )
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles(
                "s3://foo/1/28/0/MSK_bla_B02.tiff", self.product
            ),
            ("MSK_bla_B02", ["data-mask"]),
        )
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles(
                "s3://foo/1/28/0/Foo-bar.xml", self.product
            ),
            ("Foo-bar.xml", ["metadata"]),
        )
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles(
                "s3://foo/1/28/0/thumbnail.png", self.product
            ),
            ("thumbnail.png", ["thumbnail"]),
        )
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles(
                "s3://foo/1/28/0/Foo_bar-ql.jpg", self.product
            ),
            ("ql.jpg", ["overview"]),
        )

    def test_driver_s2_get_local_dataset_address_bad_band(self):
        """Driver must raise AddressNotFound if non existent band is requested"""
        with self._filesystem_product() as product:
            driver = Sentinel2Driver()
            band = "B02"
            self.assertRaises(AddressNotFound, driver.get_data_address, product, band)

    @contextmanager
    def _filesystem_product(self):
        original = self.product.location
        try:
            self.product.location = "file:///{}".format(
                self.product.properties["title"].strip("/")
            )
            yield self.product
        finally:
            self.product.location = original
