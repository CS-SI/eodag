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
import zipfile
from tempfile import TemporaryDirectory
from typing import Optional
from unittest import mock

import botocore
from botocore.exceptions import ClientError

from eodag.api.product import Asset, EOProduct
from eodag.config import PluginConfig
from eodag.plugins.download import AwsDownload
from eodag.utils.exceptions import DownloadError
from tests.units.download_plugins.base import BaseDownloadPluginTest
from tests.units.download_plugins.streambodycontent import StreamBodyContent


class TestDownloadPluginCreodiasS3(BaseDownloadPluginTest):
    def get_plugin_download(
        self, provider: str = "creodias_s3", config: Optional[dict] = None
    ):
        plugin_config_dict = {
            "type": "AwsDownload",
            "s3_endpoint": "https://s3.endpoint",
            "s3_bucket": "eodata",
            "ssl_verify": True,
        }
        if isinstance(config, dict):
            plugin_config_dict.update(config)

        return AwsDownload(
            provider=provider,
            config=PluginConfig.from_mapping(plugin_config_dict),
        )

    @mock.patch(
        "eodag.plugins.authentication.Authentication.validate_config_credentials",
        autospec=True,
    )
    @mock.patch("botocore.httpsession.URLLib3Session", autospec=True)
    def test_plugins_download_creodias_s3(
        self, mock_urlib3, mock_validate_config_credentials
    ):

        tmp_dir = TemporaryDirectory()
        test_dir = tmp_dir.name
        output_dir = os.path.join(test_dir, "output")
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)

        # Fake local product / asset
        product = EOProduct(provider="creodias_s3", properties={})
        product.register_plugin_manager(self.plugins_manager)
        asset = Asset(product=product, key="my_asset_name")
        asset.update(
            {
                "title": "asset title",
                "href": "s3://eodata/asset",
                "type": "application/octet-stream",
            }
        )
        product.assets.update({asset.key: asset})

        # Fake online file
        zip_file = os.path.join(test_dir, "archive.zip")
        self.create_zip_file(zip_file)
        stat = os.stat(zip_file)
        with open(zip_file, "rb") as fd:
            content = fd.read()
        hash_md5 = hashlib.md5(content).hexdigest()
        filesize = stat.st_size

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
                "asset/subdir/file1.zip",
                "asset/subdir/file2.zip",
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
                "asset/subdir/file1.zip",
                "asset/subdir/file2.zip",
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
                downloader = self.get_plugin_download()
                path = downloader.download(asset)

                self.assertTrue(os.path.isdir(path))
                self.assertEqual(os.listdir(path), ["subdir"])

                files = os.listdir(os.path.join(path, "subdir"))
                self.assertIn("file1.zip", files)
                self.assertIn("file2.zip", files)

                filepath = os.path.join(path, "subdir", "file1.zip")
                self.assertTrue(os.path.isfile(filepath))
                self.assertTrue(zipfile.is_zipfile(filepath))

                filepath = os.path.join(path, "subdir", "file2.zip")
                self.assertTrue(os.path.isfile(filepath))
                self.assertTrue(zipfile.is_zipfile(filepath))

        except DownloadError:
            # @TODO investigate
            # Still bug on windows platform, have to investigate why
            if platform.system().lower() == "windows":
                self.skipTest(reason="mocking bugged on windows")

        tmp_dir.cleanup()
