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
import datetime
import json
from pathlib import Path
from unittest import mock

import botocore
from botocore.exceptions import ClientError

from eodag.config import PluginConfig
from eodag.plugins.authentication import AwsAuth
from tests.units.download_plugins.streambodycontent import StreamBodyContent
from tests.units.search_plugins.base import BaseSearchPluginTest
from tests.units.search_plugins.mock_response import MockResponse
from tests.utils import TEST_RESOURCES_PATH


class TestSearchPluginCreodiasS3Search(BaseSearchPluginTest):
    def setUp(self):
        super(TestSearchPluginCreodiasS3Search, self).setUp()
        self.provider = "creodias_s3"

    def asset_plugin_patch(
        self, asset, provider="creodias_s3", credentials: dict = None
    ):
        if credentials is None:
            credentials = {
                "aws_access_key_id": "foo",
                "aws_secret_access_key": "bar",
            }

        def patch():
            download_plugin = self.plugins_manager.get_download_plugin(provider)
            auth_plugin = AwsAuth(
                provider, PluginConfig.from_mapping({"credentials": credentials})
            )
            return download_plugin, auth_plugin

        asset.get_downloader_and_auth = patch

    @mock.patch("botocore.httpsession.URLLib3Session", autospec=True)
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_creodias_s3_links(self, mock_request, mock_urllib3):

        creodias_search_result_file = (
            Path(TEST_RESOURCES_PATH) / "eodag_search_result_creodias.json"
        )
        with open(creodias_search_result_file) as f:
            creodias_search_result = json.load(f)
        mock_request.return_value = MockResponse(creodias_search_result, 200)

        def mock_make_api_call(self, operation_name, *args, **kwargs):
            def now():
                return datetime.datetime.now(datetime.timezone.utc)

            if operation_name == "ListObjects":
                s3_response_file = (
                    Path(TEST_RESOURCES_PATH)
                    / "provider_responses/creodias_s3_objects.json"
                )
                with open(s3_response_file) as f:
                    result = json.load(f)
                return result
            elif operation_name == "HeadObject":
                return {
                    "ResponseMetadata": {
                        "RequestId": "tx0000015e7333f240e6553-0069e23a41-c11fd35-default",
                        "HostId": "",
                        "HTTPStatusCode": 200,
                        "HTTPHeaders": {
                            "content-type": "binary/octet-stream",
                            "content-length": "51897972",
                            "server": "envoy",
                            "date": "Fri, 17 Apr 2026 13:48:49 GMT",
                            "accept-ranges": "bytes",
                            "last-modified": "Mon, 10 Mar 2025 16:54:10 GMT",
                            "x-rgw-object-type": "Normal",
                            "etag": '"4e2e0458cfb8d363e799fcd270bc64bd"',
                            "x-amz-meta-mtime": "1624356859.838",
                            "x-amz-request-id": "tx0000015e7333f240e6553-0069e23a41-c11fd35-default",
                            "x-envoy-upstream-service-time": "52",
                            "x-ratelimit-limit": "5000, 5000;w=60",
                            "x-ratelimit-remaining": "4995",
                            "x-ratelimit-reset": "11",
                        },
                        "RetryAttempts": 0,
                    },
                    "AcceptRanges": "bytes",
                    "LastModified": now(),
                    "ContentLength": 0,
                    "ContentType": "application/zip",
                    "Metadata": {},
                }
            elif operation_name == "GetObject":
                return {
                    "ResponseMetadata": {
                        "RequestId": "tx00000494eabbc72a06bc7-0069e23a43-159ab80f-default",
                        "HostId": "",
                        "HTTPStatusCode": 200,
                        "HTTPHeaders": {
                            "content-type": "binary/octet-stream",
                            "content-length": "2106",
                            "server": "envoy",
                            "date": "Fri, 17 Apr 2026 13:48:51 GMT",
                            "accept-ranges": "bytes",
                            "last-modified": "Mon, 10 Mar 2025 16:54:08 GMT",
                            "x-rgw-object-type": "Normal",
                            "etag": '"28cb3d82a5b4b95a175a5e01f3d475f4"',
                            "x-amz-meta-mtime": "1624356859.048",
                            "x-amz-request-id": "tx00000494eabbc72a06bc7-0069e23a43-159ab80f-default",
                            "x-envoy-upstream-service-time": "68",
                            "x-ratelimit-limit": "5000, 5000;w=60",
                            "x-ratelimit-remaining": "4982",
                            "x-ratelimit-reset": "9",
                        },
                        "RetryAttempts": 0,
                    },
                    "AcceptRanges": "bytes",
                    "LastModified": now(),
                    "ContentLength": 0,
                    "ContentType": "application/zip",
                    "Body": botocore.response.StreamingBody(StreamBodyContent(b""), 0),
                    "Metadata": {},
                }

            # Unsupported for test
            parsed_response = {"Error": {"Code": "500", "Message": "Error"}}
            raise ClientError(parsed_response, operation_name)

        with mock.patch(
            "botocore.client.BaseClient._make_api_call", new=mock_make_api_call
        ):

            # s3 links should be added to products with register_downloader
            search_plugin = self.get_search_plugin("S1_SAR_GRD", self.provider)
            res = search_plugin.query(collection="S1_SAR_GRD")
            for product in res.data:
                asset = product.assets["download_link"]
                self.asset_plugin_patch(
                    asset,
                    credentials={
                        "aws_access_key_id": "foo",
                        "aws_secret_access_key": "bar",
                    },
                )
                asset.download()
                break

        product = res[0]
        self.assertEqual(1, len(product.assets))
        # check if s3 links have been created correctly
        self.assertEqual(asset["href"], product.assets["download_link"]["href"])
        self.assertIsNotNone(product.driver)

    @mock.patch("botocore.httpsession.URLLib3Session", autospec=True)
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_creodias_s3_client_error(self, mock_request, mock_urllib3):
        def mock_make_api_call(self, operation_name, *args, **kwargs):

            # Unsupported for test
            parsed_response = {"Error": {"Code": "500", "Message": "Error"}}
            raise ClientError(parsed_response, operation_name)

        with mock.patch(
            "botocore.client.BaseClient._make_api_call", new=mock_make_api_call
        ):

            # request error should be raised when there is an error when fetching data from the s3
            search_plugin = self.get_search_plugin("S1_SAR_GRD", self.provider)
            creodias_search_result_file = (
                Path(TEST_RESOURCES_PATH) / "eodag_search_result_creodias.json"
            )
            with open(creodias_search_result_file) as f:
                creodias_search_result = json.load(f)
            mock_request.return_value = MockResponse(creodias_search_result, 200)

            with self.assertRaises(botocore.exceptions.ClientError):
                res = search_plugin.query(collection="S1_SAR_GRD")
                for product in res:
                    if "download_link" in product.assets:
                        asset = product.assets["download_link"]
                        self.asset_plugin_patch(
                            asset,
                            credentials={
                                "aws_access_key_id": "foo",
                                "aws_secret_access_key": "bar",
                            },
                        )
                        asset.download()
