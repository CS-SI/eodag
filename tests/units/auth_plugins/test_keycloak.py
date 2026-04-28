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

from datetime import timedelta
from unittest import mock

import responses
from pystac.utils import now_in_utc
from requests import Request
from requests.auth import AuthBase

from eodag.api.provider import ProvidersDict
from eodag.plugins.manager import PluginManager
from eodag.utils.exceptions import MisconfiguredError
from tests.units.auth_plugins.base import BaseAuthPluginTest


class TestAuthPluginKeycloakOIDCPasswordAuth(BaseAuthPluginTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        providers = ProvidersDict.from_configs(
            {
                "foo_provider": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "KeycloakOIDCPasswordAuth",
                        "oidc_config_url": "http://foo.bar/auth/realms/myrealm/.well-known/openid-configuration",
                        "client_id": "baz",
                        "realm": "qux",
                        "client_secret": "1234",
                        "token_provision": "qs",
                        "token_qs_key": "totoken",
                    },
                }
            }
        )
        cls.plugins_manager = PluginManager(providers)
        oidc_config = {
            "authorization_endpoint": "http://foo.bar/auth/realms/myrealm/protocol/openid-connect/auth",
            "token_endpoint": "http://foo.bar/auth/realms/myrealm/protocol/openid-connect/token",
            "jwks_uri": "http://foo.bar/auth/realms/myrealm/protocol/openid-connect/certs",
            "id_token_signing_alg_values_supported": ["RS256", "HS512"],
        }
        with mock.patch(
            "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.requests.get",
            autospec=True,
        ) as mock_request:
            mock_request.return_value.json.side_effect = [oidc_config, oidc_config]
            plugin_test = cls()
            plugin_test.plugins_manager = cls.plugins_manager
            cls.auth_plugin = cls.get_auth_plugin(plugin_test, "foo_provider")

    def tearDown(self):
        super(TestAuthPluginKeycloakOIDCPasswordAuth, self).tearDown()
        self.auth_plugin.access_token = ""
        self.auth_plugin.refresh_token = ""

    def test_plugins_auth_keycloak_validate_credentials(self):
        """KeycloakOIDCPasswordAuth.validate_credentials must raise exception if not well configured"""
        auth_plugin = self.auth_plugin

        # credentials missing
        self.assertRaises(MisconfiguredError, auth_plugin.validate_config_credentials)

        auth_plugin.config.credentials = {"username": "john"}

        # no error
        auth_plugin.validate_config_credentials()

        # oidc_config_url missing
        oidc_config_url = auth_plugin.config.__dict__.pop("oidc_config_url")
        self.assertRaises(MisconfiguredError, auth_plugin.validate_config_credentials)
        auth_plugin.config.oidc_config_url = oidc_config_url
        # client_id missing
        client_id = auth_plugin.config.__dict__.pop("client_id")
        self.assertRaises(MisconfiguredError, auth_plugin.validate_config_credentials)
        auth_plugin.config.client_id = client_id
        # client_secret missing
        client_secret = auth_plugin.config.__dict__.pop("client_secret")
        self.assertRaises(MisconfiguredError, auth_plugin.validate_config_credentials)
        auth_plugin.config.client_secret = client_secret
        # token_provision missing
        token_provision = auth_plugin.config.__dict__.pop("token_provision")
        self.assertRaises(MisconfiguredError, auth_plugin.validate_config_credentials)
        auth_plugin.config.token_provision = token_provision

        # no error
        auth_plugin.validate_config_credentials()

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcrefreshtokenbase.OIDCRefreshTokenBase.decode_jwt_token",
        autospec=True,
    )
    def test_plugins_auth_keycloak_authenticate(self, mock_decode):
        """KeycloakOIDCPasswordAuth.authenticate must query and store the token as expected"""
        auth_plugin = self.auth_plugin
        auth_plugin.config.credentials = {"username": "john"}
        mock_decode.return_value = {
            "exp": (now_in_utc() + timedelta(seconds=3600)).timestamp()
        }

        with responses.RequestsMock(assert_all_requests_are_fired=True) as rsps:
            url = "http://foo.bar/auth/realms/myrealm/protocol/openid-connect/token"
            req_kwargs = {
                "client_id": "baz",
                "client_secret": "1234",
                "grant_type": "password",
                "username": "john",
            }
            rsps.add(
                responses.POST,
                url,
                status=200,
                json={"access_token": "obtained-token", "expires_in": 3600},
                match=[responses.matchers.urlencoded_params_matcher(req_kwargs)],
            )

            # check if returned auth object is an instance of requests.AuthBase
            auth = auth_plugin.authenticate()
            assert isinstance(auth, AuthBase)
            self.assertEqual(auth.key, "totoken")
            self.assertEqual(auth.token, "obtained-token")
            self.assertEqual(auth.where, "qs")

        # check that token has been stored
        self.assertEqual(auth_plugin.access_token, "obtained-token")

        # check that stored token is used if available
        auth = auth_plugin.authenticate()
        # check if returned auth object is an instance of requests.AuthBase
        assert isinstance(auth, AuthBase)
        self.assertEqual(auth.key, "totoken")
        self.assertEqual(auth.token, "obtained-token")
        self.assertEqual(auth.where, "qs")

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcrefreshtokenbase.OIDCRefreshTokenBase.decode_jwt_token",
        autospec=True,
    )
    def test_plugins_auth_keycloak_authenticate_qs(self, mock_decode):
        """KeycloakOIDCPasswordAuth.authenticate must return a AuthBase object that will inject the token in a query-string"""  # noqa
        auth_plugin = self.auth_plugin
        auth_plugin.config.credentials = {"username": "john"}
        mock_decode.return_value = {
            "exp": (now_in_utc() + timedelta(seconds=3600)).timestamp()
        }

        with responses.RequestsMock(assert_all_requests_are_fired=True) as rsps:
            url = "http://foo.bar/auth/realms/myrealm/protocol/openid-connect/token"
            rsps.add(
                responses.POST,
                url,
                status=200,
                json={"access_token": "obtained-token", "expires_in": 3600},
            )

            # check if returned auth object is an instance of requests.AuthBase
            auth = auth_plugin.authenticate()
            assert isinstance(auth, AuthBase)

            # check if query string is integrated to the request
            req = Request("GET", "https://httpbin.org/get").prepare()
            auth(req)
            self.assertEqual(req.url, "https://httpbin.org/get?totoken=obtained-token")

            another_req = Request("GET", "https://httpbin.org/get?baz=qux").prepare()
            auth(another_req)
            self.assertEqual(
                another_req.url,
                "https://httpbin.org/get?baz=qux&totoken=obtained-token",
            )

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcrefreshtokenbase.OIDCRefreshTokenBase.decode_jwt_token",
        autospec=True,
    )
    def test_plugins_auth_keycloak_authenticate_header(self, mock_decode):
        """KeycloakOIDCPasswordAuth.authenticate must return a AuthBase object that will inject the token in the header"""  # noqa
        auth_plugin = self.auth_plugin
        auth_plugin.config.credentials = {"username": "john"}
        mock_decode.return_value = {
            "exp": (now_in_utc() + timedelta(seconds=3600)).timestamp()
        }

        # backup token_provision and change it to header mode
        token_provision_qs = auth_plugin.config.token_provision
        auth_plugin.config.token_provision = "header"

        with responses.RequestsMock(assert_all_requests_are_fired=True) as rsps:
            url = "http://foo.bar/auth/realms/myrealm/protocol/openid-connect/token"
            rsps.add(
                responses.POST,
                url,
                status=200,
                json={"access_token": "obtained-token", "expires_in": 3600},
            )

            # check if returned auth object is an instance of requests.AuthBase
            auth = auth_plugin.authenticate()
            assert isinstance(auth, AuthBase)

            # check if token header is integrated to the request
            req = Request("GET", "https://httpbin.org/get").prepare()
            auth(req)
            self.assertEqual(req.url, "https://httpbin.org/get")
            self.assertEqual(req.headers, {"Authorization": "Bearer obtained-token"})

            another_req = Request(
                "GET", "https://httpbin.org/get", headers={"existing-header": "value"}
            ).prepare()
            auth(another_req)
            self.assertEqual(
                another_req.headers,
                {"Authorization": "Bearer obtained-token", "existing-header": "value"},
            )

        auth_plugin.config.token_provision = token_provision_qs

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcrefreshtokenbase.OIDCRefreshTokenBase.decode_jwt_token",
        autospec=True,
    )
    def test_plugins_auth_keycloak_authenticate_use_refresh_token(self, mock_decode):
        """KeycloakOIDCPasswordAuth.authenticate must query and store the token as expected"""
        auth_plugin = self.auth_plugin
        auth_plugin.config.credentials = {"username": "john"}
        mock_decode.return_value = {"exp": now_in_utc().timestamp()}

        with responses.RequestsMock(assert_all_requests_are_fired=True) as rsps:
            url = "http://foo.bar/auth/realms/myrealm/protocol/openid-connect/token"
            req_kwargs = {
                "client_id": "baz",
                "client_secret": "1234",
                "grant_type": "password",
                "username": "john",
            }
            rsps.add(
                responses.POST,
                url,
                status=200,
                json={
                    "access_token": "obtained-token",
                    "expires_in": 0,
                    "refresh_expires_in": 1000,
                    "refresh_token": "abc",
                },
                match=[responses.matchers.urlencoded_params_matcher(req_kwargs)],
            )

            # check if returned auth object is an instance of requests.AuthBase
            auth = auth_plugin.authenticate()
            assert isinstance(auth, AuthBase)
            self.assertEqual(auth.key, "totoken")
            self.assertEqual(auth.token, "obtained-token")
            self.assertEqual(auth.where, "qs")

        # check that token and refresh token have been stored
        self.assertEqual(auth_plugin.access_token, "obtained-token")
        self.assertEqual("abc", auth_plugin.refresh_token)

        # check that stored token is used if new auth request fails
        with responses.RequestsMock(assert_all_requests_are_fired=True) as rsps:
            url = "http://foo.bar/auth/realms/myrealm/protocol/openid-connect/token"
            req_kwargs = {
                "client_id": "baz",
                "client_secret": "1234",
                "grant_type": "refresh_token",
                "refresh_token": "abc",
            }
            rsps.add(
                responses.POST,
                url,
                status=200,
                json={
                    "access_token": "new-token",
                    "expires_in": 0,
                    "refresh_expires_in": 1000,
                    "refresh_token": "abcd",
                },
                match=[responses.matchers.urlencoded_params_matcher(req_kwargs)],
            )

            # check if returned auth object is an instance of requests.AuthBase
            auth = auth_plugin.authenticate()
            assert isinstance(auth, AuthBase)
            self.assertEqual(auth.key, "totoken")
            self.assertEqual(auth.token, "new-token")
            self.assertEqual(auth.where, "qs")
