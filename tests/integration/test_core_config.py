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

from tests.context import (
    HTTP_REQ_TIMEOUT,
    USER_AGENT,
    AuthenticationError,
    EODataAccessGateway,
    HeaderAuth,
    PluginConfig,
)


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

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    @mock.patch("eodag.plugins.search.qssearch.PostJsonSearch._request", autospec=True)
    def test_core_providers_config_update(
        self, mock__request, mock_fetch_product_types_list
    ):
        """Providers config must be updatable"""
        mock__request.return_value = mock.Mock()
        mock__request_side_effect = [
            {
                "context": {
                    "matched": 1,
                },
                "features": [
                    {
                        "id": "foo",
                        "bar": "baz",
                        "geometry": "POLYGON((180 -90, 180 90, -180 90, -180 -90, 180 -90))",
                    }
                ],
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

        # add new provider that requires auth but without credentials
        self.dag.update_providers_config(
            """
            bar_provider:
                search:
                    type: StacSearch
                    api_endpoint: https://foo.bar/search
                    need_auth: True
                products:
                    GENERIC_PRODUCT_TYPE:
                        productType: '{productType}'
            """
        )
        self.assertNotIn("bar_provider", self.dag.providers_config)

        # update provider with credentials
        self.dag.update_providers_config(
            """
            bar_provider:
                auth:
                    credentials:
                        username: bar
                        password: foo
            """
        )
        self.assertIsInstance(
            self.dag.providers_config["bar_provider"].auth, PluginConfig
        )
        self.assertEqual(
            self.dag.providers_config["bar_provider"].auth.credentials["username"],
            "bar",
        )


class TestCoreProductTypesConfig(TestCase):
    def setUp(self):
        super(TestCoreProductTypesConfig, self).setUp()
        # Mock home and eodag conf directory to tmp dir
        self.tmp_home_dir = tempfile.TemporaryDirectory()
        self.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, return_value=self.tmp_home_dir.name
        )
        self.expanduser_mock.start()
        self.dag = EODataAccessGateway()

    def tearDown(self):
        super(TestCoreProductTypesConfig, self).tearDown()
        # stop Mock and remove tmp config dir
        self.expanduser_mock.stop()
        self.tmp_home_dir.cleanup()

    @mock.patch(
        "eodag.plugins.search.qssearch.requests.adapters.HTTPAdapter.build_response",
        autospec=True,
    )
    @mock.patch("eodag.plugins.search.qssearch.urlopen", autospec=True)
    @mock.patch("eodag.plugins.search.qssearch.requests.get", autospec=True)
    def test_core_discover_product_types_auth(
        self, mock_requests_get, mock_urlopen, mock_build_response
    ):
        # without auth plugin
        self.dag.update_providers_config(
            """
            foo_provider:
                search:
                    type: StacSearch
                    api_endpoint: https://foo.bar/search
                    discover_product_types:
                        fetch_url: https://foo.bar/collections
                    need_auth: true
                products:
                    GENERIC_PRODUCT_TYPE:
                        productType: '{productType}'
            """
        )
        with self.assertLogs(level="WARNING") as cm:
            ext_product_types_conf = self.dag.discover_product_types(
                provider="foo_provider"
            )
            self.assertIsNone(ext_product_types_conf["foo_provider"])
            self.assertIn(
                "Could not authenticate on foo_provider using None plugin",
                str(cm.output),
            )

        # with auth plugin but without credentials
        self.dag.update_providers_config(
            """
            foo_provider:
                auth:
                    type: HTTPHeaderAuth
                    headers:
                        Authorization: "Apikey {apikey}"
            """
        )
        with self.assertLogs(level="WARNING") as cm:
            ext_product_types_conf = self.dag.discover_product_types(
                provider="foo_provider"
            )
            self.assertIsNone(ext_product_types_conf["foo_provider"])
            self.assertIn(
                "Could not authenticate on foo_provider: Missing credentials",
                str(cm.output),
            )

        # succeeds with auth plugin and credentials
        self.dag.update_providers_config(
            """
            foo_provider:
                auth:
                    credentials:
                        apikey: my-api-key
            """
        )
        self.dag.discover_product_types(provider="foo_provider")

        mock_requests_get.assert_called_once_with(
            self.dag.providers_config["foo_provider"].search.discover_product_types[
                "fetch_url"
            ],
            auth=mock.ANY,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
        )

        mock_urlopen.return_value.json.return_value = {}
        mock_build_response.return_value.json.return_value = {}

        # succeeds with dont_quote attribute
        self.dag.update_providers_config(
            """
            foo_provider:
                search:
                    dont_quote:
                        - '['
                        - ']'
            """
        )
        self.dag.discover_product_types(provider="foo_provider")

        mock_urlopen.assert_called_once()
        self.assertDictEqual(
            {
                k.lower(): v
                for k, v in mock_urlopen.call_args_list[0][0][0].headers.items()
            },
            {k.lower(): v for k, v in USER_AGENT.items()},
        )

        call_args, call_kwargs = mock_requests_get.call_args
        self.assertIsInstance(call_kwargs["auth"], HeaderAuth)

        # warning if another AuthenticationError
        with mock.patch(
            "eodag.plugins.manager.PluginManager.get_auth_plugin",
        ) as mock_get_auth_plugin:
            mock_get_auth_plugin.return_value.authenticate.side_effect = (
                AuthenticationError("cannot auth for test")
            )
            with self.assertLogs(level="WARNING") as cm:
                ext_product_types_conf = self.dag.discover_product_types(
                    provider="foo_provider"
                )
                self.assertIsNone(ext_product_types_conf["foo_provider"])
                self.assertIn(
                    "Could not authenticate on foo_provider: cannot auth for test",
                    str(cm.output),
                )
