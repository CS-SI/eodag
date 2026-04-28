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
import re
import ssl
from pathlib import Path
from unittest import mock

from requests import RequestException

from eodag.api.product import EOProduct
from eodag.api.provider import Provider
from eodag.plugins.search import PreparedSearch
from eodag.utils import HTTP_REQ_TIMEOUT, USER_AGENT, cached_parse, cached_yaml_load_all
from tests.units.search_plugins.base import BaseSearchPluginTest
from tests.utils import TEST_RESOURCES_PATH


class TestSearchPluginODataV4Search(BaseSearchPluginTest):
    def setUp(self):
        super(TestSearchPluginODataV4Search, self).setUp()

        # manually add conf as this provider is not supported any more
        onda_config = cached_yaml_load_all(Path(TEST_RESOURCES_PATH) / "onda_conf.yml")[
            0
        ]
        self.plugins_manager.providers["onda"] = Provider(onda_config)
        self.plugins_manager.rebuild()

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

    def _test_plugins_search_odatav4search_normalize_results_onda(self):
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

    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.requests.get", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.QueryStringSearch._request",
        autospec=True,
    )
    def _test_plugins_search_odatav4search_count_and_search_onda(
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
        products = self.onda_search_plugin.query(
            prep=PreparedSearch(
                page=1,
                limit=2,
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

        self.assertEqual(products.number_matched, self.onda_products_count)
        self.assertEqual(len(products.data), number_of_products)
        self.assertIsInstance(products.data[0], EOProduct)
        # products count non extracted from search results as count endpoint is specified
        self.assertFalse(hasattr(self.onda_search_plugin, "total_items_nb"))

    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.get_ssl_context", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.Request", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.urlopen", autospec=True
    )
    @mock.patch("eodag.plugins.search.qssearch.querystringsearch.cast", autospec=True)
    def _test_plugins_search_odatav4search_with_ssl_context(
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
                limit=2,
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

    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.requests.get", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def _test_plugins_search_odatav4search_count_and_search_onda_per_product_metadata_query(
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
        products = self.onda_search_plugin.query(
            prep=PreparedSearch(
                page=1,
                limit=2,
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
            products.data[1].properties["uid"],
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

        self.assertEqual(products.number_matched, self.onda_products_count)
        self.assertEqual(len(products.data), number_of_products)
        self.assertIsInstance(products.data[0], EOProduct)
        # products count non extracted from search results as count endpoint is specified
        self.assertFalse(hasattr(self.onda_search_plugin, "total_items_nb"))

    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.requests.get", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.QueryStringSearch._request",
        autospec=True,
    )
    def _test_plugins_search_odatav4search_count_and_search_onda_per_product_metadata_query_request_error(
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
            self.onda_search_plugin.query(
                prep=PreparedSearch(
                    page=1,
                    limit=2,
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
    def _test_plugins_search_odatav4search_search_cloudcover_onda(
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
        """The metadata mapping for ODataV4Search should not mix specific collections metadata-mapping"""
        wkt_geometry = self.search_criteria_s2_msi_l1c["geometry"].wkt
        mock__request.return_value = mock.Mock()
        result = {
            "value": [
                {
                    "id": "foo",
                    "footprint": wkt_geometry,
                },
            ],
        }
        mock__request.return_value.json.side_effect = [5, result, 5, result]
        search_plugin = self.get_search_plugin(provider="onda")

        # update metadata_mapping only for S1_SAR_GRD
        search_plugin.config.products["S1_SAR_GRD"]["metadata_mapping"]["bar"] = (
            None,
            "baz",
        )

        products = search_plugin.query(
            collection="S1_SAR_GRD",
            auth=None,
        )
        self.assertIn("bar", products[0].properties)
        self.assertEqual(products[0].properties["bar"], "baz")

        # search with another collection
        self.assertNotIn(
            "bar", search_plugin.config.products["S1_SAR_SLC"]["metadata_mapping"]
        )
        products = search_plugin.query(
            collection="S1_SAR_SLC",
            auth=None,
        )
        self.assertNotIn("bar", products.data[0].properties)
