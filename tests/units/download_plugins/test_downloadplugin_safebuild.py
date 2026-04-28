# -*- coding: utf-8 -*-
# Copyright 2018, CS GROUP - France, http://www.c-s.fr
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
import json
import os
import unittest
from tempfile import TemporaryDirectory
from typing import Optional
from unittest import mock

import botocore
from botocore.exceptions import ClientError, HTTPClientError

from eodag.api.product import Asset, EOProduct
from eodag.api.provider import ProvidersDict
from eodag.config import PluginConfig, load_default_config
from eodag.plugins.download import AwsDownload
from eodag.plugins.manager import PluginManager
from eodag.utils.mime import Mime
from tests.units.download_plugins.streambodycontent import StreamBodyContent
from tests.utils import TEST_RESOURCES_PATH


class TestSafeBuild(unittest.TestCase):
    def setUp(self):
        super(TestSafeBuild, self).setUp()

        providers = ProvidersDict.from_configs(load_default_config())
        self.plugins_manager = PluginManager(providers)
        self.tmp_download_dir = TemporaryDirectory()
        self.tmp_download_path = self.tmp_download_dir.name

    def tearDown(self):
        self.tmp_download_dir.cleanup()

    def get_plugin_download(
        self, provider: str = "wekeo_main", config: Optional[dict] = None
    ):
        plugin_config_dict = {
            "type": "HTTPDownload",
            "extract": True,
            "archive_depth": 1,
            "max_workers": 4,
            "ssl_verify": True,
        }
        if isinstance(config, dict):
            plugin_config_dict.update(config)

        return AwsDownload(
            provider=provider,
            config=PluginConfig.from_mapping(plugin_config_dict),
        )

    def scan_dir(self, base_path: str, rel_path: str = ""):
        files = os.listdir(os.path.join(base_path, rel_path))
        results = []
        for file in files:
            filepath = os.path.join(base_path, rel_path, file)
            if os.path.isfile(filepath):
                results.append("{}/{}".format(rel_path, file).lstrip("/"))
            elif os.path.isdir(filepath):
                results += self.scan_dir(
                    base_path, "{}/{}".format(rel_path, file).lstrip("/")
                )
        return results

    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth.validate_config_credentials",
        autospec=True,
    )
    @mock.patch("botocore.httpsession.URLLib3Session", autospec=True)
    def test_downloadplugins_safebuild(self, mock_urllib3, mock_awsauth_validate_creds):

        product = EOProduct(
            provider="earth_search",
            properties={
                "constellation": "sentinel-2",
                "datetime": "2021-12-01T00:00:02.032000Z",
                "id": "S2B_MSIL1C_20211130T235939_N0301_R116_T59VMF_20211201T012623",
                "eodag:product_path": "products/2021/11/30/S2B_MSIL1C_20211130T235939_"
                + "N0301_R116_T59VMF_20211201T012623",
            },
            collection="S2_MSI_L1C",
        )
        product.register_plugin_manager(self.plugins_manager)
        asset = Asset(product=product, key="blue")
        asset.update(
            {
                "title": "B02",
                "href": "s3://sentinel-s2-l2a/tiles/59/V/MF/2021/12/1/0/B02.jp2",
                "order:status": "succeeded",
                "type": "image/jp2",
                "eo:bands": [
                    {
                        "name": "blue",
                        "common_name": "blue",
                        "description": "Blue (band 2)",
                        "center_wavelength": 0.49,
                        "full_width_half_max": 0.098,
                    }
                ],
                "gsd": 10,
                "proj:shape": [10980, 10980],
                "proj:transform": [10, 0, 399960, 0, -10, 6600000],
                "raster:bands": [
                    {
                        "nodata": 0,
                        "data_type": "uint16",
                        "bits_per_sample": 15,
                        "spatial_resolution": 10,
                        "scale": 0.0001,
                        "offset": 0,
                    }
                ],
                "roles": ["data"],
            }
        )
        product.assets.update({asset.key: asset})

        asset_files = {}
        map = {}
        base_path = os.path.join(TEST_RESOURCES_PATH, "safe_build_earth_search")
        for item in os.listdir(base_path):
            path = os.path.join(base_path, item)
            if os.path.isfile(path):
                if item == "mapping.json":
                    with open(path, "r") as fd:
                        content = fd.read()
                        map = json.loads(content)
                else:
                    stat = os.stat(path)
                    with open(path, "rb") as fd:
                        content = fd.read()
                    hash_md5 = hashlib.md5(content).hexdigest()
                    filesize = stat.st_size
                    asset_files[item] = {
                        "path": path,
                        "size": filesize,
                        "etag": hash_md5,
                        "mime": Mime.guess_file_type(path)
                        if item != "manifest.safe"
                        else "application/xml",
                    }

        # S3 emulation
        def mock_make_api_call(self, operation_name, *args, **kwargs):
            params: dict = args[0]
            params.update(kwargs)

            def now():
                return datetime.datetime.now(datetime.timezone.utc)

            if operation_name == "ListObjects":
                bucket = params.get("Bucket")
                prefix = params.get("Prefix")
                content = []
                for key in map:
                    content.append(
                        {
                            "Key": key,
                            "LastModified": now(),
                            "ETag": '"{}"'.format(
                                asset_files["FORMAT_CORRECTNESS.xml"]["etag"]
                            ),
                            "Size": asset_files["FORMAT_CORRECTNESS.xml"]["size"],
                            "StorageClass": "STANDARD",
                            "Owner": {
                                "DisplayName": "Data Access",
                                "ID": "data-access",
                            },
                        }
                    )
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
                    "Contents": content,
                    "Name": bucket,
                    "Prefix": prefix,
                    "MaxKeys": 1000,
                    "EncodingType": "url",
                }
            elif operation_name == "HeadObject":
                key = params.get("Key")
                if key in map:
                    asset_file = asset_files[map[key]]
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
                        "LastModified": now(),
                        "ContentLength": asset_file["size"],
                        "ETag": '"{}"'.format(asset_file["etag"]),
                        "ContentType": asset_file["mime"],
                        "Metadata": {},
                    }
            elif operation_name == "GetObject":
                key = params.get("Key")
                if key in map:
                    asset_file = asset_files[map[key]]
                    with open(asset_file["path"], "rb") as fd:
                        content = fd.read()

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
                        "ContentLength": len(content),
                        "ETag": '"{}"'.format(asset_file["etag"]),
                        "ContentType": asset_file["mime"],
                        "Body": botocore.response.StreamingBody(
                            StreamBodyContent(content), len(content)
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

                with self.assertLogs(level="DEBUG") as cm:
                    path = asset.download(
                        no_cache=True,
                        output_extension="applicatin/ocet-stream",
                        output_dir=self.tmp_download_path,
                    )
                    self.assertTrue(
                        os.path.join(self.tmp_download_path, "manifest.safe")
                    )

                    # Check steps in log
                    steps = {
                        "mapping": False,
                        "download": False,
                        "finalize": False,
                        "safe_build": False,
                        "safe_build_missing": False,
                    }

                    for line in cm.output:
                        if line.startswith("DEBUG:eodag.download."):
                            if "Map s3_key" in line:
                                steps["mapping"] = True
                            if "Download" in line:
                                steps["download"] = True
                            if "Finalize SAFE product" in line:
                                steps["finalize"] = True
                            if "SAFE build: complete" in line:
                                steps["safe_build"] = True
                        if line.startswith("WARNING:eodag.download."):
                            if "SAFE build" in line and "is missing" in line:
                                steps["safe_build_missing"] = True

                    self.assertTrue(steps["mapping"])
                    self.assertTrue(steps["download"])
                    self.assertTrue(steps["finalize"])
                    self.assertTrue(steps["safe_build"])
                    self.assertTrue(steps["safe_build_missing"])

                # Check for file renaming
                files = self.scan_dir(path)
                files.sort()
                self.assertEqual(
                    files,
                    [
                        "DATASTRIP/DS_VGS4_20211201T012623_S20211130T235940/QI_DATA/FORMAT_CORRECTNESS.xml",
                        "DATASTRIP/DS_VGS4_20211201T012623_S20211130T235940/QI_DATA/GENERAL_QUALITY.xml",
                        "DATASTRIP/DS_VGS4_20211201T012623_S20211130T235940/QI_DATA/GEOMETRIC_QUALITY.xml",
                        "DATASTRIP/DS_VGS4_20211201T012623_S20211130T235940/QI_DATA/RADIOMETRIC_QUALITY.xml",
                        "DATASTRIP/DS_VGS4_20211201T012623_S20211130T235940/QI_DATA/SENSOR_QUALITY.xml",
                        "HTML/UserProduct_index.html",
                        "HTML/UserProduct_index.xsl",
                        "INSPIRE.xml",
                        "MTD_MSIL1C.xml",
                        "manifest.safe",
                        "productInfo.json",
                    ],
                )

        except HTTPClientError:
            # S3 http request forbidden, catch as error on post requests
            pass
