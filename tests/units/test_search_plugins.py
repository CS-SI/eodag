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

import json
import unittest
from pathlib import Path
from unittest import mock

from tests.context import (
    TEST_RESOURCES_PATH,
    EOProduct,
    PluginManager,
    get_geometry_from_various,
    load_default_config,
)


class BaseSearchPluginTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        providers_config = load_default_config()
        cls.plugins_manager = PluginManager(providers_config)
        cls.product_type = "S2_MSI_L1C"
        geom = [137.772897, 13.134202, 153.749135, 23.885986]
        geometry = get_geometry_from_various([], geometry=geom)
        cls.search_criteria_s2_msi_l1c = {
            "productType": cls.product_type,
            "startTimeFromAscendingNode": "2020-08-08",
            "completionTimeFromAscendingNode": "2020-08-16",
            "geometry": geometry,
        }
        cls.provider_resp_dir = Path(TEST_RESOURCES_PATH) / "provider_responses"

    def get_search_plugin(self, product_type=None, provider=None):
        return next(
            self.plugins_manager.get_search_plugins(
                product_type=product_type, provider=provider
            )
        )

    def get_auth_plugin(self, provider):
        return self.plugins_manager.get_auth_plugin(provider)


class TestSearchPluginQueryStringSearch(BaseSearchPluginTest):
    def setUp(self):
        # One of the providers that has a QueryStringSearch Search plugin
        provider = "sobloo"
        self.sobloo_search_plugin = self.get_search_plugin(self.product_type, provider)
        self.sobloo_auth_plugin = self.get_auth_plugin(provider)
        # Some expected results
        with open(self.provider_resp_dir / "sobloo_count.json") as f:
            self.sobloo_resp_count = json.load(f)
        self.sobloo_url_count = "https://sobloo.eu/api/v1/services/search?f=acquisition.beginViewingDate:gte:1596844800000&f=acquisition.endViewingDate:lte:1597536000000&f=identification.type:eq:S2MSI1C&gintersect=POLYGON ((137.7729 13.1342, 137.7729 23.8860, 153.7491 23.8860, 153.7491 13.1342, 137.7729 13.1342))&size=1&from=0"  # noqa
        self.sobloo_products_count = 47

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_querystringseach_count_and_search_sobloo(
        self, mock__request
    ):
        """A query with a QueryStringSearch (sobloo here) must return tuple with a list of EOProduct and a number of available products"""  # noqa
        with open(self.provider_resp_dir / "sobloo_search.json") as f:
            sobloo_resp_search = json.load(f)
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.side_effect = [
            self.sobloo_resp_count,
            sobloo_resp_search,
        ]
        products, estimate = self.sobloo_search_plugin.query(
            page=1,
            items_per_page=2,
            auth=self.sobloo_auth_plugin,
            **self.search_criteria_s2_msi_l1c
        )

        # Specific expected results
        sobloo_url_search = "https://sobloo.eu/api/v1/services/search?f=acquisition.beginViewingDate:gte:1596844800000&f=acquisition.endViewingDate:lte:1597536000000&f=identification.type:eq:S2MSI1C&gintersect=POLYGON ((137.7729 13.1342, 137.7729 23.8860, 153.7491 23.8860, 153.7491 13.1342, 137.7729 13.1342))&size=2&from=0"  # noqa
        number_of_products = 2

        mock__request.assert_any_call(
            mock.ANY,
            self.sobloo_url_count,
            info_message=mock.ANY,
            exception_message=mock.ANY,
        )
        mock__request.assert_called_with(
            mock.ANY,
            sobloo_url_search,
            info_message=mock.ANY,
            exception_message=mock.ANY,
        )
        self.assertEqual(estimate, self.sobloo_products_count)
        self.assertEqual(len(products), number_of_products)
        self.assertIsInstance(products[0], EOProduct)

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.count_hits", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_querystringseach_no_count_and_search_sobloo(
        self, mock__request, mock_count_hits
    ):
        """A query with a QueryStringSearch (here sobloo) without a count"""
        with open(self.provider_resp_dir / "sobloo_search.json") as f:
            sobloo_resp_search = json.load(f)
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.return_value = sobloo_resp_search
        products, estimate = self.sobloo_search_plugin.query(
            count=False,
            page=1,
            items_per_page=2,
            auth=self.sobloo_auth_plugin,
            **self.search_criteria_s2_msi_l1c
        )

        # Specific expected results
        sobloo_url_search = "https://sobloo.eu/api/v1/services/search?f=acquisition.beginViewingDate:gte:1596844800000&f=acquisition.endViewingDate:lte:1597536000000&f=identification.type:eq:S2MSI1C&gintersect=POLYGON ((137.7729 13.1342, 137.7729 23.8860, 153.7491 23.8860, 153.7491 13.1342, 137.7729 13.1342))&size=2&from=0"  # noqa
        number_of_products = 2

        mock_count_hits.assert_not_called()
        mock__request.assert_called_once_with(
            mock.ANY,
            sobloo_url_search,
            info_message=mock.ANY,
            exception_message=mock.ANY,
        )
        self.assertIsNone(estimate)
        self.assertEqual(len(products), number_of_products)
        self.assertIsInstance(products[0], EOProduct)

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_querystringseach_discover_product_types(
        self, mock__request
    ):
        """QueryStringSearch.discover_product_types must return a well formatted dict"""
        # One of the providers that has a QueryStringSearch Search plugin and discover_product_types configured
        provider = "creodias"
        search_plugin = self.get_search_plugin(self.product_type, provider)

        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.return_value = {
            "collections": [
                {
                    "id": "foo_collection",
                    "displayName": "The FOO collection",
                    "billing": "free",
                },
                {
                    "id": "bar_collection",
                    "displayName": "The BAR non-free collection",
                    "billing": "non-free",
                },
            ]
        }
        conf_update_dict = search_plugin.discover_product_types()
        self.assertIn("foo_collection", conf_update_dict["providers_config"])
        self.assertIn("foo_collection", conf_update_dict["product_types_config"])
        self.assertNotIn("bar_collection", conf_update_dict["providers_config"])
        self.assertNotIn("bar_collection", conf_update_dict["product_types_config"])
        self.assertEqual(
            conf_update_dict["providers_config"]["foo_collection"]["collection"],
            "foo_collection",
        )
        self.assertEqual(
            conf_update_dict["product_types_config"]["foo_collection"]["title"],
            "The FOO collection",
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_querystringseach_discover_product_types_keywords(
        self, mock__request
    ):
        """QueryStringSearch.discover_product_types must return a dict with well formatted keywords"""
        # One of the providers that has a QueryStringSearch Search plugin and keywords configured
        provider = "astraea_eod"
        search_plugin = self.get_search_plugin(self.product_type, provider)

        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.return_value = {
            "collections": [
                {
                    "id": "foo_collection",
                    "keywords": ["foo", "bar"],
                    "summaries": {
                        "instruments": ["baZ"],
                        "constellation": "qux,foo",
                        "platform": ["quux", "corge", "bar"],
                        "processing:level": "GRAULT",
                    },
                },
            ]
        }
        conf_update_dict = search_plugin.discover_product_types()
        keywords_list = conf_update_dict["product_types_config"]["foo_collection"][
            "keywords"
        ].split(",")

        self.assertEqual(
            [
                "bar",
                "baz",
                "corge",
                "foo",
                "foo-collection",
                "grault",
                "quux",
                "qux",
            ],
            keywords_list,
        )


class TestSearchPluginPostJsonSearch(BaseSearchPluginTest):
    def setUp(self):
        # One of the providers that has a PostJsonSearch Search plugin
        provider = "aws_eos"
        self.awseos_search_plugin = self.get_search_plugin(self.product_type, provider)
        self.awseos_auth_plugin = self.get_auth_plugin(provider)
        self.awseos_auth_plugin.config.credentials = dict(apikey="dummyapikey")
        # Some expected results
        with open(self.provider_resp_dir / "awseos_count.json") as f:
            self.awseos_resp_count = json.load(f)
        self.awseos_url = (
            "https://gate.eos.com/api/lms/search/v2/sentinel2?api_key=dummyapikey"
        )
        self.awseos_products_count = 44

    @mock.patch("eodag.plugins.search.qssearch.PostJsonSearch._request", autospec=True)
    def test_plugins_search_postjsonsearch_count_and_search_awseos(self, mock__request):
        """A query with a PostJsonSearch (here aws_eos) must return tuple with a list of EOProduct and a number of available products"""  # noqa
        with open(self.provider_resp_dir / "awseos_search.json") as f:
            awseos_resp_search = json.load(f)
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.side_effect = [
            self.awseos_resp_count,
            awseos_resp_search,
        ]
        products, estimate = self.awseos_search_plugin.query(
            page=1,
            items_per_page=2,
            auth=self.awseos_auth_plugin,
            **self.search_criteria_s2_msi_l1c
        )

        # Specific expected results
        number_of_products = 2

        mock__request.assert_any_call(
            mock.ANY,
            self.awseos_url,
            info_message=mock.ANY,
            exception_message=mock.ANY,
        )
        mock__request.assert_called_with(
            mock.ANY,
            self.awseos_url,
            info_message=mock.ANY,
            exception_message=mock.ANY,
        )

        self.assertEqual(estimate, self.awseos_products_count)
        self.assertEqual(len(products), number_of_products)
        self.assertIsInstance(products[0], EOProduct)

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.count_hits", autospec=True
    )
    @mock.patch("eodag.plugins.search.qssearch.PostJsonSearch._request", autospec=True)
    def test_plugins_search_postjsonsearch_no_count_and_search_awseos(
        self, mock__request, mock_count_hits
    ):
        """A query with a PostJsonSearch (here aws_eos) without a count"""
        with open(self.provider_resp_dir / "awseos_search.json") as f:
            awseos_resp_search = json.load(f)
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.return_value = awseos_resp_search
        products, estimate = self.awseos_search_plugin.query(
            count=False,
            page=1,
            items_per_page=2,
            auth=self.awseos_auth_plugin,
            **self.search_criteria_s2_msi_l1c
        )

        # Specific expected results
        number_of_products = 2

        mock_count_hits.assert_not_called()
        mock__request.assert_called_once_with(
            mock.ANY,
            self.awseos_url,
            info_message=mock.ANY,
            exception_message=mock.ANY,
        )

        self.assertIsNone(estimate)
        self.assertEqual(len(products), number_of_products)
        self.assertIsInstance(products[0], EOProduct)


class TestSearchPluginODataV4Search(BaseSearchPluginTest):
    def setUp(self):
        # One of the providers that has a ODataV4Search Search plugin
        provider = "onda"
        self.onda_search_plugin = self.get_search_plugin(self.product_type, provider)
        self.onda_auth_plugin = self.get_auth_plugin(provider)
        # Some expected results
        with open(self.provider_resp_dir / "onda_count.json") as f:
            self.onda_resp_count = json.load(f)
        self.onda_url_count = 'https://catalogue.onda-dias.eu/dias-catalogue/Products/$count?productType=S2MSI1C&$search="footprint:"Intersects(POLYGON ((137.7729 13.1342, 137.7729 23.8860, 153.7491 23.8860, 153.7491 13.1342, 137.7729 13.1342)))" AND productType:S2MSI1C AND beginPosition:[2020-08-08T00:00:00.000Z TO *] AND endPosition:[* TO 2020-08-16T00:00:00.000Z]"'  # noqa
        self.onda_products_count = 47

    @mock.patch("eodag.plugins.search.qssearch.requests.get", autospec=True)
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_odatav4search_count_and_search_onda(
        self, mock__request, mock_requests_get
    ):
        """A query with a ODataV4Search (here onda) must return tuple with a list of EOProduct and a number of available products"""  # noqa
        with open(self.provider_resp_dir / "onda_search.json") as f:
            onda_resp_search = json.load(f)
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.side_effect = [
            self.onda_resp_count,
            onda_resp_search,
        ]
        mock_requests_get.return_value = mock.Mock()
        # Mock requests.get in ODataV4Search.do_search that sends a request per product
        # obtained by QueryStringSearch.do_search to retrieve its metadata.
        # Just use dummy metadata here for the test.
        mock_requests_get.return_value.json.return_value = dict(
            value=[dict(id="dummy_metadata", value="dummy_metadata_val")]
        )
        products, estimate = self.onda_search_plugin.query(
            page=1,
            items_per_page=2,
            auth=self.onda_auth_plugin,
            **self.search_criteria_s2_msi_l1c
        )

        # Specific expected results
        number_of_products = 2
        onda_url_search = 'https://catalogue.onda-dias.eu/dias-catalogue/Products?productType=S2MSI1C&$format=json&$search="footprint:"Intersects(POLYGON ((137.7729 13.1342, 137.7729 23.8860, 153.7491 23.8860, 153.7491 13.1342, 137.7729 13.1342)))" AND productType:S2MSI1C AND beginPosition:[2020-08-08T00:00:00.000Z TO *] AND endPosition:[* TO 2020-08-16T00:00:00.000Z]"&$top=2&$skip=0'  # noqa

        mock__request.assert_any_call(
            mock.ANY,
            self.onda_url_count,
            info_message=mock.ANY,
            exception_message=mock.ANY,
        )
        mock__request.assert_called_with(
            mock.ANY,
            onda_url_search,
            info_message=mock.ANY,
            exception_message=mock.ANY,
        )

        self.assertEqual(estimate, self.onda_products_count)
        self.assertEqual(len(products), number_of_products)
        self.assertIsInstance(products[0], EOProduct)


class TestSearchPluginStacSearch(BaseSearchPluginTest):
    @mock.patch("eodag.plugins.search.qssearch.StacSearch._request", autospec=True)
    def test_plugins_search_stacsearch_mapping_earthsearch(self, mock__request):
        """The metadata mapping for earth_search should return well formatted results"""  # noqa

        geojson_geometry = self.search_criteria_s2_msi_l1c["geometry"].__geo_interface__

        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.side_effect = [
            {
                "context": {"page": 1, "limit": 2, "matched": 1, "returned": 2},
            },
            {
                "features": [
                    {
                        "id": "foo",
                        "geometry": geojson_geometry,
                        "properties": {
                            "sentinel:product_id": "S2B_MSIL1C_20201009T012345_N0209_R008_T31TCJ_20201009T123456",
                        },
                    },
                    {
                        "id": "bar",
                        "geometry": geojson_geometry,
                        "properties": {
                            "sentinel:product_id": "S2B_MSIL1C_20200910T012345_N0209_R008_T31TCJ_20200910T123456",
                        },
                    },
                    {
                        "id": "bar",
                        "geometry": geojson_geometry,
                        "properties": {
                            "sentinel:product_id": "S2B_MSIL1C_20201010T012345_N0209_R008_T31TCJ_20201010T123456",
                        },
                    },
                ]
            },
        ]

        search_plugin = self.get_search_plugin(self.product_type, "earth_search")

        products, estimate = search_plugin.query(
            page=1, items_per_page=2, auth=None, **self.search_criteria_s2_msi_l1c
        )
        self.assertEqual(
            products[0].properties["productPath"],
            "products/2020/10/9/S2B_MSIL1C_20201009T012345_N0209_R008_T31TCJ_20201009T123456",
        )
        self.assertEqual(
            products[1].properties["productPath"],
            "products/2020/9/10/S2B_MSIL1C_20200910T012345_N0209_R008_T31TCJ_20200910T123456",
        )
        self.assertEqual(
            products[2].properties["productPath"],
            "products/2020/10/10/S2B_MSIL1C_20201010T012345_N0209_R008_T31TCJ_20201010T123456",
        )

    @mock.patch("eodag.plugins.search.qssearch.StacSearch._request", autospec=True)
    def test_plugins_search_stacsearch_default_geometry(self, mock__request):
        """The metadata mapping for a stac provider should return a default geometry"""

        geojson_geometry = self.search_criteria_s2_msi_l1c["geometry"].__geo_interface__

        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.side_effect = [
            {
                "context": {"matched": 3},
            },
            {
                "features": [
                    {
                        "id": "foo",
                        "geometry": geojson_geometry,
                    },
                    {
                        "id": "bar",
                        "geometry": None,
                    },
                ]
            },
        ]

        search_plugin = self.get_search_plugin(self.product_type, "earth_search")

        products, estimate = search_plugin.query(
            page=1,
            items_per_page=3,
            auth=None,
        )
        self.assertEqual(
            products[0].geometry, self.search_criteria_s2_msi_l1c["geometry"]
        )
        self.assertEqual(products[1].geometry.bounds, (-180.0, -90.0, 180.0, 90.0))
