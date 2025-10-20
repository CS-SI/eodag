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
from tests.context import EOProduct, GenericDriver, NoDriver


class TestEOProductDriverGeneric(EODagTestCase):
    def setUp(self):
        super(TestEOProductDriverGeneric, self).setUp()
        self.product = EOProduct(
            self.provider, self.eoproduct_props, collection="FAKE_COLLECTION"
        )
        self.product.properties["title"] = os.path.join(
            TEST_RESOURCES_PATH,
            "products",
            "S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911",
        )

    def test_driver_generic_init(self):
        """The appropriate driver must have been set"""
        self.assertIsInstance(self.product.driver, GenericDriver)
        self.assertTrue(hasattr(self.product.driver, "legacy"))
        try:
            # import from eodag-cube if installed
            from eodag_cube.api.product.drivers.base import (  # pyright: ignore[reportMissingImports]; isort: skip
                DatasetDriver as DatasetDriver_cube,
            )

            self.assertIsInstance(self.product.driver.legacy, DatasetDriver_cube)
        except ImportError:
            self.assertIsInstance(self.product.driver.legacy, NoDriver)

    def test_driver_generic_guess_asset_key_and_roles(self):
        """The driver must guess appropriate asset key and roles"""
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles("", self.product),
            (None, None),
        )
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles(
                "2018/1/28/0/ew-hv.tif", self.product
            ),
            ("ew-hv.tif", ["data"]),
        )
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles(
                "2018/1/28/0/ew-hv.jp2", self.product
            ),
            ("ew-hv.jp2", ["data"]),
        )
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles(
                "2018/1/28/0/ew-hv.nc", self.product
            ),
            ("ew-hv.nc", ["data"]),
        )
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles(
                "2018/1/28/0/ew-hv.grib2", self.product
            ),
            ("ew-hv.grib2", ["data"]),
        )
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles(
                "2018/1/28/0/ew-hv.foo", self.product
            ),
            ("ew-hv.foo", ["auxiliary"]),
        )
        self.assertEqual(
            self.product.driver.guess_asset_key_and_roles(
                "s3://foo/1/28/0/rfi-ew-hh.xml", self.product
            ),
            ("rfi-ew-hh.xml", ["metadata"]),
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
