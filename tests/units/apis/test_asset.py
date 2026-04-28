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

import json
import os
import shutil
import tempfile
import zipfile

import responses

from tests.utils import EODagTestBase


class TestAsset(EODagTestBase):
    def create_zip_file(self, local_path: str, prepath: str = ""):

        files: dict[str, str] = {
            "file1.txt": "this is a text content",
            "config.json": json.dumps(
                {
                    "type": "Download",
                    "extract": True,
                    "archive_depth": 1,
                    "output_extension": ".json",
                    "max_workers": 4,
                    "ssl_verify": True,
                }
            ),
            "404.html": "<!doctype html><body><h1>404 Not found</h1><hr /></body></html>",
        }
        with zipfile.ZipFile(local_path, "w") as zip:
            for filename in files:
                zip.writestr(
                    "{}{}".format(prepath, filename),
                    files[filename],
                    zipfile.ZIP_DEFLATED,
                )

    @responses.activate
    def test_eoproduct_asset_stream_download(self):
        """eoproduct.assets[x].stream_download return a asset file as StreamResponse"""  # noqa
        with tempfile.TemporaryDirectory() as tmp_dir:
            local_dir = os.path.join(tmp_dir, "local")
            os.makedirs(local_dir)
            output_dir = os.path.join(tmp_dir, "output")
            os.makedirs(output_dir)
            remote_path = os.path.join(local_dir, "archive.zip")
            self.create_zip_file(remote_path)
            with open(remote_path, "rb") as fd:
                content = fd.read()
            archive_url = "https://fake.url.to/archive.zip"

            responses.add(
                responses.GET,
                archive_url,
                body=content,
                status=200,
            )
            product = self._dummy_product()
            product.assets.update(
                {
                    "download_link": {
                        "title": "download_link",
                        "href": archive_url,
                        "type": "application/zip",
                    }
                }
            )

            asset_stream = product.assets["download_link"].stream_download(
                no_cache=True, output_dir=output_dir
            )
            self.assertGreaterEqual(len(responses.calls), 1)

            # Download to tmp directory
            filepath = os.path.join(local_dir, "local-archive.zip")
            with open(filepath, "wb") as fp:
                for chunk in asset_stream.content:
                    fp.write(chunk)

            self.assertTrue(os.path.isfile(filepath))
            stat = os.stat(filepath)
            self.assertIn(stat.st_size, [489, 493])  # windows could add 3 bytes BOM
            self.assertTrue(zipfile.is_zipfile(filepath))

            shutil.rmtree(local_dir)
            shutil.rmtree(output_dir)
