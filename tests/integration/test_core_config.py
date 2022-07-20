# -*- coding: utf-8 -*-
# Copyright 2022, CS GROUP - France, https://www.csgroup.eu/
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

import tempfile
from unittest import TestCase, mock

from tests.context import EODataAccessGateway, PluginConfig


class TestCoreProvidersConfig(TestCase):
    def setUp(self):
        super(TestCoreProvidersConfig, self).setUp()
        # Mock home and eodag conf directory to tmp dir
        self.tmp_home_dir = tempfile.TemporaryDirectory()
        self.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, return_value=self.tmp_home_dir.name
        )
        self.expanduser_mock.start()
        self.dag = EODataAccessGateway()

    def tearDown(self):
        super(TestCoreProvidersConfig, self).tearDown()
        # stop Mock and remove tmp config dir
        self.expanduser_mock.stop()
        self.tmp_home_dir.cleanup()

    @mock.patch("eodag.plugins.search.qssearch.PostJsonSearch._request", autospec=True)
    def test_core_providers_config_update(self, mock__request):
        """Providers config must be updatable"""
        mock__request.return_value = mock.Mock()
        mock__request_side_effect = [
            {
                "context": {
                    "matched": 1,
                }
            },
            {
                "features": [
                    {
                        "id": "foo",
                        "bar": "baz",
                        "geometry": "POLYGON((180 -90, 180 90, -180 90, -180 -90, 180 -90))",
                    }
                ]
            },
        ]
        mock__request.return_value.json.side_effect = mock__request_side_effect

        # add new provider and search on it
        self.dag.update_providers_config(
            """
            foo_provider:
                search:
                    type: StacSearch
                    api_endpoint: https://foo.bar/search
                products:
                    GENERIC_PRODUCT_TYPE:
                        productType: '{productType}'
                download:
                    type: HTTPDownload
                    base_uri: https://foo.bar
            """
        )
        self.dag.set_preferred_provider("foo_provider")

        prods, _ = self.dag.search(raise_errors=True)
        self.assertEqual(prods[0].properties["title"], "foo")

        # update provider which have metadata_mapping already built as jsonpath by search()
        self.dag.update_providers_config(
            """
            foo_provider:
                search:
                    metadata_mapping:
                        title: '$.bar'
            """
        )
        mock__request.return_value.json.side_effect = mock__request_side_effect
        prods, _ = self.dag.search(raise_errors=True)
        self.assertEqual(prods[0].properties["title"], "baz")

        # update provider with new plugin entry
        self.dag.update_providers_config(
            """
            foo_provider:
                auth:
                    type: GenericAuth
            """
        )
        self.assertIsInstance(
            self.dag.providers_config["foo_provider"].auth, PluginConfig
        )
        self.assertEqual(
            self.dag.providers_config["foo_provider"].auth.type, "GenericAuth"
        )
