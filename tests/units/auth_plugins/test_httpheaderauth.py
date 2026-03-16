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
from eodag.api.provider import ProvidersDict
from eodag.plugins.authentication import HeaderAuth
from eodag.plugins.manager import PluginManager
from eodag.utils.exceptions import MisconfiguredError
from tests.units.auth_plugins.base import BaseAuthPluginTest


class TestAuthPluginHTTPHeaderAuth(BaseAuthPluginTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        providers = ProvidersDict.from_configs(
            {
                "provider_with_headers_in_conf": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "HTTPHeaderAuth",
                        "headers": {"X-API-Key": "{apikey}"},
                    },
                },
                "provider_with_no_header_in_conf": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "HTTPHeaderAuth",
                    },
                },
            }
        )
        cls.plugins_manager = PluginManager(providers)

    def test_plugins_auth_header_validate_credentials_empty(self):
        """HTTPHeaderAuth.validate_credentials must raise an error on empty credentials"""
        auth_plugin = self.get_auth_plugin("provider_with_headers_in_conf")
        self.assertRaises(
            MisconfiguredError,
            auth_plugin.validate_config_credentials,
        )

    def test_plugins_auth_header_validate_credentials_ok(self):
        """HTTPHeaderAuth.validate_credentials must be ok on non-empty credentials"""
        auth_plugin = self.get_auth_plugin("provider_with_headers_in_conf")

        auth_plugin.config.credentials = {"foo": "bar"}
        auth_plugin.validate_config_credentials()

    def test_plugins_auth_qsauth_authenticate(self):
        """HTTPHeaderAuth.authenticate must return a HeaderAuth object"""

        # auth with headers in conf and wrong credentials
        auth_plugin = self.get_auth_plugin("provider_with_headers_in_conf")
        auth_plugin.config.credentials = {"foo": "bar"}
        self.assertRaises(
            MisconfiguredError,
            auth_plugin.authenticate,
        )

        # auth with headers in conf
        auth_plugin = self.get_auth_plugin("provider_with_headers_in_conf")
        auth_plugin.config.credentials = {"apikey": "foo"}
        auth = auth_plugin.authenticate()
        self.assertIsInstance(auth, HeaderAuth)
        self.assertDictEqual(auth.auth_headers, {"X-API-Key": "foo"})

        # auth with headers in credentials
        auth_plugin = self.get_auth_plugin("provider_with_no_header_in_conf")
        auth_plugin.config.credentials = {"X-API-Key": "foo"}
        auth = auth_plugin.authenticate()
        self.assertIsInstance(auth, HeaderAuth)
        self.assertDictEqual(auth.auth_headers, {"X-API-Key": "foo"})
