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
from unittest import mock

from eodag.api.product import EOProduct
from eodag.plugins.search import PreparedSearch
from eodag.utils import DEFAULT_SEARCH_TIMEOUT, USER_AGENT
from tests.units.search_plugins.base import BaseSearchPluginTest


class TestSearchPluginMeteoblueSearch(BaseSearchPluginTest):
    @mock.patch(
        "eodag.plugins.authentication.qsauth.httpquerystringauth.requests.get",
        autospec=True,
    )
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

    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.requests.post", autospec=True
    )
    def test_plugins_search_buildpostsearchresult_count_and_search(
        self, mock_requests_post
    ):
        """A query with a MeteoblueSearch must return a single result"""

        # custom query for meteoblue
        custom_query = {"queries": {"foo": "bar"}}
        collection_config = {"platform": "NEMSGLOBAL", "alias": "THE.ALIAS"}
        setattr(self.search_plugin.config, "collection_config", collection_config)
        products = self.search_plugin.query(
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
        self.assertEqual(products.number_matched, 1)
        self.assertIsInstance(products[0], EOProduct)
        endpoint = "https://my.meteoblue.com/dataset/query"
        default_geom = {
            "coordinates": [
                [[180, -90], [180, 90], [-180, 90], [-180, -90], [180, -90]]
            ],
            "type": "Polygon",
        }
        # check download_link
        self.assertEqual(
            products[0].assets["download_link"]["href"],
            f"{endpoint}?" + json.dumps({"geometry": default_geom, **custom_query}),
        )
        # check eodag:order_link
        self.assertEqual(
            products[0].assets["download_link"]["order_link"],
            f"{endpoint}?"
            + json.dumps(
                {
                    "geometry": default_geom,
                    "runOnJobQueue": True,
                    **custom_query,
                }
            ),
        )
