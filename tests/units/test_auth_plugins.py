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
import unittest
from datetime import datetime, timedelta
from unittest import mock

import responses
from pystac.utils import now_in_utc
from requests import Request, Response, Timeout
from requests.auth import AuthBase
from requests.exceptions import RequestException

from eodag.config import override_config_from_mapping
from eodag.plugins.authentication.openid_connect import CodeAuthorizedAuth
from eodag.utils import MockResponse
from eodag.utils.exceptions import RequestError
from tests.context import (
    HTTP_REQ_TIMEOUT,
    USER_AGENT,
    AuthenticationError,
    HeaderAuth,
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
        return next(self.plugins_manager.get_auth_or_download_plugins("auth", provider))


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
        self.assertDictEqual(kwargs["data"], {"foo": "bar", "baz": "qux"})
        self.assertIsNone(kwargs["auth"])
        self.assertDictEqual(
            kwargs["headers"], dict(auth_plugin.config.headers, **USER_AGENT)
        )

        # check if token is integrated to the request
        req = mock.Mock(headers={})
        auth(req)
        self.assertEqual(req.headers["Authorization"], "Bearer this_is_test_token")
        self.assertEqual(req.headers["foo"], "bar")

    @mock.patch(
        "eodag.plugins.authentication.token.requests.Session.request", autospec=True
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
        self.assertIsNone(kwargs["auth"])
        self.assertDictEqual(
            kwargs["headers"], dict(auth_plugin.config.retrieve_headers, **USER_AGENT)
        )

        # check if token is integrated to the request
        req = mock.Mock(headers={})
        auth(req)
        self.assertEqual(req.headers["Authorization"], "Bearer this_is_test_token")
        self.assertEqual(req.headers["foo"], "bar")

    @mock.patch(
        "eodag.plugins.authentication.token.requests.Session.request", autospec=True
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
        "eodag.plugins.authentication.token.requests.Session.request", autospec=True
    )
    def test_plugins_auth_tokenauth_json_token_with_expiration_time(
        self, mock_requests_post
    ):
        """TokenAuth.authenticate must return a RequestsTokenAuth object using json token
        If there is an existing, valid token this token msut be used
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
            auth=None,
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
            auth=None,
        )

    @mock.patch(
        "eodag.plugins.authentication.token.requests.Session.request", autospec=True
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
            auth=None,
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
        "eodag.plugins.authentication.token.requests.Session.request", autospec=True
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
        self.assertIsNone(kwargs["auth"])
        self.assertDictEqual(kwargs["headers"], USER_AGENT)

        # check if token is integrated to the request
        req = mock.Mock(headers={})
        auth(req)
        self.assertEqual(req.headers["Authorization"], "Bearer this_is_test_token")

    @mock.patch(
        "eodag.plugins.authentication.token.requests.Session.request", autospec=True
    )
    def test_plugins_auth_tokenauth_get_method_request_authenticate(
        self, mock_requests_get
    ):
        """TokenAuth.authenticate must return a RequestsTokenAuth object with 'GET' method request"""
        auth_plugin = self.get_auth_plugin("provider_text_token_get_method")

        auth_plugin.config.credentials = {"username": "bar", "password": "qux"}

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
        self.assertTupleEqual(kwargs["auth"], ("bar", "qux"))
        self.assertDictEqual(kwargs["headers"], USER_AGENT)

        # check if token is integrated to the request
        req = mock.Mock(headers={})
        auth(req)
        self.assertEqual(req.headers["Authorization"], "Bearer this_is_test_token")

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


class TestAuthPluginAwsAuth(BaseAuthPluginTest):
    @classmethod
    def setUpClass(cls):
        super(TestAuthPluginAwsAuth, cls).setUpClass()
        cls.aws_access_key_id = "my_access_key"
        cls.aws_secret_access_key = "my_secret_key"
        cls.aws_session_token = "my_session_token"
        cls.profile_name = "my_profile"
        override_config_from_mapping(
            cls.providers_config,
            {
                "provider_with_auth_keys": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "AwsAuth",
                        "credentials": {
                            "aws_access_key_id": cls.aws_access_key_id,
                            "aws_secret_access_key": cls.aws_secret_access_key,
                        },
                    },
                },
                "provider_with_auth_keys_session": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "AwsAuth",
                        "credentials": {
                            "aws_access_key_id": cls.aws_access_key_id,
                            "aws_secret_access_key": cls.aws_secret_access_key,
                            "aws_session_token": cls.aws_session_token,
                        },
                    },
                },
                "provider_with_auth_profile": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "AwsAuth",
                        "credentials": {
                            "aws_profile": cls.profile_name,
                        },
                    },
                },
            },
        )
        cls.plugins_manager = PluginManager(cls.providers_config)

    def test_plugins_auth_aws_authenticate(self):
        """AwsAuth.authenticate must return credentials in a dict"""
        self.assertDictEqual(
            self.get_auth_plugin("provider_with_auth_keys").authenticate(),
            {
                "aws_access_key_id": self.aws_access_key_id,
                "aws_secret_access_key": self.aws_secret_access_key,
            },
        )
        self.assertDictEqual(
            self.get_auth_plugin("provider_with_auth_keys_session").authenticate(),
            {
                "aws_access_key_id": self.aws_access_key_id,
                "aws_secret_access_key": self.aws_secret_access_key,
                "aws_session_token": self.aws_session_token,
            },
        )
        self.assertDictEqual(
            self.get_auth_plugin("provider_with_auth_profile").authenticate(),
            {
                "profile_name": self.profile_name,
            },
        )


class TestAuthPluginHTTPHeaderAuth(BaseAuthPluginTest):
    @classmethod
    def setUpClass(cls):
        super(TestAuthPluginHTTPHeaderAuth, cls).setUpClass()
        override_config_from_mapping(
            cls.providers_config,
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
            },
        )
        cls.plugins_manager = PluginManager(cls.providers_config)

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
                        "oidc_config_url": "http://foo.bar/auth/realms/myrealm/.well-known/openid-configuration",
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
        oidc_config = {
            "authorization_endpoint": "http://foo.bar/auth/realms/myrealm/protocol/openid-connect/auth",
            "token_endpoint": "http://foo.bar/auth/realms/myrealm/protocol/openid-connect/token",
            "jwks_uri": "http://foo.bar/auth/realms/myrealm/protocol/openid-connect/certs",
            "id_token_signing_alg_values_supported": ["RS256", "HS512"],
        }
        with mock.patch(
            "eodag.plugins.authentication.openid_connect.requests.get", autospec=True
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
        "eodag.plugins.authentication.openid_connect.OIDCRefreshTokenBase.decode_jwt_token",
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
        "eodag.plugins.authentication.openid_connect.OIDCRefreshTokenBase.decode_jwt_token",
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
        "eodag.plugins.authentication.openid_connect.OIDCRefreshTokenBase.decode_jwt_token",
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
        "eodag.plugins.authentication.openid_connect.OIDCRefreshTokenBase.decode_jwt_token",
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
            },
        )
        cls.plugins_manager = PluginManager(cls.providers_config)

    def get_auth_plugin(self, provider):
        with mock.patch(
            "eodag.plugins.authentication.openid_connect.requests.get", autospec=True
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
        "eodag.plugins.authentication.openid_connect.OIDCRefreshTokenBase.decode_jwt_token",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth._get_token_with_refresh_token",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth._request_new_token",
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
        "eodag.plugins.authentication.openid_connect.OIDCRefreshTokenBase.decode_jwt_token",
        autospec=True,
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
        "eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth.authenticate_user",
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
        "eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth.grant_user_consent",
        autospec=True,
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
        "eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth.authenticate_user",
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
        "eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth.authenticate_user",
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
        "eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth._request_new_token",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.Session.post",
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
        "eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth._request_new_token",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.Session.post",
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
        "eodag.plugins.authentication.token.requests.Session.post", autospec=True
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
        "eodag.plugins.authentication.openid_connect.requests.Session.post",
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
        "eodag.plugins.authentication.openid_connect.requests.Session.post",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.Session.get",
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
        "eodag.plugins.authentication.token.requests.Session.post", autospec=True
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
        "eodag.plugins.authentication.token.requests.Session.post", autospec=True
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
        "eodag.plugins.authentication.token.requests.Session.post", autospec=True
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
        "eodag.plugins.authentication.openid_connect.requests.Session.post",
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
