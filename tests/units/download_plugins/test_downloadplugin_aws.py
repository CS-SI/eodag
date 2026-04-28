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
import hashlib
import os
import platform
from tempfile import TemporaryDirectory
from typing import Optional
from unittest import mock

import botocore
from botocore.exceptions import ClientError, HTTPClientError

from eodag.api.product import Asset, EOProduct
from eodag.config import PluginConfig
from eodag.plugins.download import AwsDownload
from eodag.utils.exceptions import DownloadError
from tests.units.download_plugins.base import BaseDownloadPluginTest
from tests.units.download_plugins.streambodycontent import StreamBodyContent


class TestDownloadPluginAws(BaseDownloadPluginTest):
    # @TODO to rework test with credentials usage

    def setUp(self):
        super().setUp()
        self.tmp = TemporaryDirectory()
        self.output_dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()
        super().tearDown()

    def get_plugin_download(
        self, provider: str = "aws_eos", config: Optional[dict] = None
    ):

        plugin_config_dict = {
            "type": "AwsDownload",
            "extract": True,
            "archive_depth": 1,
            "output_extension": ".json",
            "max_workers": 4,
            "ssl_verify": True,
        }
        if isinstance(config, dict):
            plugin_config_dict.update(config)

        return AwsDownload(
            provider=provider,
            config=PluginConfig.from_mapping(plugin_config_dict),
        )

    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth.validate_config_credentials",
        autospec=True,
    )
    @mock.patch("botocore.httpsession.URLLib3Session", autospec=True)
    def test_plugins_download_aws_download(
        self, mock_urllib3, mock_awsauth_validate_creds
    ):
        """AwsDownload.get_product_bucket_name_and_prefix() must extract bucket & prefix from location"""
        product = EOProduct(
            provider="aws_eos",
            properties={
                "geometry": "POINT (0 0)",
                "title": "dummy_product",
                "id": "dummy",
            },
            collection="S2_MSI_L2A",
        )
        product.register_plugin_manager(self.plugins_manager)
        asset = Asset(product=product, key="my_asset_name")
        asset.update({"title": "asset title", "href": "s3://asset.location/"})
        product.assets.update({asset.key: asset})

        # Fake online file
        zip_file = os.path.join(self.output_dir, "archive.zip")
        self.create_zip_file(zip_file)
        stat = os.stat(zip_file)
        with open(zip_file, "rb") as fd:
            content = fd.read()
        hash_md5 = hashlib.md5(content).hexdigest()
        filesize = stat.st_size

        download_plugin = self.get_plugin_download(
            "aws_eos",
            {"products": {"S2_MSI_L2A": {"default_bucket": "default_bucket"}}},
        )

        # S3 emulation
        def mock_make_api_call(self, operation_name, *args, **kwargs):
            params: dict = args[0]
            params.update(kwargs)

            def now():
                return datetime.datetime.now(datetime.timezone.utc)

            if operation_name == "ListObjects":
                bucket = params.get("Bucket")
                prefix = params.get("Prefix")
                return {
                    "ResponseMetadata": {
                        "RequestId": "tx00000939a913d4302d739-0069e23a41-bb4b7f3-default",
                        "HostId": "",
                        "HTTPStatusCode": 200,
                        "HTTPHeaders": {
                            "content-type": "application/xml",
                            "content-length": "13382",
                            "server": "envoy",
                            "date": "Fri, 17 Apr 2026 13:48:49 GMT",
                            "x-amz-request-id": "tx00000939a913d4302d739-0069e23a41-bb4b7f3-default",
                            "x-envoy-upstream-service-time": "54",
                            "x-ratelimit-limit": "5000, 5000;w=60",
                            "x-ratelimit-remaining": "4997",
                            "x-ratelimit-reset": "11",
                        },
                        "RetryAttempts": 0,
                    },
                    "IsTruncated": False,
                    "Marker": "",
                    "Contents": [
                        {
                            "Key": "{}/".format(prefix),
                            "LastModified": now(),
                            "ETag": '"d41d8cd98f00b204e9800998ecf8427e"',
                            "Size": 0,
                            "StorageClass": "STANDARD",
                            "Owner": {
                                "DisplayName": "Data Access",
                                "ID": "data-access",
                            },
                        },
                        {
                            "Key": "{}/subdir/file1.zip".format(prefix),
                            "LastModified": now(),
                            "ETag": '"{}"'.format(hash_md5),
                            "Size": filesize,
                            "StorageClass": "STANDARD",
                            "Owner": {
                                "DisplayName": "Data Access",
                                "ID": "data-access",
                            },
                        },
                        {
                            "Key": "{}/subdir/file2.zip".format(prefix),
                            "LastModified": now(),
                            "ETag": '"{}"'.format(hash_md5),
                            "Size": filesize,
                            "StorageClass": "STANDARD",
                            "Owner": {
                                "DisplayName": "Data Access",
                                "ID": "data-access",
                            },
                        },
                    ],
                    "Name": bucket,
                    "Prefix": prefix,
                    "MaxKeys": 1000,
                    "EncodingType": "url",
                }
            elif operation_name == "HeadObject" and params.get("Key") in [
                "/subdir/file1.zip",
                "/subdir/file2.zip",
            ]:
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
                    "ContentLength": filesize,
                    "ETag": '"{}"'.format(hash_md5),
                    "ContentType": "application/zip",
                    "Metadata": {},
                }
            elif operation_name == "GetObject" and params.get("Key") in [
                "/subdir/file1.zip",
                "/subdir/file2.zip",
            ]:
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
                    "ContentLength": filesize,
                    "ETag": '"{}"'.format(hash_md5),
                    "ContentType": "application/zip",
                    "Body": botocore.response.StreamingBody(
                        StreamBodyContent(content), filesize
                    ),
                    "Metadata": {},
                }

            # Unsupported for test
            parsed_response = {"Error": {"Code": "500", "Message": "Error"}}
            raise ClientError(parsed_response, operation_name)

        try:
            with mock.patch(
                "botocore.client.BaseClient._make_api_call", new=mock_make_api_call
            ):
                path = download_plugin.download(
                    asset,
                    no_cache=True,
                    stream=False,
                    output_extension="applicatin/ocet-stream",
                )
                self.assertTrue(os.path.isdir(path))
        except HTTPClientError:
            # S3 http request forbidden, catch as error on post requests
            pass
        except DownloadError:
            # @TODO investigate
            # Still bug on windows platform, have to investigate why
            if platform.system().lower() == "windows":
                self.skipTest(reason="mocking bugged on windows")

    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth.validate_config_credentials",
        autospec=True,
    )
    @mock.patch("botocore.httpsession.URLLib3Session", autospec=True)
    def test_plugins_download_aws_archive_depth(
        self, mock_urllib3, mock_awsauth_validate_creds
    ):
        """AwsDownload.download() must not call safe build methods if not needed"""
        product = EOProduct(
            provider="aws_eos",
            properties={
                "geometry": "POINT (0 0)",
                "title": "dummy_product",
                "id": "dummy",
            },
            collection="S2_MSI_L2A",
        )
        product.register_plugin_manager(self.plugins_manager)
        asset = Asset(product=product, key="my_asset_name")
        asset.update(
            {
                "title": "asset title",
                "type": "application/zip",
                "href": "s3://asset.location/archive.zip",
            }
        )
        product.assets.update({asset.key: asset})

        # Fake online file
        zip_file = os.path.join(self.output_dir, "archive.zip")
        self.create_zip_file(zip_file, prepath="subdir/")
        stat = os.stat(zip_file)
        with open(zip_file, "rb") as fd:
            content = fd.read()
        hash_md5 = hashlib.md5(content).hexdigest()
        filesize = stat.st_size

        download_plugin = self.get_plugin_download(
            "aws_eos",
            {
                "archive_depth": 2,
                "products": {"S2_MSI_L2A": {"default_bucket": "default_bucket"}},
            },
        )

        # S3 emulation
        def mock_make_api_call(self, operation_name, *args, **kwargs):
            params: dict = args[0]
            params.update(kwargs)

            def now():
                return datetime.datetime.now(datetime.timezone.utc)

            if operation_name == "ListObjects":
                bucket = params.get("Bucket")
                prefix = params.get("Prefix")
                return {
                    "ResponseMetadata": {
                        "RequestId": "tx00000939a913d4302d739-0069e23a41-bb4b7f3-default",
                        "HostId": "",
                        "HTTPStatusCode": 200,
                        "HTTPHeaders": {
                            "content-type": "application/xml",
                            "content-length": "13382",
                            "server": "envoy",
                            "date": "Fri, 17 Apr 2026 13:48:49 GMT",
                            "x-amz-request-id": "tx00000939a913d4302d739-0069e23a41-bb4b7f3-default",
                            "x-envoy-upstream-service-time": "54",
                            "x-ratelimit-limit": "5000, 5000;w=60",
                            "x-ratelimit-remaining": "4997",
                            "x-ratelimit-reset": "11",
                        },
                        "RetryAttempts": 0,
                    },
                    "IsTruncated": False,
                    "Marker": "",
                    "Contents": [
                        {
                            "Key": prefix,
                            "LastModified": now(),
                            "ETag": '"{}"'.format(hash_md5),
                            "Size": filesize,
                            "StorageClass": "STANDARD",
                            "Owner": {
                                "DisplayName": "Data Access",
                                "ID": "data-access",
                            },
                        }
                    ],
                    "Name": bucket,
                    "Prefix": prefix,
                    "MaxKeys": 1000,
                    "EncodingType": "url",
                }
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
                    "ContentLength": filesize,
                    "ETag": '"{}"'.format(hash_md5),
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
                    "ContentLength": filesize,
                    "ETag": '"{}"'.format(hash_md5),
                    "ContentType": "application/zip",
                    "Body": botocore.response.StreamingBody(
                        StreamBodyContent(content), filesize
                    ),
                    "Metadata": {},
                }

            # Unsupported for test
            parsed_response = {"Error": {"Code": "500", "Message": "Error"}}
            raise ClientError(parsed_response, operation_name)

        try:
            with mock.patch(
                "botocore.client.BaseClient._make_api_call", new=mock_make_api_call
            ):
                path = download_plugin.download(asset, no_cache=True, stream=False)
                self.assertTrue(os.path.isdir(path))
                files = os.listdir(path)
                files.sort()
                self.assertEqual(files, ["404.html", "config.json", "file1.txt"])
        except HTTPClientError:
            # S3 http request forbidden, catch as error on post requests
            pass

    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth.validate_config_credentials",
        autospec=True,
    )
    @mock.patch("botocore.httpsession.URLLib3Session", autospec=True)
    def test_plugins_download_aws_no_files_in_prefix(
        self, mock_urllib3, mock_awsauth_validate_creds
    ):
        """AwsDownload.download() must fail if no product chunk is available"""

        product = EOProduct(
            provider="aws_eos",
            properties={
                "geometry": "POINT (0 0)",
                "title": "dummy_product",
                "id": "dummy",
            },
            collection="S2_MSI_L2A",
        )
        product.register_plugin_manager(self.plugins_manager)
        asset = Asset(product=product, key="my_asset_name")
        asset.update(
            {
                "title": "asset title",
                "type": "application/zip",
                "href": "s3://asset.location/archive.zip",
            }
        )
        product.assets.update({asset.key: asset})

        download_plugin = self.get_plugin_download("aws_eos")

        # S3 emulation
        def mock_make_api_call(self, operation_name, *args, **kwargs):
            params: dict = args[0]
            params.update(kwargs)

            def now():
                return datetime.datetime.now(datetime.timezone.utc)

            if operation_name == "ListObjects":
                bucket = params.get("Bucket")
                prefix = params.get("Prefix")
                return {
                    "ResponseMetadata": {
                        "RequestId": "tx00000939a913d4302d739-0069e23a41-bb4b7f3-default",
                        "HostId": "",
                        "HTTPStatusCode": 200,
                        "HTTPHeaders": {
                            "content-type": "application/xml",
                            "content-length": "13382",
                            "server": "envoy",
                            "date": "Fri, 17 Apr 2026 13:48:49 GMT",
                            "x-amz-request-id": "tx00000939a913d4302d739-0069e23a41-bb4b7f3-default",
                            "x-envoy-upstream-service-time": "54",
                            "x-ratelimit-limit": "5000, 5000;w=60",
                            "x-ratelimit-remaining": "4997",
                            "x-ratelimit-reset": "11",
                        },
                        "RetryAttempts": 0,
                    },
                    "IsTruncated": False,
                    "Marker": "",
                    "Contents": [],
                    "Name": bucket,
                    "Prefix": prefix,
                    "MaxKeys": 1000,
                    "EncodingType": "url",
                }

            # Unsupported for test
            parsed_response = {"Error": {"Code": "500", "Message": "Error"}}
            raise ClientError(parsed_response, operation_name)

        with mock.patch(
            "botocore.client.BaseClient._make_api_call", new=mock_make_api_call
        ):
            try:
                path = download_plugin.download(asset, no_cache=True, stream=False)
                self.assertIsNone(path)
            except HTTPClientError:
                # S3 http request forbidden, catch as error on post requests
                pass

    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth.validate_config_credentials",
        autospec=True,
    )
    @mock.patch("botocore.httpsession.URLLib3Session", autospec=True)
    def test_plugins_download_aws_get_rio_env(
        self, mock_urllib3, mock_awsauth_validate_creds
    ):
        """AwsDownload.get_rio_env() must return rio env dict"""
        product = EOProduct(
            provider="aws_eos",
            properties={
                "geometry": "POINT (0 0)",
                "title": "dummy_product",
                "id": "dummy",
            },
            collection="S2_MSI_L2A",
        )
        product.register_plugin_manager(self.plugins_manager)
        asset = Asset(product=product, key="my_asset_name")
        asset.update({"title": "asset title", "href": "s3://some-bucket/some/prefix"})
        product.assets.update({asset.key: asset})

        plugin = self.get_plugin_download("aws_eos")
        auth_plugin = self.plugins_manager.get_auth_plugin(plugin, asset)
        auth_plugin.authenticate()

        # nothing needed
        rio_env_dict = auth_plugin.get_rio_env()
        self.assertIn("session", rio_env_dict)
        self.assertIn("requester_pays", rio_env_dict)
        self.assertTrue(rio_env_dict["requester_pays"])

        # with endpoint url
        auth_plugin.config.s3_endpoint = "some.endpoint"
        self.assertEqual(auth_plugin.config.requester_pays, True)
        rio_env_dict = auth_plugin.get_rio_env()
        self.assertIsNotNone(rio_env_dict.pop("session", None))
        self.assertDictEqual(
            rio_env_dict,
            {
                "endpoint_url": "some.endpoint",
                "requester_pays": True,
            },
        )
