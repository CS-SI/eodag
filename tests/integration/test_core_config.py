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

from jsonpath_ng.jsonpath import Child, Fields, Root

from tests.context import (
    DEFAULT_SEARCH_TIMEOUT,
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
        "eodag.plugins.authentication.openid_connect.requests.sessions.Session.request",
        autospec=True,
    )
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_collections_list", autospec=True
    )
    @mock.patch("eodag.plugins.search.qssearch.PostJsonSearch._request", autospec=True)
    def test_core_providers_config_update(
        self, mock__request, mock_fetch_collections_list, mock_auth_session_request
    ):
        """Providers config must be updatable"""
        mock__request.return_value = mock.Mock()
        mock__request_side_effect = [
            {
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
                    GENERIC_COLLECTION:
                        _collection: '{collection}'
                download:
                    type: HTTPDownload
                    base_uri: https://foo.bar
            """
        )
        self.dag.set_preferred_provider("foo_provider")

        prods = self.dag.search(raise_errors=True, validate=False)
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
        prods = self.dag.search(raise_errors=True, validate=False)
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

        # update pruned provider with credentials
        self.assertNotIn("usgs", self.dag.providers_config)
        self.dag.update_providers_config(
            """
            usgs:
                api:
                    credentials:
                        username: foo
                        password: bar
            """
        )
        self.assertIsInstance(self.dag.providers_config["usgs"].api, PluginConfig)
        self.assertEqual(
            self.dag.providers_config["usgs"].api.credentials["username"], "foo"
        )

        # add new provider that requires auth but without credentials
        self.dag.update_providers_config(
            """
            bar_provider:
                search:
                    type: StacSearch
                    api_endpoint: https://foo.bar/search
                    need_auth: True
                auth:
                    type: GenericAuth
                products:
                    GENERIC_COLLECTION:
                        _collection: '{collection}'
            """
        )
        self.assertIn("bar_provider", self.dag.providers_config)

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

    def test_core_providers_shared_credentials(self):
        """credentials must be shared between plugins having the same matching settings"""

        self.dag.add_provider(
            "a_provider_without_creds_matching_url",
            "https://foo.bar/search",
            auth={
                "type": "GenericAuth",
                "matching_url": "http://foo.bar",
            },
        )
        self.dag.add_provider(
            "a_provider_with_creds",
            "https://foo.bar/search",
            auth={
                "type": "GenericAuth",
                "matching_url": "http://foo.bar",
                "credentials": {"username": "bar", "password": "foo"},
            },
        )
        self.dag.update_providers_config(
            """
            another_provider_with_creds:
                search:
                    type: StacSearch
                    api_endpoint: https://foo.bar/search
                products:
                    GENERIC_COLLECTION:
                        _collection: '{collection}'
                auth:
                    type: GenericAuth
                    matching_conf:
                        something: special
                    credentials:
                        username: baz
                        password: qux

            a_provider_without_creds_matching_conf:
                search:
                    type: StacSearch
                    api_endpoint: https://foo.bar/search
                products:
                    GENERIC_COLLECTION:
                        _collection: '{collection}'
                auth:
                    type: GenericAuth
                    matching_conf:
                        something: special
            """
        )
        self.assertDictEqual(
            self.dag.providers_config["a_provider_with_creds"].auth.credentials,
            {"username": "bar", "password": "foo"},
        )
        self.assertDictEqual(
            self.dag.providers_config["a_provider_with_creds"].auth.credentials,
            self.dag.providers_config[
                "a_provider_without_creds_matching_url"
            ].auth.credentials,
        )
        self.assertDictEqual(
            self.dag.providers_config["another_provider_with_creds"].auth.credentials,
            {"username": "baz", "password": "qux"},
        )
        self.assertDictEqual(
            self.dag.providers_config["another_provider_with_creds"].auth.credentials,
            self.dag.providers_config[
                "a_provider_without_creds_matching_conf"
            ].auth.credentials,
        )

    def test_core_providers_add(self):
        """add_provider method must add provider using given conf"""

        # minimal STAC provider
        self.dag.add_provider("foo", "https://foo.bar/search")
        self.assertEqual(
            self.dag.providers_config["foo"].search.type,
            "StacSearch",
        )
        self.assertEqual(
            self.dag.providers_config["foo"].search.api_endpoint,
            "https://foo.bar/search",
        )
        self.assertEqual(
            self.dag.providers_config["foo"].download.type,
            "HTTPDownload",
        )
        self.assertFalse(hasattr(self.dag.providers_config["foo"], "auth"))
        self.assertEqual(
            self.dag.get_preferred_provider()[0],
            "foo",
        )

        # Advanced QueryStringSearch provider
        self.dag.add_provider(
            "bar",
            search={
                "type": "QueryStringSearch",
                "api_endpoint": "https://foo.bar/search",
                "discover_metadata": {"metadata_path": "$.properties.*"},
            },
            download={"type": "AwsDownload"},
            auth={"type": "AwsAuth", "credentials": {"aws_profile": "abc"}},
            priority=0,
        )
        self.assertEqual(
            self.dag.providers_config["bar"].search.type,
            "QueryStringSearch",
        )
        self.assertEqual(
            self.dag.providers_config["bar"].search.api_endpoint,
            "https://foo.bar/search",
        )
        self.assertEqual(
            self.dag.providers_config["bar"].download.type,
            "AwsDownload",
        )
        self.assertEqual(
            self.dag.providers_config["bar"].auth.type,
            "AwsAuth",
        )
        self.assertDictEqual(
            self.dag.providers_config["bar"].auth.credentials,
            {"aws_profile": "abc"},
        )
        self.assertNotEqual(
            self.dag.get_preferred_provider()[0],
            "bar",
        )

        # Plugin provider
        self.dag.add_provider(
            "baz", api={"type": "UsgsApi", "some_parameter": "some_value"}
        )
        self.assertEqual(
            self.dag.providers_config["baz"].api.type,
            "UsgsApi",
        )
        self.assertEqual(
            self.dag.providers_config["baz"].api.some_parameter,
            "some_value",
        )
        self.assertFalse(hasattr(self.dag.providers_config["baz"], "search"))
        self.assertFalse(hasattr(self.dag.providers_config["baz"], "download"))
        self.assertFalse(hasattr(self.dag.providers_config["baz"], "auth"))
        self.assertEqual(
            self.dag.get_preferred_provider()[0],
            "baz",
        )

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_collections_list", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_core_providers_add_update(
        self, mock__request, mock_fetch_collections_list
    ):
        """add_provider method must add provider using given conf and update if exists"""
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.return_value = {}

        self.dag.add_provider(
            "foo",
            search={
                "type": "QueryStringSearch",
                "api_endpoint": "https://foo.bar/search",
                "pagination": {"next_page_url_tpl": ""},
                "metadata_mapping": {"bar": "$.properties.bar"},
            },
        )
        self.assertEqual(
            self.dag.providers_config["foo"].search.metadata_mapping["bar"],
            "$.properties.bar",
        )

        # search method must build metadata_mapping as jsonpath object
        self.dag.search(provider="foo", collection="abc", raise_errors=True)
        self.assertEqual(
            self.dag.providers_config["foo"].search.metadata_mapping["bar"],
            (None, Child(Child(Root(), Fields("properties")), Fields("bar"))),
        )

        # add provider again will update as already built
        self.dag.add_provider(
            "foo",
            search={
                "type": "QueryStringSearch",
                "api_endpoint": "https://foo.bar/search",
                "pagination": {"next_page_url_tpl": ""},
                "metadata_mapping": {"bar": "$.properties.baz"},
            },
        )
        self.assertEqual(
            self.dag.providers_config["foo"].search.metadata_mapping["bar"],
            (None, Child(Child(Root(), Fields("properties")), Fields("baz"))),
        )


class TestCoreCollectionsConfig(TestCase):
    def setUp(self):
        super(TestCoreCollectionsConfig, self).setUp()
        # Mock home and eodag conf directory to tmp dir
        self.tmp_home_dir = tempfile.TemporaryDirectory()
        self.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, return_value=self.tmp_home_dir.name
        )
        self.expanduser_mock.start()
        self.dag = EODataAccessGateway()

    def tearDown(self):
        super(TestCoreCollectionsConfig, self).tearDown()
        # stop Mock and remove tmp config dir
        self.expanduser_mock.stop()
        self.tmp_home_dir.cleanup()

    @mock.patch(
        "eodag.plugins.search.qssearch.requests.adapters.HTTPAdapter.build_response",
        autospec=True,
    )
    @mock.patch("eodag.plugins.search.qssearch.urlopen", autospec=True)
    @mock.patch("eodag.plugins.search.qssearch.requests.Session.get", autospec=True)
    def test_core_discover_collections_auth(
        self, mock_requests_get, mock_urlopen, mock_build_response
    ):
        # without auth plugin
        self.dag.update_providers_config(
            """
            foo_provider:
                search:
                    type: StacSearch
                    api_endpoint: https://foo.bar/search
                    discover_collections:
                        fetch_url: https://foo.bar/collections
                    need_auth: true
                products:
                    GENERIC_COLLECTION:
                        _collection: '{collection}'
            """
        )
        with self.assertLogs(level="DEBUG") as cm:
            ext_collections_conf = self.dag.discover_collections(
                provider="foo_provider"
            )
            self.assertIsNone(ext_collections_conf["foo_provider"])
            self.assertIn(
                "Could not authenticate on foo_provider for collections discovery",
                str(cm.output),
            )

        # with auth plugin but without credentials
        self.dag.update_providers_config(
            """
            foo_provider:
                auth:
                    type: HTTPHeaderAuth
                    matching_url: https://foo.bar
                    headers:
                        Authorization: "Apikey {apikey}"
            """
        )
        with self.assertLogs(level="DEBUG") as cm:
            ext_collections_conf = self.dag.discover_collections(
                provider="foo_provider"
            )
            self.assertIsNone(ext_collections_conf["foo_provider"])
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
        self.dag.discover_collections(provider="foo_provider")

        mock_requests_get.assert_called_once_with(
            mock.ANY,
            self.dag.providers_config["foo_provider"].search.discover_collections[
                "fetch_url"
            ],
            auth=mock.ANY,
            headers=USER_AGENT,
            timeout=DEFAULT_SEARCH_TIMEOUT,
            verify=True,
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
        self.dag.discover_collections(provider="foo_provider")

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
            "eodag.plugins.manager.PluginManager.get_auth_plugins",
        ) as mock_get_auth_plugins:
            mock_auth_plugin = mock.MagicMock()
            mock_auth_plugin.authenticate = mock.MagicMock(
                side_effect=AuthenticationError("cannot auth for test")
            )
            mock_get_auth_plugins.return_value = iter([mock_auth_plugin])

            with self.assertLogs(level="DEBUG") as cm:
                ext_collections_conf = self.dag.discover_collections(
                    provider="foo_provider"
                )
                self.assertIsNone(ext_collections_conf["foo_provider"])
                self.assertIn(
                    "Could not authenticate on foo_provider: cannot auth for test",
                    str(cm.output),
                )
