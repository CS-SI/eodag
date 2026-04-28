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
from pathlib import Path
from unittest import mock

from eodag.api.product import EOProduct
from eodag.api.provider import Provider
from eodag.plugins.search import PreparedSearch
from eodag.utils import cached_yaml_load_all
from tests.units.search_plugins.base import BaseSearchPluginTest
from tests.utils import TEST_RESOURCES_PATH


class TestSearchPluginQueryStringSearchXml(BaseSearchPluginTest):
    def setUp(self):
        super().setUp()

        provider = "mundi"

        # manually add conf as this provider is not supported any more
        mundi_config = cached_yaml_load_all(
            Path(TEST_RESOURCES_PATH) / "mundi_conf.yml"
        )[0]
        self.plugins_manager.providers[provider] = Provider(mundi_config)
        self.plugins_manager.rebuild()

        # One of the providers that has a QueryStringSearch Search plugin and result_type=xml
        self.mundi_search_plugin = self.get_search_plugin(self.collection, provider)
        self.mundi_auth_plugin = self.get_auth_plugin(self.mundi_search_plugin)

    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.QueryStringSearch._request",
        autospec=True,
    )
    def test_plugins_search_querystringsearch_xml_count_and_search_mundi(
        self, mock__request
    ):
        """A query with a QueryStringSearch (mundi here) must return tuple with a list of EOProduct and a number of available products"""  # noqa
        with open(self.provider_resp_dir / "mundi_search.xml", "rb") as f:
            mundi_resp_search = f.read()
        mock__request.return_value = mock.Mock()
        mock__request.return_value.content = mundi_resp_search

        products = self.mundi_search_plugin.query(
            prep=PreparedSearch(
                page=1,
                limit=2,
                auth_plugin=self.mundi_auth_plugin,
            ),
            **self.search_criteria_s2_msi_l1c,
        )

        # Specific expected results
        mundi_url_search = (
            "https://Sentinel2.browse.catalog.mundiwebservices.com/opensearch?timeStart=2020-08-08T00:00:00.000Z&"
            "timeEnd=2020-08-16T00:00:00.000Z&geometry="
            "POLYGON ((137.7729 13.1342, 137.7729 23.8860, 153.7491 23.8860, 153.7491 13.1342, 137.7729 13.1342))&"
            "productType=IMAGE&processingLevel=L1C&format=atom&relation=intersects&maxRecords=2&startIndex=1"
        )
        mundi_products_count = 47
        number_of_products = 2

        mock__request.assert_called_once()
        self.assertEqual(mock__request.call_args_list[-1][0][1].url, mundi_url_search)

        self.assertEqual(products.number_matched, mundi_products_count)
        self.assertEqual(len(products.data), number_of_products)
        self.assertIsInstance(products.data[0], EOProduct)

    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.QueryStringSearch.count_hits",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.QueryStringSearch._request",
        autospec=True,
    )
    def test_plugins_search_querystringsearch_xml_no_count_and_search_mundi(
        self, mock__request, mock_count_hits
    ):
        """A query with a QueryStringSearch (here mundi) without a count"""
        with open(self.provider_resp_dir / "mundi_search.xml", "rb") as f:
            mundi_resp_search = f.read()
        mock__request.return_value = mock.Mock()
        mock__request.return_value.content = mundi_resp_search

        products = self.mundi_search_plugin.query(
            prep=PreparedSearch(
                count=False,
                page=1,
                limit=2,
                auth_plugin=self.mundi_auth_plugin,
            ),
            **self.search_criteria_s2_msi_l1c,
        )

        # Specific expected results
        mundi_url_search = (
            "https://Sentinel2.browse.catalog.mundiwebservices.com/opensearch?timeStart=2020-08-08T00:00:00.000Z&"
            "timeEnd=2020-08-16T00:00:00.000Z&geometry="
            "POLYGON ((137.7729 13.1342, 137.7729 23.8860, 153.7491 23.8860, 153.7491 13.1342, 137.7729 13.1342))&"
            "productType=IMAGE&processingLevel=L1C&format=atom&relation=intersects&maxRecords=2&startIndex=1"
        )
        number_of_products = 2

        mock_count_hits.assert_not_called()
        mock__request.assert_called_once()
        self.assertEqual(mock__request.call_args_list[-1][0][1].url, mundi_url_search)

        self.assertIsNone(products.number_matched)
        self.assertEqual(len(products.data), number_of_products)
        self.assertIsInstance(products.data[0], EOProduct)

    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.QueryStringSearch.count_hits",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.QueryStringSearch._request",
        autospec=True,
    )
    def test_plugins_search_querystringsearch_xml_distinct_collection_mtd_mapping(
        self, mock__request, mock_count_hits
    ):
        """The metadata mapping for XML QueryStringSearch should not mix specific collections metadata-mapping"""
        with open(self.provider_resp_dir / "mundi_search.xml", "rb") as f:
            mundi_resp_search = f.read()
        mock__request.return_value = mock.Mock()
        mock__request.return_value.content = mundi_resp_search

        search_plugin = self.get_search_plugin(self.collection, "mundi")

        # update metadata_mapping only for S1_SAR_GRD
        search_plugin.config.products["S1_SAR_GRD"]["metadata_mapping"]["bar"] = (
            None,
            "dc:creator/text()",
        )
        products = search_plugin.query(
            collection="S1_SAR_GRD",
        )
        self.assertIn("bar", products.data[0].properties)
        self.assertEqual(products.data[0].properties["bar"], "dhus")

        # search with another collection
        self.assertNotIn(
            "bar", search_plugin.config.products["S1_SAR_SLC"]["metadata_mapping"]
        )
        products = search_plugin.query(
            collection="S1_SAR_SLC",
        )
        self.assertNotIn("bar", products.data[0].properties)
