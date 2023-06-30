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
import tempfile
import unittest

from requests.exceptions import RequestException

from tests import TEST_RESOURCES_PATH
from tests.context import EODataAccessGateway, RequestError, USGSError
from tests.utils import mock


class MockResponse:
    def __init__(self, json_data):
        self.json_data = json_data

    def json(self):
        return self.json_data


class TestCoreSearchErrors(unittest.TestCase):
    def setUp(self):
        super(TestCoreSearchErrors, self).setUp()
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
        super(TestCoreSearchErrors, self).tearDown()
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

        # QueryStringSearch (peps)
        self.dag.set_preferred_provider("peps")
        products, count = self.dag.search()
        self.assertEqual(count, 0)
        self.assertEqual(len(products), 0)
        # search iterator
        self.assertRaises(RequestError, next, self.dag.search_iter_page())
        # search_all
        self.assertEqual(len(self.dag.search_all()), 0)

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
        # StacSearch (astraea_eod)
        self.dag.set_preferred_provider("astraea_eod")
        products, count = self.dag.search()
        self.assertEqual(count, 0)
        self.assertEqual(len(products), 0)
        # search iterator
        self.assertRaises(RequestError, next, self.dag.search_iter_page())
        # search_all
        self.assertEqual(len(self.dag.search_all()), 0)

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
        # PostJsonSearch (aws_eos)
        self.dag.set_preferred_provider("aws_eos")
        products, count = self.dag.search()
        self.assertEqual(count, 0)
        self.assertEqual(len(products), 0)
        # search iterator
        self.assertRaises(RequestError, next, self.dag.search_iter_page())
        # search_all
        self.assertEqual(len(self.dag.search_all()), 0)

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
        # ODataV4Search (onda)
        self.dag.set_preferred_provider("onda")
        products, count = self.dag.search()
        self.assertEqual(count, 0)
        self.assertEqual(len(products), 0)
        # search iterator
        self.assertRaises(RequestError, next, self.dag.search_iter_page())
        # search_all
        self.assertEqual(len(self.dag.search_all()), 0)

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request",
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
        self, mock_fetch_product_types_list, mock_login, mock_scene_search, mock_request
    ):
        mock_request.return_value = MockResponse({"results": []})
        # UsgsApi (usgs)
        self.dag.set_preferred_provider("usgs")
        products, count = self.dag.search(productType="foo")
        self.assertEqual(count, 0)
        self.assertEqual(len(products), 0)
        # search iterator
        self.assertRaises(StopIteration, next, self.dag.search_iter_page())
        # search_all
        self.assertEqual(len(self.dag.search_all()), 0)

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
        # BuildPostSearchResult (meteoblue)
        self.dag.set_preferred_provider("meteoblue")
        products, count = self.dag.search()
        self.assertEqual(count, 0)
        self.assertEqual(len(products), 0)
        # search iterator
        self.assertRaises(RequestError, next, self.dag.search_iter_page())
        # search_all
        self.assertEqual(len(self.dag.search_all()), 0)
