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

from typing import Optional
from unittest import mock

import boto3

from eodag.api.product import EOProduct
from eodag.api.provider import ProvidersDict
from eodag.plugins.manager import PluginManager
from tests.units.auth_plugins.base import BaseAuthPluginTest


class TestAuthPluginAwsAuth(BaseAuthPluginTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.aws_access_key_id = "my_access_key"
        cls.aws_secret_access_key = "my_secret_key"
        cls.aws_session_token = "my_session_token"
        cls.profile_name = "my_profile"
        providers = ProvidersDict.from_configs(
            {
                "provider_with_auth_keys": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "AwsAuth",
                        "credentials": {
                            "aws_access_key_id": cls.aws_access_key_id,
                            "aws_secret_access_key": cls.aws_secret_access_key,
                        },
                        "s3_endpoint": "https://s3.abc.test.com",
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
            }
        )
        cls.plugins_manager = PluginManager(providers)

    @mock.patch(
        "eodag.plugins.authentication.aws_auth.create_s3_session", autospec=True
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth.get_s3_client", autospec=True
    )
    def test_plugins_auth_aws_authenticate(self, mock_s3_client, mock_create_session):
        """AwsAuth.authenticate must return an S3AuthContextPool containing available auth contexts"""

        class MockSession:
            def __init__(
                self,
                profile_name: Optional[str] = None,
                aws_access_key_id: Optional[str] = None,
                aws_secret_access_key: Optional[str] = None,
                aws_session_token: Optional[str] = None,
            ):
                self.profile_name = profile_name
                self.aws_access_key_id = aws_access_key_id
                self.aws_secret_access_key = aws_secret_access_key
                self.aws_session_token = aws_session_token
                self.resource = mock.MagicMock()

            def get_credentials(self):
                return self.__dict__

        mock_create_session.return_value = MockSession(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
        )
        plugin_auth_keys = self.get_auth_plugin("provider_with_auth_keys")
        plugin_auth_keys.authenticate()
        mock_create_session.assert_called_once_with(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
        )

        keys_dict = {
            "aws_access_key_id": self.aws_access_key_id,
            "aws_secret_access_key": self.aws_secret_access_key,
        }
        self.assertDictEqual(keys_dict, plugin_auth_keys.config.credentials)
        mock_create_session.reset_mock()

        mock_create_session.return_value = MockSession(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            aws_session_token=self.aws_session_token,
        )
        plugin_auth_keys_session = self.get_auth_plugin(
            "provider_with_auth_keys_session"
        )
        plugin_auth_keys_session.authenticate()
        mock_create_session.assert_called_once_with(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            aws_session_token=self.aws_session_token,
        )

        keys_dict = {
            "aws_access_key_id": self.aws_access_key_id,
            "aws_secret_access_key": self.aws_secret_access_key,
            "aws_session_token": self.aws_session_token,
        }
        self.assertDictEqual(keys_dict, plugin_auth_keys_session.config.credentials)
        mock_create_session.reset_mock()

        mock_create_session.return_value = MockSession(profile_name=self.profile_name)
        plugin_auth_profile = self.get_auth_plugin("provider_with_auth_profile")
        plugin_auth_profile.authenticate()
        mock_create_session.assert_called_once_with(profile_name=self.profile_name)

        keys_dict = {"aws_profile": self.profile_name}
        self.assertDictEqual(keys_dict, plugin_auth_profile.config.credentials)

    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth._create_s3_resource",
        autospec=True,
    )
    def test_plugins_download_aws_presigned_url(self, mock_s3_resource):
        """should create a presigned url to download from S3"""
        # provider with no credentials required
        provider = "provider_with_auth_keys"
        collection = "foo_product"
        product = EOProduct(
            provider,
            dict(
                geometry="POINT (0 0)",
                title="dummy_product",
                id="dummy",
            ),
            collection=collection,
        )
        product.assets.update({"a1": {"href": "https://s3.abc.test.com/b1/a1/a1.json"}})
        product.assets.update({"a2": {"href": "https://s3.abc.test.com/b1/a2/a2.json"}})
        mock_s3_resource.return_value = boto3.resource(
            service_name="s3",
            endpoint_url="https://s3.abc.test.com",
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
        )

        auth_plugin = self.get_auth_plugin("provider_with_auth_keys")
        auth_plugin.authenticate()
        url = auth_plugin.presign_url(product.assets["a1"])
        self.assertIn("https://s3.abc.test.com/b1/a1/a1.json", url)
        self.assertIn("AWSAccessKeyId=my_access_key", url)
        self.assertIn("Expires", url)
