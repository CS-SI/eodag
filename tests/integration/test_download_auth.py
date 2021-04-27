# -*- coding: utf-8 -*-
# Copyright 2021, CS GROUP - France, https://www.csgroup.eu/
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
import unittest

from pkg_resources import resource_filename

from tests import TEST_RESOURCES_PATH
from tests.context import EODataAccessGateway, MisconfiguredError


class TestEODagDownloadCredentialsNotSet(unittest.TestCase):
    """MisconfiguredError must be raised when downloading one or several products
    if the credentials are not set."""

    # USGS not tested here because when the credentials are not set it already fails during the search.
    # Given a GeoJSON Search Result it can however download the products.

    @classmethod
    def setUpClass(self):
        default_conf_file = resource_filename(
            "eodag", os.path.join("resources", "user_conf_template.yml")
        )
        self.eodag = EODataAccessGateway(user_conf_file_path=default_conf_file)

    def test_eodag_download_missing_credentials_theia(self):
        search_resuls = os.path.join(
            TEST_RESOURCES_PATH, "eodag_search_result_theia.geojson"
        )
        products = self.eodag.deserialize_and_register(search_resuls)
        with self.assertRaises(MisconfiguredError):
            self.eodag.download(products[0])
        with self.assertRaises(MisconfiguredError):
            self.eodag.download_all(products)

    def test_eodag_download_missing_credentials_sobloo(self):
        search_resuls = os.path.join(
            TEST_RESOURCES_PATH, "eodag_search_result_sobloo.geojson"
        )
        products = self.eodag.deserialize_and_register(search_resuls)
        with self.assertRaises(MisconfiguredError):
            self.eodag.download(products[0])
        with self.assertRaises(MisconfiguredError):
            self.eodag.download_all(products)

    def test_eodag_download_missing_credentials_peps(self):
        search_resuls = os.path.join(
            TEST_RESOURCES_PATH, "eodag_search_result_peps.geojson"
        )
        products = self.eodag.deserialize_and_register(search_resuls)
        with self.assertRaises(MisconfiguredError):
            self.eodag.download(products[0])
        with self.assertRaises(MisconfiguredError):
            self.eodag.download_all(products)

    def test_eodag_download_missing_credentials_creodias(self):
        search_resuls = os.path.join(
            TEST_RESOURCES_PATH, "eodag_search_result_creodias.geojson"
        )
        products = self.eodag.deserialize_and_register(search_resuls)
        with self.assertRaises(MisconfiguredError):
            self.eodag.download(products[0])
        with self.assertRaises(MisconfiguredError):
            self.eodag.download_all(products)

    def test_eodag_download_missing_credentials_mundi(self):
        search_resuls = os.path.join(
            TEST_RESOURCES_PATH, "eodag_search_result_mundi.geojson"
        )
        products = self.eodag.deserialize_and_register(search_resuls)
        with self.assertRaises(MisconfiguredError):
            self.eodag.download(products[0])
        with self.assertRaises(MisconfiguredError):
            self.eodag.download_all(products)

    def test_eodag_download_missing_credentials_onda(self):
        search_resuls = os.path.join(
            TEST_RESOURCES_PATH, "eodag_search_result_onda.geojson"
        )
        products = self.eodag.deserialize_and_register(search_resuls)
        with self.assertRaises(MisconfiguredError):
            self.eodag.download(products[0])
        with self.assertRaises(MisconfiguredError):
            self.eodag.download_all(products)
