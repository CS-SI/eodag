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
import ast
import json
import os
import re
import ssl
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import boto3
import dateutil
import requests
import responses
import yaml
from botocore.stub import Stubber
from requests import RequestException

from eodag.utils.exceptions import TimeOutError
from tests.context import (
    DEFAULT_MISSION_START_DATE,
    HTTP_REQ_TIMEOUT,
    NOT_AVAILABLE,
    TEST_RESOURCES_PATH,
    USER_AGENT,
    AuthenticationError,
    EOProduct,
    MisconfiguredError,
    PluginManager,
    RequestError,
    cached_parse,
    get_geometry_from_various,
    load_default_config,
    override_config_from_mapping,
)


class BaseSearchPluginTest(unittest.TestCase):
    def setUp(self):
        super(BaseSearchPluginTest, self).setUp()
        providers_config = load_default_config()
        self.plugins_manager = PluginManager(providers_config)
        self.product_type = "S2_MSI_L1C"
        geom = [137.772897, 13.134202, 153.749135, 23.885986]
        geometry = get_geometry_from_various([], geometry=geom)
        self.search_criteria_s2_msi_l1c = {
            "productType": self.product_type,
            "startTimeFromAscendingNode": "2020-08-08",
            "completionTimeFromAscendingNode": "2020-08-16",
            "geometry": geometry,
        }
        self.provider_resp_dir = Path(TEST_RESOURCES_PATH) / "provider_responses"

    def get_search_plugin(self, product_type=None, provider=None):
        return next(
            self.plugins_manager.get_search_plugins(
                product_type=product_type, provider=provider
            )
        )

    def get_auth_plugin(self, provider):
        return self.plugins_manager.get_auth_plugin(provider)


class TestSearchPluginQueryStringSearchXml(BaseSearchPluginTest):
    def setUp(self):
        super(TestSearchPluginQueryStringSearchXml, self).setUp()

        # manually add conf as this provider is not supported any more
        providers_config = self.plugins_manager.providers_config
        mundi_config_yaml = """
            mundi:
                search:
                    type: QueryStringSearch
                    api_endpoint: 'https://{collection}.browse.catalog.mundiwebservices.com/opensearch'
                    need_auth: false
                    result_type: 'xml'
                    results_entry: '//ns:entry'
                    literal_search_params:
                        format: atom
                        relation: intersects
                    pagination:
                        next_page_url_tpl: '{url}?{search}&maxRecords={items_per_page}&startIndex={skip_base_1}'
                        total_items_nb_key_path: '//os:totalResults/text()'
                        max_items_per_page: 50
                    discover_metadata:
                        auto_discovery: true
                        metadata_pattern: '^(?!collection)[a-zA-Z0-9]+$'
                        search_param: '{metadata}={{{metadata}}}'
                        metadata_path: '*'
                    metadata_mapping:
                        productType:
                            - 'productType'
                            - 'eo:productType/text()'
                        processingLevel:
                            - 'processingLevel'
                            - 'eo:processingLevel/text()'
                        title: 'ns:title/text()'
                        startTimeFromAscendingNode:
                            - 'timeStart={startTimeFromAscendingNode#to_iso_utc_datetime}'
                            - 'DIAS:sensingStartDate/text()'
                        completionTimeFromAscendingNode:
                            - 'timeEnd={completionTimeFromAscendingNode#to_iso_utc_datetime}'
                            - 'DIAS:sensingStopDate/text()'
                        id:
                            - 'uid={id#remove_extension}'
                            - 'dc:identifier/text()'
                        tileIdentifier:
                            - 'tileIdentifier'
                            - 'DIAS:tileIdentifier/text()'
                        geometry:
                            - 'geometry={geometry#to_rounded_wkt}'
                            - '{georss:polygon|georss:where#from_georss}'
                products:
                    S1_SAR_GRD:
                        productType: GRD
                        collection: Sentinel1
                        metadata_mapping:
                            cloudCover: 'null/text()'
                    S1_SAR_SLC:
                        productType: SLC
                        collection: Sentinel1
                        metadata_mapping:
                            cloudCover: 'null/text()'
                    S2_MSI_L1C:
                        productType: IMAGE
                        processingLevel: L1C
                        collection: Sentinel2
                    GENERIC_PRODUCT_TYPE:
                        productType: '{productType}'
                        collection: '{collection}'
                        instrument: '{instrument}'
                        processingLevel: '{processingLevel}'
                auth:
                    type: HTTPHeaderAuth
                    headers:
                        Cookie: "seeedtoken={apikey}"
        """

        mundi_config_dict = yaml.safe_load(mundi_config_yaml)
        override_config_from_mapping(providers_config, mundi_config_dict)
        self.plugins_manager = PluginManager(providers_config)

        # One of the providers that has a QueryStringSearch Search plugin and result_type=xml
        provider = "mundi"
        self.mundi_search_plugin = self.get_search_plugin(self.product_type, provider)
        self.mundi_auth_plugin = self.get_auth_plugin(provider)

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_querystringsearch_xml_count_and_search_mundi(
        self, mock__request
    ):
        """A query with a QueryStringSearch (mundi here) must return tuple with a list of EOProduct and a number of available products"""  # noqa
        with open(self.provider_resp_dir / "mundi_search.xml", "rb") as f:
            mundi_resp_search = f.read()
        mock__request.return_value = mock.Mock()
        mock__request.return_value.content = mundi_resp_search

        products, estimate = self.mundi_search_plugin.query(
            page=1,
            items_per_page=2,
            auth=self.mundi_auth_plugin,
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

        mock__request.assert_called_once_with(
            mock.ANY,
            mundi_url_search,
            info_message=mock.ANY,
            exception_message=mock.ANY,
        )
        self.assertEqual(estimate, mundi_products_count)
        self.assertEqual(len(products), number_of_products)
        self.assertIsInstance(products[0], EOProduct)
        # products count extracted from search results
        self.assertEqual(self.mundi_search_plugin.total_items_nb, mundi_products_count)

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.count_hits", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_querystringsearch_xml_no_count_and_search_mundi(
        self, mock__request, mock_count_hits
    ):
        """A query with a QueryStringSearch (here mundi) without a count"""
        with open(self.provider_resp_dir / "mundi_search.xml", "rb") as f:
            mundi_resp_search = f.read()
        mock__request.return_value = mock.Mock()
        mock__request.return_value.content = mundi_resp_search

        products, estimate = self.mundi_search_plugin.query(
            count=False,
            page=1,
            items_per_page=2,
            auth=self.mundi_auth_plugin,
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
        mock__request.assert_called_once_with(
            mock.ANY,
            mundi_url_search,
            info_message=mock.ANY,
            exception_message=mock.ANY,
        )
        self.assertIsNone(estimate)
        self.assertEqual(len(products), number_of_products)
        self.assertIsInstance(products[0], EOProduct)
        # products count should not have been extracted from search results
        self.assertIsNone(getattr(self.mundi_search_plugin, "total_items_nb", None))

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.count_hits", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_querystringsearch_xml_distinct_product_type_mtd_mapping(
        self, mock__request, mock_count_hits
    ):
        """The metadata mapping for XML QueryStringSearch should not mix specific product-types metadata-mapping"""
        with open(self.provider_resp_dir / "mundi_search.xml", "rb") as f:
            mundi_resp_search = f.read()
        mock__request.return_value = mock.Mock()
        mock__request.return_value.content = mundi_resp_search

        search_plugin = self.get_search_plugin(self.product_type, "mundi")

        # update metadata_mapping only for S1_SAR_GRD
        search_plugin.config.products["S1_SAR_GRD"]["metadata_mapping"]["bar"] = (
            None,
            "dc:creator/text()",
        )
        products, estimate = search_plugin.query(
            productType="S1_SAR_GRD",
            auth=None,
        )
        self.assertIn("bar", products[0].properties)
        self.assertEqual(products[0].properties["bar"], "dhus")

        # search with another product type
        self.assertNotIn(
            "bar", search_plugin.config.products["S1_SAR_SLC"]["metadata_mapping"]
        )
        products, estimate = search_plugin.query(
            productType="S1_SAR_SLC",
            auth=None,
        )
        self.assertNotIn("bar", products[0].properties)


class TestSearchPluginQueryStringSearch(BaseSearchPluginTest):
    def setUp(self):
        super(TestSearchPluginQueryStringSearch, self).setUp()
        # One of the providers that has a QueryStringSearch Search plugin
        provider = "peps"
        self.peps_search_plugin = self.get_search_plugin(self.product_type, provider)
        self.peps_auth_plugin = self.get_auth_plugin(provider)

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_querystringsearch_count_and_search_peps(
        self, mock__request
    ):
        """A query with a QueryStringSearch (peps here) must return tuple with a list of EOProduct and a number of available products"""  # noqa
        with open(self.provider_resp_dir / "peps_search.json") as f:
            peps_resp_search = json.load(f)
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.side_effect = [
            peps_resp_search,
        ]
        products, estimate = self.peps_search_plugin.query(
            page=1,
            items_per_page=2,
            auth=self.peps_auth_plugin,
            **self.search_criteria_s2_msi_l1c,
        )

        # Specific expected results
        peps_url_search = (
            "https://peps.cnes.fr/resto/api/collections/S2ST/search.json?startDate=2020-08-08&"
            "completionDate=2020-08-16&geometry=POLYGON ((137.7729 13.1342, 137.7729 23.8860, 153.7491 23.8860, "
            "153.7491 13.1342, 137.7729 13.1342))&productType=S2MSI1C&maxRecords=2&page=1"
        )
        peps_products_count = 47
        number_of_products = 2

        mock__request.assert_called_once_with(
            mock.ANY,
            peps_url_search,
            info_message=mock.ANY,
            exception_message=mock.ANY,
        )
        self.assertEqual(estimate, peps_products_count)
        self.assertEqual(len(products), number_of_products)
        self.assertIsInstance(products[0], EOProduct)
        # products count extracted from search results
        self.assertEqual(self.peps_search_plugin.total_items_nb, peps_products_count)

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.count_hits", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_querystringsearch_no_count_and_search_peps(
        self, mock__request, mock_count_hits
    ):
        """A query with a QueryStringSearch (here peps) without a count"""
        with open(self.provider_resp_dir / "peps_search.json") as f:
            peps_resp_search = json.load(f)
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.return_value = peps_resp_search
        products, estimate = self.peps_search_plugin.query(
            count=False,
            page=1,
            items_per_page=2,
            auth=self.peps_auth_plugin,
            **self.search_criteria_s2_msi_l1c,
        )

        # Specific expected results
        peps_url_search = (
            "https://peps.cnes.fr/resto/api/collections/S2ST/search.json?startDate=2020-08-08&"
            "completionDate=2020-08-16&geometry=POLYGON ((137.7729 13.1342, 137.7729 23.8860, 153.7491 23.8860, "
            "153.7491 13.1342, 137.7729 13.1342))&productType=S2MSI1C&maxRecords=2&page=1"
        )
        number_of_products = 2

        mock_count_hits.assert_not_called()
        mock__request.assert_called_once_with(
            mock.ANY,
            peps_url_search,
            info_message=mock.ANY,
            exception_message=mock.ANY,
        )
        self.assertIsNone(estimate)
        self.assertEqual(len(products), number_of_products)
        self.assertIsInstance(products[0], EOProduct)
        # products count should not have been extracted from search results
        self.assertIsNone(getattr(self.peps_search_plugin, "total_items_nb", None))

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.normalize_results",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_querystringsearch_search_cloudcover_peps(
        self, mock__request, mock_normalize_results
    ):
        """A query with a QueryStringSearch (here peps) must only use cloudCover filtering for non-radar product types"""  # noqa

        self.peps_search_plugin.query(productType="S2_MSI_L1C", cloudCover=50)
        mock__request.assert_called()
        self.assertIn("cloudCover", mock__request.call_args_list[-1][0][1])
        mock__request.reset_mock()

        self.peps_search_plugin.query(productType="S1_SAR_GRD", cloudCover=50)
        mock__request.assert_called()
        self.assertNotIn("cloudCover", mock__request.call_args_list[-1][0][1])

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_querystringsearch_discover_product_types(
        self, mock__request
    ):
        """QueryStringSearch.discover_product_types must return a well formatted dict"""
        # One of the providers that has a QueryStringSearch Search plugin and discover_product_types configured
        provider = "astraea_eod"
        search_plugin = self.get_search_plugin(self.product_type, provider)

        # change onfiguration for this test to filter out some collections
        results_entry = search_plugin.config.discover_product_types["results_entry"]
        search_plugin.config.discover_product_types["results_entry"] = cached_parse(
            'collections[?billing=="free"]'
        )

        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.return_value = {
            "collections": [
                {
                    "id": "foo_collection",
                    "title": "The FOO collection",
                    "billing": "free",
                },
                {
                    "id": "bar_collection",
                    "title": "The BAR non-free collection",
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
            conf_update_dict["providers_config"]["foo_collection"]["productType"],
            "foo_collection",
        )
        self.assertEqual(
            conf_update_dict["product_types_config"]["foo_collection"]["title"],
            "The FOO collection",
        )
        # restore configuration
        search_plugin.config.discover_product_types["results_entry"] = results_entry

    @mock.patch("eodag.plugins.search.qssearch.requests.get", autospec=True)
    def test_plugins_search_querystringsearch_discover_product_types_with_query_param(
        self, mock__request
    ):
        """QueryStringSearch.discover_product_types must return a well formatted dict"""
        # One of the providers that has a QueryStringSearch Search plugin and discover_product_types configured
        provider = "wekeo_cmems"
        search_plugin = self.get_search_plugin(provider=provider)

        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.side_effect = [
            {
                "features": [
                    {
                        "dataset_id": "foo_collection",
                        "metadata": {"title": "The FOO collection"},
                    }
                ]
            },
            {
                "dataset_id": "foo_collection",
                "metadata": {"title": "The FOO collection"},
            },
        ]
        search_plugin.discover_product_types()
        mock__request.assert_called_with(
            "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/datasets/foo_collection",
            timeout=HTTP_REQ_TIMEOUT,
            headers=USER_AGENT,
            verify=True,
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_querystringsearch_discover_product_types_keywords(
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

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_querystringsearch_distinct_product_type_mtd_mapping(
        self, mock__request
    ):
        """The metadata mapping for QueryStringSearch should not mix specific product-types metadata-mapping"""
        geojson_geometry = self.search_criteria_s2_msi_l1c["geometry"].__geo_interface__
        mock__request.return_value = mock.Mock()
        result = {
            "totalResults": 1,
            "features": [
                {
                    "id": "foo",
                    "geometry": geojson_geometry,
                },
            ],
        }
        mock__request.return_value.json.side_effect = [result, result]
        search_plugin = self.get_search_plugin(self.product_type, "peps")

        # update metadata_mapping only for S1_SAR_GRD
        search_plugin.config.products["S1_SAR_GRD"]["metadata_mapping"]["bar"] = (
            None,
            "baz",
        )
        products, estimate = search_plugin.query(
            productType="S1_SAR_GRD",
            auth=None,
        )
        self.assertIn("bar", products[0].properties)
        self.assertEqual(products[0].properties["bar"], "baz")

        # search with another product type
        self.assertNotIn(
            "bar", search_plugin.config.products["S1_SAR_SLC"]["metadata_mapping"]
        )
        products, estimate = search_plugin.query(
            productType="S1_SAR_SLC",
            auth=None,
        )
        self.assertNotIn("bar", products[0].properties)

    @mock.patch(
        "eodag.plugins.search.qssearch.requests.get",
        autospec=True,
        side_effect=requests.exceptions.Timeout(),
    )
    def test_plugins_search_querystringseach_timeout(self, mock__request):
        search_plugin = self.get_search_plugin(self.product_type, "peps")
        with self.assertRaises(TimeOutError):
            search_plugin.query(
                productType="S1_SAR_SLC",
                auth=None,
            )


class TestSearchPluginPostJsonSearch(BaseSearchPluginTest):
    def setUp(self):
        super(TestSearchPluginPostJsonSearch, self).setUp()
        # One of the providers that has a PostJsonSearch Search plugin
        provider = "aws_eos"
        self.awseos_search_plugin = self.get_search_plugin(self.product_type, provider)
        self.awseos_auth_plugin = self.get_auth_plugin(provider)
        self.awseos_auth_plugin.config.credentials = dict(apikey="dummyapikey")
        self.awseos_url = (
            "https://gate.eos.com/api/lms/search/v2/sentinel2?api_key=dummyapikey"
        )

    def test_plugins_search_postjsonsearch_request_error(self):
        """A query with a PostJsonSearch must handle requests errors"""

        @responses.activate(registry=responses.registries.FirstMatchRegistry)
        def run():
            responses.add(
                responses.POST, self.awseos_url, status=500, body=b"test error message"
            )

            with self.assertLogs("eodag.search.qssearch", level="DEBUG") as cm:
                with self.assertRaises(RequestError):
                    products, estimate = self.awseos_search_plugin.query(
                        page=1,
                        items_per_page=2,
                        auth=self.awseos_auth_plugin,
                        raise_errors=True,
                        **self.search_criteria_s2_msi_l1c,
                    )
                self.assertIn("test error message", str(cm.output))

        run()

    def test_plugins_search_postjsonsearch_request_auth_error(self):
        """A query with a PostJsonSearch must handle auth errors"""

        @responses.activate(registry=responses.registries.FirstMatchRegistry)
        def run():
            responses.add(
                responses.POST, self.awseos_url, status=403, body=b"test error message"
            )

            with self.assertRaisesRegex(AuthenticationError, "test error message"):
                products, estimate = self.awseos_search_plugin.query(
                    page=1,
                    items_per_page=2,
                    auth=self.awseos_auth_plugin,
                    **self.search_criteria_s2_msi_l1c,
                )

        run()

    @mock.patch("eodag.plugins.search.qssearch.PostJsonSearch._request", autospec=True)
    def test_plugins_search_postjsonsearch_count_and_search_awseos(self, mock__request):
        """A query with a PostJsonSearch (here aws_eos) must return tuple with a list of EOProduct and a number of available products"""  # noqa
        with open(self.provider_resp_dir / "awseos_search.json") as f:
            awseos_resp_search = json.load(f)
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.side_effect = [
            awseos_resp_search,
        ]
        products, estimate = self.awseos_search_plugin.query(
            page=1,
            items_per_page=2,
            auth=self.awseos_auth_plugin,
            **self.search_criteria_s2_msi_l1c,
        )

        # Specific expected results
        awseos_products_count = 44
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

        self.assertEqual(estimate, awseos_products_count)
        self.assertEqual(len(products), number_of_products)
        self.assertIsInstance(products[0], EOProduct)
        # products count extracted from search results
        self.assertEqual(
            self.awseos_search_plugin.total_items_nb, awseos_products_count
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_postjsonsearch_count_and_search_awseos_s2l2a(
        self, mock__request
    ):
        """A query with a PostJsonSearch (here aws_eos) must return a single EOProduct when search by id using specific_qssearch"""  # noqa

        mock_values = []
        with open(self.provider_resp_dir / "s2l2a_tileInfo.json") as f:
            mock_values.append(json.load(f))
        with open(self.provider_resp_dir / "s2l2a_productInfo.json") as f:
            mock_values.append(json.load(f))

        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.side_effect = mock_values

        products, estimate = self.awseos_search_plugin.query(
            auth=self.awseos_auth_plugin,
            **{
                "productType": "S2_MSI_L2A",
                "id": "S2B_MSIL2A_20220101T000459_N0301_R130_T53DMB_20220101T012649",
            },
        )

        self.assertEqual(mock__request.call_count, 2)
        mock__request.assert_any_call(
            mock.ANY,
            "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/53/D/MB/2022/1/1/0/tileInfo.json",
            info_message=mock.ANY,
            exception_message=mock.ANY,
        )
        mock__request.assert_called_with(
            mock.ANY,
            "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/53/D/MB/2022/1/1/0/productInfo.json",
            info_message=mock.ANY,
            exception_message=mock.ANY,
        )

        self.assertEqual(estimate, 1)
        self.assertEqual(len(products), 1)
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
            **self.search_criteria_s2_msi_l1c,
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
        # products count should not have been extracted from search results
        self.assertIsNone(getattr(self.awseos_search_plugin, "total_items_nb", None))

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.normalize_results",
        autospec=True,
    )
    @mock.patch("eodag.plugins.search.qssearch.requests.post", autospec=True)
    def test_plugins_search_postjsonsearch_search_cloudcover_awseos(
        self, mock_requests_post, mock_normalize_results
    ):
        """A query with a PostJsonSearch (here aws_eos) must only use cloudCover filtering for non-radar product types"""  # noqa

        self.awseos_search_plugin.query(
            auth=self.awseos_auth_plugin, productType="S2_MSI_L1C", cloudCover=50
        )
        mock_requests_post.assert_called()
        self.assertIn("cloudCoverage", str(mock_requests_post.call_args_list[-1][1]))
        mock_requests_post.reset_mock()

        self.awseos_search_plugin.query(
            auth=self.awseos_auth_plugin, productType="S1_SAR_GRD", cloudCover=50
        )
        mock_requests_post.assert_called()
        self.assertNotIn(
            "cloudCoverPercentage", str(mock_requests_post.call_args_list[-1][1])
        )

    @mock.patch("eodag.plugins.search.qssearch.PostJsonSearch._request", autospec=True)
    def test_plugins_search_postjsonsearch_distinct_product_type_mtd_mapping(
        self, mock__request
    ):
        """The metadata mapping for PostJsonSearch should not mix specific product-types metadata-mapping"""
        geojson_geometry = self.search_criteria_s2_msi_l1c["geometry"].__geo_interface__
        mock__request.return_value = mock.Mock()
        result = {
            "meta": {"page": 1, "found": 1, "limit": 2},
            "results": [
                {
                    "id": "foo",
                    "dataGeometry": geojson_geometry,
                },
            ],
        }
        mock__request.return_value.json.side_effect = [result, result]

        # update metadata_mapping only for S1_SAR_GRD
        self.awseos_search_plugin.config.products["S1_SAR_GRD"]["metadata_mapping"][
            "bar"
        ] = (
            None,
            "baz",
        )
        products, estimate = self.awseos_search_plugin.query(
            productType="S1_SAR_GRD",
            auth=self.awseos_auth_plugin,
        )
        self.assertIn("bar", products[0].properties)
        self.assertEqual(products[0].properties["bar"], "baz")

        # search with another product type
        self.assertNotIn(
            "bar",
            self.awseos_search_plugin.config.products["S2_MSI_L1C"]["metadata_mapping"],
        )
        products, estimate = self.awseos_search_plugin.query(
            productType="S2_MSI_L1C",
            auth=self.awseos_auth_plugin,
        )
        self.assertNotIn("bar", products[0].properties)


class TestSearchPluginODataV4Search(BaseSearchPluginTest):
    def setUp(self):
        super(TestSearchPluginODataV4Search, self).setUp()
        # One of the providers that has a ODataV4Search Search plugin
        provider = "onda"
        self.onda_search_plugin = self.get_search_plugin(self.product_type, provider)
        self.onda_auth_plugin = self.get_auth_plugin(provider)
        # Some expected results
        with open(self.provider_resp_dir / "onda_count.json") as f:
            self.onda_resp_count = json.load(f)
        self.onda_url_count = (
            'https://catalogue.onda-dias.eu/dias-catalogue/Products/$count?$search="footprint:"'
            "Intersects(POLYGON ((137.7729 13.1342, 137.7729 23.8860, 153.7491 23.8860, 153.7491 13.1342, "
            '137.7729 13.1342)))" AND productType:S2MSI1C AND beginPosition:[2020-08-08T00:00:00.000Z TO *] '
            'AND endPosition:[* TO 2020-08-16T00:00:00.000Z] AND foo:bar"'
        )
        self.onda_products_count = 47

    def test_plugins_search_odatav4search_normalize_results_onda(self):
        """ODataV4Search.normalize_results must use metada pre-mapping if configured"""

        self.assertTrue(hasattr(self.onda_search_plugin.config, "metadata_pre_mapping"))
        self.assertDictEqual(
            self.onda_search_plugin.config.metadata_pre_mapping,
            {
                "metadata_path": cached_parse("$.Metadata"),
                "metadata_path_id": "id",
                "metadata_path_value": "value",
            },
        )
        self.assertEqual(
            self.onda_search_plugin.config.discover_metadata["metadata_path"],
            "$.Metadata.*",
        )

        raw_results = [
            {"Metadata": [{"id": "foo", "value": "bar"}], "footprint": "POINT (0 0)"}
        ]
        products = self.onda_search_plugin.normalize_results(raw_results)

        self.assertEqual(products[0].properties["foo"], "bar")

    @mock.patch("eodag.plugins.search.qssearch.requests.get", autospec=True)
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_odatav4search_count_and_search_onda(
        self, mock__request, mock_requests_get
    ):
        """A query with a ODataV4Search (here onda) must return tuple with a list of EOProduct and a number of available products"""  # noqa
        # per_product_metadata_query parameter is updated to False if it is necessary
        per_product_metadata_query = (
            self.onda_search_plugin.config.per_product_metadata_query
        )
        if per_product_metadata_query:
            self.onda_search_plugin.config.per_product_metadata_query = False

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
            # custom query argument that must be mapped using discovery_metata.search_param
            foo="bar",
            **self.search_criteria_s2_msi_l1c,
        )
        # restore per_product_metadata_query initial value if it is necessary
        if (
            self.onda_search_plugin.config.per_product_metadata_query
            != per_product_metadata_query
        ):
            self.onda_search_plugin.config.per_product_metadata_query = (
                per_product_metadata_query
            )

        # Specific expected results
        number_of_products = 2
        onda_url_search = (
            'https://catalogue.onda-dias.eu/dias-catalogue/Products?$format=json&$search="'
            'footprint:"Intersects(POLYGON ((137.7729 13.1342, 137.7729 23.8860, 153.7491 23.8860, 153.7491 13.1342, '
            '137.7729 13.1342)))" AND productType:S2MSI1C AND beginPosition:[2020-08-08T00:00:00.000Z TO *] '
            "AND endPosition:[* TO 2020-08-16T00:00:00.000Z] "
            'AND foo:bar"&$orderby=beginPosition asc&$top=2&$skip=0&$expand=Metadata'
        )

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
        # products count non extracted from search results as count endpoint is specified
        self.assertFalse(hasattr(self.onda_search_plugin, "total_items_nb"))

    @mock.patch("eodag.plugins.search.qssearch.get_ssl_context", autospec=True)
    @mock.patch("eodag.plugins.search.qssearch.Request", autospec=True)
    @mock.patch("eodag.plugins.search.qssearch.urlopen", autospec=True)
    @mock.patch("eodag.plugins.search.qssearch.cast", autospec=True)
    def test_plugins_search_odatav4search_with_ssl_context(
        self, mock_cast, mock_urlopen, mock_request, mock_get_ssl_context
    ):
        """A query with a ODataV4Search (here onda) must return tuple with a list of EOProduct and a number of available products"""  # noqa
        self.onda_search_plugin.config.ssl_verify = False
        mock_cast.return_value.json.return_value = 2

        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        mock_request.return_value = mock.Mock()

        # Mocking return value of get_ssl_context
        mock_get_ssl_context.return_value = ssl_ctx

        self.onda_search_plugin.query(
            page=1,
            items_per_page=2,
            auth=self.onda_auth_plugin,
            # custom query argument that must be mapped using discovery_metata.search_param
            foo="bar",
            **self.search_criteria_s2_msi_l1c,
        )

        mock_get_ssl_context.assert_called_with(False)

        # # Asserting that get_ssl_context has been called
        self.assertEqual(mock_get_ssl_context.call_count, 2)

        # Asserting that urlopen has been called with the correct arguments
        mock_urlopen.assert_called_with(
            mock_request.return_value, timeout=60, context=ssl_ctx
        )

        del self.onda_search_plugin.config.ssl_verify

    @mock.patch("eodag.plugins.search.qssearch.requests.get", autospec=True)
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_odatav4search_count_and_search_onda_per_product_metadata_query(
        self, mock__request, mock_requests_get
    ):
        """A query with a ODataV4Search (here onda) must return tuple with a list of EOProduct and a number of available products for query per product metadata"""  # noqa
        # per_product_metadata_query parameter is updated to True if it is necessary
        per_product_metadata_query = (
            self.onda_search_plugin.config.per_product_metadata_query
        )
        if not per_product_metadata_query:
            self.onda_search_plugin.config.per_product_metadata_query = True

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
            # custom query argument that must be mapped using discovery_metata.search_param
            foo="bar",
            **self.search_criteria_s2_msi_l1c,
        )
        # restore per_product_metadata_query initial value if it is necessary
        if (
            self.onda_search_plugin.config.per_product_metadata_query
            != per_product_metadata_query
        ):
            self.onda_search_plugin.config.per_product_metadata_query = (
                per_product_metadata_query
            )

        # we check request arguments of the last call
        metadata_url = "{}({})/Metadata".format(
            self.onda_search_plugin.config.api_endpoint.rstrip("/"),
            products[1].properties["uid"],
        )
        mock_requests_get.assert_called_with(
            metadata_url, headers=USER_AGENT, timeout=HTTP_REQ_TIMEOUT, verify=True
        )
        # we check that two requests have been called, one per product
        self.assertEqual(mock_requests_get.call_count, 2)

        # Specific expected results
        number_of_products = 2
        onda_url_search = (
            'https://catalogue.onda-dias.eu/dias-catalogue/Products?$format=json&$search="'
            'footprint:"Intersects(POLYGON ((137.7729 13.1342, 137.7729 23.8860, 153.7491 23.8860, 153.7491 13.1342, '
            '137.7729 13.1342)))" AND productType:S2MSI1C AND beginPosition:[2020-08-08T00:00:00.000Z TO *] '
            "AND endPosition:[* TO 2020-08-16T00:00:00.000Z] "
            'AND foo:bar"&$orderby=beginPosition asc&$top=2&$skip=0&$expand=Metadata'
        )

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
        # products count non extracted from search results as count endpoint is specified
        self.assertFalse(hasattr(self.onda_search_plugin, "total_items_nb"))

    @mock.patch("eodag.plugins.search.qssearch.requests.get", autospec=True)
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_odatav4search_count_and_search_onda_per_product_metadata_query_request_error(
        self, mock__request, mock_requests_get
    ):
        """A query with a ODataV4Search (here onda) must handle requests errors for query per product metadata"""  # noqa
        # per_product_metadata_query parameter is updated to True if it is necessary
        per_product_metadata_query = (
            self.onda_search_plugin.config.per_product_metadata_query
        )
        if not per_product_metadata_query:
            self.onda_search_plugin.config.per_product_metadata_query = True
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
        mock_requests_get.side_effect = RequestException()

        with self.assertLogs(level="ERROR") as cm:
            products, estimate = self.onda_search_plugin.query(
                page=1,
                items_per_page=2,
                auth=self.onda_auth_plugin,
                # custom query argument that must be mapped using discovery_metata.search_param
                foo="bar",
                **self.search_criteria_s2_msi_l1c,
            )
            # restore per_product_metadata_query initial value if it is necessary
            if (
                self.onda_search_plugin.config.per_product_metadata_query
                != per_product_metadata_query
            ):
                self.onda_search_plugin.config.per_product_metadata_query = (
                    per_product_metadata_query
                )
            search_provider = self.onda_auth_plugin.provider
            search_type = self.onda_search_plugin.__class__.__name__
            error_message = f"Skipping error while searching for {search_provider} {search_type} instance:"
            error_message_indexes_list = [
                i.start() for i in re.finditer(error_message, str(cm.output))
            ]
            # we check that two errors have been logged, one per product
            self.assertEqual(len(error_message_indexes_list), 2)

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.normalize_results",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_odatav4search_search_cloudcover_onda(
        self, mock__request, mock_normalize_results
    ):
        """A query with a ODataV4Search (here onda) must only use cloudCover filtering for non-radar product types"""
        # per_product_metadata_query parameter is updated to False if it is necessary
        per_product_metadata_query = (
            self.onda_search_plugin.config.per_product_metadata_query
        )
        if per_product_metadata_query:
            self.onda_search_plugin.config.per_product_metadata_query = False

        self.onda_search_plugin.query(productType="S2_MSI_L1C", cloudCover=50)
        # restore per_product_metadata_query initial value if it is necessary
        if (
            self.onda_search_plugin.config.per_product_metadata_query
            != per_product_metadata_query
        ):
            self.onda_search_plugin.config.per_product_metadata_query = (
                per_product_metadata_query
            )

        mock__request.assert_called()
        self.assertIn("cloudCoverPercentage", mock__request.call_args_list[-1][0][1])
        mock__request.reset_mock()

        self.onda_search_plugin.query(productType="S1_SAR_GRD", cloudCover=50)
        mock__request.assert_called()
        self.assertNotIn("cloudCoverPercentage", mock__request.call_args_list[-1][0][1])

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_odatav4search_distinct_product_type_mtd_mapping(
        self, mock__request
    ):
        """The metadata mapping for ODataV4Search should not mix specific product-types metadata-mapping"""
        geojson_geometry = self.search_criteria_s2_msi_l1c["geometry"].__geo_interface__
        mock__request.return_value = mock.Mock()
        result = {
            "features": [
                {
                    "id": "foo",
                    "geometry": geojson_geometry,
                },
            ],
        }
        mock__request.return_value.json.side_effect = [result, result]
        search_plugin = self.get_search_plugin("onda")

        # update metadata_mapping only for S1_SAR_GRD
        search_plugin.config.products["S1_SAR_GRD"]["metadata_mapping"]["bar"] = (
            None,
            "baz",
        )
        products, estimate = search_plugin.query(
            productType="S1_SAR_GRD",
            auth=None,
        )
        self.assertIn("bar", products[0].properties)
        self.assertEqual(products[0].properties["bar"], "baz")

        # search with another product type
        self.assertNotIn(
            "bar", search_plugin.config.products["S1_SAR_SLC"]["metadata_mapping"]
        )
        products, estimate = search_plugin.query(
            productType="S1_SAR_SLC",
            auth=None,
        )
        self.assertNotIn("bar", products[0].properties)


class TestSearchPluginStacSearch(BaseSearchPluginTest):
    @mock.patch("eodag.plugins.search.qssearch.StacSearch._request", autospec=True)
    def test_plugins_search_stacsearch_mapping_earthsearch(self, mock__request):
        """The metadata mapping for earth_search should return well formatted results"""  # noqa

        geojson_geometry = self.search_criteria_s2_msi_l1c["geometry"].__geo_interface__

        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.side_effect = [
            {
                "features": [
                    {
                        "id": "foo",
                        "geometry": geojson_geometry,
                        "properties": {
                            "s2:product_uri": "S2B_MSIL1C_20201009T012345_N0209_R008_T31TCJ_20201009T123456.SAFE",
                        },
                    },
                    {
                        "id": "bar",
                        "geometry": geojson_geometry,
                        "properties": {
                            "s2:product_uri": "S2B_MSIL1C_20200910T012345_N0209_R008_T31TCJ_20200910T123456.SAFE",
                        },
                    },
                    {
                        "id": "bar",
                        "geometry": geojson_geometry,
                        "properties": {
                            "s2:product_uri": "S2B_MSIL1C_20201010T012345_N0209_R008_T31TCJ_20201010T123456.SAFE",
                        },
                    },
                ],
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
                "features": [
                    {
                        "id": "foo",
                        "geometry": geojson_geometry,
                    },
                    {
                        "id": "bar",
                        "geometry": None,
                    },
                ],
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

    @mock.patch("eodag.plugins.search.qssearch.StacSearch._request", autospec=True)
    def test_plugins_search_stacsearch_distinct_product_type_mtd_mapping(
        self, mock__request
    ):
        """The metadata mapping for a stac provider should not mix specific product-types metadata-mapping"""
        mock__request.return_value = mock.Mock()
        result = {
            "features": [
                {
                    "id": "foo",
                    "geometry": None,
                },
            ],
        }
        mock__request.return_value.json.side_effect = [result, result]
        search_plugin = self.get_search_plugin(self.product_type, "earth_search")

        # update metadata_mapping only for S2_MSI_L1C
        search_plugin.config.products["S2_MSI_L1C"]["metadata_mapping"]["bar"] = (
            None,
            "baz",
        )
        products, estimate = search_plugin.query(
            productType="S2_MSI_L1C",
            auth=None,
        )
        self.assertIn("bar", products[0].properties)
        self.assertEqual(products[0].properties["bar"], "baz")

        # search with another product type
        self.assertNotIn(
            "metadata_mapping", search_plugin.config.products["S1_SAR_GRD"]
        )
        products, estimate = search_plugin.query(
            productType="S1_SAR_GRD",
            auth=None,
        )
        self.assertNotIn("bar", products[0].properties)

    @mock.patch("eodag.plugins.search.qssearch.StacSearch._request", autospec=True)
    def test_plugins_search_stacsearch_distinct_product_type_mtd_mapping_astraea_eod(
        self, mock__request
    ):
        """The metadata mapping for a astraea_eod should correctly build assets"""
        mock__request.return_value = mock.Mock()
        result = {
            "features": [
                {
                    "id": "foo",
                    "geometry": None,
                    "assets": {
                        "productInfo": {"href": "s3://foo.bar/baz/productInfo.json"}
                    },
                },
            ],
        }
        product_type = "S1_SAR_GRD"
        mock__request.return_value.json.side_effect = [result]
        search_plugin = self.get_search_plugin(product_type, "astraea_eod")

        products, _ = search_plugin.query(
            productType=product_type,
            auth=None,
        )
        self.assertIn("productInfo", products[0].assets)
        self.assertEqual(
            products[0].assets["productInfo"]["href"],
            "s3://foo.bar/baz/productInfo.json",
        )
        self.assertIn("manifest.safe", products[0].assets)
        self.assertEqual(
            products[0].assets["manifest.safe"]["href"],
            "s3://foo.bar/baz/manifest.safe",
        )


class TestSearchPluginBuildPostSearchResult(BaseSearchPluginTest):
    @mock.patch("eodag.plugins.authentication.qsauth.requests.get", autospec=True)
    def setUp(self, mock_requests_get):
        super(TestSearchPluginBuildPostSearchResult, self).setUp()
        # enable long diffs in test reports
        self.maxDiff = None
        # One of the providers that has a BuildPostSearchResult Search plugin
        provider = "meteoblue"
        self.search_plugin = self.get_search_plugin(provider=provider)
        self.auth_plugin = self.get_auth_plugin(provider)
        self.auth_plugin.config.credentials = {"cred": "entials"}
        self.search_plugin.auth = self.auth_plugin.authenticate()

    @mock.patch("eodag.plugins.search.qssearch.requests.post", autospec=True)
    def test_plugins_search_buildpostsearchresult_count_and_search(
        self, mock_requests_post
    ):
        """A query with a BuildPostSearchResult must return a single result"""

        # custom query for meteoblue
        custom_query = {"queries": {"foo": "bar"}}
        products, estimate = self.search_plugin.query(
            auth=self.auth_plugin, **custom_query
        )

        mock_requests_post.assert_called_with(
            self.search_plugin.config.api_endpoint,
            json=mock.ANY,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            auth=self.search_plugin.auth,
            verify=True,
        )
        self.assertEqual(estimate, 1)
        self.assertIsInstance(products[0], EOProduct)
        endpoint = "https://my.meteoblue.com/dataset/query"
        default_geom = {
            "coordinates": [
                [[180, -90], [180, 90], [-180, 90], [-180, -90], [180, -90]]
            ],
            "type": "Polygon",
        }
        # check downloadLink
        self.assertEqual(
            products[0].properties["downloadLink"],
            f"{endpoint}?" + json.dumps({"geometry": default_geom, **custom_query}),
        )
        # check orderLink
        self.assertEqual(
            products[0].properties["orderLink"],
            f"{endpoint}?"
            + json.dumps(
                {"geometry": default_geom, "runOnJobQueue": True, **custom_query}
            ),
        )


class MockResponse:
    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data

    def raise_for_status(self):
        if self.status_code != 200:
            raise RequestError


class TestSearchPluginDataRequestSearch(BaseSearchPluginTest):
    @mock.patch(
        "eodag.plugins.authentication.token.requests.Session.request", autospec=True
    )
    def setUp(self, mock_requests_get):
        super(TestSearchPluginDataRequestSearch, self).setUp()
        providers_config = self.plugins_manager.providers_config
        wekeo_old_config_file = os.path.join(
            TEST_RESOURCES_PATH, "wekeo_old_config.yml"
        )
        with open(wekeo_old_config_file, "r") as file:
            wekeo_old_config_dict = yaml.safe_load(file)
        override_config_from_mapping(providers_config, wekeo_old_config_dict)
        self.plugins_manager = PluginManager(providers_config)
        provider = "wekeo_old"
        self.search_plugin = self.get_search_plugin(self.product_type, provider)
        self.auth_plugin = self.get_auth_plugin(provider)
        self.auth_plugin.config.credentials = {"username": "tony", "password": "pass"}
        mock_requests_get.return_value = MockResponse({"access_token": "token"}, 200)
        self.search_plugin.auth = self.auth_plugin.authenticate()

    @mock.patch("eodag.plugins.search.data_request_search.requests.post", autospec=True)
    @mock.patch("eodag.plugins.search.data_request_search.requests.get", autospec=True)
    def test_plugins_create_data_request(self, mock_requests_get, mock_requests_post):
        self.search_plugin._create_data_request(
            "EO:DEM:DAT:COP-DEM_GLO-30-DGED__2022_1",
            "COP_DEM_GLO30",
            productType="EO:DEM:DAT:COP-DEM_GLO-30-DGED__2022_1",
        )
        mock_requests_post.assert_called_with(
            self.search_plugin.config.data_request_url,
            json={"datasetId": "EO:DEM:DAT:COP-DEM_GLO-30-DGED__2022_1"},
            headers=getattr(self.search_plugin.auth, "headers", ""),
            timeout=HTTP_REQ_TIMEOUT,
            verify=True,
        )
        keywords = {
            "format": "GeoTiff100mt",
            "providerProductType": "Corine Land Cover 2018",
        }
        self.search_plugin._create_data_request(
            "EO:CLMS:DAT:CORINE",
            "CLMS_CORINE",
            productType="EO:CLMS:DAT:CORINE",
            **keywords,
        )
        mock_requests_post.assert_called_with(
            self.search_plugin.config.data_request_url,
            json={
                "datasetId": "EO:CLMS:DAT:CORINE",
                "stringChoiceValues": [
                    {"name": "format", "value": "GeoTiff100mt"},
                    {"name": "product_type", "value": "Corine Land Cover 2018"},
                ],
            },
            headers=getattr(self.search_plugin.auth, "headers", ""),
            timeout=HTTP_REQ_TIMEOUT,
            verify=True,
        )

    @mock.patch("eodag.plugins.search.data_request_search.requests.get", autospec=True)
    def test_plugins_check_request_status(self, mock_requests_get):
        mock_requests_get.return_value = MockResponse({"status": "completed"}, 200)
        successful = self.search_plugin._check_request_status("123")
        mock_requests_get.assert_called_with(
            self.search_plugin.config.status_url + "123",
            headers=getattr(self.search_plugin.auth, "headers", ""),
            timeout=HTTP_REQ_TIMEOUT,
            verify=True,
        )
        assert successful
        mock_requests_get.return_value = MockResponse(
            {"status": "failed", "message": "failed"}, 500
        )
        with self.assertRaises(RequestError):
            self.search_plugin._check_request_status("123")

    @mock.patch("eodag.plugins.search.data_request_search.requests.get", autospec=True)
    def test_plugins_get_result_data(self, mock_requests_get):
        self.search_plugin._get_result_data("123", items_per_page=5, page=1)
        mock_requests_get.assert_called_with(
            self.search_plugin.config.result_url.format(
                jobId="123", items_per_page=5, page=0
            ),
            headers=getattr(self.search_plugin.auth, "headers", ""),
            timeout=HTTP_REQ_TIMEOUT,
            verify=True,
        )

    @mock.patch("eodag.plugins.search.data_request_search.requests.get", autospec=True)
    def test_plugins_get_result_data_ssl_verify_false(self, mock_requests_get):
        self.search_plugin.config.ssl_verify = False
        self.search_plugin._get_result_data("123", items_per_page=5, page=1)
        mock_requests_get.assert_called_with(
            self.search_plugin.config.result_url.format(
                jobId="123", items_per_page=5, page=0
            ),
            headers=getattr(self.search_plugin.auth, "headers", ""),
            timeout=HTTP_REQ_TIMEOUT,
            verify=False,
        )

        del self.search_plugin.config.ssl_verify

    def test_plugins_search_datareq_distinct_product_type_mtd_mapping(self):
        """The metadata mapping for data_request_search should not mix specific product-types metadata-mapping"""
        geojson_geometry = self.search_criteria_s2_msi_l1c["geometry"].__geo_interface__
        result = {
            "totItems": 1,
            "content": [
                {
                    "productInfo": {"product": "FOO_BAR_BAZ_QUX_QUUX_CORGE"},
                    "extraInformation": {"footprint": geojson_geometry},
                    "url": "http://foo.bar",
                },
            ],
        }

        @responses.activate(registry=responses.registries.FirstMatchRegistry)
        def run():
            responses.add(
                responses.POST,
                self.search_plugin.config.data_request_url,
                status=200,
                json={"jobId": "123"},
            )
            responses.add(
                responses.GET,
                self.search_plugin.config.status_url + "123",
                json={"status": "completed"},
            )
            responses.add(
                responses.GET,
                self.search_plugin.config.result_url.format(
                    jobId=123, items_per_page=20, page=0
                ),
                json=result,
            )

            # update metadata_mapping only for S1_SAR_GRD
            self.search_plugin.config.products["S1_SAR_GRD"]["metadata_mapping"][
                "bar"
            ] = (
                None,
                "baz",
            )
            products, estimate = self.search_plugin.query(
                productType="S1_SAR_GRD",
                auth=None,
            )
            self.assertIn("bar", products[0].properties)
            self.assertEqual(products[0].properties["bar"], "baz")

            # search with another product type
            self.assertNotIn(
                "bar",
                self.search_plugin.config.products["S1_SAR_SLC"]["metadata_mapping"],
            )
            products, estimate = self.search_plugin.query(
                productType="S1_SAR_SLC",
                auth=None,
            )
            self.assertNotIn("bar", products[0].properties)

        run()

    def test_plugins_search_datareq_dates_required(self):
        """data_request_search query should use default dates if required"""
        geojson_geometry = self.search_criteria_s2_msi_l1c["geometry"].__geo_interface__
        result = {
            "totItems": 1,
            "content": [
                {
                    "productInfo": {"product": "FOO_BAR_BAZ_QUX_QUUX_CORGE"},
                    "extraInformation": {"footprint": geojson_geometry},
                    "url": "http://foo.bar",
                },
            ],
        }

        @responses.activate(registry=responses.registries.FirstMatchRegistry)
        def run():
            responses.add(
                responses.POST,
                self.search_plugin.config.data_request_url,
                status=200,
                json={"jobId": "123"},
            )
            responses.add(
                responses.GET,
                self.search_plugin.config.status_url + "123",
                json={"status": "completed"},
            )
            responses.add(
                responses.GET,
                self.search_plugin.config.result_url.format(
                    jobId=123, items_per_page=20, page=0
                ),
                json=result,
            )

            self.assertTrue(self.search_plugin.config.dates_required)

            products, estimate = self.search_plugin.query(
                productType="S1_SAR_GRD",
                auth=None,
            )

            request_dict = json.loads(responses.calls[0].request.body)

            self.assertEqual(request_dict["datasetId"], "EO:ESA:DAT:SENTINEL-1:SAR")
            self.assertEqual(
                dateutil.parser.parse(
                    request_dict["dateRangeSelectValues"][0]["start"]
                ),
                dateutil.parser.parse(DEFAULT_MISSION_START_DATE),
            )
            self.assertLess(
                datetime.now(timezone.utc)
                - dateutil.parser.parse(
                    request_dict["dateRangeSelectValues"][0]["end"]
                ),
                timedelta(minutes=1),
            )

        run()


class TestSearchPluginCreodiasS3Search(BaseSearchPluginTest):
    def setUp(self):
        super(TestSearchPluginCreodiasS3Search, self).setUp()
        self.provider = "creodias_s3"

    @mock.patch("eodag.plugins.search.qssearch.requests.get", autospec=True)
    def test_plugins_search_creodias_s3_links(self, mock_request):
        # s3 links should be added to products with register_downloader
        search_plugin = self.get_search_plugin("S1_SAR_GRD", self.provider)
        client = boto3.client("s3", aws_access_key_id="a", aws_secret_access_key="b")
        stubber = Stubber(client)
        s3_response_file = (
            Path(TEST_RESOURCES_PATH) / "provider_responses/creodias_s3_objects.json"
        )
        with open(s3_response_file) as f:
            list_objects_response = json.load(f)
        creodias_search_result_file = (
            Path(TEST_RESOURCES_PATH) / "eodag_search_result_creodias.geojson"
        )
        with open(creodias_search_result_file) as f:
            creodias_search_result = json.load(f)
        mock_request.return_value = MockResponse(creodias_search_result, 200)

        res = search_plugin.query("S1_SAR_GRD")
        for product in res[0]:
            download_plugin = self.plugins_manager.get_download_plugin(product)
            auth_plugin = self.plugins_manager.get_auth_plugin(self.provider)
            stubber.add_response("list_objects", list_objects_response)
            stubber.activate()
            setattr(auth_plugin, "s3_client", client)
            # fails if credentials are missing
            auth_plugin.config.credentials = {
                "aws_access_key_id": "",
                "aws_secret_access_key": "",
            }
            with self.assertRaisesRegex(
                MisconfiguredError,
                r"^Incomplete credentials .* \['aws_access_key_id', 'aws_secret_access_key'\]$",
            ):
                product.register_downloader(download_plugin, auth_plugin)
            auth_plugin.config.credentials = {
                "aws_access_key_id": "foo",
                "aws_secret_access_key": "bar",
            }
            product.register_downloader(download_plugin, auth_plugin)
        assets = res[0][0].assets
        # check if s3 links have been created correctly
        for asset in assets.values():
            self.assertIn("s3://eodata/Sentinel-1/SAR/GRD/2014/10/10", asset["href"])

    @mock.patch("eodag.plugins.search.qssearch.requests.get", autospec=True)
    def test_plugins_search_creodias_s3_client_error(self, mock_request):
        # request error should be raised when there is an error when fetching data from the s3
        search_plugin = self.get_search_plugin("S1_SAR_GRD", self.provider)
        client = boto3.client("s3", aws_access_key_id="a", aws_secret_access_key="b")
        stubber = Stubber(client)

        creodias_search_result_file = (
            Path(TEST_RESOURCES_PATH) / "eodag_search_result_creodias.geojson"
        )
        with open(creodias_search_result_file) as f:
            creodias_search_result = json.load(f)
        mock_request.return_value = MockResponse(creodias_search_result, 200)

        with self.assertRaises(RequestError):
            res = search_plugin.query("S1_SAR_GRD")
            for product in res[0]:
                download_plugin = self.plugins_manager.get_download_plugin(product)
                auth_plugin = self.plugins_manager.get_auth_plugin(self.provider)
                auth_plugin.config.credentials = {
                    "aws_access_key_id": "foo",
                    "aws_secret_access_key": "bar",
                }
                stubber.add_client_error("list_objects")
                stubber.activate()
                setattr(auth_plugin, "s3_client", client)
                product.register_downloader(download_plugin, auth_plugin)


class TestSearchPluginBuildSearchResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSearchPluginBuildSearchResult, cls).setUpClass()
        providers_config = load_default_config()
        cls.plugins_manager = PluginManager(providers_config)

    def setUp(self):
        self.provider = "cop_ads"
        self.search_plugin = self.get_search_plugin(provider=self.provider)
        self.query_dates = {
            "startTimeFromAscendingNode": "2020-01-01",
            "completionTimeFromAscendingNode": "2020-01-02",
        }
        self.product_type = "CAMS_EAC4"
        self.product_dataset = "cams-global-reanalysis-eac4"
        self.product_type_params = {
            "dataset": self.product_dataset,
            "format": "grib",
            "variable": "2m_dewpoint_temperature",
            "time": "00:00",
        }
        self.custom_query_params = {
            "dataset": "cams-global-ghg-reanalysis-egg4",
            "step": 0,
            "variable": "carbon_dioxide",
            "pressure_level": "10",
            "model_level": "1",
            "time": "00:00",
            "format": "grib",
        }

    def get_search_plugin(self, product_type=None, provider=None):
        return next(
            self.plugins_manager.get_search_plugins(
                product_type=product_type, provider=provider
            )
        )

    def test_plugins_search_buildsearchresult_dates_missing(self):
        """BuildSearchResult.query must use default dates if missing"""
        # given start & stop
        results, _ = self.search_plugin.query(
            productType=self.product_type,
            startTimeFromAscendingNode="2020-01-01",
            completionTimeFromAscendingNode="2020-01-02",
        )
        eoproduct = results[0]
        self.assertEqual(
            eoproduct.properties["startTimeFromAscendingNode"], "2020-01-01"
        )
        self.assertEqual(
            eoproduct.properties["completionTimeFromAscendingNode"], "2020-01-01"
        )

        # missing start & stop
        results, _ = self.search_plugin.query(
            productType=self.product_type,
        )
        eoproduct = results[0]
        self.assertIn(
            eoproduct.properties["startTimeFromAscendingNode"],
            DEFAULT_MISSION_START_DATE,
        )
        self.assertIn(
            eoproduct.properties["completionTimeFromAscendingNode"],
            "2015-01-01",
        )

        # missing start & stop and plugin.product_type_config set (set in core._prepare_search)
        self.search_plugin.config.product_type_config = {
            "productType": self.product_type,
            "missionStartDate": "1985-10-26",
            "missionEndDate": "2015-10-21",
        }
        results, _ = self.search_plugin.query(
            productType=self.product_type,
        )
        eoproduct = results[0]
        self.assertEqual(
            eoproduct.properties["startTimeFromAscendingNode"], "1985-10-26"
        )
        self.assertEqual(
            eoproduct.properties["completionTimeFromAscendingNode"], "1985-10-26"
        )

    def test_plugins_search_buildsearchresult_without_producttype(self):
        """
        BuildSearchResult.query must build a EOProduct from input parameters without product type.
        For test only, result cannot be downloaded.
        """
        results, count = self.search_plugin.query(
            dataset=self.product_dataset,
            startTimeFromAscendingNode="2020-01-01",
            completionTimeFromAscendingNode="2020-01-02",
        )
        assert count == 1
        eoproduct = results[0]
        assert eoproduct.geometry.bounds == (-180.0, -90.0, 180.0, 90.0)
        assert eoproduct.properties["startTimeFromAscendingNode"] == "2020-01-01"
        assert eoproduct.properties["completionTimeFromAscendingNode"] == "2020-01-01"
        assert eoproduct.properties["title"] == eoproduct.properties["id"]
        assert eoproduct.properties["title"].startswith(
            f"{self.product_dataset.upper()}"
        )
        assert eoproduct.properties["orderLink"].startswith("http")
        assert NOT_AVAILABLE in eoproduct.location

    def test_plugins_search_buildsearchresult_with_producttype(self):
        """BuildSearchResult.query must build a EOProduct from input parameters with predefined product type"""
        results, _ = self.search_plugin.query(
            **self.query_dates, productType=self.product_type, geometry=[1, 2, 3, 4]
        )
        eoproduct = results[0]
        assert eoproduct.properties["title"].startswith(self.product_type)
        assert eoproduct.geometry.bounds == (1.0, 2.0, 3.0, 4.0)
        # check if product_type_params is a subset of eoproduct.properties
        assert self.product_type_params.items() <= eoproduct.properties.items()

        # product type default settings can be overwritten using search kwargs
        results, _ = self.search_plugin.query(
            **self.query_dates,
            productType=self.product_type,
            variable="temperature",
        )
        eoproduct = results[0]
        assert eoproduct.properties["variable"] == "temperature"

    def test_plugins_search_buildsearchresult_with_custom_producttype(self):
        """BuildSearchResult.query must build a EOProduct from input parameters with custom product type"""
        results, _ = self.search_plugin.query(
            **self.query_dates,
            **self.custom_query_params,
        )
        eoproduct = results[0]
        assert eoproduct.properties["title"].startswith(
            self.custom_query_params["dataset"].upper()
        )
        # check if custom_query_params is a subset of eoproduct.properties
        for param in self.custom_query_params:
            try:
                # for numeric values
                assert eoproduct.properties[param] == ast.literal_eval(
                    self.custom_query_params[param]
                )
            except Exception:
                assert eoproduct.properties[param] == self.custom_query_params[param]

    @mock.patch("eodag.utils.constraints.requests.get", autospec=True)
    def test_plugins_search_buildsearchresult_discover_queryables(
        self, mock_requests_constraints
    ):
        constraints_path = os.path.join(TEST_RESOURCES_PATH, "constraints.json")
        with open(constraints_path) as f:
            constraints = json.load(f)
        mock_requests_constraints.return_value = MockResponse(
            constraints, status_code=200
        )
        queryables = self.search_plugin.discover_queryables(
            productType="CAMS_EU_AIR_QUALITY_RE"
        )
        self.assertEqual(11, len(queryables))
        self.assertIn("variable", queryables)
        self.assertNotIn("metadata_mapping", queryables)
        # with additional param
        queryables = self.search_plugin.discover_queryables(
            productType="CAMS_EU_AIR_QUALITY_RE",
            variable="a",
        )
        self.assertEqual(11, len(queryables))
        queryable = queryables.get("variable")
        self.assertEqual("a", queryable.__metadata__[0].get_default())
        queryable = queryables.get("month")
        self.assertTrue(queryable.__metadata__[0].is_required())
