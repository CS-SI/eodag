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

from unittest import mock

from requests.auth import AuthBase
from requests.exceptions import RequestException

from eodag.api.product import EOProduct
from eodag.api.provider import ProvidersDict
from eodag.plugins.manager import PluginManager
from eodag.utils import USER_AGENT
from eodag.utils.exceptions import AuthenticationError
from tests.units.auth_plugins.base import BaseAuthPluginTest


class TestAuthPluginSASAuth(BaseAuthPluginTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        providers = ProvidersDict.from_configs(
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
                }
            }
        )
        cls.plugins_manager = PluginManager(providers)

    def test_plugins_auth_sasauth_validate_credentials_ok(self):
        """SASAuth.validate_credentials must be ok on empty or non-empty credentials"""
        auth_plugin = self.get_auth_plugin("foo_provider")

        auth_plugin.config.credentials = {}
        auth_plugin.validate_config_credentials()
        auth_plugin.config.credentials = {"apikey": "foo"}
        auth_plugin.validate_config_credentials()

    @mock.patch(
        "eodag.plugins.authentication.sas_auth.requestssasauth.requests.get",
        autospec=True,
    )
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

    @mock.patch(
        "eodag.plugins.authentication.sas_auth.requestssasauth.requests.get",
        autospec=True,
    )
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

    @mock.patch(
        "eodag.plugins.authentication.sas_auth.requestssasauth.requests.get",
        autospec=True,
    )
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

    def test_plugins_download_http_presign_url(self):
        """should create a presigned url to download via HTTP"""
        provider = "foo_provider"
        collection = "LANDSAT_C2_L1"
        product = EOProduct(
            provider,
            dict(
                geometry="POINT (0 0)",
                title="dummy_product",
                id="dummy",
            ),
            collection=collection,
        )
        product.assets.update({"a1": {"href": "http://foo.bar.com/b1/a1/a1.json"}})
        product.assets.update({"a2": {"href": "http://foo.bar.com/b1/a2/a2.json"}})

        auth_plugin = self.get_auth_plugin("foo_provider")
        url = auth_plugin.presign_url(product.assets["a1"])
        expected_url = "http://foo.bar?href={url}".format(
            url="http://foo.bar.com/b1/a1/a1.json"
        )
        self.assertEqual(expected_url, url)
