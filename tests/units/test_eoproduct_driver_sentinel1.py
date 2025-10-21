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

from tests import TEST_RESOURCES_PATH, EODagTestCase
from tests.context import EOProduct, Sentinel1Driver


class TestEOProductDriverSentinel1Driver(EODagTestCase):
    def setUp(self):
        super(TestEOProductDriverSentinel1Driver, self).setUp()
        self.product = EOProduct(
            self.provider, self.eoproduct_props, collection="S1_SAR_OCN"
        )
        self.product.properties["title"] = os.path.join(
            TEST_RESOURCES_PATH,
            "products",
            "S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911",
        )

    def test_driver_s1_init(self):
        """The appropriate driver must have been set"""
        self.assertIsInstance(self.product.driver, Sentinel1Driver)

    def test_driver_s1_guess_asset_key_and_roles(self):
        """The driver must guess appropriate asset key and roles"""
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles("", self.product),
            (None, None),
        )
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles(
                "2018/1/28/0/ew-hv.tiff", self.product
            ),
            ("HV", ["data"]),
        )
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles(
                "http://foo/1/28/0/iw-hh.tif", self.product
            ),
            ("HH", ["data"]),
        )
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles(
                "s3://foo/1/28/0/s1a-vv.tiff", self.product
            ),
            ("VV", ["data"]),
        )
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles(
                "s3://foo/1/28/0/rfi-ew-hh.xml", self.product
            ),
            ("rfi-hh.xml", ["metadata"]),
        )
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles(
                "s3://foo/1/28/0/thumbnail.png", self.product
            ),
            ("thumbnail.png", ["thumbnail"]),
        )
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles(
                "s3://foo/1/28/0/quick-look.jpg", self.product
            ),
            ("quick-look.jpg", ["overview"]),
        )
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles(
                "s3://foo/1/28/0/foo.bar", self.product
            ),
            ("foo.bar", ["auxiliary"]),
        )
