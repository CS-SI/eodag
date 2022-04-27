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

import unittest
from unittest import mock

from requests.auth import AuthBase

from eodag.config import override_config_from_mapping
from tests.context import MisconfiguredError, PluginManager


class BaseAuthPluginTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(BaseAuthPluginTest, cls).setUpClass()
        cls.providers_config = {}
        cls.plugins_manager = PluginManager(cls.providers_config)

    def tearDown(self):
        super(BaseAuthPluginTest, self).tearDown()
        # remove credentials set during tests
        for provider in self.providers_config:
            self.get_auth_plugin(provider).config.__dict__.pop("credentials", None)

    def get_auth_plugin(self, provider):
        return self.plugins_manager.get_auth_plugin(provider)


class TestAuthPluginTokenAuth(BaseAuthPluginTest):
    @classmethod
    def setUpClass(cls):
        super(TestAuthPluginTokenAuth, cls).setUpClass()
        override_config_from_mapping(
            cls.providers_config,
            {
                "provider_text_token_simple_url": {
                    "products": {},
                    "auth": {
                        "type": "TokenAuth",
                        "auth_uri": "http://foo.bar",
                    },
                },
                "provider_text_token_format_url": {
                    "products": {},
                    "auth": {
                        "type": "TokenAuth",
                        "auth_uri": "http://foo.bar?username={username}",
                    },
                },
                "provider_text_token_header": {
                    "products": {},
                    "auth": {
                        "type": "TokenAuth",
                        "auth_uri": "http://foo.bar",
                        "headers": {
                            "Content-Type": "application/json;charset=UTF-8",
                            "Accept": "application/json",
                        },
                    },
                },
                "provider_json_token_simple_url": {
                    "products": {},
                    "auth": {
                        "type": "TokenAuth",
                        "auth_uri": "http://foo.bar",
                        "token_type": "json",
                        "token_key": "token_is_here",
                    },
                },
            },
        )
        cls.plugins_manager = PluginManager(cls.providers_config)

    def test_plugins_auth_tokenauth_validate_credentials_empty(self):
        """TokenAuth.validate_credentials must raise an error on empty credentials"""
        auth_plugin = self.get_auth_plugin("provider_text_token_simple_url")
        self.assertRaises(
            MisconfiguredError,
            auth_plugin.validate_config_credentials,
        )

    def test_plugins_auth_tokenauth_validate_credentials_ok(self):
        """TokenAuth.validate_credentials must be ok on non-empty credentials"""
        auth_plugin = self.get_auth_plugin("provider_text_token_simple_url")

        auth_plugin.config.credentials = {"foo": "bar"}
        auth_plugin.validate_config_credentials()

    def test_plugins_auth_tokenauth_validate_credentials_format_url_missing(self):
        """TokenAuth.validate_credentials must raise an error if cannot format url"""
        auth_plugin = self.get_auth_plugin("provider_text_token_format_url")

        auth_plugin.config.credentials = {"foo": "bar"}
        self.assertRaises(
            MisconfiguredError,
            auth_plugin.validate_config_credentials,
        )

    def test_plugins_auth_tokenauth_validate_credentials_format_url_ok(self):
        """TokenAuth.validate_credentials must be ok if it can format url"""
        auth_plugin = self.get_auth_plugin("provider_text_token_format_url")

        auth_plugin.config.credentials = {"foo": "bar", "username": "john"}
        auth_plugin.validate_config_credentials()

    @mock.patch("eodag.plugins.authentication.token.requests.post", autospec=True)
    def test_plugins_auth_tokenauth_text_token_authenticate(self, mock_requests_post):
        """TokenAuth.authenticate must return a RequestsTokenAuth object using text token"""
        auth_plugin = self.get_auth_plugin("provider_text_token_header")

        auth_plugin.config.credentials = {"foo": "bar"}

        # mock token post request response
        mock_requests_post.return_value = mock.Mock()
        mock_requests_post.return_value.text = "this_is_test_token"

        # check if returned auth object is an instance of requests.AuthBase
        auth = auth_plugin.authenticate()
        assert isinstance(auth, AuthBase)

        # check token post request call arguments
        args, kwargs = mock_requests_post.call_args
        assert args[0] == auth_plugin.config.auth_uri
        assert kwargs["data"] == auth_plugin.config.credentials
        assert kwargs["headers"] == auth_plugin.config.headers

        # check if token is integrated to the request
        req = mock.Mock(headers={})
        auth(req)
        assert req.headers["Authorization"] == "Bearer this_is_test_token"

    @mock.patch("eodag.plugins.authentication.token.requests.post", autospec=True)
    def test_plugins_auth_tokenauth_json_token_authenticate(self, mock_requests_post):
        """TokenAuth.authenticate must return a RequestsTokenAuth object using json token"""
        auth_plugin = self.get_auth_plugin("provider_json_token_simple_url")

        auth_plugin.config.credentials = {"foo": "bar"}

        # mock token post request response
        mock_requests_post.return_value = mock.Mock()
        mock_requests_post.return_value.json.return_value = {
            "not_token": "this_is_not_test_token",
            "token_is_here": "this_is_test_token",
        }

        # check if returned auth object is an instance of requests.AuthBase
        auth = auth_plugin.authenticate()
        assert isinstance(auth, AuthBase)

        # check if token is integrated to the request
        req = mock.Mock(headers={})
        auth(req)
        assert req.headers["Authorization"] == "Bearer this_is_test_token"
