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

from pystac.utils import now_in_utc
from requests import Response, Timeout
from requests.exceptions import RequestException

from eodag.api.provider import ProvidersDict
from eodag.plugins.authentication import CodeAuthorizedAuth
from eodag.plugins.manager import PluginManager
from eodag.utils import HTTP_REQ_TIMEOUT, USER_AGENT, MockResponse
from eodag.utils.exceptions import AuthenticationError, MisconfiguredError, RequestError
from tests.units.auth_plugins.base import BaseAuthPluginTest


class TestAuthPluginOIDCAuthorizationCodeFlowAuth(BaseAuthPluginTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        providers = ProvidersDict.from_configs(
            {
                "provider_token_provision_invalid": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "OIDCAuthorizationCodeFlowAuth",
                        "oidc_config_url": "http://auth.foo/auth/realms/myrealm/.well-known/openid-configuration",
                        "token_provision": "invalid",
                    },
                },
                "provider_token_qs_key_missing": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "OIDCAuthorizationCodeFlowAuth",
                        "oidc_config_url": "http://auth.foo/auth/realms/myrealm/.well-known/openid-configuration",
                        "token_provision": "qs",
                    },
                },
                "provider_authentication_uri_missing": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "OIDCAuthorizationCodeFlowAuth",
                        "oidc_config_url": "http://auth.foo/auth/realms/myrealm/.well-known/openid-configuration",
                        "redirect_uri": "http://provider.bar/redirect",
                        "client_id": "provider-bar-id",
                        "user_consent_needed": False,
                        "token_provision": "header",
                        "login_form_xpath": "//form[@id='form-login']",
                        "authentication_uri_source": "config",
                    },
                },
                "provider_user_consent": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "OIDCAuthorizationCodeFlowAuth",
                        "oidc_config_url": "http://auth.foo/auth/realms/myrealm/.well-known/openid-configuration",
                        "redirect_uri": "http://provider.bar/redirect",
                        "client_id": "provider-bar-id",
                        "user_consent_needed": True,
                        "user_consent_form_xpath": "//form[@id='form-user-consent']",
                        "user_consent_form_data": {
                            "const_key": "const_value",
                            "xpath_key": 'xpath(//input[@name="input_name"]/@value)',
                        },
                        "token_exchange_post_data_method": "data",
                        "token_key": "access_token",
                        "token_provision": "header",
                        "login_form_xpath": "//form[@id='form-login']",
                        "authentication_uri_source": "login-form",
                    },
                },
                "provider_client_sercret": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "OIDCAuthorizationCodeFlowAuth",
                        "oidc_config_url": "http://auth.foo/auth/realms/myrealm/.well-known/openid-configuration",
                        "redirect_uri": "http://provider.bar/redirect",
                        "client_id": "provider-bar-id",
                        "client_secret": "this-is-the-secret",
                        "user_consent_needed": False,
                        "token_exchange_post_data_method": "data",
                        "token_key": "access_token",
                        "token_provision": "header",
                        "login_form_xpath": "//form[@id='form-login']",
                        "authentication_uri_source": "login-form",
                    },
                },
                "provider_token_qs_key": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "OIDCAuthorizationCodeFlowAuth",
                        "oidc_config_url": "http://auth.foo/auth/realms/myrealm/.well-known/openid-configuration",
                        "redirect_uri": "http://provider.bar/redirect",
                        "client_id": "provider-bar-id",
                        "user_consent_needed": False,
                        "token_exchange_post_data_method": "data",
                        "token_key": "access_token",
                        "token_provision": "qs",
                        "token_qs_key": "totoken",
                        "login_form_xpath": "//form[@id='form-login']",
                        "authentication_uri_source": "login-form",
                    },
                },
                "provider_token_exchange_params": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "OIDCAuthorizationCodeFlowAuth",
                        "oidc_config_url": "http://auth.foo/auth/realms/myrealm/.well-known/openid-configuration",
                        "redirect_uri": "http://provider.bar/redirect",
                        "client_id": "provider-bar-id",
                        "user_consent_needed": False,
                        "token_exchange_post_data_method": "data",
                        "token_exchange_params": {
                            "redirect_uri": "new_redirect_uri",
                            "client_id": "new_client_id",
                        },
                        "token_key": "access_token",
                        "token_provision": "header",
                        "login_form_xpath": "//form[@id='form-login']",
                        "authentication_uri_source": "login-form",
                    },
                },
                "provider_ok": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "OIDCAuthorizationCodeFlowAuth",
                        "oidc_config_url": "http://auth.foo/auth/realms/myrealm/.well-known/openid-configuration",
                        "redirect_uri": "http://provider.bar/redirect",
                        "client_id": "provider-bar-id",
                        "user_consent_needed": False,
                        "token_exchange_post_data_method": "data",
                        "token_key": "access_token",
                        "token_provision": "header",
                        "login_form_xpath": "//form[@id='form-login']",
                        "authentication_uri_source": "login-form",
                        "additional_login_form_data": {
                            "const_key": "const_value",
                            "xpath_key": 'xpath(//input[@name="input_name"]/@value)',
                        },
                        "exchange_url_error_pattern": {
                            "TERMS_AND_CONDITIONS": "Terms and conditions are not accepted"
                        },
                    },
                },
            }
        )
        cls.plugins_manager = PluginManager(providers)

    def get_auth_plugin(self, provider):
        with mock.patch(
            "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.requests.get",
            autospec=True,
        ) as mock_request:
            oidc_config = {
                "authorization_endpoint": "http://foo.bar/auth/realms/myrealm/protocol/openid-connect/auth",
                "token_endpoint": "http://foo.bar/auth/realms/myrealm/protocol/openid-connect/token",
                "jwks_uri": "http://foo.bar/auth/realms/myrealm/protocol/openid-connect/certs",
                "id_token_signing_alg_values_supported": ["RS256", "HS512"],
            }
            mock_request.return_value.json.side_effect = [oidc_config, oidc_config]
            auth_plugin = super(
                TestAuthPluginOIDCAuthorizationCodeFlowAuth, self
            ).get_auth_plugin(provider)
            # reset token info
            auth_plugin.token_info = {}
            return auth_plugin

    def test_plugins_auth_codeflowauth_validate_credentials(self):
        """OIDCAuthorizationCodeFlowAuth.validate_credentials must raise an error if credentials are not valid"""
        # `token_provision` not valid
        auth_plugin = self.get_auth_plugin("provider_token_provision_invalid")
        auth_plugin.config.credentials = {"foo": "bar"}
        with self.assertRaises(MisconfiguredError) as context:
            auth_plugin.validate_config_credentials()
        self.assertTrue(
            '"token_provision" must be one of "qs" or "header"'
            in str(context.exception)
        )
        # `token_provision=="qs"` but `token_qs_key` is missing
        auth_plugin = self.get_auth_plugin("provider_token_qs_key_missing")
        auth_plugin.config.credentials = {"foo": "bar"}
        with self.assertRaises(MisconfiguredError) as context:
            auth_plugin.validate_config_credentials()
        self.assertTrue(
            '"qs" must have "token_qs_key" config parameter as well'
            in str(context.exception)
        )
        # Missing credentials
        auth_plugin = self.get_auth_plugin("provider_ok")
        with self.assertRaises(MisconfiguredError) as context:
            auth_plugin.validate_config_credentials()
        self.assertTrue("Missing credentials" in str(context.exception))

    def test_plugins_auth_codeflowauth_validate_credentials_ok(self):
        """OIDCAuthorizationCodeFlowAuth.validate_credentials must be ok on non-empty credentials"""
        auth_plugin = self.get_auth_plugin("provider_ok")

        auth_plugin.config.credentials = {"foo": "bar"}
        auth_plugin.validate_config_credentials()

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcrefreshtokenbase.OIDCRefreshTokenBase.decode_jwt_token",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.OIDCAuthorizationCodeFlowAuth"
        + "._get_token_with_refresh_token",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.OIDCAuthorizationCodeFlowAuth"
        + "._request_new_token",
        autospec=True,
    )
    def test_plugins_auth_codeflowauth_authenticate_ok(
        self, mock_request_new_token, mock_get_token_with_refresh_token, mock_decode
    ):
        """
        OIDCAuthorizationCodeFlowAuth.authenticate must check if the token is expired, call the correct
        function to get a new one and update the access token, all while considering the authentication
        token's expiration margin.
        """
        auth_plugin = self.get_auth_plugin("provider_ok")
        current_time = now_in_utc()
        json_response = {
            "access_token": "obtained-access-token",
            "expires_in": "3600",
            "refresh_expires_in": "7200",
            "refresh_token": "obtained-refresh-token",
        }
        mock_request_new_token.return_value = json_response
        mock_get_token_with_refresh_token.return_value = json_response
        expiration = current_time + timedelta(
            seconds=float(json_response["expires_in"])
        )
        mock_decode.return_value = {"exp": expiration.timestamp()}

        def _authenticate(
            called_once: mock.Mock, not_called: mock.Mock, access_token: str
        ) -> None:
            auth = auth_plugin.authenticate()
            called_once.assert_called_once()
            not_called.assert_not_called()
            self.assertEqual(auth.token, access_token)
            called_once.reset_mock()
            not_called.reset_mock()

        # No info: first time -> new auth
        _authenticate(
            mock_request_new_token,
            mock_get_token_with_refresh_token,
            json_response["access_token"],
        )
        # Check internal `token_info`` stores the new data
        self.assertEqual(
            auth_plugin.refresh_token,
            json_response["refresh_token"],
        )
        self.assertEqual(
            auth_plugin.access_token,
            json_response["access_token"],
        )
        self.assertEqual(auth_plugin.access_token_expiration, expiration)
        # refresh token expiration is calculated during test execution -> diff to previously
        # stored current time should be > refresh_expires_in (equals for windows due to less precision)
        self.assertGreaterEqual(
            auth_plugin.refresh_token_expiration.timestamp() - current_time.timestamp(),
            7200,
        )

        # Refresh token available but expired and access token expired-> new auth
        auth_plugin.refresh_token = "old-refresh-token"
        auth_plugin.refresh_token_expiration = current_time - timedelta(hours=3)
        auth_plugin.access_token = "old-access-token"
        auth_plugin.access_token_expiration = current_time - timedelta(hours=4)
        _authenticate(
            mock_request_new_token,
            mock_get_token_with_refresh_token,
            json_response["access_token"],
        )

        # Refresh token available but expires in a minute (60s) and access token expired-> new auth
        # 60s = the default time for the config parameter "token_expiration_margin"
        auth_plugin.refresh_token = "old-refresh-token"
        auth_plugin.refresh_token_expiration = current_time + timedelta(seconds=60)
        auth_plugin.access_token = "old-access-token"
        auth_plugin.access_token_expiration = current_time - timedelta(hours=4)
        _authenticate(
            mock_request_new_token,
            mock_get_token_with_refresh_token,
            json_response["access_token"],
        )

        # Refresh token *not* available and access token expired - new auth
        auth_plugin.access_token = "old-access-token"
        auth_plugin.refresh_token = ""
        auth_plugin.access_token_expiration = current_time - timedelta(hours=4)

        _authenticate(
            mock_request_new_token,
            mock_get_token_with_refresh_token,
            json_response["access_token"],
        )

        # Refresh token *not* available and access token expires in a minute (60s)- new auth
        # 60s = the default time for the config parameter "token_expiration_margin"
        auth_plugin.access_token = "old-access-token"
        auth_plugin.refresh_token = ""
        auth_plugin.access_token_expiration = current_time + timedelta(seconds=60)

        _authenticate(
            mock_request_new_token,
            mock_get_token_with_refresh_token,
            json_response["access_token"],
        )

        # Refresh token available and access token expired -> refresh
        auth_plugin.refresh_token = "old-refresh-token"
        auth_plugin.refresh_token_expiration = current_time + timedelta(hours=3)
        auth_plugin.access_token = "old-access-token"
        auth_plugin.access_token_expiration = current_time - timedelta(hours=4)
        _authenticate(
            mock_get_token_with_refresh_token,
            mock_request_new_token,
            json_response["access_token"],
        )

        # Refresh token available and access token expires in a minute (60s)-> refresh
        # 60s = the default time for the config parameter "token_expiration_margin"
        auth_plugin.refresh_token = "old-refresh-token"
        auth_plugin.refresh_token_expiration = current_time + timedelta(hours=3)
        auth_plugin.access_token = "old-access-token"
        auth_plugin.access_token_expiration = current_time + timedelta(seconds=60)
        _authenticate(
            mock_get_token_with_refresh_token,
            mock_request_new_token,
            json_response["access_token"],
        )

        # Both Refresh token and access token expire in a minute (60s)-> new auth
        # 60s = the default time for the config parameter "token_expiration_margin"
        auth_plugin.refresh_token = "old-refresh-token"
        auth_plugin.refresh_token_expiration = current_time + timedelta(seconds=60)
        auth_plugin.access_token = "old-access-token"
        auth_plugin.access_token_expiration = current_time + timedelta(seconds=60)
        _authenticate(
            mock_request_new_token,
            mock_get_token_with_refresh_token,
            json_response["access_token"],
        )

        # Access token not expired -> use already retrieved token
        auth_plugin.refresh_token = "old-refresh-token"
        auth_plugin.refresh_token_expiration = current_time + timedelta(hours=3)
        auth_plugin.access_token = "old-access-token"
        auth_plugin.access_token_expiration = current_time + timedelta(hours=2)
        auth = auth_plugin.authenticate()
        mock_request_new_token.assert_not_called()
        mock_get_token_with_refresh_token.assert_not_called()
        self.assertEqual(auth.token, auth_plugin.access_token)

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcrefreshtokenbase.OIDCRefreshTokenBase.decode_jwt_token",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.OIDCAuthorizationCodeFlowAuth"
        + ".compute_state",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.OIDCAuthorizationCodeFlowAuth"
        + ".exchange_code_for_token",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.OIDCAuthorizationCodeFlowAuth"
        + ".authenticate_user",
        autospec=True,
    )
    def test_plugins_auth_codeflowauth_authenticate_token_qs_key_ok(
        self,
        mock_authenticate_user,
        mock_exchange_code_for_token,
        mock_compute_state,
        mock_decode,
    ):
        """OIDCAuthorizationCodeFlowAuth.authenticate must return a CodeAuthorizedAuth object with a `key`
        if `token_provision=="qs"`"""
        auth_plugin = self.get_auth_plugin("provider_token_qs_key")
        state = "1234567890123456789012"
        exchange_url = auth_plugin.config.redirect_uri
        json_response = {
            "access_token": "obtained-access-token",
            "expires_in": "3600",
            "refresh_expires_in": "0",
            "refresh_token": "obtained-refresh-token",
        }
        mock_authenticate_user.return_value = mock.Mock(url=exchange_url)
        mock_compute_state.return_value = state
        mock_exchange_code_for_token.return_value = MockResponse(json_response, 200)
        mock_decode.return_value = {
            "exp": (now_in_utc() + timedelta(seconds=3600)).timestamp()
        }

        auth = auth_plugin.authenticate()

        mock_authenticate_user.assert_called_once_with(auth_plugin, state)
        mock_exchange_code_for_token.assert_called_once_with(
            auth_plugin, exchange_url, state
        )
        self.assertIsInstance(auth, CodeAuthorizedAuth)
        self.assertEqual(auth.token, json_response["access_token"])
        self.assertEqual(auth.where, "qs")
        self.assertEqual(auth.key, auth_plugin.config.token_qs_key)

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.OIDCAuthorizationCodeFlowAuth"
        + ".authenticate_user",
        autospec=True,
        return_value=mock.Mock(url="http://foo.bar", text=""),
    )
    def test_plugins_auth_codeflowauth_request_new_token_no_redirect(
        self,
        mock_authenticate_user,
    ):
        """OIDCAuthorizationCodeFlowAuth.request_new_token must raise and error if the provider doesn't redirect
        to `redirect_uri`"""
        auth_plugin = self.get_auth_plugin("provider_ok")
        self.assertRaises(
            AuthenticationError,
            auth_plugin._request_new_token,
        )

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.OIDCAuthorizationCodeFlowAuth"
        + ".compute_state",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.OIDCAuthorizationCodeFlowAuth"
        + ".exchange_code_for_token",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.OIDCAuthorizationCodeFlowAuth"
        + ".authenticate_user",
        autospec=True,
    )
    def test_plugins_auth_codeflowauth_request_new_token_ok(
        self,
        mock_authenticate_user,
        mock_exchange_code_for_token,
        mock_compute_state,
    ):
        """OIDCAuthorizationCodeFlowAuth.request_new_token must return the JSON response from the auth server"""
        auth_plugin = self.get_auth_plugin("provider_ok")
        state = "1234567890123456789012"
        exchange_url = auth_plugin.config.redirect_uri
        json_response = {
            "access_token": "obtained-access-token",
            "expires_in": "3600",
            "refresh_expires_in": "0",
            "refresh_token": "obtained-refresh-token",
        }
        mock_authenticate_user.return_value = mock.Mock(url=exchange_url)
        mock_compute_state.return_value = state
        mock_exchange_code_for_token.return_value.json.return_value = json_response

        resp = auth_plugin._request_new_token()

        mock_authenticate_user.assert_called_once_with(auth_plugin, state)
        mock_exchange_code_for_token.assert_called_once_with(
            auth_plugin, exchange_url, state
        )
        # Check returned value is the server's JSON response
        self.assertEqual(resp, json_response)

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.OIDCAuthorizationCodeFlowAuth"
        + ".grant_user_consent",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.OIDCAuthorizationCodeFlowAuth"
        + ".compute_state",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.OIDCAuthorizationCodeFlowAuth"
        + ".exchange_code_for_token",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.OIDCAuthorizationCodeFlowAuth"
        + ".authenticate_user",
        autospec=True,
    )
    def test_plugins_auth_codeflowauth_request_new_token_user_consent_needed_ok(
        self,
        mock_authenticate_user,
        mock_exchange_code_for_token,
        mock_compute_state,
        mock_grant_user_consent,
    ):
        """OIDCAuthorizationCodeFlowAuth.request_new_token must call `grant_user_consent`
        if `user_consent_needed==True`"""
        auth_plugin = self.get_auth_plugin("provider_user_consent")
        state = "1234567890123456789012"
        exchange_url = auth_plugin.config.redirect_uri
        json_response = {
            "access_token": "obtained-access-token",
            "expires_in": "3600",
            "refresh_expires_in": "0",
            "refresh_token": "obtained-refresh-token",
        }
        mock_authenticate_user.return_value = mock.Mock(
            url=auth_plugin.config.redirect_uri + "/user_consent"
        )
        mock_compute_state.return_value = state
        mock_exchange_code_for_token.return_value = MockResponse(json_response, 200)
        mock_grant_user_consent.return_value = mock.Mock(url=exchange_url)

        resp = auth_plugin._request_new_token()

        mock_authenticate_user.assert_called_once_with(auth_plugin, state)
        mock_grant_user_consent.assert_called_once_with(
            auth_plugin,
            mock_authenticate_user.return_value,
        )
        mock_exchange_code_for_token.assert_called_once_with(
            auth_plugin, exchange_url, state
        )
        self.assertEqual(resp, json_response)

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.OIDCAuthorizationCodeFlowAuth"
        + ".authenticate_user",
        autospec=True,
        return_value=mock.Mock(
            url="http://auth.foo/error?err_code=TERMS_AND_CONDITIONS"
        ),
    )
    def test_plugins_auth_codeflowauth_request_new_token_exchange_url_error_pattern(
        self,
        mock_authenticate_user,
    ):
        """OIDCAuthorizationCodeFlowAuth.request_new_token must raise an error if the exchange URL matches the
        patter `exchange_url_error_pattern`"""
        auth_plugin = self.get_auth_plugin("provider_ok")
        with self.assertRaises(AuthenticationError) as context:
            auth_plugin._request_new_token()
        self.assertEqual(
            "Terms and conditions are not accepted", str(context.exception)
        )

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.OIDCAuthorizationCodeFlowAuth"
        + ".authenticate_user",
        autospec=True,
    )
    def test_plugins_auth_codeflowauth_request_new_token_invalid_authentication(
        self, mock_authenticate_user
    ):
        """OIDCAuthorizationCodeFlowAuth.request_new_token must raise an authentication error if the username
        or password is invalid"""
        auth_plugin = self.get_auth_plugin("provider_ok")

        auth_plugin.config.credentials = {"username": "foo", "password": "bar"}
        auth_plugin.config.redirect_uri = "https://correct.redirect.uri"

        mock_response = MockResponse(json_data={"some": "data"})

        mock_response.url = "https://malicious-site.com/fake-auth"
        mock_response.text = "Invalid username or password"

        mock_authenticate_user.return_value = mock_response

        with self.assertRaises(AuthenticationError):
            auth_plugin._request_new_token()

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.OIDCAuthorizationCodeFlowAuth"
        + "._request_new_token",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.requests.Session.post",
        autospec=True,
    )
    def test_plugins_auth_codeflowauth_get_token_with_refresh_token_ok(
        self,
        mock_requests_post,
        mock_request_new_token,
    ):
        """OIDCAuthorizationCodeFlowAuth.get_token_with_refresh_token must call the token URI with a token refresh
        request and return the JSON response"""
        auth_plugin = self.get_auth_plugin("provider_ok")
        auth_plugin.refresh_token = "old-refresh-token"
        token_data = auth_plugin._prepare_token_post_data(
            {
                "refresh_token": auth_plugin.refresh_token,
                "grant_type": "refresh_token",
            }
        )
        json_response = {
            "access_token": "obtained-access-token",
            "expires_in": "3600",
            "refresh_expires_in": "0",
            "refresh_token": "obtained-refresh-token",
        }
        mock_requests_post.return_value = MockResponse(json_response, 200)

        resp = auth_plugin._get_token_with_refresh_token()
        post_request_kwargs = {
            auth_plugin.config.token_exchange_post_data_method: token_data
        }
        mock_requests_post.assert_called_once_with(
            mock.ANY,
            "http://foo.bar/auth/realms/myrealm/protocol/openid-connect/token",
            timeout=HTTP_REQ_TIMEOUT,
            verify=True,
            **post_request_kwargs,
        )
        mock_request_new_token.assert_not_called()
        self.assertEqual(resp, json_response)

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.OIDCAuthorizationCodeFlowAuth"
        + "._request_new_token",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.requests.Session.post",
        autospec=True,
    )
    def test_plugins_auth_codeflowauth_get_token_with_refresh_token_http_exception(
        self,
        mock_requests_post,
        mock_request_new_token,
    ):
        """OIDCAuthorizationCodeFlowAuth.get_token_with_refresh_token must call `request_new_token()` if the POST
        request raises an exception other than time out"""
        auth_plugin = self.get_auth_plugin("provider_ok")
        auth_plugin.token_info = {"refresh_token": "old-refresh-token"}
        mock_requests_post.return_value = MockResponse({"err": "message"}, 500)

        auth_plugin._get_token_with_refresh_token()
        mock_request_new_token.assert_called_once()

    @mock.patch(
        "eodag.plugins.authentication.token.tokenauth.requests.Session.post",
        autospec=True,
    )
    def test_plugins_auth_codeflowauth_grant_user_consent(
        self,
        mock_requests_post,
    ):
        """OIDCAuthorizationCodeFlowAuth.grant_user_consent must read the data from the config or from the consent
        form"""
        auth_plugin = self.get_auth_plugin("provider_user_consent")
        authentication_response = mock.Mock()
        authentication_response.text = """
            <html>
                <head></head>
                <body>
                    <form id="form-user-consent" method="post">
                        <input name="input_name" value="additional value" />
                    </form>
                </body>
            </html>
        """

        auth_plugin.grant_user_consent(authentication_response)
        mock_requests_post.assert_called_once_with(
            mock.ANY,
            "http://foo.bar/auth/realms/myrealm/protocol/openid-connect/auth",
            data={"const_key": "const_value", "xpath_key": "additional value"},
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            verify=True,
        )

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.requests.Session.post",
        side_effect=[RequestException("network error"), Timeout("timeout error")],
        autospec=True,
    )
    def test_plugins_auth_codeflowauth_grant_user_consent_error(
        self, mock_requests_post
    ):
        """OIDCAuthorizationCodeFlowAuth.grant_user_consent must raise a time out or request error if the POST
        request detects a timeout or request exception"""
        auth_plugin = self.get_auth_plugin("provider_user_consent")
        authentication_response = Response()

        authentication_response._content = b"""
            <html>
                <head></head>
                <body>
                    <form id="form-user-consent" method="post">
                        <input name="input_name" value="additional value" />
                    </form>
                </body>
            </html>
        """

        with self.assertRaises(RequestError):
            auth_plugin.grant_user_consent(authentication_response)

        with self.assertRaises(TimeoutError):
            auth_plugin.grant_user_consent(authentication_response)

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.requests.Session.get",
        autospec=True,
    )
    def test_plugins_auth_codeflowauth_authenticate_user_no_action(
        self,
        mock_requests_get,
    ):
        """OIDCAuthorizationCodeFlowAuth.authenticate_user raise an error if the authentication URI is not available.

        The configuration of the plugin used in this test instructs to retrieve the authentication URI
        from the login form of the authorization server."""
        auth_plugin = self.get_auth_plugin("provider_ok")
        auth_plugin.config.credentials = {"foo": "bar"}

        # Mock get request to the authorization URI (no action attribute in the form)
        mock_requests_get.return_value = mock.Mock()
        mock_requests_get.return_value.text = """
            <html>
                <head></head>
                <body>
                    <form id="form-login" method="post">
                        <input name="username" type="text" />
                        <input name="password" type="password" />
                        <input name="login" type="submit" value="Sign In" />
                    </form>
                </body>
            </html>
        """
        state = "1234567890123456789012"
        self.assertRaises(
            MisconfiguredError,
            auth_plugin.authenticate_user,
            state,
        )

        # First and only request: get the authorization URI
        mock_requests_get.assert_called_once_with(
            mock.ANY,
            "http://foo.bar/auth/realms/myrealm/protocol/openid-connect/auth",
            params={
                "client_id": auth_plugin.config.client_id,
                "response_type": auth_plugin.RESPONSE_TYPE,
                "scope": auth_plugin.SCOPE,
                "state": state,
                "redirect_uri": auth_plugin.config.redirect_uri,
            },
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            verify=True,
        )

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.requests.Session.get",
        autospec=True,
    )
    def test_plugins_auth_codeflowauth_authenticate_user_no_authentication_uri(
        self,
        mock_requests_get,
    ):
        """OIDCAuthorizationCodeFlowAuth.authenticate_user raise an error if the authentication URI is not available.

        In this test the authentication URI is in the plugin configuration."""
        auth_plugin = self.get_auth_plugin("provider_authentication_uri_missing")
        auth_plugin.config.credentials = {"foo": "bar"}

        # Mock get request to the authorization URI (no action attribute in the form)
        mock_requests_get.return_value = mock.Mock()
        mock_requests_get.return_value.text = """
            <html>
                <head></head>
                <body>
                    <form id="form-login" method="post">
                        <input name="username" type="text" />
                        <input name="password" type="password" />
                        <input name="login" type="submit" value="Sign In" />
                    </form>
                </body>
            </html>
        """
        state = "1234567890123456789012"
        self.assertRaises(
            MisconfiguredError,
            auth_plugin.authenticate_user,
            state,
        )

        # First and only request: get the authorization URI
        mock_requests_get.assert_called_once_with(
            mock.ANY,
            "http://foo.bar/auth/realms/myrealm/protocol/openid-connect/auth",
            params={
                "client_id": auth_plugin.config.client_id,
                "response_type": auth_plugin.RESPONSE_TYPE,
                "scope": auth_plugin.SCOPE,
                "state": state,
                "redirect_uri": auth_plugin.config.redirect_uri,
            },
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            verify=True,
        )

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.requests.Session.post",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.requests.Session.get",
        autospec=True,
    )
    def test_plugins_auth_codeflowauth_authenticate_user_ok(
        self,
        mock_requests_get,
        mock_requests_post,
    ):
        """OIDCAuthorizationCodeFlowAuth.authenticate_user must pass the credentials to the the authentication URI"""
        auth_plugin = self.get_auth_plugin("provider_ok")
        auth_plugin.config.credentials = {"foo": "bar"}

        # Mock get request to the authorization URI
        mock_requests_get.return_value = mock.Mock()
        mock_requests_get.return_value.text = """
            <html>
                <head></head>
                <body>
                    <form id="form-login" method="post" action="http://auth.foo/authentication">
                        <input name="username" type="text" />
                        <input name="password" type="password" />
                        <input name="login" type="submit" value="Sign In" />
                        <input name="input_name" type="hidden" value="additional value" />
                    </form>
                </body>
            </html>
        """
        mock_requests_post.return_value = mock.Mock()
        state = "1234567890123456789012"
        auth_response = auth_plugin.authenticate_user(state)

        # First request: get the authorization URI
        mock_requests_get.assert_called_once_with(
            mock.ANY,
            "http://foo.bar/auth/realms/myrealm/protocol/openid-connect/auth",
            params={
                "client_id": auth_plugin.config.client_id,
                "response_type": auth_plugin.RESPONSE_TYPE,
                "scope": auth_plugin.SCOPE,
                "state": state,
                "redirect_uri": auth_plugin.config.redirect_uri,
            },
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            verify=True,
        )
        # Second request: post to the authentication URI
        mock_requests_post.assert_called_once_with(
            mock.ANY,
            "http://auth.foo/authentication",
            data={
                "foo": "bar",
                "const_key": "const_value",
                "xpath_key": "additional value",
            },
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            verify=True,
        )
        # authenticate_user returns the authentication response
        self.assertEqual(mock_requests_post.return_value, auth_response)

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.requests.Session.post",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.requests.Session.get",
        autospec=True,
    )
    def test_plugins_auth_codeflowauth_authenticate_user_errors(
        self, mock_requests_get, mock_requests_post
    ):
        """OIDCAuthorizationCodeFlowAuth.authenticate_user must raise a time out or request error if the POST and GET
        requests detect a timeout or request exception"""
        auth_plugin = self.get_auth_plugin("provider_ok")

        state = "onvNjZbMkkjIpbnS"
        auth_plugin.config.credentials = {"username": "foo", "password": "bar"}

        mock_requests_get.side_effect = RequestException("network error")
        with self.assertRaises(RequestError):
            auth_plugin.authenticate_user(state)

        mock_requests_get.side_effect = Timeout("timeout error")
        with self.assertRaises(TimeoutError):
            auth_plugin.authenticate_user(state)

        mock_requests_get.return_value = mock.Mock()
        mock_requests_get.return_value.text = """
            <html>
                <head></head>
                <body>
                    <form id="form-login" method="post" action="/do_login">
                        <input name="username" type="text" />
                        <input name="password" type="password" />
                        <input name="login" type="submit" value="Sign In" />
                    </form>
                </body>
            </html>
        """
        mock_requests_get.side_effect = None

        mock_requests_post.side_effect = RequestException("network error")
        with self.assertRaises(RequestError):
            auth_plugin.authenticate_user(state)

        mock_requests_post.side_effect = Timeout("timeout error")
        with self.assertRaises(TimeoutError):
            auth_plugin.authenticate_user(state)

    def test_plugins_auth_codeflowauth_exchange_code_for_token_state_mismatch(
        self,
    ):
        """OIDCAuthorizationCodeFlowAuth.exchange_code_for_token must raise an error if the returned state is
        mismatched"""
        auth_plugin = self.get_auth_plugin("provider_ok")
        auth_plugin.config.credentials = {"foo": "bar"}

        state = "1234567890123456789012"
        authorized_url = f"{auth_plugin.config.redirect_uri}?state=mismatch"
        self.assertRaises(
            AuthenticationError,
            auth_plugin.exchange_code_for_token,
            authorized_url,
            state,
        )

    @mock.patch(
        "eodag.plugins.authentication.token.tokenauth.requests.Session.post",
        autospec=True,
    )
    def test_plugins_auth_codeflowauth_exchange_code_for_token_ok(
        self,
        mock_requests_post,
    ):
        """OIDCAuthorizationCodeFlowAuth.exchange_code_for_token must post to the `token_uri` the authorization code
        and the state"""
        auth_plugin = self.get_auth_plugin("provider_ok")
        mock_requests_post.return_value = mock.Mock()
        json_response = {
            "access_token": "obtained-access-token",
            "expires_in": "3600",
            "refresh_expires_in": "0",
            "refresh_token": "obtained-refresh-token",
        }
        mock_requests_post.return_value = MockResponse(json_response, 200)
        state = "1234567890123456789012"
        auth_code = "code_abcde"
        authorized_url = (
            f"{auth_plugin.config.redirect_uri}?state={state}&code={auth_code}"
        )
        auth_plugin.config.credentials = {"foo": "bar"}

        response = auth_plugin.exchange_code_for_token(authorized_url, state)
        self.assertEqual(response.json()["access_token"], json_response["access_token"])
        mock_requests_post.assert_called_once_with(
            mock.ANY,
            "http://foo.bar/auth/realms/myrealm/protocol/openid-connect/token",
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            data={
                "redirect_uri": auth_plugin.config.redirect_uri,
                "client_id": auth_plugin.config.client_id,
                "code": auth_code,
                "state": state,
                "grant_type": "authorization_code",
            },
            verify=True,
        )

    @mock.patch(
        "eodag.plugins.authentication.token.tokenauth.requests.Session.post",
        autospec=True,
    )
    def test_plugins_auth_codeflowauth_exchange_code_for_token_client_secret_ok(
        self,
        mock_requests_post,
    ):
        """OIDCAuthorizationCodeFlowAuth.exchange_code_for_token must authenticated with a BASIC Auth if the
        `client_secret` is known"""
        auth_plugin = self.get_auth_plugin("provider_client_sercret")
        mock_requests_post.return_value = mock.Mock()
        json_response = {
            "access_token": "obtained-access-token",
            "expires_in": "3600",
            "refresh_expires_in": "0",
            "refresh_token": "obtained-refresh-token",
        }
        mock_requests_post.return_value = MockResponse(json_response, 200)
        state = "1234567890123456789012"
        auth_code = "code_abcde"
        authorized_url = (
            f"{auth_plugin.config.redirect_uri}?state={state}&code={auth_code}"
        )
        auth_plugin.config.credentials = {"foo": "bar"}

        response = auth_plugin.exchange_code_for_token(authorized_url, state)
        self.assertEqual(response.json()["access_token"], json_response["access_token"])
        mock_requests_post.assert_called_once_with(
            mock.ANY,
            "http://foo.bar/auth/realms/myrealm/protocol/openid-connect/token",
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            data={
                "redirect_uri": auth_plugin.config.redirect_uri,
                "client_id": auth_plugin.config.client_id,
                "auth": (
                    auth_plugin.config.client_id,
                    auth_plugin.config.client_secret,
                ),
                "client_secret": auth_plugin.config.client_secret,
                "code": auth_code,
                "state": state,
                "grant_type": "authorization_code",
            },
            verify=True,
        )

    @mock.patch(
        "eodag.plugins.authentication.token.tokenauth.requests.Session.post",
        autospec=True,
    )
    def test_plugins_auth_codeflowauth_exchange_code_for_token_exchange_params_ok(
        self,
        mock_requests_post,
    ):
        """OIDCAuthorizationCodeFlowAuth.exchange_code_for_token must update the POST params if necessary"""
        auth_plugin = self.get_auth_plugin("provider_token_exchange_params")

        mock_requests_post.return_value = mock.Mock()
        json_response = {
            "access_token": "obtained-access-token",
            "expires_in": "3600",
            "refresh_expires_in": "0",
            "refresh_token": "obtained-refresh-token",
        }
        mock_requests_post.return_value = MockResponse(json_response, 200)
        state = "1234567890123456789012"
        auth_code = "code_abcde"
        authorized_url = (
            f"{auth_plugin.config.redirect_uri}?state={state}&code={auth_code}"
        )
        auth_plugin.config.credentials = {"foo": "bar"}

        response = auth_plugin.exchange_code_for_token(authorized_url, state)
        self.assertEqual(response.json()["access_token"], json_response["access_token"])
        mock_requests_post.assert_called_once_with(
            mock.ANY,
            "http://foo.bar/auth/realms/myrealm/protocol/openid-connect/token",
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            data={
                auth_plugin.config.token_exchange_params[
                    "redirect_uri"
                ]: auth_plugin.config.redirect_uri,
                auth_plugin.config.token_exchange_params[
                    "client_id"
                ]: auth_plugin.config.client_id,
                "code": auth_code,
                "state": state,
                "grant_type": "authorization_code",
            },
            verify=True,
        )

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.requests.Session.post",
        side_effect=[RequestException("network error"), Timeout("timeout error")],
        autospec=True,
    )
    def test_plugins_auth_codeflowauth_exchange_code_for_token_error(
        self, mock_requests_post
    ):
        """OIDCAuthorizationCodeFlowAuth.exchange_code_for_token must raise a time out or request error if the POST
        request detects a timeout or request exception"""
        auth_plugin = self.get_auth_plugin("provider_user_consent")

        authorized_url = "https://foo.eu?state=onvNjZbMkkjIpbnS&code=2ce1c24c"
        state = "onvNjZbMkkjIpbnS"

        with self.assertRaises(RequestError):
            auth_plugin.exchange_code_for_token(authorized_url, state)

        with self.assertRaises(TimeoutError):
            auth_plugin.exchange_code_for_token(authorized_url, state)
