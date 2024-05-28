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
import os
import tempfile
import unittest

from requests.exceptions import RequestException

from tests import TEST_RESOURCES_PATH
from tests.context import (
    EODataAccessGateway,
    EOProduct,
    NoMatchingProductType,
    RequestError,
    USGSError,
    ValidationError,
)
from tests.utils import mock


class MockResponse:
    def __init__(self, json_data):
        self.json_data = json_data

    def json(self):
        return self.json_data


class TestCoreSearch(unittest.TestCase):
    def setUp(self):
        super(TestCoreSearch, self).setUp()
        # Mock home and eodag conf directory to tmp dir
        self.tmp_home_dir = tempfile.TemporaryDirectory()
        self.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, return_value=self.tmp_home_dir.name
        )
        self.expanduser_mock.start()
        # load fake credentials to prevent providers needing auth for search to be pruned
        config_path = os.path.join(TEST_RESOURCES_PATH, "wrong_credentials_conf.yml")
        self.dag = EODataAccessGateway(user_conf_file_path=config_path)

    def tearDown(self):
        super(TestCoreSearch, self).tearDown()
        # stop Mock and remove tmp config dir
        self.expanduser_mock.stop()
        self.tmp_home_dir.cleanup()

    @mock.patch(
        "eodag.plugins.search.qssearch.requests.get",
        autospec=True,
        side_effect=RequestException,
    )
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    @mock.patch(
        "eodag.plugins.authentication.qsauth.HttpQueryStringAuth.authenticate",
        autospec=True,
    )
    def test_core_search_errors_qssearch(
        self, mock_authenticate, mock_fetch_product_types_list, mock_get
    ):
        # QueryStringSearch / peps
        self.dag.set_preferred_provider("peps")
        self.assertRaises(ValidationError, self.dag.search, raise_errors=True)
        self.assertRaises(
            RequestError, self.dag.search, productType="foo", raise_errors=True
        )
        # search iterator
        self.assertRaises(
            RequestError, next, self.dag.search_iter_page(productType="foo")
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.requests.post",
        autospec=True,
        side_effect=RequestException,
    )
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.query",
        autospec=True,
    )
    def test_core_search_errors_stacsearch(
        self, mock_query, mock_fetch_product_types_list, mock_post
    ):
        mock_query.return_value = ([], 0)
        # StacSearch / astraea_eod
        self.dag.set_preferred_provider("astraea_eod")
        self.assertRaises(RequestError, self.dag.search, raise_errors=True)
        # search iterator
        self.assertRaises(RequestError, next, self.dag.search_iter_page())

    @mock.patch(
        "eodag.plugins.search.qssearch.requests.post",
        autospec=True,
        side_effect=RequestException,
    )
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request",
        autospec=True,
    )
    def test_core_search_errors_postjson(
        self, mock_request, mock_fetch_product_types_list, mock_post
    ):
        mock_request.return_value = MockResponse({"results": []})
        # PostJsonSearch / aws_eos
        self.dag.set_preferred_provider("aws_eos")
        self.assertRaises(RequestError, self.dag.search, raise_errors=True)
        # search iterator
        self.assertRaises(RequestError, next, self.dag.search_iter_page())

    @mock.patch(
        "eodag.plugins.authentication.qsauth.HttpQueryStringAuth.authenticate",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.urlopen",
        autospec=True,
        side_effect=RequestException,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.requests.get",
        autospec=True,
        side_effect=RequestException,
    )
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    def test_core_search_errors_odata(
        self, mock_fetch_product_types_list, mock_get, mock_urlopen, mock_authenticate
    ):
        # ODataV4Search / onda
        self.dag.set_preferred_provider("onda")
        self.assertRaises(ValidationError, self.dag.search, raise_errors=True)
        self.assertRaises(
            RequestError, self.dag.search, productType="foo", raise_errors=True
        )
        # search iterator
        self.assertRaises(
            RequestError, next, self.dag.search_iter_page(productType="foo")
        )

    @mock.patch(
        "eodag.plugins.apis.usgs.api.scene_search", autospec=True, side_effect=USGSError
    )
    @mock.patch("eodag.plugins.apis.usgs.api.login", autospec=True)
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    def test_core_search_errors_usgs(
        self, mock_fetch_product_types_list, mock_login, mock_scene_search
    ):
        # UsgsApi / usgs
        self.dag.set_preferred_provider("usgs")
        self.assertRaises(NoMatchingProductType, self.dag.search, raise_errors=True)
        self.assertRaises(
            RequestError, self.dag.search, raise_errors=True, productType="foo"
        )
        # search iterator
        self.assertRaises(
            RequestError, next, self.dag.search_iter_page(productType="foo")
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.requests.post",
        autospec=True,
        side_effect=RequestException,
    )
    @mock.patch(
        "eodag.plugins.authentication.qsauth.HttpQueryStringAuth.authenticate",
        autospec=True,
    )
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    def test_core_search_errors_buildpost(
        self, mock_fetch_product_types_list, mock_authenticate, mock_post, mock_request
    ):
        mock_request.return_value = MockResponse({"results": []})
        # BuildPostSearchResult / meteoblue
        self.dag.set_preferred_provider("meteoblue")
        self.assertRaises(RequestError, self.dag.search, raise_errors=True)
        # search iterator
        self.assertRaises(RequestError, next, self.dag.search_iter_page())

    @mock.patch(
        "eodag.plugins.authentication.token.TokenAuth.authenticate",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.requests.Request",
        autospec=True,
        side_effect=RequestException,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.requests.post",
        autospec=True,
        side_effect=RequestException,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.requests.get",
        autospec=True,
        side_effect=RequestException,
    )
    def test_core_search_fallback_find_nothing(
        self, mock_get, mock_post, mock_request, mock_auth
    ):
        """Core search must loop over providers until finding a non empty result"""
        product_type = "S1_SAR_SLC"
        available_providers = self.dag.available_providers(product_type)
        self.assertListEqual(
            available_providers,
            [
                "peps",
                "cop_dataspace",
                "creodias",
                "creodias_s3",
                "onda",
                "sara",
                "wekeo",
            ],
        )

        products, count = self.dag.search(productType="S1_SAR_SLC")
        self.assertEqual(len(products), 0)
        self.assertEqual(count, 0)
        self.assertEqual(
            mock_get.call_count + mock_post.call_count + mock_request.call_count,
            len(available_providers),
            "all available providers must have been requested",
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.requests.Request",
        autospec=True,
        side_effect=RequestException,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.requests.get",
        autospec=True,
        side_effect=RequestException,
    )
    def test_core_search_fallback_raise_errors(self, mock_get, mock_request):
        """Core search fallback mechanism must halt loop on error if raise_errors is set"""
        product_type = "S1_SAR_SLC"
        available_providers = self.dag.available_providers(product_type)
        self.assertListEqual(
            available_providers,
            [
                "peps",
                "cop_dataspace",
                "creodias",
                "creodias_s3",
                "onda",
                "sara",
                "wekeo",
            ],
        )

        self.assertRaises(
            RequestError, self.dag.search, productType="S1_SAR_SLC", raise_errors=True
        )
        self.assertEqual(
            mock_get.call_count + mock_request.call_count,
            1,
            "only 1 provider must have been requested",
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.requests.Request",
        autospec=True,
        side_effect=RequestException,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.requests.get",
        autospec=True,
    )
    def test_core_search_fallback_find_on_first(self, mock_get, mock_request):
        """Core search must loop over providers until finding a non empty result"""
        product_type = "S1_SAR_SLC"
        available_providers = self.dag.available_providers(product_type)
        self.assertListEqual(
            available_providers,
            [
                "peps",
                "cop_dataspace",
                "creodias",
                "creodias_s3",
                "onda",
                "sara",
                "wekeo",
            ],
        )

        # peps comes 1st by priority
        peps_resp_search_file = os.path.join(
            TEST_RESOURCES_PATH, "provider_responses", "peps_search.json"
        )
        with open(peps_resp_search_file, encoding="utf-8") as f:
            peps_resp_search_file_content = json.load(f)
        peps_resp_search_results_count = len(peps_resp_search_file_content["features"])

        mock_get.return_value.json.return_value = peps_resp_search_file_content

        products, _ = self.dag.search(productType="S1_SAR_SLC")
        self.assertEqual(len(products), peps_resp_search_results_count)
        self.assertEqual(
            mock_get.call_count + mock_request.call_count,
            1,
            "only 1 provider out of 7 must have been requested",
        )

    # onda uses requests.Request then urllib with HTTPAdapter.build_response
    @mock.patch(
        "eodag.plugins.search.qssearch.requests.adapters.HTTPAdapter.build_response",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.urlopen",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.requests.Request",
        autospec=True,
        # fail on creodias, then succeeds on onda (count and search)
        side_effect=[RequestException, mock.DEFAULT, mock.DEFAULT],
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.requests.get",
        autospec=True,
        side_effect=RequestException,
    )
    def test_core_search_fallback_find_on_fourth(
        self, mock_get, mock_request, mock_urlopen, mock_httpadapter
    ):
        """Core search must loop over providers until finding a non empty result"""
        product_type = "S1_SAR_SLC"
        available_providers = self.dag.available_providers(product_type)
        self.assertListEqual(
            available_providers,
            [
                "peps",
                "cop_dataspace",
                "creodias",
                "creodias_s3",
                "onda",
                "sara",
                "wekeo",
            ],
        )

        # onda comes 3rd by priority
        onda_resp_search_file = os.path.join(
            TEST_RESOURCES_PATH, "provider_responses", "onda_search.json"
        )
        with open(onda_resp_search_file, encoding="utf-8") as f:
            onda_resp_search_file_content = json.load(f)
        onda_resp_search_results_count = len(onda_resp_search_file_content["value"])

        # results_count, results content
        mock_httpadapter.return_value.json.side_effect = [
            2,
            onda_resp_search_file_content,
        ]

        products, _ = self.dag.search(productType="S1_SAR_SLC")
        self.assertEqual(len(products), onda_resp_search_results_count)
        self.assertEqual(
            mock_get.call_count + mock_request.call_count,
            4,
            "there must have been 4 requests (3 providers search and 1 count request)",
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.query",
        autospec=True,
    )
    def test_core_search_fallback_find_on_fourth_empty_results(self, mock_query):
        """Core search must loop over providers until finding a non empty result"""
        product_type = "S1_SAR_SLC"
        available_providers = self.dag.available_providers(product_type)
        self.assertListEqual(
            available_providers,
            [
                "peps",
                "cop_dataspace",
                "creodias",
                "creodias_s3",
                "onda",
                "sara",
                "wekeo",
            ],
        )

        mock_query.side_effect = [
            ([], 0),
            ([], 0),
            ([], 0),
            ([EOProduct("onda", dict(geometry="POINT (0 0)", id="a"))], 1),
        ]

        products, count = self.dag.search(productType="S1_SAR_SLC")
        self.assertEqual(len(products), 1)
        self.assertEqual(count, 1)
        self.assertEqual(
            mock_query.call_count, 4, "4 provider out of 6 must have been requested"
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.query",
        autospec=True,
    )
    def test_core_search_fallback_given_provider(self, mock_query):
        """Core search must not loop over providers if a provider is specified"""
        product_type = "S1_SAR_SLC"
        available_providers = self.dag.available_providers(product_type)
        self.assertListEqual(
            available_providers,
            [
                "peps",
                "cop_dataspace",
                "creodias",
                "creodias_s3",
                "onda",
                "sara",
                "wekeo",
            ],
        )

        mock_query.return_value = ([], 0)

        products, count = self.dag.search(productType="S1_SAR_SLC", provider="onda")
        self.assertEqual(len(products), 0)
        self.assertEqual(count, 0)
        self.assertEqual(
            mock_query.call_count,
            1,
            "only 1 provider out of 6 must have been requested",
        )
