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
        "eodag.plugins.search.qssearch.requests.Session.get",
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
        self.assertRaises(
            RequestError, self.dag.search, productType="foo", raise_errors=True
        )
        # search iterator
        self.assertRaises(
            RequestError, next, self.dag.search_iter_page(productType="foo")
        )

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.sessions.Session.request",
        autospec=True,
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
        self,
        mock_query,
        mock_fetch_product_types_list,
        mock_post,
        mock_auth_session_request,
    ):
        mock_query.return_value = ([], 0)
        # StacSearch / earth_search
        self.dag.set_preferred_provider("earth_search")
        self.assertRaises(RequestError, self.dag.search, raise_errors=True)
        # search iterator
        self.assertRaises(RequestError, next, self.dag.search_iter_page())

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.sessions.Session.request",
        autospec=True,
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
        "eodag.plugins.search.qssearch.QueryStringSearch._request",
        autospec=True,
    )
    def test_core_search_errors_postjson(
        self,
        mock_request,
        mock_fetch_product_types_list,
        mock_post,
        mock_auth_session_request,
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
        # ODataV4Search / creodias
        self.dag.set_preferred_provider("creodias")
        self.assertRaises(
            RequestError, self.dag.search, productType="foo", raise_errors=True
        )
        # search iterator
        self.assertRaises(
            RequestError, next, self.dag.search_iter_page(productType="foo")
        )

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.sessions.Session.request",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.apis.usgs.api.scene_search", autospec=True, side_effect=USGSError
    )
    @mock.patch("eodag.plugins.apis.usgs.api.login", autospec=True)
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    def test_core_search_errors_usgs(
        self,
        mock_fetch_product_types_list,
        mock_login,
        mock_scene_search,
        mock_auth_session_request,
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
        "eodag.plugins.authentication.openid_connect.requests.sessions.Session.request",
        autospec=True,
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
        self,
        mock_fetch_product_types_list,
        mock_authenticate,
        mock_post,
        mock_request,
        mock_auth_session_request,
    ):
        mock_request.return_value = MockResponse({"results": []})
        # MeteoblueSearch / meteoblue
        self.dag.set_preferred_provider("meteoblue")
        self.assertRaises(RequestError, self.dag.search, raise_errors=True)
        # search iterator
        self.assertRaises(RequestError, next, self.dag.search_iter_page())

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.get",
        autospec=True,
    )
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
        "eodag.plugins.search.qssearch.requests.Session.get",
        autospec=True,
        side_effect=RequestException,
    )
    def test_core_search_fallback_find_nothing(
        self, mock_get, mock_post, mock_request, mock_auth_token, mock_auth_oidc
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
                "dedl",
                "geodes",
                "sara",
                "wekeo_main",
            ],
        )

        search_result = self.dag.search(productType="S1_SAR_SLC", count=True)
        self.assertEqual(len(search_result), 0)
        self.assertEqual(search_result.number_matched, 0)
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
        "eodag.plugins.search.qssearch.requests.Session.get",
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
                "dedl",
                "geodes",
                "sara",
                "wekeo_main",
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
        "eodag.plugins.search.qssearch.requests.Session.get",
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
                "dedl",
                "geodes",
                "sara",
                "wekeo_main",
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

        search_result = self.dag.search(productType="S1_SAR_SLC", count=True)
        self.assertEqual(len(search_result), peps_resp_search_results_count)
        self.assertEqual(
            mock_get.call_count + mock_request.call_count,
            1,
            "only 1 provider out of 7 must have been requested",
        )

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.get",
        autospec=True,
    )
    # creodias uses requests.Request then urllib with HTTPAdapter.build_response
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
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.requests.Session.get",
        autospec=True,
        # fail on other providers
        side_effect=RequestException,
    )
    def test_core_search_fallback_find_on_second(
        self, mock_get, mock_request, mock_urlopen, mock_httpadapter, mock_auth_get
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
                "dedl",
                "geodes",
                "sara",
                "wekeo_main",
            ],
        )

        # creodias comes 2nd by priority
        creodias_resp_search_file = os.path.join(
            TEST_RESOURCES_PATH, "eodag_search_result_creodias.json"
        )
        with open(creodias_resp_search_file, encoding="utf-8") as f:
            creodias_resp_search_file_content = json.load(f)
        creodias_resp_search_results_count = len(
            creodias_resp_search_file_content["value"]
        )

        # results content
        mock_httpadapter.return_value.json.side_effect = [
            creodias_resp_search_file_content,
        ]

        search_result = self.dag.search(productType="S1_SAR_SLC", count=True)
        self.assertEqual(len(search_result), creodias_resp_search_results_count)
        self.assertEqual(
            mock_get.call_count + mock_request.call_count,
            2,
            "there must have been 2 requests",
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.query",
        autospec=True,
    )
    def test_core_search_fallback_find_on_second_empty_results(self, mock_query):
        """Core search must loop over providers until finding a non empty result"""
        product_type = "S1_SAR_SLC"
        available_providers = self.dag.available_providers(product_type)
        self.assertListEqual(
            available_providers,
            [
                "peps",
                "cop_dataspace",
                "creodias",
                "dedl",
                "geodes",
                "sara",
                "wekeo_main",
            ],
        )

        mock_query.side_effect = [
            ([], 0),
            ([EOProduct("creodias", dict(geometry="POINT (0 0)", id="a"))], 1),
        ]

        search_result = self.dag.search(productType="S1_SAR_SLC", count=True)
        self.assertEqual(len(search_result), 1)
        self.assertEqual(search_result.number_matched, 1)
        self.assertEqual(
            mock_query.call_count,
            2,
            f"2 provider out of {len(available_providers)} must have been requested",
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
                "dedl",
                "geodes",
                "sara",
                "wekeo_main",
            ],
        )

        mock_query.return_value = ([], 0)

        search_result = self.dag.search(
            productType="S1_SAR_SLC", provider="creodias", count=True
        )
        self.assertEqual(len(search_result), 0)
        self.assertEqual(search_result.number_matched, 0)
        self.assertEqual(
            mock_query.call_count,
            1,
            "only 1 provider out of 6 must have been requested",
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.StacSearch.query",
        autospec=True,
    )
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    def test_core_search_auths_matching(
        self, mock_fetch_product_types_list, mock_query
    ):
        """Core search must set and use appropriate auth plugins"""

        self.dag.add_provider(
            "foo",
            "https://foo.bar/search",
            auth={
                "type": "GenericAuth",
                "matching_url": "https://foo.bar",
                "credentials": {"username": "a-username", "password": "a-password"},
            },
            search_auth={
                "type": "GenericAuth",
                "matching_conf": {"something": "special"},
                "credentials": {
                    "username": "another-username",
                    "password": "another-password",
                },
            },
            download_auth={
                "type": "GenericAuth",
                "matching_url": "https://somewhere",
                "credentials": {
                    "username": "yet-another-username",
                    "password": "yet-another-password",
                },
            },
        )

        # auth plugin without match configuration
        self.dag.add_provider(
            "provider_without_match_configured",
            "https://foo.bar/baz/search",
            search={"need_auth": True},
            auth={
                "type": "GenericAuth",
                "credentials": {
                    "username": "some-username",
                    "password": "some-password",
                },
            },
        )
        self.dag.search(provider="provider_without_match_configured")
        self.assertEqual(mock_query.call_args[0][1].auth.username, "some-username")
        mock_query.reset_mock()

        # search endpoint matching
        self.dag.add_provider(
            "provider_matching_search_api",
            "https://foo.bar/baz/search",
            search={"need_auth": True},
        )
        self.dag.search(provider="provider_matching_search_api")
        self.assertEqual(mock_query.call_args[0][1].auth.username, "a-username")
        mock_query.reset_mock()

        # plugin conf matching
        self.dag.add_provider(
            "provider_matching_another_search_api",
            "https://fooooo.bar/search",
            search={"need_auth": True, "something": "special"},
        )
        self.dag.search(provider="provider_matching_another_search_api")
        self.assertEqual(mock_query.call_args[0][1].auth.username, "another-username")
        mock_query.reset_mock()

        # download link matching
        self.dag.add_provider(
            "provider_matching_download_link",
            "https://foo.bar/baz/search",
        )
        mock_query.side_effect = [
            (
                [
                    EOProduct(
                        "provider_matching_download_link",
                        dict(
                            geometry="POINT (0 0)",
                            id="a",
                            downloadLink="https://somewhere/to/download",
                        ),
                    )
                ],
                1,
            ),
        ]
        results = self.dag.search(provider="provider_matching_download_link")
        self.assertEqual(
            results[0].downloader_auth.config.credentials["username"],
            "yet-another-username",
        )
        mock_query.reset_mock()

        # order link matching
        self.dag.add_provider(
            "provider_matching_order_link",
            "https://foo.bar/baz/search",
        )
        mock_query.side_effect = [
            (
                [
                    EOProduct(
                        "provider_matching_download_link",
                        dict(
                            geometry="POINT (0 0)",
                            id="a",
                            orderLink="https://somewhere/to/download",
                        ),
                    )
                ],
                1,
            ),
        ]
        results = self.dag.search(provider="provider_matching_download_link")
        self.assertEqual(
            results[0].downloader_auth.config.credentials["username"],
            "yet-another-username",
        )
        mock_query.reset_mock()

        # first asset matching
        self.dag.add_provider(
            "provider_matching_asset",
            "https://foo.bar/baz/search",
        )
        product_with_assets = EOProduct(
            "provider_matching_asset", dict(geometry="POINT (0 0)", id="a")
        )
        product_with_assets.assets.update(
            {"aa": {"href": "https://foo.bar/download/asset"}}
        )
        mock_query.side_effect = [([product_with_assets], 1)]
        results = self.dag.search(provider="provider_matching_asset")
        self.assertEqual(
            results[0].downloader_auth.config.credentials["username"], "a-username"
        )
