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
from copy import deepcopy as copy_deepcopy
from datetime import datetime
from pathlib import Path
from typing import Literal, Union, get_origin
from unittest import mock
from unittest.mock import call

import boto3
import botocore
import pytest
import requests
import responses
from botocore.stub import Stubber
from jsonpath_ng import JSONPath, parse
from pydantic_core import PydanticUndefined
from requests import RequestException
from shapely.geometry.base import BaseGeometry
from typing_extensions import get_args

from eodag.api.product import AssetsDict
from eodag.api.product.metadata_mapping import get_queryable_from_provider
from eodag.utils import deepcopy
from eodag.utils.exceptions import (
    PluginImplementationError,
    UnsupportedCollection,
    ValidationError,
)
from tests.context import (
    DEFAULT_MISSION_START_DATE,
    DEFAULT_SEARCH_TIMEOUT,
    HTTP_REQ_TIMEOUT,
    NOT_AVAILABLE,
    TEST_RESOURCES_PATH,
    USER_AGENT,
    AuthenticationError,
    EOProduct,
    MisconfiguredError,
    NotAvailableError,
    PluginManager,
    PreparedSearch,
    QueryStringSearch,
    RequestError,
    TimeOutError,
    cached_parse,
    cached_yaml_load_all,
    ecmwf_temporal_to_eodag,
    get_geometry_from_various,
    load_default_config,
    merge_configs,
)


class BaseSearchPluginTest(unittest.TestCase):
    def setUp(self):
        super(BaseSearchPluginTest, self).setUp()
        providers_config = load_default_config()
        self.plugins_manager = PluginManager(providers_config)
        self.collection = "S2_MSI_L1C"
        geom = [137.772897, 13.134202, 153.749135, 23.885986]
        geometry = get_geometry_from_various([], geometry=geom)
        self.search_criteria_s2_msi_l1c = {
            "collection": self.collection,
            "start_datetime": "2020-08-08",
            "end_datetime": "2020-08-16",
            "geometry": geometry,
        }
        self.provider_resp_dir = Path(TEST_RESOURCES_PATH) / "provider_responses"

    def get_search_plugin(self, collection=None, provider=None):
        return next(
            self.plugins_manager.get_search_plugins(
                collection=collection, provider=provider
            )
        )

    def get_auth_plugin(self, search_plugin):
        return self.plugins_manager.get_auth_plugin(search_plugin)

    def test_get_assets_from_mapping(self):
        search_plugin = self.get_search_plugin(provider="geodes")
        search_plugin.config.assets_mapping = {
            "one": {"href": "$.properties.href", "roles": ["a_role"], "title": "One"},
            "two": {
                "href": "https://a.static_url.com",
                "roles": ["a_role"],
                "title": "Two",
            },
        }
        provider_item = {"id": "ID123456", "properties": {"href": "a.product.com/ONE"}}
        asset_mappings = search_plugin.get_assets_from_mapping(provider_item)
        self.assertEqual(2, len(asset_mappings))
        self.assertEqual("a.product.com/ONE", asset_mappings["one"]["href"])
        self.assertEqual("One", asset_mappings["one"]["title"])
        self.assertListEqual(["a_role"], asset_mappings["one"]["roles"])
        self.assertEqual("https://a.static_url.com", asset_mappings["two"]["href"])
        self.assertEqual("Two", asset_mappings["two"]["title"])
        self.assertListEqual(["a_role"], asset_mappings["two"]["roles"])


class TestSearchPluginQueryStringSearchXml(BaseSearchPluginTest):
    def setUp(self):
        super(TestSearchPluginQueryStringSearchXml, self).setUp()

        # manually add conf as this provider is not supported any more
        providers_config = self.plugins_manager.providers_config
        mundi_config = cached_yaml_load_all(
            Path(TEST_RESOURCES_PATH) / "mundi_conf.yml"
        )[0]
        merge_configs(providers_config, {"mundi": mundi_config})
        self.plugins_manager = PluginManager(providers_config)

        # One of the providers that has a QueryStringSearch Search plugin and result_type=xml
        provider = "mundi"
        self.mundi_search_plugin = self.get_search_plugin(self.collection, provider)
        self.mundi_auth_plugin = self.get_auth_plugin(self.mundi_search_plugin)

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
            prep=PreparedSearch(
                page=1,
                items_per_page=2,
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

        self.assertEqual(estimate, mundi_products_count)
        self.assertEqual(len(products), number_of_products)
        self.assertIsInstance(products[0], EOProduct)

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
            prep=PreparedSearch(
                count=False,
                page=1,
                items_per_page=2,
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

        self.assertIsNone(estimate)
        self.assertEqual(len(products), number_of_products)
        self.assertIsInstance(products[0], EOProduct)

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.count_hits", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_querystringsearch_xml_distinct_collection_mtd_mapping(
        self, mock__request, mock_count_hits
    ):
        """The metadata mapping for XML QueryStringSearch should not mix specific product-types metadata-mapping"""
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
        products, estimate = search_plugin.query(
            collection="S1_SAR_GRD",
        )
        self.assertIn("bar", products[0].properties)
        self.assertEqual(products[0].properties["bar"], "dhus")

        # search with another collection
        self.assertNotIn(
            "bar", search_plugin.config.products["S1_SAR_SLC"]["metadata_mapping"]
        )
        products, estimate = search_plugin.query(
            collection="S1_SAR_SLC",
        )
        self.assertNotIn("bar", products[0].properties)


class TestSearchPluginQueryStringSearch(BaseSearchPluginTest):
    def setUp(self):
        super(TestSearchPluginQueryStringSearch, self).setUp()
        # One of the providers that has a QueryStringSearch Search plugin
        provider = "peps"
        self.peps_search_plugin = self.get_search_plugin(self.collection, provider)
        self.peps_auth_plugin = self.get_auth_plugin(self.peps_search_plugin)

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_querystringsearch_count_and_search_peps(
        self, mock__request
    ):
        self.maxDiff = None
        """A query with a QueryStringSearch (peps here) must return tuple with a list of EOProduct and a number of available products"""  # noqa
        with open(self.provider_resp_dir / "peps_search.json") as f:
            peps_resp_search = json.load(f)
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.side_effect = [
            peps_resp_search,
        ]
        products, estimate = self.peps_search_plugin.query(
            prep=PreparedSearch(
                page=1,
                items_per_page=2,
                auth_plugin=self.peps_auth_plugin,
            ),
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

        mock__request.assert_called_once()
        self.assertEqual(mock__request.call_args_list[-1][0][1].url, peps_url_search)

        self.assertEqual(estimate, peps_products_count)
        self.assertEqual(len(products), number_of_products)
        self.assertIsInstance(products[0], EOProduct)

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
            prep=PreparedSearch(
                count=False,
                page=1,
                items_per_page=2,
                auth_plugin=self.peps_auth_plugin,
            ),
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
        mock__request.assert_called_once()
        self.assertEqual(mock__request.call_args_list[-1][0][1].url, peps_url_search)

        self.assertIsNone(estimate)
        self.assertEqual(len(products), number_of_products)
        self.assertIsInstance(products[0], EOProduct)

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
        """A query with a QueryStringSearch (here peps) must only use cloudCover filtering for non-radar collections"""  # noqa

        self.peps_search_plugin.query(collection="S2_MSI_L1C", cloudCover=50)
        mock__request.assert_called()
        self.assertIn("eo:cloud_cover", mock__request.call_args_list[-1][0][1].url)
        mock__request.reset_mock()

        self.peps_search_plugin.query(collection="S1_SAR_GRD", cloudCover=50)
        mock__request.assert_called()
        self.assertNotIn("eo:cloud_cover", mock__request.call_args_list[-1][0][1].url)

    def test_plugins_search_querystringsearch_search_peps_ko(self):
        """A query with a parameter which is not queryable must
        raise an error if the provider does not allow it"""  # noqa
        # with raised error parameter set to True in the global config of the provider
        provider_search_plugin_config = copy_deepcopy(self.peps_search_plugin.config)
        self.peps_search_plugin.config.discover_metadata[
            "raise_mtd_discovery_error"
        ] = True

        with self.assertRaises(ValidationError) as context:
            self.peps_search_plugin.query(
                prep=PreparedSearch(
                    page=1,
                    items_per_page=2,
                    auth_plugin=self.peps_auth_plugin,
                ),
                **{**self.search_criteria_s2_msi_l1c, **{"foo": "bar"}},
            )
        self.assertEqual(
            "Search parameters which are not queryable are disallowed for this collection on this provider: "
            f"please remove 'foo' from your search parameters. Collection: "
            f"{self.search_criteria_s2_msi_l1c['collection']} / provider : {self.peps_search_plugin.provider}",
            context.exception.message,
        )

        # with raised error parameter set to True in the config of the collection of the provider

        # first, update this parameter to False in the global config
        # to show that it is going to be taken over by this new config
        self.peps_search_plugin.config.discover_metadata[
            "raise_mtd_discovery_error"
        ] = False

        self.peps_search_plugin.config.products[
            self.search_criteria_s2_msi_l1c["collection"]
        ]["discover_metadata"] = {"raise_mtd_discovery_error": True}

        with self.assertRaises(ValidationError) as context:
            self.peps_search_plugin.query(
                prep=PreparedSearch(
                    page=1,
                    items_per_page=2,
                    auth_plugin=self.peps_auth_plugin,
                ),
                **{**self.search_criteria_s2_msi_l1c, **{"foo": "bar"}},
            )
        self.assertEqual(
            "Search parameters which are not queryable are disallowed for this collection on this provider: "
            f"please remove 'foo' from your search parameters. Collection: "
            f"{self.search_criteria_s2_msi_l1c['collection']} / provider : {self.peps_search_plugin.provider}",
            context.exception.message,
        )

        # restore the original config
        self.peps_search_plugin.config = provider_search_plugin_config

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_querystringsearch_discover_collections(self, mock__request):
        """QueryStringSearch.discover_collections must return a well formatted dict"""
        # One of the providers that has a QueryStringSearch Search plugin and discover_collections configured
        provider = "earth_search"
        search_plugin = self.get_search_plugin(self.collection, provider)

        # change onfiguration for this test to filter out some collections
        results_entry = search_plugin.config.discover_collections["results_entry"]
        search_plugin.config.discover_collections["results_entry"] = cached_parse(
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
        conf_update_dict = search_plugin.discover_collections()
        self.assertIn("foo_collection", conf_update_dict["providers_config"])
        self.assertIn("foo_collection", conf_update_dict["collections_config"])
        self.assertNotIn("bar_collection", conf_update_dict["providers_config"])
        self.assertNotIn("bar_collection", conf_update_dict["collections_config"])
        self.assertEqual(
            conf_update_dict["providers_config"]["foo_collection"]["_collection"],
            "foo_collection",
        )
        self.assertEqual(
            conf_update_dict["collections_config"]["foo_collection"]["title"],
            "The FOO collection",
        )
        # restore configuration
        search_plugin.config.discover_collections["results_entry"] = results_entry

    def test_plugins_search_querystringsearch_discover_collections_paginated(self):
        """QueryStringSearch.discover_collections must handle pagination"""
        # One of the providers that has a QueryStringSearch Search plugin and discover_collections configured
        provider = "earth_search"
        search_plugin = self.get_search_plugin(self.collection, provider)

        # change configuration for this test to filter out some collections
        discover_collections_conf = search_plugin.config.discover_collections
        search_plugin.config.discover_collections[
            "fetch_url"
        ] = "https://foo.bar/collections"
        search_plugin.config.discover_collections[
            "next_page_url_tpl"
        ] = "{url}?page={page}"
        search_plugin.config.discover_collections["start_page"] = 0

        with responses.RequestsMock(
            assert_all_requests_are_fired=True
        ) as mock_requests_post:
            mock_requests_post.add(
                responses.GET,
                "https://foo.bar/collections?page=0",
                json={
                    "collections": [
                        {
                            "id": "foo_collection",
                            "title": "The FOO collection",
                            "billing": "free",
                        }
                    ]
                },
            )
            mock_requests_post.add(
                responses.GET,
                "https://foo.bar/collections?page=1",
                json={
                    "collections": [
                        {
                            "id": "bar_collection",
                            "title": "The BAR non-free collection",
                            "billing": "non-free",
                        },
                    ]
                },
            )
            mock_requests_post.add(
                responses.GET,
                "https://foo.bar/collections?page=2",
                json={"collections": []},
            )
            conf_update_dict = search_plugin.discover_collections()
            self.assertIn("foo_collection", conf_update_dict["providers_config"])
            self.assertIn("foo_collection", conf_update_dict["collections_config"])
            self.assertIn("bar_collection", conf_update_dict["providers_config"])
            self.assertIn("bar_collection", conf_update_dict["collections_config"])
            self.assertEqual(
                conf_update_dict["providers_config"]["foo_collection"]["_collection"],
                "foo_collection",
            )
            self.assertEqual(
                conf_update_dict["collections_config"]["foo_collection"]["title"],
                "The FOO collection",
            )

        # restore configuration
        search_plugin.config.discover_collections = discover_collections_conf

    def test_plugins_search_querystringsearch_discover_collections_without_fetch_url(
        self,
    ):
        """QueryStringSearch.discover_collections must handle missing fetch_url"""
        # One of the providers that has a QueryStringSearch Search plugin and discover_collections configured
        provider = "earth_search"
        search_plugin = self.get_search_plugin(self.collection, provider)

        discover_collections_conf = search_plugin.config.discover_collections
        search_plugin.config.discover_collections.pop("fetch_url", None)

        response = search_plugin.discover_collections()
        self.assertIsNone(response)
        search_plugin.config.discover_collections = discover_collections_conf

    def test_plugins_search_querystringsearch_discover_collections_paginated_qs_dict(
        self,
    ):
        """
        QueryStringSearch.discover_collections must handle paginated responses with query string parameters
        """
        provider = "earth_search"
        search_plugin = self.get_search_plugin(self.collection, provider)

        # change configuration for this test to filter out some collections
        discover_collections_conf = search_plugin.config.discover_collections
        search_plugin.config.discover_collections[
            "fetch_url"
        ] = "https://foo.bar/collections"
        search_plugin.config.discover_collections[
            "next_page_url_tpl"
        ] = "{url}?page={page}"
        search_plugin.config.discover_collections["start_page"] = 0
        search_plugin.config.discover_collections[
            "single_collection_fetch_qs"
        ] = "foo=bar"

        with responses.RequestsMock(
            assert_all_requests_are_fired=True
        ) as mock_requests_post:
            mock_requests_post.add(
                responses.GET,
                "https://foo.bar/collections?page=0&foo=bar",
                json={
                    "collections": [
                        {
                            "id": "foo_collection",
                            "title": "The FOO collection",
                            "billing": "free",
                        }
                    ]
                },
            )
            mock_requests_post.add(
                responses.GET,
                "https://foo.bar/collections?page=1&foo=bar",
                json={
                    "collections": [
                        {
                            "id": "bar_collection",
                            "title": "The BAR non-free collection",
                            "billing": "non-free",
                        },
                    ]
                },
            )
            mock_requests_post.add(
                responses.GET,
                "https://foo.bar/collections?page=2&foo=bar",
                json={"collections": []},
            )
            conf_update_dict = search_plugin.discover_collections()
            self.assertIn("foo_collection", conf_update_dict["providers_config"])
            self.assertIn("foo_collection", conf_update_dict["collections_config"])
            self.assertIn("bar_collection", conf_update_dict["providers_config"])
            self.assertIn("bar_collection", conf_update_dict["collections_config"])
            self.assertEqual(
                conf_update_dict["providers_config"]["foo_collection"]["_collection"],
                "foo_collection",
            )
            self.assertEqual(
                conf_update_dict["collections_config"]["foo_collection"]["title"],
                "The FOO collection",
            )

        search_plugin.config.discover_collections = discover_collections_conf

    def test_plugins_search_querystringsearch_discover_collections_per_page_no_fetch_url(
        self,
    ):
        """QueryStringSearch.discover_collections must handle paginated responses with query string parameters"""
        provider = "earth_search"
        search_plugin = self.get_search_plugin(self.collection, provider)
        discover_collections_conf = search_plugin.config.discover_collections
        search_plugin.config.discover_collections.pop("fetch_url")
        search_plugin.config.discover_collections[
            "next_page_url_tpl"
        ] = "{url}?page={page}"
        search_plugin.config.discover_collections["start_page"] = 0
        result = search_plugin.discover_collections_per_page()
        assert result is None

        search_plugin.config.discover_collections = discover_collections_conf

    def test_plugins_search_querystringsearch_discover_collections_per_page_keyerror(
        self,
    ):
        """QueryStringSearch.discover_collections must handle missing keys in the response"""
        provider = "earth_search"
        search_plugin = self.get_search_plugin(self.collection, provider)
        discover_collections_conf = search_plugin.config.discover_collections
        search_plugin.config.discover_collections = {
            "result_type": "json",
            "results_entry": parse("$.collections"),
        }

        class DummyResponse:
            def json(self):
                return {"collections": [{}]}

        with mock.patch.object(
            QueryStringSearch, "_request", return_value=DummyResponse()
        ):
            with self.assertLogs(level="WARNING") as log:
                result = search_plugin.discover_collections_per_page(
                    fetch_url="https://foo.bar/collections"
                )
                assert result is None
                assert any("Incomplete" in m for m in log.output)
        search_plugin.config.discover_collections = discover_collections_conf

    def test_plugins_search_querystringsearch_discover_collections_per_page_request_exception(
        self,
    ):
        """QueryStringSearch.discover_collections must handle request exceptions"""
        provider = "earth_search"
        search_plugin = self.get_search_plugin(self.collection, provider)
        discover_collections_conf = search_plugin.config.discover_collections
        search_plugin.config.discover_collections = {
            "result_type": "json",
            "results_entry": JSONPath(),
        }

        class DummyResponse:
            def json(self):
                raise requests.RequestException("boom")

        with mock.patch.object(
            QueryStringSearch, "_request", return_value=DummyResponse()
        ):
            with self.assertLogs(level="DEBUG") as log:
                result = search_plugin.discover_collections_per_page(
                    fetch_url="https://foo.bar/collections"
                )
                assert result is None
                assert any(
                    "Could not parse discovered product types response" in m
                    for m in log.output
                )

        search_plugin.config.discover_collections = discover_collections_conf

    @mock.patch("eodag.plugins.search.qssearch.PostJsonSearch._request", autospec=True)
    def test_plugins_search_querystringsearch_discover_collections_post(
        self, mock__request
    ):
        """QueryStringSearch.discover_collections must be able to query using POST requests"""
        # One of the providers that has a QueryStringSearch.discover_collections configured with POST requests
        provider = "geodes"
        search_plugin = self.get_search_plugin(self.collection, provider)

        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.return_value = {
            "collections": [
                {
                    "id": "foo_collection",
                    "title": "The FOO collection",
                },
                {
                    "id": "bar_collection",
                    "title": "The BAR collection",
                },
            ]
        }
        conf_update_dict = search_plugin.discover_collections()
        self.assertIn("foo_collection", conf_update_dict["providers_config"])
        self.assertIn("foo_collection", conf_update_dict["collections_config"])
        self.assertIn("bar_collection", conf_update_dict["providers_config"])
        self.assertIn("bar_collection", conf_update_dict["collections_config"])
        self.assertEqual(
            conf_update_dict["providers_config"]["foo_collection"]["_collection"],
            "foo_collection",
        )
        self.assertEqual(
            conf_update_dict["collections_config"]["foo_collection"]["title"],
            "The FOO collection",
        )

    @mock.patch("eodag.plugins.search.qssearch.requests.Session.get", autospec=True)
    def test_plugins_search_querystringsearch_discover_collections_with_query_param(
        self, mock__request
    ):
        """QueryStringSearch.discover_collections must return a well formatted dict"""
        # One of the providers that has discover_collections() configured with QueryStringSearch
        provider = "wekeo_cmems"
        search_plugin = self.get_search_plugin(provider=provider)
        self.assertEqual("PostJsonSearch", search_plugin.__class__.__name__)
        self.assertEqual(
            "QueryStringSearch",
            search_plugin.discover_collections.__func__.__qualname__.split(".")[0],
        )

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
        search_plugin.discover_collections()
        mock__request.assert_called_with(
            mock.ANY,
            "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/datasets/foo_collection",
            timeout=60,
            headers=USER_AGENT,
            verify=True,
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_querystringsearch_discover_collections_keywords(
        self, mock__request
    ):
        """QueryStringSearch.discover_collections must return a dict with well formatted keywords"""
        # One of the providers that has a QueryStringSearch Search plugin and keywords configured
        provider = "earth_search"
        search_plugin = self.get_search_plugin(self.collection, provider)

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
        conf_update_dict = search_plugin.discover_collections()
        keywords_list = conf_update_dict["collections_config"]["foo_collection"][
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
    def test_plugins_search_querystringsearch_distinct_collection_mtd_mapping(
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
        search_plugin = self.get_search_plugin(self.collection, "peps")

        # update metadata_mapping only for S1_SAR_GRD
        search_plugin.config.products["S1_SAR_GRD"]["metadata_mapping"]["bar"] = (
            None,
            "baz",
        )
        products, estimate = search_plugin.query(
            collection="S1_SAR_GRD",
            auth=None,
        )
        self.assertIn("bar", products[0].properties)
        self.assertEqual(products[0].properties["bar"], "baz")

        # search with another collection
        self.assertNotIn(
            "bar", search_plugin.config.products["S1_SAR_SLC"]["metadata_mapping"]
        )
        products, estimate = search_plugin.query(
            collection="S1_SAR_SLC",
            auth=None,
        )
        self.assertNotIn("bar", products[0].properties)

    @mock.patch(
        "eodag.plugins.search.qssearch.requests.Session.get",
        autospec=True,
        side_effect=requests.exceptions.Timeout(),
    )
    def test_plugins_search_querystringseach_timeout(self, mock__request):
        search_plugin = self.get_search_plugin(self.collection, "peps")
        with self.assertRaises(TimeOutError):
            search_plugin.query(
                collection="S1_SAR_SLC",
                auth=None,
            )

    def test_plugins_search_querystringsearch_count_hits_xml(self):
        """Test QueryStringSearch.count_hits() with XML response and XPath key path"""
        provider = "earth_search"
        search_plugin = self.get_search_plugin(self.collection, provider)
        search_plugin.config.pagination = {
            "total_items_nb_key_path": "string(//ns:TotalResults)"
        }
        xml = (
            """<root xmlns="http://example.com"><TotalResults>4</TotalResults></root>"""
        )

        mock_response = mock.Mock()
        mock_response.content = xml.encode()

        with mock.patch.object(search_plugin, "_request", return_value=mock_response):
            result = search_plugin.count_hits("http://fake.url", result_type="xml")
            assert result == 4

    def test_plugins_search_querystringsearch_count_hits_json_dict_ok(self):
        """Test QueryStringSearch.count_hits() with JSON response and JSONPath key path"""
        provider = "earth_search"
        search_plugin = self.get_search_plugin(self.collection, provider)
        search_plugin.config.pagination = {"total_items_nb_key_path": parse("$.total")}

        mock_response = mock.Mock()
        mock_response.json.return_value = {"total": 99}

        with mock.patch.object(search_plugin, "_request", return_value=mock_response):
            result = search_plugin.count_hits("http://fake.url")
            assert result == 99

    def test_plugins_search_querystringsearch_count_hits_json_dict_not_jsonpath(self):
        """Test QueryStringSearch.count_hits() with JSON response and non-JSONPath key path"""
        provider = "earth_search"
        search_plugin = self.get_search_plugin(self.collection, provider)
        search_plugin.config.pagination = {"total_items_nb_key_path": "$.total"}

        mock_response = mock.Mock()
        mock_response.json.return_value = {"total": 99}

        with mock.patch.object(search_plugin, "_request", return_value=mock_response):
            with pytest.raises(PluginImplementationError):
                search_plugin.count_hits("http://fake.url")

    def test_plugins_search_querystringsearch_count_hits_json_dict_jsonpath_not_found(
        self,
    ):
        """Test QueryStringSearch.count_hits() with JSON response and JSONPath key path not found in the response"""
        provider = "earth_search"
        search_plugin = self.get_search_plugin(self.collection, provider)
        search_plugin.config.pagination = {
            "total_items_nb_key_path": parse("$.missing")
        }

        mock_response = mock.Mock()
        mock_response.json.return_value = {"total": 99}

        with mock.patch.object(search_plugin, "_request", return_value=mock_response):
            with pytest.raises(MisconfiguredError):
                search_plugin.count_hits("http://fake.url")


class TestSearchPluginPostJsonSearch(BaseSearchPluginTest):
    def setUp(self):
        super(TestSearchPluginPostJsonSearch, self).setUp()
        # One of the providers that has a PostJsonSearch Search plugin
        provider = "aws_eos"
        self.awseos_search_plugin = self.get_search_plugin(self.collection, provider)
        self.awseos_auth_plugin = self.get_auth_plugin(self.awseos_search_plugin)
        self.awseos_auth_plugin.config.credentials = dict(apikey="dummyapikey")
        self.awseos_url = "https://gate.eos.com/api/lms/search/v2/sentinel2"

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
                        prep=PreparedSearch(
                            page=1,
                            items_per_page=2,
                            auth_plugin=self.awseos_auth_plugin,
                        ),
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
                    prep=PreparedSearch(
                        page=1,
                        items_per_page=2,
                        auth_plugin=self.awseos_auth_plugin,
                    ),
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
            prep=PreparedSearch(
                page=1,
                items_per_page=2,
                auth_plugin=self.awseos_auth_plugin,
            ),
            **self.search_criteria_s2_msi_l1c,
        )

        # Specific expected results
        awseos_products_count = 44
        number_of_products = 2

        self.assertEqual(mock__request.call_args_list[-1][0][1].url, self.awseos_url)

        self.assertEqual(estimate, awseos_products_count)
        self.assertEqual(len(products), number_of_products)
        self.assertIsInstance(products[0], EOProduct)

    @mock.patch("eodag.plugins.search.qssearch.PostJsonSearch._request", autospec=True)
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
            prep=PreparedSearch(auth_plugin=self.awseos_auth_plugin, count=True),
            **{
                "collection": "S2_MSI_L2A",
                "id": "S2B_MSIL2A_20220101T000459_N0301_R130_T53DMB_20220101T012649",
            },
        )

        self.assertEqual(mock__request.call_count, 2)
        self.assertEqual(
            mock__request.call_args_list[0][0][1].url,
            "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/53/D/MB/2022/1/1/0/tileInfo.json",
        )
        self.assertEqual(
            mock__request.call_args_list[1][0][1].url,
            "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/53/D/MB/2022/1/1/0/productInfo.json",
        )

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
            prep=PreparedSearch(
                count=False,
                page=1,
                items_per_page=2,
                auth_plugin=self.awseos_auth_plugin,
            ),
            **self.search_criteria_s2_msi_l1c,
        )

        # Specific expected results
        number_of_products = 2

        mock_count_hits.assert_not_called()
        self.assertEqual(mock__request.call_args_list[0][0][1].url, self.awseos_url)

        self.assertIsNone(estimate)
        self.assertEqual(len(products), number_of_products)
        self.assertIsInstance(products[0], EOProduct)
        # products count should not have been extracted from search results
        self.assertIsNone(
            getattr(mock__request.call_args_list[0][0][1], "total_items_nb", None)
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.normalize_results",
        autospec=True,
    )
    @mock.patch("eodag.plugins.search.qssearch.requests.post", autospec=True)
    def test_plugins_search_postjsonsearch_search_cloudcover_awseos(
        self, mock_requests_post, mock_normalize_results
    ):
        """A query with a PostJsonSearch (here aws_eos) must only use cloudCover filtering for non-radar collections"""  # noqa

        self.awseos_search_plugin.query(
            prep=PreparedSearch(auth_plugin=self.awseos_auth_plugin),
            collection="S2_MSI_L1C",
            **{"eo:cloud_cover": 50},
        )
        mock_requests_post.assert_called()
        self.assertIn("cloudCoverage", str(mock_requests_post.call_args_list[-1][1]))
        mock_requests_post.reset_mock()

        self.awseos_search_plugin.query(
            prep=PreparedSearch(auth_plugin=self.awseos_auth_plugin),
            collection="S1_SAR_GRD",
            **{"eo:cloud_cover": 50},
        )
        mock_requests_post.assert_called()
        self.assertNotIn(
            "cloudCoverPercentage", str(mock_requests_post.call_args_list[-1][1])
        )

    @mock.patch("eodag.plugins.search.qssearch.PostJsonSearch._request", autospec=True)
    def test_plugins_search_postjsonsearch_distinct_collection_mtd_mapping(
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
            prep=PreparedSearch(auth_plugin=self.awseos_auth_plugin),
            collection="S1_SAR_GRD",
        )
        self.assertIn("bar", products[0].properties)
        self.assertEqual(products[0].properties["bar"], "baz")

        # search with another collection
        self.assertNotIn(
            "bar",
            self.awseos_search_plugin.config.products["S2_MSI_L1C"]["metadata_mapping"],
        )
        products, estimate = self.awseos_search_plugin.query(
            prep=PreparedSearch(auth_plugin=self.awseos_auth_plugin),
            collection="S2_MSI_L1C",
        )
        self.assertNotIn("bar", products[0].properties)

    @mock.patch("eodag.plugins.search.qssearch.requests.post", autospec=True)
    @mock.patch(
        "eodag.plugins.search.qssearch.PostJsonSearch.normalize_results", autospec=True
    )
    def test_plugins_search_postjsonsearch_default_dates(
        self, mock_normalize, mock_request
    ):
        provider = "wekeo_ecmwf"
        search_plugins = self.plugins_manager.get_search_plugins(provider=provider)
        search_plugin = next(search_plugins)
        mock_request.return_value = MockResponse({"features": []}, 200)
        # year, month, day, time given -> don't use default dates
        search_plugin.query(
            prep=PreparedSearch(),
            collection="ERA5_SL",
            **{
                "ecmwf:year": "2020",
                "ecmwf:month": ["02"],
                "ecmwf:day": ["20", "21"],
                "ecmwf:time": ["01:00"],
            },
        )
        mock_request.assert_called_with(
            "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/search",
            json={
                "year": "2020",
                "month": ["02"],
                "day": ["20", "21"],
                "time": ["01:00"],
                "dataset_id": "EO:ECMWF:DAT:REANALYSIS_ERA5_SINGLE_LEVELS",
                "itemsPerPage": 20,
                "startIndex": 0,
            },
            headers=USER_AGENT,
            timeout=60,
            verify=True,
        )
        # start date given and converted to year, month, day, time
        search_plugin.query(
            prep=PreparedSearch(),
            collection="ERA5_SL",
            start_datetime="2021-02-01T03:00:00Z",
        )
        mock_request.assert_called_with(
            "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/search",
            json={
                "year": ["2021"],
                "month": ["02"],
                "day": ["01"],
                "time": ["03:00"],
                "dataset_id": "EO:ECMWF:DAT:REANALYSIS_ERA5_SINGLE_LEVELS",
                "itemsPerPage": 20,
                "startIndex": 0,
            },
            headers=USER_AGENT,
            timeout=60,
            verify=True,
        )
        # no date info given -> default dates (missionStartDate) which are then converted to year, month, day, time
        pt_conf = {
            "ID": "ERA5_SL",
            "description": "ERA5 abstract",
            "instruments": [],
            "constellation": "ERA5",
            "platform": "ERA5",
            "processing:level": None,
            "keywords": [
                "ECMWF",
                "Reanalysis",
                "ERA5",
                "CDS",
                "Atmospheric",
                "land",
                "sea",
                "hourly",
                "single",
                "levels",
            ],
            "sensorType": "ATMOSPHERIC",
            "license": "other",
            "title": "ERA5 hourly data on single levels from 1940 to present",
            "extent": {"temporal": {"interval": [["1940-01-01T00:00:00Z", None]]}},
            "_id": "ERA5_SL",
        }
        search_plugin.config.collection_config = dict(
            pt_conf,
            **{"_collection": "ERA5_SL"},
        )
        search_plugin.query(collection="ERA5_SL", prep=PreparedSearch())
        mock_request.assert_called_with(
            "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/search",
            json={
                "year": ["1940"],
                "month": ["01"],
                "day": ["01"],
                "time": ["00:00"],
                "dataset_id": "EO:ECMWF:DAT:REANALYSIS_ERA5_SINGLE_LEVELS",
                "itemsPerPage": 20,
                "startIndex": 0,
            },
            headers=USER_AGENT,
            timeout=60,
            verify=True,
        )
        # collection with dates are query params -> use missionStartDate and today
        pt_conf = {
            "ID": "CAMS_EAC4",
            "description": "CAMS_EAC4 abstract",
            "instruments": [],
            "constellation": "CAMS",
            "platform": "CAMS",
            "processing:level": None,
            "keywords": [
                "Copernicus",
                "ADS",
                "CAMS",
                "Atmosphere",
                "Atmospheric",
                "EWMCF",
                "EAC4",
            ],
            "sensorType": "ATMOSPHERIC",
            "license": "other",
            "title": "CAMS global reanalysis (EAC4)",
            "extent": {"temporal": {"interval": [["2003-01-01T00:00:00Z", None]]}},
            "_id": "CAMS_EAC4",
        }
        search_plugin.config.collection_config = dict(
            pt_conf,
            **{"_collection": "CAMS_EAC4"},
        )
        search_plugin.query(collection="CAMS_EAC4", prep=PreparedSearch())
        mock_request.assert_called_with(
            "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/search",
            json={
                "startdate": "2003-01-01T00:00:00.000Z",
                "enddate": "2003-01-01T00:00:00.000Z",
                "dataset_id": "EO:ECMWF:DAT:CAMS_GLOBAL_REANALYSIS_EAC4",
                "itemsPerPage": 20,
                "startIndex": 0,
            },
            headers=USER_AGENT,
            timeout=60,
            verify=True,
        )

    @mock.patch("eodag.plugins.search.qssearch.PostJsonSearch._request", autospec=True)
    def test_plugins_search_postjsonsearch_query_params_wekeo(self, mock__request):
        """A query with PostJsonSearch (here wekeo) must generate query params corresponding to the
        search criteria"""
        provider = "wekeo_ecmwf"
        collection = "GRIDDED_GLACIERS_MASS_CHANGE"
        search_plugin = self.get_search_plugin(collection, provider)
        auth_plugin = self.get_auth_plugin(search_plugin)

        mock__request.return_value = mock.Mock()

        def _test_query_params(search_criteria, raw_result, expected_query_params):
            mock__request.reset_mock()
            mock__request.return_value.json.side_effect = [raw_result]
            results, _ = search_plugin.query(
                prep=PreparedSearch(
                    page=1,
                    items_per_page=10,
                    auth_plugin=auth_plugin,
                ),
                **search_criteria,
            )
            self.assertDictEqual(
                mock__request.call_args_list[0].args[1].query_params,
                expected_query_params,
            )

        raw_result = {
            "properties": {"itemsPerPage": 1, "startIndex": 0, "totalResults": 1},
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "startdate": "1975-01-01T00:00:00Z",
                        "enddate": "2024-09-30T00:00:00Z",
                    },
                    "id": "derived-gridded-glacier-mass-change-576f8a153a25a83d9d3a5cfb03c4a759",
                }
            ],
        }

        # Test #1: using the datetime
        search_criteria = {
            "collection": collection,
            "start_datetime": "1980-01-01",
            "end_datetime": "1981-12-31",
            "ecmwf:variable": "glacier_mass_change",
            "ecmwf:data_format": "zip",
            "ecmwf:product_version": "wgms_fog_2022_09",
        }
        expected_query_params = {
            "dataset_id": "EO:ECMWF:DAT:DERIVED_GRIDDED_GLACIER_MASS_CHANGE",
            "hydrological_year": ["1980_81"],
            "variable": "glacier_mass_change",
            "data_format": "zip",
            "product_version": "wgms_fog_2022_09",
            "itemsPerPage": 10,
            "startIndex": 0,
        }
        _test_query_params(search_criteria, raw_result, expected_query_params)

        # Test #2: using parameter hydrological_year (single value)
        search_criteria = {
            "collection": collection,
            "ecmwf:variable": "glacier_mass_change",
            "ecmwf:data_format": "zip",
            "ecmwf:product_version": "wgms_fog_2022_09",
            "ecmwf:hydrological_year": ["2020_21"],
        }
        expected_query_params = {
            "dataset_id": "EO:ECMWF:DAT:DERIVED_GRIDDED_GLACIER_MASS_CHANGE",
            "hydrological_year": ["2020_21"],
            "variable": "glacier_mass_change",
            "data_format": "zip",
            "product_version": "wgms_fog_2022_09",
            "itemsPerPage": 10,
            "startIndex": 0,
        }
        _test_query_params(search_criteria, raw_result, expected_query_params)

        # Test #3: using parameter hydrological_year (multiple values)
        search_criteria = {
            "collection": collection,
            "ecmwf:variable": "glacier_mass_change",
            "ecmwf:data_format": "zip",
            "ecmwf:product_version": "wgms_fog_2022_09",
            "ecmwf:hydrological_year": ["1990_91", "2020_21"],
        }
        expected_query_params = {
            "dataset_id": "EO:ECMWF:DAT:DERIVED_GRIDDED_GLACIER_MASS_CHANGE",
            "hydrological_year": ["1990_91", "2020_21"],
            "variable": "glacier_mass_change",
            "data_format": "zip",
            "product_version": "wgms_fog_2022_09",
            "itemsPerPage": 10,
            "startIndex": 0,
        }
        _test_query_params(search_criteria, raw_result, expected_query_params)


class TestSearchPluginODataV4Search(BaseSearchPluginTest):
    def setUp(self):
        super(TestSearchPluginODataV4Search, self).setUp()

        # manually add conf as this provider is not supported any more
        providers_config = self.plugins_manager.providers_config
        onda_config = cached_yaml_load_all(Path(TEST_RESOURCES_PATH) / "onda_conf.yml")[
            0
        ]
        merge_configs(providers_config, {"onda": onda_config})
        self.plugins_manager = PluginManager(providers_config)

        # One of the providers that has a ODataV4Search Search plugin
        provider = "onda"
        self.onda_search_plugin = self.get_search_plugin(self.collection, provider)
        self.onda_auth_plugin = self.get_auth_plugin(self.onda_search_plugin)
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

        self.assertEqual(products[0].properties["onda:foo"], "bar")

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
            prep=PreparedSearch(
                page=1,
                items_per_page=2,
                auth=self.onda_auth_plugin,
            ),
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

        self.assertEqual(
            mock__request.call_args_list[0].args[1].url, self.onda_url_count
        )
        self.assertEqual(mock__request.call_args_list[1].args[1].url, onda_url_search)

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
            prep=PreparedSearch(
                page=1,
                items_per_page=2,
                auth=self.onda_auth_plugin,
            ),
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
            prep=PreparedSearch(
                page=1,
                items_per_page=2,
                auth=self.onda_auth_plugin,
            ),
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

        self.assertEqual(
            mock__request.call_args_list[0].args[1].url, self.onda_url_count
        )
        self.assertEqual(mock__request.call_args_list[1].args[1].url, onda_url_search)

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
                prep=PreparedSearch(
                    page=1,
                    items_per_page=2,
                    auth=self.onda_auth_plugin,
                ),
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
            error_message = f"Skipping error while searching for {search_provider} {search_type} instance"
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
        """A query with a ODataV4Search (here onda) must only use cloudCover filtering for non-radar collections"""
        # per_product_metadata_query parameter is updated to False if it is necessary
        per_product_metadata_query = (
            self.onda_search_plugin.config.per_product_metadata_query
        )
        if per_product_metadata_query:
            self.onda_search_plugin.config.per_product_metadata_query = False

        self.onda_search_plugin.query(collection="S2_MSI_L1C", cloudCover=50)
        # restore per_product_metadata_query initial value if it is necessary
        if (
            self.onda_search_plugin.config.per_product_metadata_query
            != per_product_metadata_query
        ):
            self.onda_search_plugin.config.per_product_metadata_query = (
                per_product_metadata_query
            )

        mock__request.assert_called()
        self.assertIn(
            "cloudCoverPercentage", mock__request.call_args_list[-1][0][1].url
        )
        mock__request.reset_mock()

        self.onda_search_plugin.query(collection="S1_SAR_GRD", cloudCover=50)
        mock__request.assert_called()
        self.assertNotIn(
            "cloudCoverPercentage", mock__request.call_args_list[-1][0][1].url
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_odatav4search_distinct_collection_mtd_mapping(
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
            collection="S1_SAR_GRD",
            auth=None,
        )
        self.assertIn("bar", products[0].properties)
        self.assertEqual(products[0].properties["bar"], "baz")

        # search with another collection
        self.assertNotIn(
            "bar", search_plugin.config.products["S1_SAR_SLC"]["metadata_mapping"]
        )
        products, estimate = search_plugin.query(
            collection="S1_SAR_SLC",
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

        search_plugin = self.get_search_plugin(self.collection, "earth_search")

        products, estimate = search_plugin.query(
            prep=PreparedSearch(page=1, items_per_page=2),
            **self.search_criteria_s2_msi_l1c,
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

        search_plugin = self.get_search_plugin(self.collection, "earth_search")

        products, estimate = search_plugin.query(
            prep=PreparedSearch(
                page=1,
                items_per_page=3,
            )
        )
        self.assertEqual(
            products[0].geometry, self.search_criteria_s2_msi_l1c["geometry"]
        )
        self.assertEqual(products[1].geometry.bounds, (-180.0, -90.0, 180.0, 90.0))

    @mock.patch(
        "eodag.api.product.drivers.base.DatasetDriver.guess_asset_key_and_roles",
        autospec=True,
    )
    @mock.patch.dict(QueryStringSearch.extract_properties, {"json": mock.MagicMock()})
    def test_plugins_search_stacsearch_normalize_asset_key_from_href(
        self, mock_guess_asset_key_and_roles
    ):
        """normalize_results must guess asset key from href if asset_key_from_href is set to True"""

        mock_properties_from_json = QueryStringSearch.extract_properties["json"]
        mock_properties_from_json.return_value = {
            "geometry": "POINT (0 0)",
            "assets": {
                "foo": {
                    "href": "https://example.com/foo",
                    "roles": ["bar"],
                },
            },
        }
        mock_guess_asset_key_and_roles.return_value = ("normalized_key", ["some_role"])

        # guess asset key from href
        search_plugin = self.get_search_plugin(self.collection, "earth_search")
        self.assertFalse(hasattr(search_plugin.config, "asset_key_from_href"))
        products = search_plugin.normalize_results([{}])
        mock_guess_asset_key_and_roles.assert_called_once_with(
            products[0].driver, "https://example.com/foo", products[0]
        )
        self.assertEqual(len(products[0].assets), 1)
        self.assertEqual(products[0].assets["normalized_key"]["roles"], ["some_role"])

        mock_guess_asset_key_and_roles.reset_mock()
        # guess asset key from origin key
        search_plugin = self.get_search_plugin(self.collection, "geodes")
        self.assertEqual(search_plugin.config.asset_key_from_href, False)
        products = search_plugin.normalize_results([{}])
        mock_guess_asset_key_and_roles.assert_called_once_with(
            products[0].driver, "foo", products[0]
        )
        self.assertEqual(len(products[0].assets), 1)
        self.assertEqual(products[0].assets["normalized_key"]["roles"], ["some_role"])
        # title is also set using normlized key
        self.assertEqual(
            products[0].assets["normalized_key"]["title"], "normalized_key"
        )

    @mock.patch("eodag.plugins.search.qssearch.requests.post", autospec=True)
    def test_plugins_search_stacsearch_opened_time_intervals(self, mock_requests_post):
        """Opened time intervals must be handled by StacSearch plugin"""
        mock_requests_post.return_value = mock.Mock()
        mock_requests_post.return_value.json.side_effect = [
            {
                "features": [
                    {
                        "id": "foo",
                        "geometry": None,
                    },
                ],
            },
        ] * 4
        search_plugin = self.get_search_plugin(self.collection, "earth_search")

        search_plugin.query(
            start_datetime="2020-01-01",
            end_datetime="2020-01-02",
        )
        self.assertEqual(
            mock_requests_post.call_args.kwargs["json"]["datetime"],
            "2020-01-01T00:00:00.000Z/2020-01-02T00:00:00.000Z",
        )

        search_plugin.query(start_datetime="2020-01-01")
        self.assertEqual(
            mock_requests_post.call_args.kwargs["json"]["datetime"],
            "2020-01-01T00:00:00.000Z/..",
        )

        search_plugin.query(end_datetime="2020-01-02")
        self.assertEqual(
            mock_requests_post.call_args.kwargs["json"]["datetime"],
            "../2020-01-02T00:00:00.000Z",
        )

        search_plugin.query()
        self.assertNotIn("datetime", mock_requests_post.call_args.kwargs["json"])

    @mock.patch("eodag.plugins.search.qssearch.StacSearch._request", autospec=True)
    def test_plugins_search_stacsearch_distinct_collection_mtd_mapping(
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
        search_plugin = self.get_search_plugin(self.collection, "earth_search")

        # update metadata_mapping only for S2_MSI_L1C
        search_plugin.config.products["S2_MSI_L1C"]["metadata_mapping"]["bar"] = (
            None,
            "baz",
        )
        products, estimate = search_plugin.query(
            collection="S2_MSI_L1C",
            auth=None,
        )
        self.assertIn("bar", products[0].properties)
        self.assertEqual(products[0].properties["bar"], "baz")

        # search with another collection
        self.assertNotIn(
            "metadata_mapping", search_plugin.config.products["S1_SAR_GRD"]
        )
        products, estimate = search_plugin.query(
            collection="S1_SAR_GRD",
            auth=None,
        )
        self.assertNotIn("bar", products[0].properties)

    @mock.patch("eodag.plugins.search.qssearch.StacSearch._request", autospec=True)
    def test_plugins_search_stacsearch_distinct_collection_mtd_mapping_earth_search(
        self, mock__request
    ):
        """The metadata mapping for a earth_search should correctly build tileIdentifier"""
        mock__request.return_value = mock.Mock()
        result = {
            "features": [
                {
                    "id": "foo",
                    "geometry": None,
                    "properties": {
                        "mgrs:utm_zone": "31",
                        "mgrs:latitude_band": "T",
                        "mgrs:grid_square": "CJ",
                    },
                },
            ],
        }
        collection = "S2_MSI_L1C"
        mock__request.return_value.json.side_effect = [result]
        search_plugin = self.get_search_plugin(collection, "earth_search")

        products, _ = search_plugin.query(
            collection=collection,
            auth=None,
        )
        self.assertIn("tileIdentifier", products[0].properties)
        self.assertEqual(
            products[0].properties["tileIdentifier"],
            "31TCJ",
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_stacsearch_discover_queryables(self, mock_request):
        provider_queryables = {
            "type": "object",
            "title": "Querable",
            "properties": {
                "dataset_id": {
                    "title": "dataset_id",
                    "type": "string",
                    "oneOf": [
                        {
                            "const": "EO:ESA:DAT:COP-DEM",
                            "title": "EO:ESA:DAT:COP-DEM",
                            "group": None,
                        }
                    ],
                },
                "bbox": {
                    "title": "Bbox",
                    "type": "array",
                    "minItems": 4,
                    "maxItems": 4,
                    "items": [
                        {"type": "number", "maximum": 180, "minimum": -180},
                        {"type": "number", "maximum": 90, "minimum": -90},
                        {"type": "number", "maximum": 180, "minimum": -180},
                        {"type": "number", "maximum": 90, "minimum": -90},
                    ],
                },
                "productIdentifier": {
                    "title": "Product Identifier",
                    "type": "string",
                    "pattern": "^[a-zA-Z0-9]+$",
                },
                "collection": {
                    "title": "Collection",
                    "type": "string",
                    "oneOf": [
                        {"const": "DGE_30", "title": "DGE_30", "group": None},
                        {"const": "DGE_90", "title": "DGE_90", "group": None},
                        {"const": "DTE_30", "title": "DTE_30", "group": None},
                        {"const": "DTE_90", "title": "DTE_90", "group": None},
                    ],
                },
                "startdate": {
                    "title": "Start Date",
                    "type": "string",
                    "format": "date-time",
                    "minimum": "",
                    "maximum": "",
                    "default": "",
                },
                "enddate": {
                    "title": "End Date",
                    "type": "string",
                    "format": "date-time",
                    "minimum": "",
                    "maximum": "",
                    "default": "",
                },
            },
            "required": ["dataset_id"],
        }
        mock_request.return_value = mock.Mock()
        mock_request.return_value.json.side_effect = [provider_queryables]
        plugin = self.get_search_plugin(provider="wekeo_main")
        queryables = plugin.discover_queryables(
            collection="COP_DEM_GLO90_DGED", provider="wekeo_main"
        )
        self.assertIn("collection", queryables)
        self.assertIn("providerCollection", queryables)
        self.assertIn("geom", queryables)
        self.assertIn("start", queryables)
        self.assertIn("end", queryables)

    @mock.patch("eodag.plugins.search.qssearch.StacSearch._request", autospec=True)
    def test_plugins_search_stacsearch_unparsed_query_parameters(self, mock__request):
        """search_param_unparsed should pass query params as-is to the provider"""
        result = {"features": []}
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.side_effect = [result]
        search_plugin = self.get_search_plugin(provider="earth_search")
        search_plugin.query(query={"foo": "bar", "baz": "qux"})

        self.assertTrue(mock__request.called)
        called_args, _ = mock__request.call_args
        prepared_search = called_args[1]
        self.assertEqual(
            prepared_search.query_params["query"], {"foo": "bar", "baz": "qux"}
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_dedl_discover_queryables(self, mock_request):
        """
        Test the discovery and parsing of queryables from the DEDL provider.

        This test verifies that:
        - The "ecmwf:time" field is correctly interpreted as an annotated list with a
        single literal value "00:00".
        - The "start" field is interpreted as an annotated union of datetime and date types.
        - The "geom" field is interpreted as an annotated union that includes a string,
        a dictionary with string keys and float values, and subclasses of BaseGeometry.

        The test mocks the _request method of the plugin to simulate a response with
        predefined queryables, then verifies the correctness of the resulting type annotations.
        """
        provider_queryables = {
            "$schema": "https://json-schema.org/draft/2019-09/schema",
            "type": "object",
            "title": "Queryables for EODAG STAC API",
            "description": "Queryable names for the EODAG STAC API Item Search filter. ",
            "properties": {
                "ecmwf:variable": {
                    "default": "10m_u_component_of_wind",
                    "items": {
                        "enum": [
                            "10m_u_component_of_wind",
                            "10m_v_component_of_wind",
                            "2m_dewpoint_temperature",
                            "2m_temperature",
                        ],
                        "type": "string",
                    },
                    "title": "variable",
                    "type": "array",
                },
                "ecmwf:pressure_level": {
                    "items": {},
                    "title": "pressure_level",
                    "type": "array",
                },
                "ecmwf:time": {
                    "default": "00:00",
                    "description": "Model base time as HH:MM (UTC)",
                    "items": {"const": "00:00", "type": "string"},
                    "title": "time",
                    "type": "array",
                },
                "start_datetime": {
                    "anyOf": [
                        {"format": "date-time", "type": "string"},
                        {"format": "date", "type": "string"},
                    ],
                    "default": "2015-01-01T00:00:00Z",
                    "title": "start_datetime",
                },
                "end_datetime": {
                    "anyOf": [
                        {"format": "date-time", "type": "string"},
                        {"format": "date", "type": "string"},
                    ],
                    "default": "2015-01-01T00:00:00Z",
                    "title": "end_datetime",
                },
                "geometry": {
                    "description": "Geometry",
                    "ref": "https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json#/geometry",
                },
                "bbox": {
                    "description": "BBox",
                    "type": "array",
                    "oneOf": [
                        {"minItems": 4, "maxItems": 4},
                        {"minItems": 6, "maxItems": 6},
                    ],
                    "items": {"type": "number"},
                },
            },
            "required": [
                "ecmwf:variable",
                "ecmwf:time",
                "start_datetime",
                "geometry",
                "bbox",
            ],
            "additionalProperties": False,
        }
        mock_request.return_value = mock.Mock()
        mock_request.return_value.json.side_effect = [provider_queryables]
        plugin = self.get_search_plugin(provider="dedl")
        queryables_dedl = plugin.discover_queryables(
            collection="CAMS_GAC_FORECAST", provider="dedl"
        )

        # Check that "ecmwf:time" has type Annotated[list[Literal['00:00']], ...]
        self.assertIn("ecmwf:time", queryables_dedl)
        annotated_type = queryables_dedl["ecmwf:time"]
        args = get_args(annotated_type)
        base_type = args[0]
        self.assertEqual(get_origin(base_type), list)
        literal_args = get_args(base_type)
        self.assertEqual(literal_args, (Literal["00:00"],))

        # Check that "start" has type Annotated[str, ...]
        self.assertIn("start", queryables_dedl)
        annotated_type = queryables_dedl["start"]
        args = get_args(annotated_type)
        self.assertEqual(args[0], str)

        # Check that "geom" has type Annotated[Union[str, dict[str, float], BaseGeometry], ...]
        self.assertIn("geom", queryables_dedl)
        annotated_type = queryables_dedl["geom"]
        args = get_args(annotated_type)
        base_type = args[0]
        self.assertEqual(get_origin(base_type), Union)
        union_args = get_args(base_type)
        self.assertIn(str, union_args)
        self.assertTrue(any(get_origin(arg) is dict for arg in union_args))
        self.assertTrue(
            any(
                issubclass(arg, BaseGeometry)
                for arg in union_args
                if isinstance(arg, type)
            )
        )


class TestSearchPluginMeteoblueSearch(BaseSearchPluginTest):
    @mock.patch("eodag.plugins.authentication.qsauth.requests.get", autospec=True)
    def setUp(self, mock_requests_get):
        super(TestSearchPluginMeteoblueSearch, self).setUp()
        # enable long diffs in test reports
        self.maxDiff = None
        # One of the providers that has a MeteoblueSearch Search plugin
        provider = "meteoblue"
        self.search_plugin = self.get_search_plugin(provider=provider)
        self.auth_plugin = self.get_auth_plugin(self.search_plugin)
        self.auth_plugin.config.credentials = {"cred": "entials"}
        self.auth = self.auth_plugin.authenticate()

    @mock.patch("eodag.plugins.search.qssearch.requests.post", autospec=True)
    def test_plugins_search_buildpostsearchresult_count_and_search(
        self, mock_requests_post
    ):
        """A query with a MeteoblueSearch must return a single result"""

        # custom query for meteoblue
        custom_query = {"queries": {"foo": "bar"}}
        products, estimate = self.search_plugin.query(
            prep=PreparedSearch(auth_plugin=self.auth_plugin, auth=self.auth),
            **custom_query,
        )

        mock_requests_post.assert_called_with(
            self.search_plugin.config.api_endpoint,
            json=mock.ANY,
            headers=USER_AGENT,
            timeout=DEFAULT_SEARCH_TIMEOUT,
            auth=self.auth,
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
                {
                    "geometry": default_geom,
                    "runOnJobQueue": True,
                    **custom_query,
                }
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


class TestSearchPluginCreodiasS3Search(BaseSearchPluginTest):
    def setUp(self):
        super(TestSearchPluginCreodiasS3Search, self).setUp()
        self.provider = "creodias_s3"

    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth.get_s3_client", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_creodias_s3_links(self, mock_request, mock_s3_client):
        # s3 links should be added to products with register_downloader
        search_plugin = self.get_search_plugin("S1_SAR_GRD", self.provider)
        client = boto3.client("s3", aws_access_key_id="a", aws_secret_access_key="b")
        mock_s3_client.return_value = client
        stubber = Stubber(client)
        s3_response_file = (
            Path(TEST_RESOURCES_PATH) / "provider_responses/creodias_s3_objects.json"
        )
        with open(s3_response_file) as f:
            list_objects_response = json.load(f)
        creodias_search_result_file = (
            Path(TEST_RESOURCES_PATH) / "eodag_search_result_creodias.json"
        )
        with open(creodias_search_result_file) as f:
            creodias_search_result = json.load(f)
        mock_request.return_value = MockResponse(creodias_search_result, 200)

        res = search_plugin.query(collection="S1_SAR_GRD")
        for product in res[0]:
            download_plugin = self.plugins_manager.get_download_plugin(product)
            auth_plugin = self.plugins_manager.get_auth_plugin(download_plugin, product)
            stubber.add_response("list_objects", list_objects_response)
            stubber.activate()
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
        self.assertEqual(3, len(assets))
        # check if s3 links have been created correctly
        for asset in assets.values():
            self.assertIn("s3://eodata/Sentinel-1/SAR/GRD/2014/10/10", asset["href"])

        # no occur should occur and assets should be empty if list_objects does not have content
        # (this situation will occur if the product does not have assets but is a tar file)
        stubber.add_response("list_objects", {})
        download_plugin = self.plugins_manager.get_download_plugin(res[0][0])
        auth_plugin = self.plugins_manager.get_auth_plugin(download_plugin, res[0][0])
        res[0][0].driver = None
        res[0][0].assets = AssetsDict(res[0][0])
        res[0][0].register_downloader(download_plugin, auth_plugin)
        self.assertIsNotNone(res[0][0].driver)
        self.assertEqual(0, len(res[0][0].assets))

    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth.get_s3_client", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_creodias_s3_client_error(
        self, mock_request, mock_s3_client
    ):
        # request error should be raised when there is an error when fetching data from the s3
        search_plugin = self.get_search_plugin("S1_SAR_GRD", self.provider)
        client = boto3.client("s3", aws_access_key_id="a", aws_secret_access_key="b")
        mock_s3_client.return_value = client
        stubber = Stubber(client)

        creodias_search_result_file = (
            Path(TEST_RESOURCES_PATH) / "eodag_search_result_creodias.json"
        )
        with open(creodias_search_result_file) as f:
            creodias_search_result = json.load(f)
        mock_request.return_value = MockResponse(creodias_search_result, 200)

        with self.assertRaises(NotAvailableError):
            res = search_plugin.query(collection="S1_SAR_GRD")
            for product in res[0]:
                download_plugin = self.plugins_manager.get_download_plugin(product)
                auth_plugin = self.plugins_manager.get_auth_plugin(
                    download_plugin, product
                )
                auth_plugin.config.credentials = {
                    "aws_access_key_id": "foo",
                    "aws_secret_access_key": "bar",
                }
                stubber.add_client_error("list_objects")
                stubber.activate()
                product.register_downloader(download_plugin, auth_plugin)


class TestSearchPluginECMWFSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSearchPluginECMWFSearch, cls).setUpClass()
        providers_config = load_default_config()
        cls.plugins_manager = PluginManager(providers_config)

    def setUp(self):
        self.provider = "cop_ads"
        self.search_plugin = self.get_search_plugin(provider=self.provider)
        self.query_dates = {
            "start_datetime": "2020-01-01",
            "end_datetime": "2020-01-02",
        }
        self.collection = "CAMS_EAC4"
        self.product_dataset = "cams-global-reanalysis-eac4"
        self.collection_params = {
            "ecmwf:dataset": self.product_dataset,
        }
        self.custom_query_params = {
            "ecmwf:dataset": "cams-global-ghg-reanalysis-egg4",
            "ecmwf:step": 0,
            "ecmwf:variable": "carbon_dioxide",
            "ecmwf:pressure_level": "10",
            "ecmwf:model_level": "1",
            "ecmwf:time": "00:00",
            "ecmwf:data_format": "grib",
        }

    def get_search_plugin(self, collection=None, provider=None):
        return next(
            self.plugins_manager.get_search_plugins(
                collection=collection, provider=provider
            )
        )

    def test_plugins_search_ecmwfsearch_exclude_end_date(self):
        """ECMWFSearch.query must adapt end date in certain cases"""
        # start & stop as dates -> keep end date as it is
        results, _ = self.search_plugin.query(
            collection=self.collection,
            start_datetime="2020-01-01",
            end_datetime="2020-01-02",
        )
        eoproduct = results[0]
        self.assertEqual(
            "2020-01-01T00:00:00.000Z",
            eoproduct.properties["start_datetime"],
        )
        self.assertEqual(
            "2020-01-02T00:00:00.000Z",
            eoproduct.properties["end_datetime"],
        )
        # start & stop as datetimes, not midnight -> keep and dates as it is
        results, _ = self.search_plugin.query(
            collection=self.collection,
            start_datetime="2020-01-01T02:00:00Z",
            end_datetime="2020-01-02T03:00:00Z",
        )
        eoproduct = results[0]
        self.assertEqual(
            "2020-01-01T02:00:00.000Z",
            eoproduct.properties["start_datetime"],
        )
        self.assertEqual(
            "2020-01-02T03:00:00.000Z",
            eoproduct.properties["end_datetime"],
        )
        # start & stop as datetimes, midnight -> exclude end date
        results, _ = self.search_plugin.query(
            collection=self.collection,
            start_datetime="2020-01-01T00:00:00Z",
            end_datetime="2020-01-02T00:00:00Z",
        )
        eoproduct = results[0]
        self.assertEqual(
            "2020-01-01T00:00:00.000Z",
            eoproduct.properties["start_datetime"],
        )
        self.assertEqual(
            "2020-01-01T00:00:00.000Z",
            eoproduct.properties["end_datetime"],
        )
        # start & stop same date -> keep end date
        results, _ = self.search_plugin.query(
            collection=self.collection,
            start_datetime="2020-01-01T00:00:00Z",
            end_datetime="2020-01-01T00:00:00Z",
        )
        eoproduct = results[0]
        self.assertEqual(
            "2020-01-01T00:00:00.000Z",
            eoproduct.properties["start_datetime"],
        )
        self.assertEqual(
            "2020-01-01T00:00:00.000Z",
            eoproduct.properties["end_datetime"],
        )

    def test_plugins_search_ecmwfsearch_dates_missing(self):
        """ECMWFSearch.query must use default dates if missing"""
        # given start & stop
        results, _ = self.search_plugin.query(
            collection=self.collection,
            start_datetime="2020-01-01",
            end_datetime="2020-01-02",
        )
        eoproduct = results[0]
        self.assertEqual(
            eoproduct.properties["start_datetime"],
            "2020-01-01T00:00:00.000Z",
        )
        self.assertEqual(
            eoproduct.properties["end_datetime"],
            "2020-01-02T00:00:00.000Z",
        )

        # missing start & stop
        results, _ = self.search_plugin.query(
            collection=self.collection,
        )
        eoproduct = results[0]
        self.assertIn(
            eoproduct.properties["start_datetime"],
            DEFAULT_MISSION_START_DATE,
        )
        exp_end_date = datetime.strptime(
            DEFAULT_MISSION_START_DATE, "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        self.assertIn(
            eoproduct.properties["end_datetime"],
            exp_end_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z",
        )

        # missing start & stop and plugin.collection_config set (set in core._prepare_search)
        self.search_plugin.config.collection_config = {
            "_collection": self.collection,
            "extent": {"temporal": {"interval": [["1985-10-26", "2015-10-21"]]}},
            "alias": "THE.ALIAS",
        }
        results, _ = self.search_plugin.query(
            collection="THE.ALIAS",
        )
        eoproduct = results[0]
        self.assertEqual(
            eoproduct.properties["start_datetime"],
            "1985-10-26T00:00:00.000Z",
        )
        self.assertEqual(
            eoproduct.properties["end_datetime"],
            "1985-10-26T00:00:00.000Z",
        )
        self.assertEqual("THE.ALIAS", eoproduct.properties["eodag:alias"])

    def test_plugins_search_ecmwfsearch_with_year_month_day_filter(self):
        """ECMWFSearch.query must use have datetime in response if year, month, day used in filters"""

        results, _ = self.search_plugin.query(
            prep=PreparedSearch(),
            collection="ERA5_SL",
            **{
                "ecmwf:year": "2020",
                "ecmwf:month": ["02"],
                "ecmwf:day": ["20", "21"],
                "ecmwf:time": ["01:00"],
            },
        )
        eoproduct = results[0]

        self.assertEqual(
            eoproduct.properties["start_datetime"],
            "2020-02-20T01:00:00.000Z",
        )
        self.assertEqual(
            eoproduct.properties["end_datetime"],
            "2020-02-21T01:00:00.000Z",
        )
        self.assertEqual(
            eoproduct.properties["ecmwf:year"],
            "2020",
        )
        self.assertEqual(
            eoproduct.properties["ecmwf:month"],
            ["02"],
        )
        self.assertEqual(
            eoproduct.properties["ecmwf:day"],
            ["20", "21"],
        )

    def test_plugins_search_ecmwfsearch_without_producttype(self):
        """
        ECMWFSearch.query must build a EOProduct from input parameters without collection.
        For test only, result cannot be downloaded.
        """
        results, count = self.search_plugin.query(
            PreparedSearch(count=True),
            **{
                "ecmwf:dataset": self.product_dataset,
                "start_datetime": "2020-01-01",
                "end_datetime": "2020-01-02",
            },
        )
        assert count == 1
        eoproduct = results[0]
        assert eoproduct.geometry.bounds == (-180.0, -90.0, 180.0, 90.0)
        assert eoproduct.properties["start_datetime"] == "2020-01-01T00:00:00.000Z"
        assert eoproduct.properties["end_datetime"] == "2020-01-02T00:00:00.000Z"
        assert eoproduct.properties["title"] == eoproduct.properties["id"]
        assert eoproduct.properties["title"].startswith(
            f"{self.product_dataset.upper()}"
        )
        assert eoproduct.properties["orderLink"].startswith("http")
        assert NOT_AVAILABLE in eoproduct.location

    def test_plugins_search_ecmwfsearch_with_producttype(self):
        """ECMWFSearch.query must build a EOProduct from input parameters with predefined collection"""
        results, _ = self.search_plugin.query(
            **self.query_dates, collection=self.collection, geometry=[1, 2, 3, 4]
        )
        eoproduct = results[0]
        assert eoproduct.properties["title"].startswith(self.collection)
        assert eoproduct.geometry.bounds == (1.0, 2.0, 3.0, 4.0)
        # check if collection_params is a subset of eoproduct.properties
        assert self.collection_params.items() <= eoproduct.properties.items()

        # collection default settings can be overwritten using search kwargs
        results, _ = self.search_plugin.query(
            **self.query_dates,
            **{"collection": self.collection, "ecmwf:variable": "temperature"},
        )
        eoproduct = results[0]
        assert eoproduct.properties["ecmwf:variable"] == "temperature"

    def test_plugins_search_ecmwfsearch_with_custom_producttype(self):
        """ECMWFSearch.query must build a EOProduct from input parameters with custom collection"""
        results, _ = self.search_plugin.query(
            **self.query_dates,
            **self.custom_query_params,
        )
        eoproduct = results[0]
        assert eoproduct.properties["title"].startswith(
            self.custom_query_params["ecmwf:dataset"].upper()
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

    def test_plugins_search_ecmwf_temporal_to_eodag(self):
        """ecmwf_temporal_to_eodag must parse all expected dates formats"""
        self.assertEqual(
            ecmwf_temporal_to_eodag(
                dict(day="15", month="02", year="2022", time="0600")
            ),
            ("2022-02-15T06:00:00Z", "2022-02-15T06:00:00Z"),
        )
        self.assertEqual(
            ecmwf_temporal_to_eodag(dict(hday="15", hmonth="02", hyear="2022")),
            ("2022-02-15T00:00:00Z", "2022-02-15T00:00:00Z"),
        )
        self.assertEqual(
            ecmwf_temporal_to_eodag(dict(date="2022-02-15")),
            ("2022-02-15T00:00:00Z", "2022-02-15T00:00:00Z"),
        )
        self.assertEqual(
            ecmwf_temporal_to_eodag(
                dict(date="2022-02-15T00:00:00Z/2022-02-16T00:00:00Z")
            ),
            ("2022-02-15T00:00:00Z", "2022-02-16T00:00:00Z"),
        )
        self.assertEqual(
            ecmwf_temporal_to_eodag(dict(date="20220215/to/20220216")),
            ("2022-02-15T00:00:00Z", "2022-02-16T00:00:00Z"),
        )
        # List of dates
        self.assertEqual(
            ecmwf_temporal_to_eodag(dict(date=["20220215", "20220216"])),
            ("2022-02-15T00:00:00Z", "2022-02-16T00:00:00Z"),
        )
        self.assertEqual(
            ecmwf_temporal_to_eodag(dict(date=["20220215"])),
            ("2022-02-15T00:00:00Z", "2022-02-15T00:00:00Z"),
        )

    def test_plugins_search_ecmwfsearch_get_available_values_from_contraints(self):
        """ECMWFSearch must return available values from constraints"""
        constraints = [
            {"date": ["2025-01-01/2025-06-01"], "variable": ["a", "b"]},
            {"date": ["2024-01-01/2024-12-01"], "variable": ["a", "b", "c"]},
        ]
        form_keywords = ["date", "variable"]

        # with a date range as a string
        input_keywords = {"date": "2025-01-01/2025-02-01", "variable": "a"}
        available_values = self.search_plugin.available_values_from_constraints(
            constraints, input_keywords, form_keywords
        )
        available_values = {k: sorted(v) for k, v in available_values.items()}
        self.assertIn("variable", available_values)
        self.assertListEqual(["a", "b"], available_values["variable"])
        self.assertIn("date", available_values)

        # with a date range as the first element of a string list
        input_keywords = {"date": ["2025-01-01/2025-02-01"], "variable": "a"}
        available_values = self.search_plugin.available_values_from_constraints(
            constraints, input_keywords, form_keywords
        )
        available_values = {k: sorted(v) for k, v in available_values.items()}
        self.assertIn("variable", available_values)
        self.assertListEqual(["a", "b"], available_values["variable"])
        self.assertIn("date", available_values)

    @mock.patch(
        "eodag.plugins.search.build_search_result.ECMWFSearch._fetch_data",
        autospec=True,
    )
    def test_plugins_search_ecmwfsearch_discover_queryables_ok(self, mock__fetch_data):
        constraints_path = os.path.join(TEST_RESOURCES_PATH, "constraints.json")
        with open(constraints_path) as f:
            constraints = json.load(f)
        constraints[0]["variable"].append("nitrogen_dioxide")
        constraints[0]["type"].append("validated_reanalysis")
        form_path = os.path.join(TEST_RESOURCES_PATH, "form.json")
        with open(form_path) as f:
            form = json.load(f)
        mock__fetch_data.side_effect = [constraints, form]
        collection_config = {
            "extent": {"temporal": {"interval": [["2001-01-01T00:00:00Z", None]]}}
        }
        setattr(self.search_plugin.config, "collection_config", collection_config)

        provider_queryables_from_constraints_file = [
            "ecmwf:year",
            "ecmwf:month",
            "ecmwf:day",
            "ecmwf:time",
            "ecmwf:variable",
            "ecmwf:leadtime_hour",
            "ecmwf:type",
            "ecmwf:product_type",
        ]
        default_values = deepcopy(
            getattr(self.search_plugin.config, "products", {}).get(
                "CAMS_EU_AIR_QUALITY_RE", {}
            )
        )
        default_values.pop("metadata_mapping", None)
        # ECMWF-like providers don't have default values anymore: override a default value
        default_values["data_format"] = "grib"
        params = deepcopy(default_values)
        params["collection"] = "CAMS_EU_AIR_QUALITY_RE"
        # set a parameter among the required ones of the form file with a default value in this form but not among the
        # ones of the constraints file to an empty value to check if its associated queryable has no default value
        eodag_formatted_data_format = "ecmwf:data_format"
        provider_data_format = eodag_formatted_data_format.replace("ecmwf:", "")
        self.assertIn(provider_data_format, default_values)
        self.assertIn(provider_data_format, [param["name"] for param in form])
        data_format_in_form = [
            param for param in form if param["name"] == provider_data_format
        ][0]
        self.assertTrue(data_format_in_form.get("required", False))
        self.assertIsNotNone(data_format_in_form.get("details", {}).get("default"))
        for constraint in constraints:
            self.assertNotIn(provider_data_format, constraint)
        params[eodag_formatted_data_format] = ""

        # use a parameter among the ones of the form file but not among the ones of the constraints file
        # and of provider default configuration to check if an error is raised, which is supposed to not happen
        eodag_formatted_download_format = "ecmwf:download_format"
        provider_download_format = eodag_formatted_download_format.replace("ecmwf:", "")
        self.assertNotIn(eodag_formatted_download_format, default_values)
        self.assertIn(provider_download_format, [param["name"] for param in form])
        for constraint in constraints:
            self.assertNotIn(provider_data_format, constraint)
        params[eodag_formatted_download_format] = "foo"
        # create parameters matching the first constraint
        params["variable"] = "nitrogen_dioxide"

        queryables = self.search_plugin.discover_queryables(**params)
        # no error was raised, as expected
        self.assertIsNotNone(queryables)

        mock__fetch_data.assert_has_calls(
            [
                call(
                    mock.ANY,
                    "https://ads.atmosphere.copernicus.eu/api/catalogue/v1/collections/"
                    "cams-europe-air-quality-reanalyses/constraints.json",
                ),
                call(
                    mock.ANY,
                    "https://ads.atmosphere.copernicus.eu/api/catalogue/v1/collections/"
                    "cams-europe-air-quality-reanalyses/form.json",
                ),
            ]
        )

        # queryables from provider constraints file are added (here the ones of CAMS_EU_AIR_QUALITY_RE for cop_ads)
        for provider_queryable in provider_queryables_from_constraints_file:
            provider_queryable = (
                get_queryable_from_provider(
                    provider_queryable,
                    self.search_plugin.get_metadata_mapping("CAMS_EU_AIR_QUALITY_RE"),
                )
                or provider_queryable
            )
            self.assertIn(provider_queryable, queryables)

        # default properties in provider config are added and must be default values of the queryables
        for property, default_value in self.search_plugin.config.products[
            "CAMS_EU_AIR_QUALITY_RE"
        ].items():
            queryable = queryables.get(property)
            # a special case for eodag_formatted_data_format queryable is required
            # as its default value has been overwritten by an empty value
            if queryable is not None and property == eodag_formatted_data_format:
                self.assertEqual(
                    PydanticUndefined, queryable.__metadata__[0].get_default()
                )
                # queryables with empty default values are required
                self.assertTrue(queryable.__metadata__[0].is_required())
            elif queryable is not None:
                self.assertEqual(default_value, queryable.__metadata__[0].get_default())
                # queryables with default values are not required
                self.assertFalse(queryable.__metadata__[0].is_required())

        # required queryable
        queryable = queryables.get("ecmwf:month")
        if queryable is not None:
            self.assertEqual(["01"], queryable.__metadata__[0].get_default())
            self.assertFalse(queryable.__metadata__[0].is_required())

        # check that queryable constraints from the constraints file are in queryable info
        queryable = queryables.get("ecmwf:variable")
        if queryable is not None:
            variable_constraints = constraints[0]["variable"]
            # remove queryable constraints duplicates to make the assertion works
            self.assertSetEqual(
                set(variable_constraints),
                set(get_args(queryable.__origin__.__args__[0])),
            )

        # reset mock
        mock__fetch_data.reset_mock()
        mock__fetch_data.side_effect = [constraints, form]
        # with additional param
        params = deepcopy(default_values)
        params["collection"] = "CAMS_EU_AIR_QUALITY_RE"
        params["ecmwf:variable"] = "a"
        queryables = self.search_plugin.discover_queryables(**params)
        self.assertIsNotNone(queryables)

        # cached values are not used to make the set of unit tests work then the mock is called again
        mock__fetch_data.assert_has_calls(
            [
                call(
                    mock.ANY,
                    "https://ads.atmosphere.copernicus.eu/api/catalogue/v1/collections/"
                    "cams-europe-air-quality-reanalyses/constraints.json",
                ),
                call(
                    mock.ANY,
                    "https://ads.atmosphere.copernicus.eu/api/catalogue/v1/collections/"
                    "cams-europe-air-quality-reanalyses/form.json",
                ),
            ]
        )

        self.assertEqual(12, len(queryables))
        # default properties called in function arguments are added and must be default values of the queryables
        queryable = queryables.get("ecmwf:variable")
        if queryable is not None:
            self.assertEqual("a", queryable.__metadata__[0].get_default())
            self.assertFalse(queryable.__metadata__[0].is_required())

    @mock.patch(
        "eodag.plugins.search.build_search_result.ECMWFSearch._fetch_data",
        autospec=True,
    )
    def test_plugins_search_ecmwfsearch_discover_queryables_ko(self, mock__fetch_data):
        constraints_path = os.path.join(TEST_RESOURCES_PATH, "constraints.json")
        with open(constraints_path) as f:
            constraints = json.load(f)
        form_path = os.path.join(TEST_RESOURCES_PATH, "form.json")
        with open(form_path) as f:
            form = json.load(f)
        mock__fetch_data.side_effect = [constraints, form]

        default_values = deepcopy(
            getattr(self.search_plugin.config, "products", {}).get(
                "CAMS_EU_AIR_QUALITY_RE", {}
            )
        )
        default_values.pop("metadata_mapping", None)
        params = deepcopy(default_values)
        params["collection"] = "CAMS_EU_AIR_QUALITY_RE"

        # use a wrong parameter, e.g. it is not among the ones of the form file, not among
        # the ones of the constraints file and not among the ones of default provider configuration
        wrong_queryable = "foo"
        self.assertNotIn(wrong_queryable, default_values)
        self.assertNotIn(wrong_queryable, [param["name"] for param in form])
        for constraint in constraints:
            self.assertNotIn(wrong_queryable, constraint)
        params[wrong_queryable] = "bar"

        # Test the function, expecting ValidationError to be raised
        with self.assertRaises(ValidationError) as context:
            self.search_plugin.discover_queryables(**params)
        self.assertEqual(
            f"'{wrong_queryable}' is not a queryable parameter for {self.provider}",
            context.exception.message,
        )

    @mock.patch("eodag.utils.requests.requests.sessions.Session.get", autospec=True)
    def test_plugins_search_ecmwf_search_wekeo_discover_queryables(
        self, mock_requests_get
    ):
        # One of the providers that has discover_queryables() configured with QueryStringSearch
        search_plugin = self.get_search_plugin(provider="wekeo_ecmwf")
        self.assertEqual("WekeoECMWFSearch", search_plugin.__class__.__name__)
        self.assertEqual(
            "ECMWFSearch",
            search_plugin.discover_queryables.__func__.__qualname__.split(".")[0],
        )

        constraints_path = os.path.join(TEST_RESOURCES_PATH, "constraints.json")
        with open(constraints_path) as f:
            constraints = json.load(f)
        wekeo_ecmwf_constraints = {"constraints": constraints[0]}
        mock_requests_get.return_value = MockResponse(
            wekeo_ecmwf_constraints, status_code=200
        )

        provider_queryables_from_constraints_file = [
            "ecmwf:year",
            "ecmwf:month",
            "ecmwf:day",
            "ecmwf:time",
            "ecmwf:variable",
            "ecmwf:leadtime_hour",
            "ecmwf:type",
            "ecmwf:product_type",
        ]

        queryables = search_plugin._get_collection_queryables(
            collection="ERA5_SL_MONTHLY", alias=None, filters={}
        )
        self.assertIsNotNone(queryables)

        mock_requests_get.assert_called_once_with(
            mock.ANY,
            "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/queryable/"
            "EO:ECMWF:DAT:REANALYSIS_ERA5_SINGLE_LEVELS_MONTHLY_MEANS",
            headers=USER_AGENT,
            auth=None,
            timeout=60,
        )

        # queryables from provider constraints file are added (here the ones of ERA5_SL_MONTHLY for wekeo_ecmwf)
        for provider_queryable in provider_queryables_from_constraints_file:
            provider_queryable = (
                get_queryable_from_provider(
                    provider_queryable,
                    search_plugin.get_metadata_mapping("ERA5_SL_MONTHLY"),
                )
                or provider_queryable
            )
            self.assertIn(provider_queryable, queryables)

        # default properties in provider config are added and must be default values of the queryables
        for property, default_value in search_plugin.config.products[
            "ERA5_SL_MONTHLY"
        ].items():
            queryable = queryables.get(property)
            if queryable is not None:
                self.assertEqual(default_value, queryable.__metadata__[0].get_default())
                # queryables with default values are not required
                self.assertFalse(queryable.__metadata__[0].is_required())

        # queryables without default values are required
        queryable = queryables.get("month")
        if queryable is not None:
            self.assertEqual(PydanticUndefined, queryable.__metadata__[0].get_default())
            self.assertTrue(queryable.__metadata__[0].is_required())

        # check that queryable constraints from the constraints file are in queryable info
        # (here it is a case where all constraints of "variable" queryable can be taken into account)
        queryable = queryables.get("variable")
        if queryable is not None:
            variable_constraints = []
            for constraint in constraints:
                if "variable" in constraint:
                    variable_constraints.extend(constraint["variable"])
            # remove queryable constraints duplicates to make the assertion works
            self.assertSetEqual(
                set(variable_constraints), set(queryable.__origin__.__args__)
            )

        # reset mock
        mock_requests_get.reset_mock()

        # with additional param
        queryables = search_plugin.discover_queryables(
            collection="ERA5_SL_MONTHLY",
            **{"ecmwf:variable": "a"},
        )
        self.assertIsNotNone(queryables)

        self.assertEqual(10, len(queryables))
        # default properties called in function arguments are added and must be default values of the queryables
        queryable = queryables.get("ecmwf:variable")
        if queryable is not None:
            self.assertEqual("a", queryable.__metadata__[0].get_default())
            self.assertFalse(queryable.__metadata__[0].is_required())


class TestSearchPluginCopMarineSearch(BaseSearchPluginTest):
    def setUp(self):
        super(TestSearchPluginCopMarineSearch, self).setUp()
        self.provider = "cop_marine"
        self.product_data = {
            "id": "PRODUCT_A",
            "type": "Collection",
            "stac_version": "1.0.0",
            "stac_extensions": [
                "https://stac-extensions.github.io/scientific/v1.0.0/schema.json"
            ],
            "title": "Product A",
            "description": "A nice description",
            "license": "other",
            "providers": [
                {"name": "CLS (France)", "roles": ["producer"]},
                {
                    "name": "Copernicus Marine Service",
                    "roles": ["host", "processor"],
                    "url": "https://marine.copernicus.eu",
                },
            ],
            "keywords": [
                "oceanographic-geographical-features",
                "satellite-observation",
                "level-3",
            ],
            "links": [
                {
                    "rel": "root",
                    "href": "../catalog.stac.json",
                    "title": "Copernicus Marine Data Store",
                    "type": "application/json",
                },
                {
                    "rel": "parent",
                    "href": "../catalog.stac.json",
                    "title": "Copernicus Marine Data Store",
                    "type": "application/json",
                },
                {
                    "rel": "item",
                    "href": "dataset-number-one/dataset.stac.json",
                    "title": "dataset-number-one",
                    "type": "application/json",
                },
                {
                    "rel": "item",
                    "href": "dataset-number-two/dataset.stac.json",
                    "title": "dataset-number-two",
                    "type": "application/json",
                },
                {
                    "rel": "license",
                    "href": "https://marine.copernicus.eu/user-corner/service-commitments-and-licence",
                    "title": "Copernicus Marine Service Commitments and Licence",
                    "type": "text/html",
                },
            ],
            "extent": {
                "temporal": {
                    "interval": [
                        ["1970-01-01T00:00:00.000000Z", "1970-01-01T00:00:00.000000Z"]
                    ]
                },
                "spatial": {"bbox": [[0, 0, 0, 0]]},
            },
            "assets": {
                "thumbnail": {
                    "href": "https://catalogue.marine.copernicus.eu/documents/IMG/WAVE_GLO_PHY_SPC_L3_MY_014_006.png",
                    "type": "image/png",
                    "roles": ["thumbnail"],
                    "title": "GLOBAL OCEAN L3 SPECTRAL PARAMETERS FROM REPROCESSED SATELLITE MEASUREMENTS thumbnail",
                }
            },
            "properties": {
                "altId": "450bf368-2407-4c2c-8535-f215a4cda963",
                "created": "2021-04-23",
                "modifiedDate": "2021-04-23",
                "contacts": [
                    {
                        "name": "Jim Gabriel",
                        "organisationName": "Heaven Inc",
                        "responsiblePartyRole": "custodian",
                        "email": "jim.gabriel@heaven.com",
                    }
                ],
                "projection": "WGS84 / Simple Mercator (EPSG:41001)",
                "formats": ["NetCDF-4"],
                "featureTypes": ["Swath", "Trajectory"],
                "tempResolutions": ["Instantaneous"],
                "rank": 15015,
                "areas": [
                    "Global Ocean",
                ],
                "times": ["Past"],
                "sources": ["Satellite observations"],
                "colors": ["Blue Ocean"],
                "directives": [
                    "Water Framework Directive (WFD)",
                    "Maritime Spatial Planning (MSP)",
                ],
                "crs": "EPSG:3857",
                "isStaging": False,
                "admp_updated": "2023-11-07T16:54:54.688320Z",
            },
            "sci:doi": "10.48670/moi-00174",
        }
        self.dataset1_data = {
            "id": "dataset-number-one",
            "type": "Feature",
            "stac_version": "1.0.0",
            "stac_extensions": [
                "https://stac-extensions.github.io/datacube/v2.1.0/schema.json"
            ],
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [0, 0], [0, 0], [0, 0], [0, 0]]],
            },
            "bbox": [0, 0, 0, 0],
            "properties": {
                "title": "dataset-number-one",
                "datetime": "1970-01-01T00:00:00.000000Z",
            },
            "links": [
                {
                    "rel": "root",
                    "href": "../../catalog.stac.json",
                    "title": "Copernicus Marine Data Store",
                    "type": "application/json",
                },
                {
                    "rel": "parent",
                    "href": "../product.stac.json",
                    "title": "PRODUCT A",
                    "type": "application/json",
                },
                {
                    "rel": "collection",
                    "href": "../product.stac.json",
                    "title": "PRODUCT A",
                    "type": "application/json",
                },
            ],
            "assets": {
                "native": {
                    "id": "native",
                    "href": "https://s3.test.com/bucket1/native/PRODUCT_A/dataset-number-one",
                    "type": "application/x-netcdf",
                    "roles": ["data"],
                    "title": "Native dataset",
                    "description": "The original, non-ARCO version of this dataset, as published by the data provider.",
                }
            },
            "collection": "PRODUCT_A",
        }
        self.dataset2_data = deepcopy(self.dataset1_data)
        self.dataset2_data["id"] = "dataset-number-two"
        self.dataset2_data["properties"]["title"] = "dataset-number-two"
        self.dataset2_data["assets"]["native"][
            "href"
        ] = "https://s3.test.com/bucket1/native/PRODUCT_A/dataset-number-two"

        self.list_objects_response1 = {
            "Contents": [
                {
                    "Key": "native/PRODUCT_A/dataset-number-one/item_20200102_20200103_hdkIFE.KFNEDNF_20210101.nc"
                },
                {
                    "Key": "native/PRODUCT_A/dataset-number-one/item_20200104_20200105_hdkIFEKFNEDNF_20210101.nc"
                },
                {
                    "Key": "native/PRODUCT_A/dataset-number-one/item_20200302_20200303_hdkIFEKFNEDN_20210101.nc"
                },
            ]
        }
        self.list_objects_response2 = {
            "Contents": [
                {
                    "Key": "native/PRODUCT_A/dataset-number-two/item_20200102_20200103_fizncnqijei_20210101.nc"
                },
                {
                    "Key": "native/PRODUCT_A/dataset-number-two/item_20200204_20200205_niznjvnqkrf_20210101.nc"
                },
                {
                    "Key": "native/PRODUCT_A/dataset-number-two/item_20200302_20200303_fIZHVCOINine_20210101.nc"
                },
            ]
        }
        self.list_objects_response3 = {
            "Contents": [
                {
                    "Key": "native/PRODUCT_A/dataset-number-two/item_15325642_fizncnqijei.nc"
                },
                {
                    "Key": "native/PRODUCT_A/dataset-number-two/item_846282_niznjvnqkrf.nc"
                },
            ]
        }
        self.s3 = boto3.client(
            "s3",
            config=botocore.config.Config(
                # Configures to use subdomain/virtual calling format.
                s3={"addressing_style": "virtual"},
                signature_version=botocore.UNSIGNED,
            ),
        )

    @mock.patch("eodag.plugins.search.cop_marine.requests.get")
    def test_plugins_search_cop_marine_query_with_dates(self, mock_requests_get):
        mock_requests_get.return_value.json.side_effect = [
            self.product_data,
            self.dataset1_data,
            self.dataset2_data,
        ]
        search_plugin = self.get_search_plugin("PRODUCT_A", self.provider)

        with mock.patch("eodag.plugins.search.cop_marine._get_s3_client") as s3_stub:
            s3_stub.return_value = self.s3
            stubber = Stubber(self.s3)
            stubber.add_response(
                "list_objects",
                self.list_objects_response1,
                {"Bucket": "bucket1", "Prefix": "native/PRODUCT_A/dataset-number-one"},
            )
            stubber.add_response(
                "list_objects",
                self.list_objects_response2,
                {"Bucket": "bucket1", "Prefix": "native/PRODUCT_A/dataset-number-two"},
            )
            stubber.activate()
            result, num_total = search_plugin.query(
                collection="PRODUCT_A",
                start_datetime="2020-01-01T01:00:00Z",
                end_datetime="2020-02-01T01:00:00Z",
            )
            mock_requests_get.assert_has_calls(
                calls=[
                    call(
                        "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/product.stac.json"
                    ),
                    call().json(),
                    call(
                        "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/dataset-number-one/dataset.stac.json"
                    ),
                    call().json(),
                    call(
                        "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/dataset-number-two/dataset.stac.json"
                    ),
                    call().json(),
                ]
            )
            self.assertEqual(3, num_total)
            products_dataset1 = [
                product
                for product in result
                if product.properties["dataset"] == "dataset-number-one"
            ]
            products_dataset2 = [
                product
                for product in result
                if product.properties["dataset"] == "dataset-number-two"
            ]
            self.assertEqual(2, len(products_dataset1))
            self.assertEqual(1, len(products_dataset2))
            self.assertEqual(
                "2020-01-02T00:00:00Z",
                products_dataset2[0].properties["start_datetime"],
            )
            self.assertEqual(
                "2020-01-03T00:00:00Z",
                products_dataset2[0].properties["end_datetime"],
            )

    @mock.patch("eodag.plugins.search.cop_marine.requests.get")
    def test_plugins_search_cop_marine_query_no_dates_in_id(self, mock_requests_get):
        mock_requests_get.return_value.json.side_effect = [
            self.product_data,
            self.dataset1_data,
            self.dataset2_data,
        ]

        search_plugin = self.get_search_plugin("PRODUCT_A", self.provider)
        search_plugin.config.products = {
            "PRODUCT_A": {
                "_collection": "PRODUCT_A",
                "code_mapping": {"param": "platform", "index": 1},
            }
        }

        with mock.patch("eodag.plugins.search.cop_marine._get_s3_client") as s3_stub:
            s3_stub.return_value = self.s3
            stubber = Stubber(self.s3)
            stubber.add_response(
                "list_objects",
                self.list_objects_response1,
                {"Bucket": "bucket1", "Prefix": "native/PRODUCT_A/dataset-number-one"},
            )
            stubber.add_response(
                "list_objects",
                self.list_objects_response3,
                {"Bucket": "bucket1", "Prefix": "native/PRODUCT_A/dataset-number-two"},
            )
            stubber.add_response(
                "list_objects",
                {},
                {
                    "Bucket": "bucket1",
                    "Prefix": "native/PRODUCT_A/dataset-number-two",
                    "Marker": "native/PRODUCT_A/dataset-number-two/item_846282_niznjvnqkrf.nc",
                },
            )
            stubber.activate()
            result, num_total = search_plugin.query(
                collection="PRODUCT_A",
                start_datetime="1969-01-01T01:00:00Z",
                end_datetime="1970-02-01T01:00:00Z",
            )
            mock_requests_get.assert_has_calls(
                calls=[
                    call(
                        "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/product.stac.json"
                    ),
                    call().json(),
                    call(
                        "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/dataset-number-one/dataset.stac.json"
                    ),
                    call().json(),
                    call(
                        "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/dataset-number-two/dataset.stac.json"
                    ),
                    call().json(),
                ]
            )
            self.assertEqual(2, num_total)
            products_dataset2 = [
                product
                for product in result
                if product.properties["dataset"] == "dataset-number-two"
            ]
            self.assertEqual(2, len(products_dataset2))
            self.assertEqual(
                "1970-01-01T00:00:00.000000Z",
                products_dataset2[0].properties["start_datetime"],
            )
            self.assertEqual(
                "1970-01-01T00:00:00.000000Z",
                products_dataset2[0].properties["end_datetime"],
            )
            self.assertEqual(
                "15325642",
                products_dataset2[0].properties["platform"],
            )

    @mock.patch("eodag.plugins.search.cop_marine.requests.get")
    def test_plugins_search_cop_marine_query_with_id(self, mock_requests_get):
        mock_requests_get.return_value.json.side_effect = [
            self.product_data,
            self.dataset1_data,
            self.dataset2_data,
            self.product_data,
            self.dataset1_data,
            self.dataset2_data,
        ]

        search_plugin = self.get_search_plugin("PRODUCT_A", self.provider)

        with mock.patch("eodag.plugins.search.cop_marine._get_s3_client") as s3_stub:
            s3_stub.return_value = self.s3
            stubber = Stubber(self.s3)
            for i in [
                0,
                1,
            ]:  # add responses twice because 2 search requests will be executed
                stubber.add_response(
                    "list_objects",
                    self.list_objects_response1,
                    {
                        "Bucket": "bucket1",
                        "Prefix": "native/PRODUCT_A/dataset-number-one",
                    },
                )
                stubber.add_response(
                    "list_objects",
                    {},
                    {
                        "Bucket": "bucket1",
                        "Marker": "native/PRODUCT_A/dataset-number-one/item_20200302_20200303_hdkIFEKFNEDN_20210101.nc",
                        "Prefix": "native/PRODUCT_A/dataset-number-one",
                    },
                )
                stubber.add_response(
                    "list_objects",
                    self.list_objects_response2,
                    {
                        "Bucket": "bucket1",
                        "Prefix": "native/PRODUCT_A/dataset-number-two",
                    },
                )
            stubber.activate()
            result, num_total = search_plugin.query(
                collection="PRODUCT_A",
                id="item_20200204_20200205_niznjvnqkrf_20210101",
            )
            self.assertEqual(1, num_total)
            self.assertEqual(
                "item_20200204_20200205_niznjvnqkrf_20210101",
                result[0].properties["id"],
            )
            result, num_total = search_plugin.query(
                collection="PRODUCT_A",
                id="item_20200102_20200103_hdkIFE.KFNEDNF_20210101",
            )
            self.assertEqual(1, num_total)
            self.assertEqual(
                "item_20200102_20200103_hdkIFE.KFNEDNF_20210101",
                result[0].properties["id"],
            )

    @mock.patch("eodag.plugins.search.cop_marine.requests.get")
    def test_plugins_search_cop_marine_search_by_id_no_dates_in_id(
        self, mock_requests_get
    ):
        mock_requests_get.return_value.json.side_effect = [
            self.product_data,
            self.dataset1_data,
            self.dataset2_data,
        ]

        search_plugin = self.get_search_plugin("PRODUCT_A", self.provider)
        search_plugin.config.products = {
            "PRODUCT_A": {
                "_collection": "PRODUCT_A",
                "code_mapping": {"param": "platform", "index": 1},
            }
        }

        with mock.patch("eodag.plugins.search.cop_marine._get_s3_client") as s3_stub:
            s3_stub.return_value = self.s3
            stubber = Stubber(self.s3)
            stubber.add_response(
                "list_objects",
                self.list_objects_response1,
                {"Bucket": "bucket1", "Prefix": "native/PRODUCT_A/dataset-number-one"},
            )
            stubber.add_response(
                "list_objects",
                {},
                {
                    "Bucket": "bucket1",
                    "Marker": "native/PRODUCT_A/dataset-number-one/item_20200302_20200303_hdkIFEKFNEDN_20210101.nc",
                    "Prefix": "native/PRODUCT_A/dataset-number-one",
                },
            )
            stubber.add_response(
                "list_objects",
                self.list_objects_response3,
                {"Bucket": "bucket1", "Prefix": "native/PRODUCT_A/dataset-number-two"},
            )
            stubber.add_response(
                "list_objects",
                {},
                {
                    "Bucket": "bucket1",
                    "Prefix": "native/PRODUCT_A/dataset-number-two",
                    "Marker": "native/PRODUCT_A/dataset-number-two/item_846282_niznjvnqkrf.nc",
                },
            )
            stubber.activate()
            result, num_total = search_plugin.query(
                collection="PRODUCT_A", id="item_846282_niznjvnqkrf"
            )
            mock_requests_get.assert_has_calls(
                calls=[
                    call(
                        "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/product.stac.json"
                    ),
                    call().json(),
                    call(
                        "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/dataset-number-one/dataset.stac.json"
                    ),
                    call().json(),
                    call(
                        "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/dataset-number-two/dataset.stac.json"
                    ),
                    call().json(),
                ]
            )
            self.assertEqual(1, num_total)
            self.assertEqual("item_846282_niznjvnqkrf", result[0].properties["id"])

    @mock.patch("eodag.plugins.search.cop_marine.requests.get")
    def test_plugins_search_cop_marine_query_with_not_intersected_geom(
        self, mock_requests_get
    ):
        """A query with a geometry that does not intersect the dataset geometries must return no result"""
        mock_requests_get.return_value.json.side_effect = [
            self.product_data,
            self.dataset1_data,
            self.dataset2_data,
        ]

        geometry = get_geometry_from_various(geometry=[10, 20, 30, 40])

        # check that "geometry" does not intersect the dataset geometries
        self.assertFalse(
            get_geometry_from_various(
                geometry=self.dataset1_data["geometry"]
            ).intersects(geometry)
        )
        self.assertFalse(
            get_geometry_from_various(
                geometry=self.dataset2_data["geometry"]
            ).intersects(geometry)
        )

        search_plugin = self.get_search_plugin("PRODUCT_A", self.provider)

        result, num_total = search_plugin.query(
            collection="PRODUCT_A",
            geometry=geometry,
        )

        mock_requests_get.assert_has_calls(
            calls=[
                call(
                    "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/product.stac.json"
                ),
                call().json(),
                call(
                    "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/dataset-number-one/dataset.stac.json"
                ),
                call().json(),
                call(
                    "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/dataset-number-two/dataset.stac.json"
                ),
                call().json(),
            ]
        )

        # check that no result has been found
        self.assertListEqual(result, [])
        self.assertEqual(num_total, 0)

    @mock.patch("eodag.plugins.search.cop_marine.requests.get")
    def test_plugins_search_cop_marine_with_errors(self, mock_requests_get):
        exc = requests.RequestException()
        exc.errno = 404
        mock_requests_get.side_effect = exc
        search_plugin = self.get_search_plugin("PRODUCT_A", self.provider)
        with self.assertRaises(UnsupportedCollection):
            search_plugin.query(
                collection="PRODUCT_AX",
                id="item_20200204_20200205_niznjvnqkrf_20210101",
            )
        mock_requests_get.reset()
        mock_requests_get.side_effect = requests.exceptions.ConnectionError()
        with self.assertRaises(RequestError):
            search_plugin.query(
                collection="PRODUCT_A",
                id="item_20200204_20200205_niznjvnqkrf_20210101",
            )

    def test_plugins_search_postjsonsearch_discover_queryables(self):
        """Queryables discovery with a CopMarineSearch must return static queryables with an adaptative default value"""  # noqa
        search_plugin = self.get_search_plugin("PRODUCT_A", self.provider)
        kwargs = {"collection": "PRODUCT_A", "provider": self.provider}

        queryables = search_plugin.discover_queryables(**kwargs)

        self.assertIsNotNone(queryables)
        # check that the queryables are the ones expected (they are always the same ones)
        self.assertListEqual(
            list(queryables.keys()), ["collection", "id", "start", "end", "geom"]
        )
        # check that each queryable does not have a default value except the one set in the kwargs
        for key, queryable in queryables.items():
            if key in kwargs:
                self.assertIsNotNone(queryable.__metadata__[0].get_default())
            else:
                self.assertIsNone(queryable.__metadata__[0].get_default())


class TestSearchPluginWekeoSearch(BaseSearchPluginTest):
    def setUp(self):
        super(TestSearchPluginWekeoSearch, self).setUp()
        # One of the providers that has a WekeoSearch Search plugin
        provider = "wekeo_main"
        self.wekeomain_search_plugin = self.get_search_plugin(self.collection, provider)
        self.wekeomain_auth_plugin = self.get_auth_plugin(self.wekeomain_search_plugin)

    def test_plugins_search_wekeosearch_init_wekeomain(self):
        """Check that the WekeoSearch plugin is initialized correctly for wekeo_main provider"""

        default_providers_config = load_default_config()
        default_config = default_providers_config["wekeo_main"]
        # "orderLink" in S1_SAR_GRD but not in provider conf or S1_SAR_SLC conf
        self.assertNotIn("orderLink", default_config.search.metadata_mapping)
        self.assertIn(
            "orderLink", default_config.products["S1_SAR_GRD"]["metadata_mapping"]
        )
        self.assertNotIn("metadata_mapping", default_config.products["S1_SAR_SLC"])

        # metadata_mapping_from_product: from S1_SAR_GRD to S1_SAR_SLC
        self.assertEqual(
            default_config.products["S1_SAR_SLC"]["metadata_mapping_from_product"],
            "S1_SAR_GRD",
        )

        # check initialized plugin configuration
        self.assertDictEqual(
            self.wekeomain_search_plugin.config.products["S1_SAR_GRD"][
                "metadata_mapping"
            ],
            self.wekeomain_search_plugin.config.products["S1_SAR_SLC"][
                "metadata_mapping"
            ],
        )

        # CLMS_GLO_LAI_333M has both metadata_mapping_from_product and metadata_mapping
        # "metadata_mapping" must override "metadata_mapping_from_product"
        self.assertIn(
            "orderLink",
            default_config.products["CLMS_GLO_LAI_333M"]["metadata_mapping"],
        )
        self.assertIn(
            "orderLink",
            default_config.products["CLMS_GLO_FCOVER_333M"]["metadata_mapping"],
        )
        self.assertEqual(
            default_config.products["CLMS_GLO_LAI_333M"][
                "metadata_mapping_from_product"
            ],
            "CLMS_GLO_FCOVER_333M",
        )
        self.assertNotEqual(
            self.wekeomain_search_plugin.config.products["CLMS_GLO_LAI_333M"][
                "metadata_mapping"
            ]["orderLink"],
            self.wekeomain_search_plugin.config.products["CLMS_GLO_FCOVER_333M"][
                "metadata_mapping"
            ]["orderLink"],
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.normalize_results",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.StacSearch.build_query_string", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.PostJsonSearch.build_query_string", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.WekeoSearch._request",
        autospec=True,
    )
    def test_plugins_search_wekeosearch_search_wekeomain(
        self,
        mock__request,
        mock_build_qs_postjsonsearch,
        mock_build_qs_stacsearch,
        mock_normalize_results,
    ):
        """A query with a WekeoSearch provider (here wekeo_main) must use build_query_string() of PostJsonSearch"""  # noqa
        mock_build_qs_postjsonsearch.return_value = (
            mock_build_qs_stacsearch.return_value
        ) = (
            {
                "dataset_id": "EO:ESA:DAT:SENTINEL-2",
                "startDate": "2020-08-08",
                "completionDate": "2020-08-16",
                "bbox": [137.772897, 13.134202, 153.749135, 23.885986],
                "processing:level": "S2MSI1C",
            },
            mock.ANY,
        )

        self.wekeomain_search_plugin.query(
            prep=PreparedSearch(
                page=1,
                items_per_page=2,
                auth_plugin=self.wekeomain_auth_plugin,
            ),
            **self.search_criteria_s2_msi_l1c,
        )

        mock__request.assert_called()
        mock_build_qs_postjsonsearch.assert_called()
        mock_build_qs_stacsearch.assert_not_called()

    def test_plugins_search_wekeosearch_search_wekeomain_ko(self):
        """A query with a parameter which is not queryable must
        raise an error if the provider does not allow it"""  # noqa
        # with raised error parameter set to True in the global config of the provider
        provider_search_plugin_config = copy_deepcopy(
            self.wekeomain_search_plugin.config
        )
        self.wekeomain_search_plugin.config.discover_metadata = {
            "raise_mtd_discovery_error": True
        }

        with self.assertRaises(ValidationError) as context:
            self.wekeomain_search_plugin.query(
                prep=PreparedSearch(
                    page=1,
                    items_per_page=2,
                    auth_plugin=self.wekeomain_auth_plugin,
                ),
                **{**self.search_criteria_s2_msi_l1c, **{"foo": "bar"}},
            )
        self.assertEqual(
            "Search parameters which are not queryable are disallowed for this collection on this provider: "
            f"please remove 'foo' from your search parameters. Collection: "
            f"{self.search_criteria_s2_msi_l1c['collection']} / provider : {self.wekeomain_search_plugin.provider}",
            context.exception.message,
        )

        # with raised error parameter set to True in the config of the collection of the provider

        # first, update this parameter to False in the global config
        # to show that it is going to be taken over by this new config
        self.wekeomain_search_plugin.config.discover_metadata[
            "raise_mtd_discovery_error"
        ] = False

        self.wekeomain_search_plugin.config.products[
            self.search_criteria_s2_msi_l1c["collection"]
        ]["discover_metadata"] = {"raise_mtd_discovery_error": True}

        with self.assertRaises(ValidationError) as context:
            self.wekeomain_search_plugin.query(
                prep=PreparedSearch(
                    page=1,
                    items_per_page=2,
                    auth_plugin=self.wekeomain_auth_plugin,
                ),
                **{**self.search_criteria_s2_msi_l1c, **{"foo": "bar"}},
            )
        self.assertEqual(
            "Search parameters which are not queryable are disallowed for this collection on this provider: "
            f"please remove 'foo' from your search parameters. Collection: "
            f"{self.search_criteria_s2_msi_l1c['collection']} / provider : {self.wekeomain_search_plugin.provider}",
            context.exception.message,
        )

        # restore the original config
        self.wekeomain_search_plugin.config = provider_search_plugin_config

    @mock.patch(
        "eodag.plugins.search.qssearch.PostJsonSearch.discover_queryables",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.StacSearch.discover_queryables", autospec=True
    )
    def test_plugins_search_postjsonsearch_discover_queryables(
        self,
        mock_stacsearch_discover_queryables,
        mock_postjsonsearch_discover_queryables,
    ):
        """Queryables discovery with a PostJsonSearchWithStacQueryables (here wekeo_main) must use discover_queryables() of StacSearch"""  # noqa
        self.wekeomain_search_plugin.discover_queryables(collection=self.collection)
        mock_stacsearch_discover_queryables.assert_called()
        mock_postjsonsearch_discover_queryables.assert_not_called()


class TestSearchPluginDedtLumi(BaseSearchPluginTest):
    def setUp(self):
        super(TestSearchPluginDedtLumi, self).setUp()
        self.provider = "dedt_lumi"
        self.search_plugin = self.get_search_plugin(provider=self.provider)
        self.collection = "DT_CLIMATE_ADAPTATION"

    def test_plugins_apis_dedt_lumi_query_feature(self):
        """Test the proper handling of geom into ecmwf:feature"""

        # Search using geometry
        _expected_feature = {
            "shape": [[43.0, 1.0], [44.0, 1.0], [44.0, 2.0], [43.0, 2.0], [43.0, 1.0]],
            "type": "polygon",
        }
        results, _ = self.search_plugin.query(
            collection=self.collection,
            start="2021-01-01",
            geometry={"lonmin": 1, "latmin": 43, "lonmax": 2, "latmax": 44},
        )
        eoproduct = results[0]

        self.assertDictEqual(_expected_feature, eoproduct.properties["ecmwf:feature"])

        # Unsupported multi-polygon
        with self.assertRaises(ValidationError):
            self.search_plugin.query(
                collection=self.collection,
                start="2021-01-01",
                geometry="""MULTIPOLYGON (
                    ((1.23 43.42, 1.23 43.76, 1.68 43.76, 1.68 43.42, 1.23 43.42)),
                    ((2.23 43.42, 2.23 43.76, 3.68 43.76, 3.68 43.42, 2.23 43.42))
                )""",
            )
