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

import pickle
from datetime import datetime
from unittest import mock

import responses
from requests.auth import AuthBase

from eodag.api.provider import ProvidersDict
from eodag.plugins.manager import PluginManager
from eodag.utils import HTTP_REQ_TIMEOUT, USER_AGENT
from eodag.utils.exceptions import AuthenticationError, MisconfiguredError
from tests.units.auth_plugins.base import BaseAuthPluginTest


class TestAuthPluginTokenAuth(BaseAuthPluginTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        providers = ProvidersDict.from_configs(
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
                "provider_text_token_retrieve_header": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "TokenAuth",
                        "auth_uri": "http://foo.bar",
                        "headers": {
                            "Content-Type": "application/json;charset=UTF-8",
                            "Accept": "application/json",
                            "foo": "{foo}",
                        },
                        "retrieve_headers": {
                            "Authorization": "Bearer {auth_for_token}",
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
                "provider_json_token_with_expiration": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "TokenAuth",
                        "auth_uri": "http://foo.bar",
                        "token_type": "json",
                        "token_key": "token_is_here",
                        "token_expiration_key": "token_expiration",
                    },
                },
                "provider_json_token_with_refresh": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "TokenAuth",
                        "auth_uri": "http://foo.bar",
                        "refresh_uri": "http://baz.qux",
                        "token_type": "json",
                        "token_key": "token_is_here",
                        "refresh_token_key": "refresh_token_is_here",
                        "token_expiration_key": "token_expiration",
                    },
                },
                "provider_text_token_req_data": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "TokenAuth",
                        "auth_uri": "http://foo.bar",
                        "req_data": {"grant_type": "client_credentials"},
                    },
                },
                "provider_text_token_get_method": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "TokenAuth",
                        "auth_uri": "http://foo.bar",
                        "request_method": "GET",
                        "auth_tuple": ["username", "password1", "password2"],
                    },
                },
                "provider_text_token_auth_error_code": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "TokenAuth",
                        "auth_uri": "http://foo.bar",
                        "auth_error_code": 401,
                    },
                },
                "provider_text_token_post_credentials_true": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "TokenAuth",
                        "auth_uri": "http://foo.bar?username={username}",
                        "post_credentials": True,
                    },
                },
                "provider_text_token_post_credentials_false": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "TokenAuth",
                        "auth_uri": "http://foo.bar",
                        "post_credentials": False,
                    },
                },
            }
        )

        cls.plugins_manager = PluginManager(providers)

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
        "eodag.plugins.authentication.token.tokenauth.requests.Session.request",
        autospec=True,
    )
    def test_plugins_auth_tokenauth_authenticate_format_url_ok(self, mock_request):
        """TokenAuth.authenticate must be ok if it can format url"""
        auth_plugin = self.get_auth_plugin("provider_text_token_format_url")

        auth_plugin.config.credentials = {"foo": "bar", "username": "jo{hn"}
        auth_plugin.authenticate()

        # validate_config_credentials should have been called a 2nd time in authenticate
        # to format already parsed auth_uri (would fail as credentials contain a non-escaped '{' character)
        auth_plugin.authenticate()

    @mock.patch(
        "eodag.plugins.authentication.token.tokenauth.requests.Session.request",
        autospec=True,
    )
    def test_plugins_auth_tokenauth_text_token_authenticate(self, mock_requests_post):
        """TokenAuth.authenticate must return a RequestsTokenAuth object using text token"""
        auth_plugin = self.get_auth_plugin("provider_text_token_header")

        auth_plugin.config.credentials = {"foo": "bar", "baz": "qux"}

        # mock token post request response
        mock_requests_post.return_value = mock.Mock()
        mock_requests_post.return_value.text = "this_is_test_token"

        # check if returned auth object is an instance of requests.AuthBase
        auth = auth_plugin.authenticate()
        self.assertTrue(isinstance(auth, AuthBase))

        # token was set in the plugin
        self.assertEqual(auth_plugin.token, "this_is_test_token")

        # check token post request call arguments
        args, kwargs = mock_requests_post.call_args
        self.assertEqual(kwargs["url"], auth_plugin.config.auth_uri)
        self.assertDictEqual(kwargs["data"], {"foo": "bar", "baz": "qux"})
        self.assertNotIn("auth", kwargs)
        self.assertDictEqual(
            kwargs["headers"], dict(auth_plugin.config.headers, **USER_AGENT)
        )

        # check if token is integrated to the request
        req = mock.Mock(headers={})
        auth(req)
        self.assertEqual(req.headers["Authorization"], "Bearer this_is_test_token")
        self.assertEqual(req.headers["foo"], "bar")

    @mock.patch(
        "eodag.plugins.authentication.token.tokenauth.requests.Session.request",
        autospec=True,
    )
    def test_plugins_auth_tokenauth_text_token_retrieve_authenticate(
        self, mock_requests_post
    ):
        """TokenAuth.authenticate must return a RequestsTokenAuth object using text token and a retrieve headers"""
        auth_plugin = self.get_auth_plugin("provider_text_token_retrieve_header")

        auth_plugin.config.credentials = {
            "foo": "bar",
            "baz": "qux",
            "auth_for_token": "a_token",
        }

        # mock token post request response
        mock_requests_post.return_value = mock.Mock()
        mock_requests_post.return_value.text = "this_is_test_token"

        # check if returned auth object is an instance of requests.AuthBase
        auth = auth_plugin.authenticate()
        self.assertTrue(isinstance(auth, AuthBase))

        # check token post request call arguments
        args, kwargs = mock_requests_post.call_args
        self.assertEqual(kwargs["url"], auth_plugin.config.auth_uri)
        self.assertDictEqual(
            kwargs["data"], {"foo": "bar", "baz": "qux", "auth_for_token": "a_token"}
        )
        self.assertNotIn("auth", kwargs)
        self.assertDictEqual(
            kwargs["headers"], dict(auth_plugin.config.retrieve_headers, **USER_AGENT)
        )

        # check if token is integrated to the request
        req = mock.Mock(headers={})
        auth(req)
        self.assertEqual(req.headers["Authorization"], "Bearer this_is_test_token")
        self.assertEqual(req.headers["foo"], "bar")

    @mock.patch(
        "eodag.plugins.authentication.token.tokenauth.requests.Session.request",
        autospec=True,
    )
    def test_plugins_auth_tokenauth_json_token_authenticate(self, mock_requests_post):
        """TokenAuth.authenticate must return a RequestsTokenAuth object using json token"""
        auth_plugin = self.get_auth_plugin("provider_json_token_with_expiration")

        auth_plugin.config.credentials = {"foo": "bar", "baz": "qux"}

        # mock token post request response
        mock_requests_post.return_value = mock.Mock()
        mock_requests_post.return_value.json.return_value = {
            "not_token": "this_is_not_test_token",
            "token_is_here": "this_is_test_token",
            "token_expiration": 1000,
        }

        # check if returned auth object is an instance of requests.AuthBase
        auth = auth_plugin.authenticate()
        assert isinstance(auth, AuthBase)

        # check if token is integrated to the request
        req = mock.Mock(headers={})
        auth(req)
        assert req.headers["Authorization"] == "Bearer this_is_test_token"

    @mock.patch(
        "eodag.plugins.authentication.token.tokenauth.requests.Session.request",
        autospec=True,
    )
    def test_plugins_auth_tokenauth_json_token_with_expiration_time(
        self, mock_requests_post
    ):
        """TokenAuth.authenticate must return a RequestsTokenAuth object using json token
        If there is an existing, valid token this token must be used
        """
        auth_plugin = self.get_auth_plugin("provider_json_token_with_expiration")
        auth_plugin.__init__(
            auth_plugin.provider, auth_plugin.config
        )  # ensure that variables are reset

        auth_plugin.config.credentials = {"foo": "bar", "baz": "qux"}

        # mock token post request response
        mock_requests_post.return_value = mock.Mock()
        mock_requests_post.return_value.json.return_value = {
            "not_token": "this_is_not_test_token",
            "token_is_here": "this_is_test_token",
            "token_expiration": 1000,
        }

        # check if returned auth object is an instance of requests.AuthBase
        auth = auth_plugin.authenticate()
        self.assertTrue(isinstance(auth, AuthBase))
        self.assertEqual("this_is_test_token", auth_plugin.token)
        # token request should be sent
        mock_requests_post.assert_called_once_with(
            mock.ANY,
            method="POST",
            url=auth_plugin.config.auth_uri,
            timeout=HTTP_REQ_TIMEOUT,
            headers=USER_AGENT,
            data=auth_plugin.config.credentials,
            verify=True,
        )
        mock_requests_post.reset_mock()
        # second call should use existing token
        auth = auth_plugin.authenticate()
        self.assertTrue(isinstance(auth, AuthBase))
        mock_requests_post.assert_not_called()
        # reset expiration -> token should be fetched again
        auth_plugin.token_expiration = datetime.now()
        mock_requests_post.return_value.json.return_value = {
            "not_token": "this_is_not_test_token",
            "token_is_here": "this_is_a_new_token",
            "token_expiration": 1000,
        }
        auth = auth_plugin.authenticate()
        self.assertTrue(isinstance(auth, AuthBase))
        self.assertEqual("this_is_a_new_token", auth_plugin.token)
        mock_requests_post.assert_called_once_with(
            mock.ANY,
            method="POST",
            url=auth_plugin.config.auth_uri,
            timeout=HTTP_REQ_TIMEOUT,
            headers=USER_AGENT,
            data=auth_plugin.config.credentials,
            verify=True,
        )

    @mock.patch(
        "eodag.plugins.authentication.token.tokenauth.requests.Session.request",
        autospec=True,
    )
    def test_plugins_auth_tokenauth_json_token_with_refresh(self, mock_requests_post):
        """
        TokenAuth.authenticate must return a RequestsTokenAuth object using json token.
        This token can be refreshed.
        """
        auth_plugin = self.get_auth_plugin("provider_json_token_with_refresh")

        auth_plugin.config.credentials = {
            "foo": "bar",
            "baz": "qux",
            "client_id": "id",
            "client_secret": "secret",
        }

        # mock token post request response
        mock_requests_post.return_value = mock.Mock()
        mock_requests_post.return_value.json.return_value = {
            "not_token": "this_is_not_test_token",
            "token_is_here": "this_is_test_token",
            "refresh_token_is_here": "first_refresh_token",
            "token_expiration": 1000,
        }

        # check if returned auth object is an instance of requests.AuthBase
        auth = auth_plugin.authenticate()
        assert isinstance(auth, AuthBase)

        # check if token is integrated to the request
        req = mock.Mock(headers={})
        auth(req)
        assert req.headers["Authorization"] == "Bearer this_is_test_token"

        # token request should be sent
        mock_requests_post.assert_called_once_with(
            mock.ANY,
            method="POST",
            url=auth_plugin.config.auth_uri,
            timeout=HTTP_REQ_TIMEOUT,
            headers=USER_AGENT,
            data=auth_plugin.config.credentials,
            verify=True,
        )

        # Serialize then deserialize the auth plugin, check that it still works the same
        auth_plugin = pickle.loads(pickle.dumps(auth_plugin))

        mock_requests_post.reset_mock()
        # second call should use existing token
        auth = auth_plugin.authenticate()
        assert isinstance(auth, AuthBase)
        mock_requests_post.assert_not_called()

        # reset expiration -> token should be fetched again
        # The refresh token mechanism will be used.
        auth_plugin.token_expiration = datetime.now()
        mock_requests_post.return_value.json.return_value = {
            "not_token": "this_is_not_test_token",
            "token_is_here": "this_is_a_refreshed_token",
            "refresh_token_is_here": "second_refresh_token",  # used to refresh again the token (not used in this test)
            "token_expiration": 1000,
        }
        auth = auth_plugin.authenticate()

        assert isinstance(auth, AuthBase)
        req = mock.Mock(headers={})
        auth(req)
        assert req.headers["Authorization"] == "Bearer this_is_a_refreshed_token"

        mock_requests_post.assert_called_once_with(
            mock.ANY,
            method="POST",
            url=auth_plugin.config.refresh_uri,
            timeout=HTTP_REQ_TIMEOUT,
            headers=USER_AGENT,
            # only client_id and secret are passed + the refresh token from the first call
            # and the grant type
            data={
                "grant_type": "refresh_token",  # hardcoded
                "client_id": "id",
                "client_secret": "secret",
                "refresh_token": "first_refresh_token",
            },
            verify=True,
            json=None,
        )

    @mock.patch(
        "eodag.plugins.authentication.token.tokenauth.requests.Session.request",
        autospec=True,
    )
    def test_plugins_auth_tokenauth_with_data_authenticate(self, mock_requests_post):
        """TokenAuth.authenticate must return a RequestsTokenAuth object when 'data' request argument is required"""
        auth_plugin = self.get_auth_plugin("provider_text_token_req_data")

        auth_plugin.config.credentials = {"foo": "bar", "baz": "qux"}

        # mock token post request response
        mock_requests_post.return_value = mock.Mock()
        mock_requests_post.return_value.text = "this_is_test_token"

        # check if returned auth object is an instance of requests.AuthBase
        auth = auth_plugin.authenticate()
        self.assertTrue(isinstance(auth, AuthBase))

        # check token post request call arguments
        args, kwargs = mock_requests_post.call_args
        self.assertEqual(kwargs["url"], auth_plugin.config.auth_uri)
        self.assertDictEqual(
            kwargs["data"],
            {"grant_type": "client_credentials", "foo": "bar", "baz": "qux"},
        )
        self.assertNotIn("auth", kwargs)
        self.assertDictEqual(kwargs["headers"], USER_AGENT)

        # check if token is integrated to the request
        req = mock.Mock(headers={})
        auth(req)
        self.assertEqual(req.headers["Authorization"], "Bearer this_is_test_token")

    @mock.patch(
        "eodag.plugins.authentication.token.tokenauth.requests.Session.request",
        autospec=True,
    )
    def test_plugins_auth_tokenauth_get_method_auth_tuple(self, mock_requests_get):
        """TokenAuth.authenticate must return a RequestsTokenAuth object with 'GET' method request and auth tuple"""
        auth_plugin = self.get_auth_plugin("provider_text_token_get_method")

        auth_plugin.config.credentials = {
            "username": "bar",
            "password1": "qux",
            "password2": "quux",
        }

        # mock token get request response
        mock_requests_get.return_value = mock.Mock()
        mock_requests_get.return_value.text = "this_is_test_token"

        # check if returned auth object is an instance of requests.AuthBase
        auth = auth_plugin.authenticate()
        self.assertTrue(isinstance(auth, AuthBase))

        # check token get request call arguments
        args, kwargs = mock_requests_get.call_args
        self.assertEqual(kwargs["url"], auth_plugin.config.auth_uri)
        self.assertNotIn("data", kwargs)
        self.assertTupleEqual(kwargs["auth"], ("bar", "qux", "quux"))
        self.assertDictEqual(kwargs["headers"], USER_AGENT)

        # check if token is integrated to the request
        req = mock.Mock(headers={})
        auth(req)
        self.assertEqual(req.headers["Authorization"], "Bearer this_is_test_token")

    @mock.patch(
        "eodag.plugins.authentication.token.tokenauth.requests.Session.request",
        autospec=True,
    )
    def test_plugins_auth_tokenauth_get_method_auth_tuple_incomplete(
        self, mock_requests_get
    ):
        """TokenAuth.authenticate must fail with 'GET' method request and incomplete auth tuple"""
        auth_plugin = self.get_auth_plugin("provider_text_token_get_method")

        auth_plugin.config.credentials = {"username": "bar", "password1": "qux"}

        # mock token get request response
        mock_requests_get.return_value = mock.Mock()
        mock_requests_get.return_value.text = "this_is_test_token"

        # check if returned auth object is an instance of requests.AuthBase
        with self.assertRaisesRegex(
            MisconfiguredError,
            r"Missing credentials inputs for provider provider_text_token_get_method: \['password2'\]",
        ):
            auth_plugin.authenticate()

    @mock.patch(
        "eodag.plugins.authentication.token.tokenauth.requests.Session.request",
        autospec=True,
    )
    def test_plugins_auth_tokenauth_post_credentials_true(self, mock_requests_post):
        """TokenAuth.authenticate must post credentials when post_credentials is True even if creds are in URI"""
        auth_plugin = self.get_auth_plugin("provider_text_token_post_credentials_true")

        auth_plugin.config.credentials = {"username": "bar", "baz": "qux"}

        # mock token post request response
        mock_requests_post.return_value = mock.Mock()
        mock_requests_post.return_value.text = "this_is_test_token"

        auth = auth_plugin.authenticate()
        self.assertTrue(isinstance(auth, AuthBase))

        # credentials must be in data even though they are embedded in auth_uri
        args, kwargs = mock_requests_post.call_args
        self.assertDictEqual(kwargs["data"], {"username": "bar", "baz": "qux"})

    @mock.patch(
        "eodag.plugins.authentication.token.tokenauth.requests.Session.request",
        autospec=True,
    )
    def test_plugins_auth_tokenauth_post_credentials_false(self, mock_requests_post):
        """TokenAuth.authenticate must not post credentials when post_credentials is False"""
        auth_plugin = self.get_auth_plugin("provider_text_token_post_credentials_false")

        auth_plugin.config.credentials = {"foo": "bar", "baz": "qux"}

        # mock token post request response
        mock_requests_post.return_value = mock.Mock()
        mock_requests_post.return_value.text = "this_is_test_token"

        auth = auth_plugin.authenticate()
        self.assertTrue(isinstance(auth, AuthBase))

        # credentials must NOT be in data even though they are not in auth_uri
        args, kwargs = mock_requests_post.call_args
        self.assertDictEqual(kwargs["data"], {})

    @mock.patch(
        "eodag.plugins.authentication.token.tokenauth.requests.Session.request",
        autospec=True,
    )
    def test_plugins_auth_tokenauth_post_credentials_default(self, mock_requests_post):
        """TokenAuth.authenticate must not post credentials by default when they are already in auth_uri"""
        auth_plugin = self.get_auth_plugin("provider_text_token_format_url")

        # use a single credential whose value will appear in the formatted auth_uri
        auth_plugin.config.credentials = {"username": "bar"}

        # mock token post request response
        mock_requests_post.return_value = mock.Mock()
        mock_requests_post.return_value.text = "this_is_test_token"

        auth = auth_plugin.authenticate()
        self.assertTrue(isinstance(auth, AuthBase))

        # credentials must NOT be in data because all values are in auth_uri
        args, kwargs = mock_requests_post.call_args
        self.assertDictEqual(kwargs["data"], {})

    def test_plugins_auth_tokenauth_request_error(self):
        """TokenAuth.authenticate must raise an AuthenticationError if a request error occurs"""
        auth_plugin = self.get_auth_plugin("provider_text_token_auth_error_code")

        auth_plugin.config.credentials = {"foo": "bar", "baz": "qux"}

        with self.assertRaisesRegex(
            AuthenticationError,
            "('Could no get authentication token', '404 .* 'test error message')",
        ):
            # mock token post request response with a different status code from the one in the provider auth config
            with responses.RequestsMock(
                assert_all_requests_are_fired=True
            ) as mock_requests_post:
                mock_requests_post.add(
                    responses.POST,
                    auth_plugin.config.auth_uri,
                    status=404,
                    body=b"test error message",
                )
                self.assertNotEqual(auth_plugin.config.auth_error_code, 404)
                auth_plugin.authenticate()

    def test_plugins_auth_tokenauth_wrong_credentials_request_error(self):
        """TokenAuth.authenticate must raise an AuthenticationError with a
        specific message if a request error occurs due to wrong credentials"""
        provider = "provider_text_token_auth_error_code"
        auth_plugin = self.get_auth_plugin(provider)

        auth_plugin.config.credentials = {"foo": "bar", "baz": "qux"}

        with self.assertRaisesRegex(
            AuthenticationError,
            f"('Please check your credentials for {provider}.', 'HTTP Error 401 returned.', 'test error message')",
        ):
            # mock token post request response with the same status code as the one in the provider auth config
            with responses.RequestsMock(
                assert_all_requests_are_fired=True
            ) as mock_requests_post:
                mock_requests_post.add(
                    responses.POST,
                    auth_plugin.config.auth_uri,
                    status=401,
                    body=b"test error message",
                )
                self.assertEqual(auth_plugin.config.auth_error_code, 401)
                auth_plugin.authenticate()
