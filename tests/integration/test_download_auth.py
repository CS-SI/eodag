# -*- coding: utf-8 -*-
# Copyright 2018, CS GROUP - France, https://www.csgroup.eu/
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
from importlib.resources import files as res_files
from tempfile import TemporaryDirectory
from unittest import mock

from tests import TEST_RESOURCES_PATH
from tests.context import EODataAccessGateway, MisconfiguredError


class TestEODagDownloadCredentialsNotSet(unittest.TestCase):
    """MisconfiguredError must be raised when downloading one or several products
    if the credentials are not set."""

    # USGS not tested here because when the credentials are not set it already fails during the search.
    # Given a GeoJSON Search Result it can however download the products.

    @classmethod
    def setUpClass(cls):
        super(TestEODagDownloadCredentialsNotSet, cls).setUpClass()
        # Mock home and eodag conf directory to tmp dir
        cls.tmp_home_dir = TemporaryDirectory()
        expanduser_mock_side_effect = (
            lambda *x: x[0]
            .replace("~user", cls.tmp_home_dir.name)
            .replace("~", cls.tmp_home_dir.name)
        )
        cls.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, side_effect=expanduser_mock_side_effect
        )
        cls.expanduser_mock.start()

        default_conf_file = str(
            res_files("eodag") / "resources" / "user_conf_template.yml"
        )
        cls.eodag = EODataAccessGateway(user_conf_file_path=default_conf_file)

    @classmethod
    def tearDownClass(cls):
        super(TestEODagDownloadCredentialsNotSet, cls).tearDownClass()
        # stop Mock and remove tmp config dir
        cls.expanduser_mock.stop()
        cls.tmp_home_dir.cleanup()

    def test_eodag_download_missing_credentials_theia(self):
        search_resuls = os.path.join(
            TEST_RESOURCES_PATH, "eodag_search_result_theia.geojson"
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

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.get", autospec=True
    )
    def test_eodag_download_missing_credentials_creodias(self, mock_requests):
        search_resuls = os.path.join(
            TEST_RESOURCES_PATH, "eodag_search_result_creodias.geojson"
        )
        products = self.eodag.deserialize_and_register(search_resuls)
        with self.assertRaises(MisconfiguredError):
            self.eodag.download(products[0])
        with self.assertRaises(MisconfiguredError):
            self.eodag.download_all(products)
