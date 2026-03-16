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
from copy import deepcopy as copy_deepcopy
from unittest import mock

import pytest
import requests
import responses
from jsonpath_ng import JSONPath, parse

from eodag.api.product import EOProduct
from eodag.plugins.search import PreparedSearch, QueryStringSearch
from eodag.utils import USER_AGENT, cached_parse
from eodag.utils.exceptions import (
    MisconfiguredError,
    PluginImplementationError,
    QuotaExceededError,
    TimeOutError,
    ValidationError,
)
from tests.units.search_plugins.base import BaseSearchPluginTest
from tests.units.search_plugins.mock_response import MockResponse


class TestSearchPluginQueryStringSearch(BaseSearchPluginTest):
    def setUp(self):
        super(TestSearchPluginQueryStringSearch, self).setUp()
        # One of the providers that has a QueryStringSearch Search plugin
        provider = "sara"
        self.sara_search_plugin = self.get_search_plugin(self.collection, provider)
        self.sara_auth_plugin = self.get_auth_plugin(self.sara_search_plugin)

    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.QueryStringSearch._request",
        autospec=True,
    )
    def test_plugins_search_querystringsearch_count_and_search_cop_dataspace(
        self, mock__request
    ):
        self.maxDiff = None
        """A query with a QueryStringSearch (sara here) must return tuple with a list of EOProduct and a number of available products"""  # noqa
        with open(self.provider_resp_dir / "sara_search.json") as f:
            sara_resp_search = json.load(f)
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.side_effect = [
            sara_resp_search,
        ]
        products = self.sara_search_plugin.query(
            prep=PreparedSearch(
                page=1,
                limit=2,
                auth_plugin=self.sara_auth_plugin,
            ),
            **self.search_criteria_s2_msi_l1c,
        )

        # Specific expected results
        sara_url_search = (
            "https://copernicus.nci.org.au/sara.server/1.0/api/collections/S2/search.json?startDate=2020-08-08&"
            "completionDate=2020-08-16&geometry=POLYGON ((137.7729 13.1342, 137.7729 23.8860, 153.7491 23.8860, "
            "153.7491 13.1342, 137.7729 13.1342))&productType=S2MSIL1C&instrument=MSI&processingLevel=L1C&"
            "sortParam=startDate&sortOrder=asc&maxRecords=2&page=1"
        )
        sara_products_count = 47
        number_of_products = 2

        mock__request.assert_called_once()
        self.assertEqual(mock__request.call_args_list[-1][0][1].url, sara_url_search)

        self.assertEqual(products.number_matched, sara_products_count)
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
    def test_plugins_search_querystringsearch_no_count_and_search_cop_dataspace(
        self, mock__request, mock_count_hits
    ):
        """A query with a QueryStringSearch (here sara) without a count"""
        with open(self.provider_resp_dir / "sara_search.json") as f:
            sara_resp_search = json.load(f)
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.return_value = sara_resp_search
        products = self.sara_search_plugin.query(
            prep=PreparedSearch(
                count=False,
                page=1,
                limit=2,
                auth_plugin=self.sara_auth_plugin,
            ),
            **self.search_criteria_s2_msi_l1c,
        )

        # Specific expected results
        sara_url_search = (
            "https://copernicus.nci.org.au/sara.server/1.0/api/collections/S2/search.json?startDate=2020-08-08&"
            "completionDate=2020-08-16&geometry=POLYGON ((137.7729 13.1342, 137.7729 23.8860, 153.7491 23.8860, "
            "153.7491 13.1342, 137.7729 13.1342))&productType=S2MSIL1C&instrument=MSI&processingLevel=L1C&"
            "sortParam=startDate&sortOrder=asc&maxRecords=2&page=1"
        )
        number_of_products = 2

        mock_count_hits.assert_not_called()
        mock__request.assert_called_once()
        self.assertEqual(mock__request.call_args_list[-1][0][1].url, sara_url_search)

        self.assertIsNone(products.number_matched)
        self.assertEqual(len(products.data), number_of_products)
        self.assertIsInstance(products.data[0], EOProduct)

    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.QueryStringSearch.normalize_results",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.QueryStringSearch._request",
        autospec=True,
    )
    def test_plugins_search_querystringsearch_search_cloudcover_cop_dataspace(
        self, mock__request, mock_normalize_results
    ):
        """A query with a QueryStringSearch (here sara) must use cloudCover filtering when configured"""

        self.sara_search_plugin.query(collection="S2_MSI_L1C", **{"eo:cloud_cover": 50})
        mock__request.assert_called()
        self.assertIn("cloudCover", mock__request.call_args_list[-1][0][1].url)

    def test_plugins_search_querystringsearch_search_cop_dataspace_ko(self):
        """A query with a parameter which is not queryable must
        raise an error if the provider does not allow it"""  # noqa
        # with raised error parameter set to True in the global config of the provider
        provider_search_plugin_config = copy_deepcopy(self.sara_search_plugin.config)
        self.sara_search_plugin.config.discover_metadata[
            "raise_mtd_discovery_error"
        ] = True

        with self.assertRaises(ValidationError) as context:
            self.sara_search_plugin.query(
                prep=PreparedSearch(
                    page=1,
                    limit=2,
                    auth_plugin=self.sara_auth_plugin,
                ),
                **{**self.search_criteria_s2_msi_l1c, **{"foo": "bar"}},
            )
        self.assertEqual(
            "Search parameters which are not queryable are disallowed for this collection on this provider: "
            f"please remove 'foo' from your search parameters. Collection: "
            f"{self.search_criteria_s2_msi_l1c['collection']} / provider : {self.sara_search_plugin.provider}",
            context.exception.message,
        )

        # with raised error parameter set to True in the config of the collection of the provider

        # first, update this parameter to False in the global config
        # to show that it is going to be taken over by this new config
        self.sara_search_plugin.config.discover_metadata[
            "raise_mtd_discovery_error"
        ] = False

        self.sara_search_plugin.config.products[
            self.search_criteria_s2_msi_l1c["collection"]
        ]["discover_metadata"] = {"raise_mtd_discovery_error": True}

        with self.assertRaises(ValidationError) as context:
            self.sara_search_plugin.query(
                prep=PreparedSearch(
                    page=1,
                    limit=2,
                    auth_plugin=self.sara_auth_plugin,
                ),
                **{**self.search_criteria_s2_msi_l1c, **{"foo": "bar"}},
            )
        self.assertEqual(
            "Search parameters which are not queryable are disallowed for this collection on this provider: "
            f"please remove 'foo' from your search parameters. Collection: "
            f"{self.search_criteria_s2_msi_l1c['collection']} / provider : {self.sara_search_plugin.provider}",
            context.exception.message,
        )

        # restore the original config
        self.sara_search_plugin.config = provider_search_plugin_config

    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.requests.Session.get",
        autospec=True,
    )
    def test_plugins_search_querystringsearch_search_quota_exceeded(
        self, mock__request
    ):
        """A query with a QueryStringSearch must handle a 429 response returned by the provider"""
        response = MockResponse({}, status_code=429)
        mock__request.side_effect = requests.exceptions.HTTPError(response=response)
        prep = PreparedSearch(collection="S2_MSI_L1C", count=False)
        with self.assertRaises(QuotaExceededError):
            self.sara_search_plugin.query(
                prep=prep, collection="S2_MSI_L1C", **{"eo:cloud_cover": 50}
            )

    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.QueryStringSearch._request",
        autospec=True,
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

    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.QueryStringSearch._request",
        autospec=True,
    )
    def test_plugins_search_querystringsearch_discover_collections_unparsable_metadata_mapping(
        self, mock__request
    ):
        """QueryStringSearch.discover_collections must merge unparsable metadata_mapping with default"""
        provider = "earth_search"
        search_plugin = self.get_search_plugin(self.collection, provider)

        # backup and set unparsable_properties with a metadata_mapping override
        discover_collections_conf = copy_deepcopy(
            search_plugin.config.discover_collections
        )
        from eodag.api.product.metadata_mapping import (
            mtd_cfg_as_conversion_and_querypath,
        )

        search_plugin.config.discover_collections[
            "generic_collection_unparsable_properties"
        ] = {
            "metadata_mapping": mtd_cfg_as_conversion_and_querypath(
                {"eo:cloud_cover": "$.null"}
            )
        }

        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.return_value = {
            "collections": [
                {
                    "id": "foo_collection",
                    "title": "The FOO collection",
                },
            ]
        }
        conf_update_dict = search_plugin.discover_collections()
        providers_config = conf_update_dict["providers_config"]["foo_collection"]

        # unparsable metadata_mapping should be merged with default metadata_mapping
        self.assertIn("metadata_mapping", providers_config)
        merged_mapping = providers_config["metadata_mapping"]

        # should contain the override from unparsable_properties
        self.assertIn("eo:cloud_cover", merged_mapping)

        # should also contain keys from the default metadata_mapping
        self.assertIn("id", merged_mapping)
        self.assertIn("geometry", merged_mapping)
        self.assertIn("start_datetime", merged_mapping)

        # restore configuration
        search_plugin.config.discover_collections = discover_collections_conf

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
                    "Could not parse discovered collections response" in m
                    for m in log.output
                )

        search_plugin.config.discover_collections = discover_collections_conf

    @responses.activate
    def test_plugins_search_querystringsearch_discover_collections_post(self):
        """QueryStringSearch.discover_collections must be able to query using POST requests"""
        # One of the providers that has a QueryStringSearch.discover_collections configured with POST requests
        provider = "geodes"
        search_plugin = self.get_search_plugin(self.collection, provider)

        responses.add(
            responses.GET,
            "https://geodes-portal.cnes.fr/api/stac/collections",
            body=json.dumps(
                {
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
            ),
            status=200,
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

    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.requests.Session.get",
        autospec=True,
    )
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
        "eodag.plugins.search.qssearch.querystringsearch.requests.Session.get",
        autospec=True,
    )
    def test_plugins_search_querystringsearch_discover_collections_with_id_to_rename(
        self, mock__request
    ):
        """QueryStringSearch.discover_collections must handle collections that have to be renamed"""
        # One of the providers that has discover_collections() configured with QueryStringSearch
        provider = "wekeo_cmems"
        search_plugin = self.get_search_plugin(provider=provider)
        # change configuration for this test to rename the collection id
        search_plugin.config.discover_collections[
            "single_collection_parsable_metadata"
        ]["id"] = (None, cached_parse("$.metadata.understandable_id"))

        # case where the name to replace the current id exists in the metadata
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.side_effect = [
            {
                "features": [
                    {
                        "dataset_id": "1a2b3c4d",
                        "metadata": {"title": "The FOO collection"},
                    }
                ]
            },
            {
                "dataset_id": "1a2b3c4d",
                "metadata": {
                    "title": "The FOO collection",
                    "understandable_id": "foo_collection",
                },
            },
        ]

        with self.assertLogs(level="DEBUG") as cm:
            conf_update_dict = search_plugin.discover_collections()
            self.assertIn(
                "Rename 1a2b3c4d collection to foo_collection", str(cm.output)
            )

        self.assertIn("foo_collection", conf_update_dict["providers_config"])
        self.assertIn("foo_collection", conf_update_dict["collections_config"])
        self.assertNotIn("1a2b3c4d", conf_update_dict["providers_config"])
        self.assertNotIn("1a2b3c4d", conf_update_dict["collections_config"])
        self.assertEqual(
            conf_update_dict["providers_config"]["foo_collection"]["collection"],
            "1a2b3c4d",
        )
        self.assertNotIn("id", conf_update_dict["collections_config"]["foo_collection"])

        # case where the name to replace the current id does not exist in the metadata
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.side_effect = [
            {
                "features": [
                    {
                        "dataset_id": "5e6f7g8h",
                        "metadata": {"title": "The BAR collection"},
                    }
                ]
            },
            {
                "dataset_id": "5e6f7g8h",
                "metadata": {"title": "The BAR collection"},
            },
        ]

        conf_update_dict = search_plugin.discover_collections()

        self.assertNotIn("5e6f7g8h", conf_update_dict["providers_config"])
        self.assertNotIn("5e6f7g8h", conf_update_dict["collections_config"])

        # restore configuration
        del search_plugin.config.discover_collections[
            "single_collection_parsable_metadata"
        ]["id"]

    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.QueryStringSearch._request",
        autospec=True,
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
        ]

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
        "eodag.plugins.search.qssearch.querystringsearch.QueryStringSearch._request",
        autospec=True,
    )
    def test_plugins_search_querystringsearch_distinct_collection_mtd_mapping(
        self, mock__request
    ):
        """The metadata mapping for QueryStringSearch should not mix specific collections metadata-mapping"""
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
        search_plugin = self.get_search_plugin(self.collection, "sara")

        # ensure metadata_mapping exists for S1_SAR_GRD and S1_SAR_SLC
        search_plugin.config.products["S1_SAR_GRD"].setdefault("metadata_mapping", {})
        search_plugin.config.products["S1_SAR_SLC"].setdefault("metadata_mapping", {})

        # update metadata_mapping only for S1_SAR_GRD
        search_plugin.config.products["S1_SAR_GRD"]["metadata_mapping"]["bar"] = (
            None,
            "baz",
        )
        products = search_plugin.query(
            collection="S1_SAR_GRD",
            auth=None,
        )
        self.assertIn("bar", products.data[0].properties)
        self.assertEqual(products.data[0].properties["bar"], "baz")

        # search with another collection
        self.assertNotIn(
            "bar", search_plugin.config.products["S1_SAR_SLC"]["metadata_mapping"]
        )
        products = search_plugin.query(
            collection="S1_SAR_SLC",
            auth=None,
        )
        self.assertNotIn("bar", products.data[0].properties)

    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.requests.Session.get",
        autospec=True,
        side_effect=requests.exceptions.Timeout(),
    )
    def test_plugins_search_querystringseach_timeout(self, mock__request):
        search_plugin = self.get_search_plugin(self.collection, "sara")
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
