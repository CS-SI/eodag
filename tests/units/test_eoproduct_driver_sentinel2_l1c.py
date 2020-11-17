# -*- coding: utf-8 -*-
# Copyright 2020, CS GROUP - France, http://www.c-s.fr
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

import boto3
from moto import mock_s3

from tests import TEST_RESOURCES_PATH, EODagTestCase
from tests.context import (
    AddressNotFound,
    EOProduct,
    Sentinel2L1C,
    UnsupportedDatasetAddressScheme,
)


class TestEOProductDriverSentinel2L1C(EODagTestCase):
    def setUp(self):
        super(TestEOProductDriverSentinel2L1C, self).setUp()
        self.product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        self.product.properties["title"] = os.path.join(
            TEST_RESOURCES_PATH,
            "products",
            "S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911.SAFE",
        )
        self.sentinel2_l1c_driver = Sentinel2L1C()

    def test_driver_get_local_dataset_address_bad_band(self):
        """Driver must raise AddressNotFound if non existent band is requested"""
        with self._filesystem_product() as product:
            driver = Sentinel2L1C()
            band = "B02"
            self.assertRaises(AddressNotFound, driver.get_data_address, product, band)

    def test_driver_get_local_dataset_address_ok(self):
        """Driver returns a good address for an existing band"""
        with self._filesystem_product() as product:
            band = "B01"
            address = self.sentinel2_l1c_driver.get_data_address(product, band)
            self.assertEqual(address, self.local_band_file)

    @mock_s3
    def test_driver_get_amazon_s3_remote_dataset_address_ok(self):
        """Driver must returns a good address for an existing band for a product stored on amazon s3"""
        with self._remote_product_s3() as product:
            self.create_mock_s3_bucket_and_product()
            band = "B01"
            address = self.sentinel2_l1c_driver.get_data_address(product, band)
            self.assertEqual(
                address, "s3://sentinel-s2-l1c/tiles/31/T/DJ/2018/1/28/0/B01.jp2"
            )

    def test_driver_get_http_remote_dataset_address_fail(self):
        """Driver must raise UnsupportedDatasetAddressScheme if location scheme is http or https"""
        # Default value of self.product.location is 'https://...'
        band = "B01"
        self.assertRaises(
            UnsupportedDatasetAddressScheme,
            self.sentinel2_l1c_driver.get_data_address,
            self.product,
            band,
        )

    @contextmanager
    def _filesystem_product(self):
        original = self.product.location
        try:
            self.product.location = "file://{}".format(self.product.properties["title"])
            yield self.product
        finally:
            self.product.location = original

    @contextmanager
    def _remote_product_s3(self):
        original = self.product.location
        try:
            self.product.location = "s3://tiles/31/T/DJ/2018/1/28/0/"

            # Finding the address of an eo_product on amazon s3 require us to to
            # connect to aws with some credentials
            # And this is the responsibility of the eo_product downloader_auth plugin
            class MockAuthenticator(object):
                """A fake authenticator plugin"""

                def authenticate(self):
                    return "access_key", "access_secret"

            self.product.downloader_auth = MockAuthenticator()
            yield self.product
        finally:
            self.product.location = original

    @staticmethod
    def create_mock_s3_bucket_and_product():
        """Create the bucket and the product on a mocked s3 resource.

        WARNING::

            This internal method should only be used in a test decorated with: @mock_s3 from moto module
        """
        s3 = boto3.resource("s3")
        s3.create_bucket(Bucket="sentinel-s2-l1c")
        s3.meta.client.put_object(
            Bucket="sentinel-s2-l1c", Key="tiles/31/T/DJ/2018/1/28/0/B01.jp2"
        )
