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

import responses
from requests import Request
from requests.auth import AuthBase
from requests.exceptions import RequestException

from eodag.config import override_config_from_mapping
from eodag.plugins.authentication.openid_connect import CodeAuthorizedAuth
from eodag.utils.exceptions import RequestError
from tests.context import (
    HTTP_REQ_TIMEOUT,
    USER_AGENT,
    AuthenticationError,
    MisconfiguredError,
    PluginManager,
)


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
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "TokenAuth",
                        "auth_uri": "http://foo.bar",
                    },
                },
                "provider_text_token_format_url": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "TokenAuth",
                        "auth_uri": "http://foo.bar?username={username}",
                    },
                },
                "provider_text_token_header": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "TokenAuth",
                        "auth_uri": "http://foo.bar",
                        "headers": {
                            "Content-Type": "application/json;charset=UTF-8",
                            "Accept": "application/json",
                            "foo": "{foo}",
                        },
                    },
                },
                "provider_json_token_simple_url": {
                    "products": {"foo_product": {}},
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

    @mock.patch(
        "eodag.plugins.authentication.token.requests.Session.request", autospec=True
    )
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
        assert kwargs["url"] == auth_plugin.config.auth_uri
        assert kwargs["data"] == auth_plugin.config.credentials
        assert kwargs["headers"] == dict(auth_plugin.config.headers, **USER_AGENT)

        # check if token is integrated to the request
        req = mock.Mock(headers={})
        auth(req)
        assert req.headers["Authorization"] == "Bearer this_is_test_token"
        assert req.headers["foo"] == "bar"

    @mock.patch(
        "eodag.plugins.authentication.token.requests.Session.request", autospec=True
    )
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

    @mock.patch(
        "eodag.plugins.authentication.token.requests.Session.post", autospec=True
    )
    def test_plugins_auth_tokenauth_request_error(self, mock_requests_post):
        """TokenAuth.authenticate must raise an AuthenticationError if a request error occurs"""
        auth_plugin = self.get_auth_plugin("provider_json_token_simple_url")

        auth_plugin.config.credentials = {"foo": "bar"}

        # mock token post request response
        mock_requests_post.side_effect = RequestException

        self.assertRaises(
            AuthenticationError,
            auth_plugin.authenticate,
        )


class TestAuthPluginHttpQueryStringAuth(BaseAuthPluginTest):
    @classmethod
    def setUpClass(cls):
        super(TestAuthPluginHttpQueryStringAuth, cls).setUpClass()
        override_config_from_mapping(
            cls.providers_config,
            {
                "foo_provider": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "HttpQueryStringAuth",
                        "auth_uri": "http://foo.bar",
                    },
                },
            },
        )
        cls.plugins_manager = PluginManager(cls.providers_config)

    def test_plugins_auth_qsauth_validate_credentials_empty(self):
        """HttpQueryStringAuth.validate_credentials must raise an error on empty credentials"""
        auth_plugin = self.get_auth_plugin("foo_provider")
        self.assertRaises(
            MisconfiguredError,
            auth_plugin.validate_config_credentials,
        )

    def test_plugins_auth_qsauth_validate_credentials_ok(self):
        """HttpQueryStringAuth.validate_credentials must be ok on non-empty credentials"""
        auth_plugin = self.get_auth_plugin("foo_provider")

        auth_plugin.config.credentials = {"foo": "bar"}
        auth_plugin.validate_config_credentials()

    @mock.patch("eodag.plugins.authentication.qsauth.requests.get", autospec=True)
    def test_plugins_auth_qsauth_authenticate(self, mock_requests_get):
        """HttpQueryStringAuth.authenticate must return a QueryStringAuth object using query string"""
        auth_plugin = self.get_auth_plugin("foo_provider")

        auth_plugin.config.credentials = {"foo": "bar"}

        # check if returned auth object is an instance of requests.AuthBase
        auth = auth_plugin.authenticate()
        self.assertIsInstance(auth, AuthBase)

        # check if requests.get has been sent with right parameters
        mock_requests_get.assert_called_once_with(
            auth_plugin.config.auth_uri,
            timeout=HTTP_REQ_TIMEOUT,
            headers=USER_AGENT,
            auth=auth,
            verify=True,
        )

        # check auth query string
        self.assertEqual(auth.parse_args, auth_plugin.config.credentials)

        # check if query string is integrated to the request
        req = Request("GET", "https://httpbin.org/get").prepare()
        auth(req)
        self.assertEqual(req.url, "https://httpbin.org/get?foo=bar")

        another_req = Request("GET", "https://httpbin.org/get?baz=qux").prepare()
        auth(another_req)
        self.assertEqual(another_req.url, "https://httpbin.org/get?baz=qux&foo=bar")

    @mock.patch("eodag.plugins.authentication.qsauth.requests.get", autospec=True)
    def test_plugins_auth_qsauth_request_error(self, mock_requests_get):
        """HttpQueryStringAuth.authenticate must raise an AuthenticationError if a request error occurs"""
        auth_plugin = self.get_auth_plugin("foo_provider")

        auth_plugin.config.credentials = {"foo": "bar"}

        # mock auth get request response
        mock_requests_get.side_effect = RequestException

        self.assertRaises(
            AuthenticationError,
            auth_plugin.authenticate,
        )


class TestAuthPluginSASAuth(BaseAuthPluginTest):
    @classmethod
    def setUpClass(cls):
        super(TestAuthPluginSASAuth, cls).setUpClass()
        override_config_from_mapping(
            cls.providers_config,
            {
                "foo_provider": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "SASAuth",
                        "auth_uri": "http://foo.bar?href={url}",
                        "signed_url_key": "href",
                        "headers": {
                            "Ocp-Apim-Subscription-Key": "{apikey}",
                        },
                    },
                },
            },
        )
        cls.plugins_manager = PluginManager(cls.providers_config)

    def test_plugins_auth_sasauth_validate_credentials_ok(self):
        """SASAuth.validate_credentials must be ok on empty or non-empty credentials"""
        auth_plugin = self.get_auth_plugin("foo_provider")

        auth_plugin.config.credentials = {}
        auth_plugin.validate_config_credentials()
        auth_plugin.config.credentials = {"apikey": "foo"}
        auth_plugin.validate_config_credentials()

    @mock.patch("eodag.plugins.authentication.sas_auth.requests.get", autospec=True)
    def test_plugins_auth_sasauth_text_token_authenticate_with_credentials(
        self, mock_requests_get
    ):
        """When a user has credentials, SASAuth.authenticate must return
        a RequestsSASAuth object with his subscription key in its headers
        """
        auth_plugin = self.get_auth_plugin("foo_provider")

        auth_plugin.config.credentials = {"apikey": "foo"}

        # mock full signed url get request response
        mock_requests_get.return_value = mock.Mock()
        mock_requests_get.return_value.json.return_value = {
            "msft:expiry": "this_is_test_key_expiration_date",
            "href": "this_is_test_full_signed_url",
        }

        # check if returned auth object is an instance of requests.AuthBase
        auth = auth_plugin.authenticate()
        assert isinstance(auth, AuthBase)

        # check if the full signed url and the subscription key are integrated to the request
        url = "url"
        req = mock.Mock(headers={}, url=url)
        auth(req)
        assert req.url == "this_is_test_full_signed_url"
        assert req.headers["Ocp-Apim-Subscription-Key"] == "foo"

        # check SAS get request call arguments
        args, kwargs = mock_requests_get.call_args
        assert args[0] == auth_plugin.config.auth_uri.format(url=url)
        auth_plugin_headers = {"Ocp-Apim-Subscription-Key": "foo"}
        self.assertDictEqual(kwargs["headers"], dict(auth_plugin_headers, **USER_AGENT))

    @mock.patch("eodag.plugins.authentication.sas_auth.requests.get", autospec=True)
    def test_plugins_auth_sasauth_text_token_authenticate_without_credentials(
        self, mock_requests_get
    ):
        """When a user does not have credentials, SASAuth.authenticate must return
        a RequestsSASAuth object without his subscription key in its headers
        """
        auth_plugin = self.get_auth_plugin("foo_provider")

        auth_plugin.config.credentials = {}

        # mock full signed url get request response
        mock_requests_get.return_value = mock.Mock()
        mock_requests_get.return_value.json.return_value = {
            "msft:expiry": "this_is_test_key_expiration_date",
            "href": "this_is_test_full_signed_url",
        }

        # check if returned auth object is an instance of requests.AuthBase
        auth = auth_plugin.authenticate()
        assert isinstance(auth, AuthBase)

        # check if only the full signed url is integrated to the request
        url = "url"
        req = mock.Mock(headers={}, url=url)
        auth(req)
        assert req.url == "this_is_test_full_signed_url"

        # check SAS get request call arguments
        args, kwargs = mock_requests_get.call_args
        assert args[0] == auth_plugin.config.auth_uri.format(url=url)
        # check if headers only has the user agent as a request call argument
        assert kwargs["headers"] == USER_AGENT

    @mock.patch("eodag.plugins.authentication.sas_auth.requests.get", autospec=True)
    def test_plugins_auth_sasauth_request_error(self, mock_requests_get):
        """SASAuth.authenticate must raise an AuthenticationError if an error occurs"""
        auth_plugin = self.get_auth_plugin("foo_provider")

        auth_plugin.config.credentials = {"apikey": "foo"}

        # mock SAS get request response
        mock_requests_get.side_effect = RequestException()

        # check if returned auth object is an instance of requests.AuthBase
        auth = auth_plugin.authenticate()
        assert isinstance(auth, AuthBase)

        req = mock.Mock(headers={}, url="url")
        with self.assertRaises(AuthenticationError):
            auth(req)


class TestAuthPluginKeycloakOIDCPasswordAuth(BaseAuthPluginTest):
    @classmethod
    def setUpClass(cls):
        super(TestAuthPluginKeycloakOIDCPasswordAuth, cls).setUpClass()
        override_config_from_mapping(
            cls.providers_config,
            {
                "foo_provider": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "KeycloakOIDCPasswordAuth",
                        "auth_base_uri": "http://foo.bar",
                        "client_id": "baz",
                        "realm": "qux",
                        "client_secret": "1234",
                        "token_provision": "qs",
                        "token_qs_key": "totoken",
                    },
                },
            },
        )
        cls.plugins_manager = PluginManager(cls.providers_config)

    def test_plugins_auth_keycloak_validate_credentials(self):
        """KeycloakOIDCPasswordAuth.validate_credentials must raise exception if not well configured"""
        auth_plugin = self.get_auth_plugin("foo_provider")

        # credentials missing
        self.assertRaises(MisconfiguredError, auth_plugin.validate_config_credentials)

        auth_plugin.config.credentials = {"username": "john"}

        # no error
        auth_plugin.validate_config_credentials()

        # auth_base_uri missing
        auth_base_uri = auth_plugin.config.__dict__.pop("auth_base_uri")
        self.assertRaises(MisconfiguredError, auth_plugin.validate_config_credentials)
        auth_plugin.config.auth_base_uri = auth_base_uri
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

    def test_plugins_auth_keycloak_authenticate(self):
        """KeycloakOIDCPasswordAuth.authenticate must query and store the token as expected"""
        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {"username": "john"}

        with responses.RequestsMock(assert_all_requests_are_fired=True) as rsps:
            url = "http://foo.bar/realms/qux/protocol/openid-connect/token"
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
                json={"access_token": "obtained-token", "expires_in": 0},
                match=[responses.matchers.urlencoded_params_matcher(req_kwargs)],
            )

            # check if returned auth object is an instance of requests.AuthBase
            auth = auth_plugin.authenticate()
            assert isinstance(auth, AuthBase)
            self.assertEqual(auth.key, "totoken")
            self.assertEqual(auth.token, "obtained-token")
            self.assertEqual(auth.where, "qs")

        # check that token has been stored
        self.assertEqual(auth_plugin.retrieved_token, "obtained-token")

        # check that stored token is used if new auth request fails
        with responses.RequestsMock(assert_all_requests_are_fired=True) as rsps:
            url = "http://foo.bar/realms/qux/protocol/openid-connect/token"
            req_kwargs = {
                "client_id": "baz",
                "client_secret": "1234",
                "grant_type": "password",
                "username": "john",
            }
            rsps.add(
                responses.POST,
                url,
                status=401,
                json={"error": "not allowed"},
                match=[responses.matchers.urlencoded_params_matcher(req_kwargs)],
            )

            # check if returned auth object is an instance of requests.AuthBase
            auth = auth_plugin.authenticate()
            assert isinstance(auth, AuthBase)
            self.assertEqual(auth.key, "totoken")
            self.assertEqual(auth.token, "obtained-token")
            self.assertEqual(auth.where, "qs")

    def test_plugins_auth_keycloak_authenticate_qs(self):
        """KeycloakOIDCPasswordAuth.authenticate must return a AuthBase object that will inject the token in a query-string"""  # noqa
        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {"username": "john"}

        with responses.RequestsMock(assert_all_requests_are_fired=True) as rsps:
            url = "http://foo.bar/realms/qux/protocol/openid-connect/token"
            rsps.add(
                responses.POST,
                url,
                status=200,
                json={"access_token": "obtained-token", "expires_in": 0},
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

    def test_plugins_auth_keycloak_authenticate_header(self):
        """KeycloakOIDCPasswordAuth.authenticate must return a AuthBase object that will inject the token in the header"""  # noqa
        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {"username": "john"}

        # backup token_provision and change it to header mode
        token_provision_qs = auth_plugin.config.token_provision
        auth_plugin.config.token_provision = "header"

        with responses.RequestsMock(assert_all_requests_are_fired=True) as rsps:
            url = "http://foo.bar/realms/qux/protocol/openid-connect/token"
            rsps.add(
                responses.POST,
                url,
                status=200,
                json={"access_token": "obtained-token", "expires_in": 0},
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

    def test_plugins_auth_keycloak_authenticate_use_refresh_token(self):
        """KeycloakOIDCPasswordAuth.authenticate must query and store the token as expected"""
        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {"username": "john"}

        with responses.RequestsMock(assert_all_requests_are_fired=True) as rsps:
            url = "http://foo.bar/realms/qux/protocol/openid-connect/token"
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
        self.assertEqual(auth_plugin.retrieved_token, "obtained-token")
        assert auth_plugin.token_info
        self.assertEqual("abc", auth_plugin.token_info["refresh_token"])

        # check that stored token is used if new auth request fails
        with responses.RequestsMock(assert_all_requests_are_fired=True) as rsps:
            url = "http://foo.bar/realms/qux/protocol/openid-connect/token"
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


class TestAuthPluginOIDCAuthorizationCodeFlowAuth(BaseAuthPluginTest):
    @classmethod
    def setUpClass(cls):
        super(TestAuthPluginOIDCAuthorizationCodeFlowAuth, cls).setUpClass()
        override_config_from_mapping(
            cls.providers_config,
            {
                "provider_token_provision_invalid": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "OIDCAuthorizationCodeFlowAuth",
                        "token_provision": "invalid",
                    },
                },
                "provider_token_qs_key_missing": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "OIDCAuthorizationCodeFlowAuth",
                        "token_provision": "qs",
                    },
                },
                "provider_authentication_uri_missing": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "OIDCAuthorizationCodeFlowAuth",
                        "authorization_uri": "http://auth.foo/authorization",
                        "redirect_uri": "http://provider.bar/redirect",
                        "token_uri": "http://auth.foo/token",
                        "client_id": "provider-bar-id",
                        "user_consent_needed": False,
                        "token_provision": "header",
                        "login_form_xpath": "//form[@id='form-login']",
                        "authentication_uri_source": "config",
                    },
                },
                "provider_ok": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "OIDCAuthorizationCodeFlowAuth",
                        "authorization_uri": "http://auth.foo/authorization",
                        "redirect_uri": "http://provider.bar/redirect",
                        "token_uri": "http://auth.foo/token",
                        "client_id": "provider-bar-id",
                        "user_consent_needed": False,
                        "token_exchange_post_data_method": "data",
                        "token_key": "access_token",
                        "token_provision": "header",
                        "login_form_xpath": "//form[@id='form-login']",
                        "authentication_uri_source": "login-form",
                        "additional_login_form_data": {
                            "const_key": "const_value",
                            # FIXME "xpath_key": 'xpath(//input[@name="input_name"]/@value)'
                        },
                    },
                },
            },
        )
        cls.plugins_manager = PluginManager(cls.providers_config)

    def test_plugins_auth_codeflowauth_validate_credentials(self):
        """OIDCAuthorizationCodeFlowAuth.validate_credentials must raise an error if credentials are not valid"""
        # `token_provision` not valid
        auth_plugin = self.get_auth_plugin("provider_token_provision_invalid")
        self.assertRaises(
            MisconfiguredError,
            auth_plugin.validate_config_credentials,
        )
        # `token_provision=="qs"` but `token_qs_key` is missing
        auth_plugin = self.get_auth_plugin("provider_token_qs_key_missing")
        self.assertRaises(
            MisconfiguredError,
            auth_plugin.validate_config_credentials,
        )
        # Missing credentials
        auth_plugin = self.get_auth_plugin("provider_ok")
        self.assertRaises(
            MisconfiguredError,
            auth_plugin.validate_config_credentials,
        )

    def test_plugins_auth_codeflowauth_validate_credentials_ok(self):
        """OIDCAuthorizationCodeFlowAuth.validate_credentials must be ok on non-empty credentials"""
        auth_plugin = self.get_auth_plugin("provider_ok")

        auth_plugin.config.credentials = {"foo": "bar"}
        auth_plugin.validate_config_credentials()

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth.authenticate_user",
        autospec=True,
        return_value=mock.Mock(url="http://foo.bar"),
    )
    def test_plugins_auth_codeflowauth_authenticate_no_redirect(
        self,
        mock_authenticate_user,
    ):
        """OIDCAuthorizationCodeFlowAuth.authenticate must raise and error if the provider doesn't redirect
        to the given URI"""
        auth_plugin = self.get_auth_plugin("provider_ok")
        self.assertRaises(
            AuthenticationError,
            auth_plugin.authenticate,
        )

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth.compute_state",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth.exchange_code_for_token",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth.authenticate_user",
        autospec=True,
    )
    def test_plugins_auth_codeflowauth_authenticate_ok(
        self,
        mock_authenticate_user,
        mock_exchange_code_for_token,
        mock_compute_state,
    ):
        """OIDCAuthorizationCodeFlowAuth.authenticate must return a CodeAuthorizedAuth object"""
        auth_plugin = self.get_auth_plugin("provider_ok")
        state = "1234567890123456789012"
        exchange_url = auth_plugin.config.redirect_uri
        token = "token123"
        mock_authenticate_user.return_value = mock.Mock(url=exchange_url)
        mock_compute_state.return_value = state
        mock_exchange_code_for_token.return_value = token

        auth = auth_plugin.authenticate()

        mock_authenticate_user.assert_called_once_with(auth_plugin, state)
        mock_exchange_code_for_token.assert_called_once_with(
            auth_plugin, exchange_url, state
        )
        self.assertIsInstance(auth, CodeAuthorizedAuth)
        self.assertEqual(auth.token, token)
        self.assertEqual(auth.where, "header")
        self.assertIsNone(auth.key)

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.Session.get",
        autospec=True,
    )
    def test_plugins_auth_codeflowauth_authenticate_user_no_login_forms(
        self,
        mock_requests_post,
    ):
        """OIDCAuthorizationCodeFlowAuth.authenticate_user must assume user is already logged in if there is
        no form in the reply"""
        auth_plugin = self.get_auth_plugin("provider_ok")
        auth_plugin.config.credentials = {"foo": "bar"}

        # mock token post request response
        mock_requests_post.return_value = mock.Mock()
        mock_requests_post.return_value.text = """
            <html>
                <head><title>No forms</title></head>
                <body><p>Hello</p></body>
            </html>
        """
        state = "1234567890123456789012"
        auth = auth_plugin.authenticate_user(state)
        self.assertEqual(auth, mock_requests_post.return_value)

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.Session.get",
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
                <head><title>No forms</title></head>
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
            RequestError,
            auth_plugin.authenticate_user,
            state,
        )

        # First and only request: get the authorization URI
        mock_requests_get.assert_called_once_with(
            mock.ANY,
            auth_plugin.config.authorization_uri,
            params={
                "client_id": auth_plugin.config.client_id,
                "response_type": auth_plugin.RESPONSE_TYPE,
                "scope": auth_plugin.SCOPE,
                "state": state,
                "redirect_uri": auth_plugin.config.redirect_uri,
            },
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
        )

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.Session.get",
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
                <head><title>No forms</title></head>
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
            auth_plugin.config.authorization_uri,
            params={
                "client_id": auth_plugin.config.client_id,
                "response_type": auth_plugin.RESPONSE_TYPE,
                "scope": auth_plugin.SCOPE,
                "state": state,
                "redirect_uri": auth_plugin.config.redirect_uri,
            },
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
        )

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.Session.post",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.Session.get",
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
                <head><title>No forms</title></head>
                <body>
                    <form id="form-login" method="post" action="http://auth.foo/authentication">
                        <input name="username" type="text" />
                        <input name="password" type="password" />
                        <input name="login" type="submit" value="Sign In" />
                        <input name="input_name" type="hidden" value="hidden value" />
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
            auth_plugin.config.authorization_uri,
            params={
                "client_id": auth_plugin.config.client_id,
                "response_type": auth_plugin.RESPONSE_TYPE,
                "scope": auth_plugin.SCOPE,
                "state": state,
                "redirect_uri": auth_plugin.config.redirect_uri,
            },
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
        )
        # Second request: post to the authentication URI
        mock_requests_post.assert_called_once_with(
            mock.ANY,
            "http://auth.foo/authentication",
            data={
                "foo": "bar",
                "const_key": "const_value",
                # FIXME "xpath_name": "hidden value",
            },
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
        )
        # authenticate_user returns the authentication response
        self.assertEqual(mock_requests_post.return_value, auth_response)

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
        "eodag.plugins.authentication.token.requests.Session.post", autospec=True
    )
    def test_plugins_auth_codeflowauth_exchange_code_for_token_ok(
        self,
        mock_requests_post,
    ):
        """OIDCAuthorizationCodeFlowAuth.exchange_code_for_token must post to the token_uri the authorization code
        and the state"""
        auth_plugin = self.get_auth_plugin("provider_ok")
        mock_requests_post.return_value = mock.Mock()
        access_token = "token_12345"
        mock_requests_post.return_value.json.return_value = {
            "access_token": access_token
        }
        state = "1234567890123456789012"
        auth_code = "code_abcde"
        authorized_url = (
            f"{auth_plugin.config.redirect_uri}?state={state}&code={auth_code}"
        )
        auth_plugin.config.credentials = {"foo": "bar"}

        returned_access_token = auth_plugin.exchange_code_for_token(
            authorized_url, state
        )
        self.assertEqual(returned_access_token, access_token)
        mock_requests_post.assert_called_once_with(
            mock.ANY,
            auth_plugin.config.token_uri,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            data={
                "redirect_uri": auth_plugin.config.redirect_uri,
                "client_id": auth_plugin.config.client_id,
                "code": auth_code,
                "state": state,
                "grant_type": "authorization_code",
            },
        )
