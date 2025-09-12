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
from tempfile import TemporaryDirectory

from tests import TEST_RESOURCES_PATH
from tests.context import EODataAccessGateway
from tests.utils import mock


class TestSearchStacStatic(unittest.TestCase):
    def setUp(self):
        super(TestSearchStacStatic, self).setUp()

        # Mock home and eodag conf directory to tmp dir
        self.tmp_home_dir = TemporaryDirectory()
        self.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, return_value=self.tmp_home_dir.name
        )
        self.expanduser_mock.start()

        self.dag = EODataAccessGateway()

        self.cat_dir_path = self.root_cat = os.path.join(TEST_RESOURCES_PATH, "stac")
        self.root_cat = os.path.join(self.cat_dir_path, "catalog.json")
        self.root_cat_len = 5
        self.child_cat = os.path.join(
            self.cat_dir_path, "country", "FRA", "year", "2018", "2018.json"
        )
        self.child_cat_len = 2
        self.item = os.path.join(
            os.path.dirname(self.child_cat),
            "items",
            "S2A_MSIL1C_20181231T141041_N0207_R110_T21NYF_20181231T155050",
            "S2A_MSIL1C_20181231T141041_N0207_R110_T21NYF_20181231T155050.json",
        )
        self.singlefile_cat = os.path.join(TEST_RESOURCES_PATH, "stac_singlefile.json")
        self.singlefile_cat_len = 5

        self.stac_provider = "planetary_computer"
        self.collection = "S2_MSI_L2A"

        self.extent_big = {"lonmin": -55, "lonmax": -53, "latmin": 2, "latmax": 5}
        self.extent_small = {"lonmin": -55, "lonmax": -54.5, "latmin": 2, "latmax": 2.5}

        self.static_stac_provider = "foo_static"
        self.dag.update_providers_config(
            f"""
            {self.static_stac_provider}:
                search:
                    type: StaticStacSearch
                    api_endpoint: {self.root_cat}
                products:
                    GENERIC_COLLECTION:
                        _collection: '{{collection}}'
                download:
                    type: HTTPDownload
                    base_uri: https://fake-endpoint
        """
        )
        self.dag.set_preferred_provider(self.static_stac_provider)

    def tearDown(self):
        super(TestSearchStacStatic, self).tearDown()
        # stop Mock and remove tmp config dir
        self.expanduser_mock.stop()
        self.tmp_home_dir.cleanup()

    def test_search_stac_static(self):
        """Use StaticStacSearch plugin to search all items"""
        # mock on fetch_collections_list not needed with provider specified,
        #    as product types discovery must be disabled by default for stac static
        search_result = self.dag.search(
            provider=self.static_stac_provider, count=True, validate=False
        )
        self.assertEqual(len(search_result), self.root_cat_len)
        self.assertEqual(search_result.number_matched, self.root_cat_len)
        for item in search_result:
            self.assertEqual(item.provider, self.static_stac_provider)

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.sessions.Session.request",
        autospec=True,
    )
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_collections_list", autospec=True
    )
    def test_search_stac_static_by_date(
        self, mock_fetch_collections_list, mock_auth_session_request
    ):
        """Use StaticStacSearch plugin to search by date"""
        filtered_sr = self.dag.search(
            start="2018-01-01", end="2019-01-01", count=True, validate=False
        )
        self.assertEqual(len(filtered_sr), self.child_cat_len)
        self.assertEqual(filtered_sr.number_matched, self.child_cat_len)
        for item in filtered_sr:
            self.assertIn("2018", item.properties["start_datetime"])

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.sessions.Session.request",
        autospec=True,
    )
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_collections_list", autospec=True
    )
    def test_search_stac_static_by_geom(
        self, mock_fetch_collections_list, mock_auth_session_request
    ):
        """Use StaticStacSearch plugin to search by geometry"""
        search_result = self.dag.search(
            geom=self.extent_big, count=True, validate=False
        )
        self.assertEqual(len(search_result), 3)
        self.assertEqual(search_result.number_matched, 3)

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.sessions.Session.request",
        autospec=True,
    )
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_collections_list", autospec=True
    )
    def test_search_stac_static_by_property(
        self, mock_fetch_collections_list, mock_auth_session_request
    ):
        """Use StaticStacSearch plugin to search by property"""
        search_result = self.dag.search(orbitNumber=110, count=True, validate=False)
        self.assertEqual(len(search_result), 3)
        self.assertEqual(search_result.number_matched, 3)

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.sessions.Session.request",
        autospec=True,
    )
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_collections_list", autospec=True
    )
    def test_search_stac_static_by_cloudcover(
        self, mock_fetch_collections_list, mock_auth_session_request
    ):
        """Use StaticStacSearch plugin to search by cloud cover"""
        search_result = self.dag.search(cloudCover=10, count=True, validate=False)
        self.assertEqual(len(search_result), 1)
        self.assertEqual(search_result.number_matched, 1)
