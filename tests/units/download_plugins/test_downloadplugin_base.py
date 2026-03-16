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
import zipfile
from tempfile import TemporaryDirectory
from typing import Optional

from requests import Response

from eodag.api.product import Asset, EOProduct
from eodag.config import PluginConfig
from eodag.plugins.download import Download, StreamResponse
from tests.units.download_plugins.base import BaseDownloadPluginTest


class TestDownloadPluginBase(BaseDownloadPluginTest):
    def get_plugin_download(
        self, provider: str = "cop_database", config: Optional[dict] = None
    ):

        plugin_config_dict = {
            "type": "Download",
            "extract": True,
            "archive_depth": 1,
            "output_extension": ".json",
            "max_workers": 4,
            "ssl_verify": True,
        }
        if isinstance(config, dict):
            plugin_config_dict.update(config)

        return Download(
            provider=provider,
            config=PluginConfig.from_mapping(plugin_config_dict),
        )

    def create_asset_archive(
        self, output_dir: str, asset: Asset, prepath: str = ""
    ) -> str:

        plugin_download = self.get_plugin_download()

        product = EOProduct(provider="cop_database", properties={})
        asset = Asset(product=product, key="my_asset_name")
        asset.update({"title": "asset title", "href": "http://asset.location/"})
        product.assets.update({asset.key: asset})

        statements = plugin_download.get_statements(
            asset, output_extension=".zip", output_dir=output_dir
        )

        # Generate an archive
        local_path = statements.get("local_path")
        self.create_zip_file(local_path, prepath)

        return local_path

    def test_plugins_download_statements(self):

        plugin_download = self.get_plugin_download()

        with TemporaryDirectory() as output_dir:

            product = EOProduct(provider="cop_database", properties={})
            asset = Asset(product=product, key="my_asset_name")
            asset.update({"title": "asset title", "href": "http://asset.location/"})
            product.assets.update({asset.key: asset})

            statements = plugin_download.get_statements(asset, output_dir=output_dir)
            self.assertEqual(statements.get("ordered"), False)
            self.assertEqual(statements.get("order_id"), "")
            self.assertEqual(statements.get("status_link"), "")
            self.assertEqual(statements.get("href"), "")
            self.assertNotEqual(statements.get("local_path", ""), None)
            self.assertTrue(
                statements.get("local_path", "").endswith("{}.json".format(asset.key))
            )

            # Statements must not be consider if href is not set
            statements["order_id"] = "some order id"
            plugin_download.set_statements(asset, statements, output_dir=output_dir)
            new_statements = plugin_download.get_statements(
                asset, output_dir=output_dir
            )
            self.assertEqual(new_statements.get("order_id"), "")

            # Statements must not be consider if href is not set
            statements["href"] = asset.get("href")
            statements["order_id"] = "some order id"
            plugin_download.set_statements(asset, statements, output_dir=output_dir)
            new_statements = plugin_download.get_statements(
                asset, output_dir=output_dir
            )
            self.assertEqual(new_statements.get("order_id"), "some order id")

    def test_plugins_download_cache(self):

        plugin_download = self.get_plugin_download()

        tmp_dir = TemporaryDirectory()
        output_dir = tmp_dir.name

        product = EOProduct(provider="cop_database", properties={})
        asset = Asset(product=product, key="my_asset_name")
        asset.update({"title": "asset title", "href": "http://asset.location/"})
        product.assets.update({asset.key: asset})

        statements = plugin_download.get_statements(asset, output_dir=output_dir)
        cache = plugin_download.get_cache(asset, statements, stream=False)
        self.assertEqual(cache, None)

        # Create a file cache and update statements
        local_path = statements.get("local_path")
        with open(local_path, "w+") as fd:
            fd.write(json.dumps({"data": "ok"}))

        statements["href"] = asset.get("href")
        plugin_download.set_statements(asset, statements, output_dir=output_dir)

        cache = plugin_download.get_cache(asset, statements, stream=False)
        self.assertEqual(cache, local_path)

        cache_stream = plugin_download.get_cache(asset, statements, stream=True)
        self.assertTrue(isinstance(cache_stream, StreamResponse))

        tmp_dir.cleanup()

    def test_plugins_download_asset_metadata_from_response(self):

        plugin_download = self.get_plugin_download()

        product = EOProduct(provider="cop_database", properties={})
        asset = Asset(product=product, key="my_asset_name")
        asset.update({"title": "asset title", "href": "http://asset.location/"})
        product.assets.update({asset.key: asset})

        response = Response()
        response.status_code = 200
        response.headers = {
            "content-length": 4,
            "content-type": "text/plain",
            "etag": "938c2cc0dcc05f2b68c4287040cfcf71",
            "last-modified": "Wed, 15 Apr 2025 16:18:00 GMT",
        }
        response._content = b"frog"

        plugin_download.asset_metadata_from_response(asset, response)

        self.assertEqual(asset.get("type"), "text/plain")
        self.assertEqual(asset.get("file:size"), 4)
        self.assertEqual(asset.get("file:checksum"), "938c2cc0dcc05f2b68c4287040cfcf71")
        self.assertEqual(asset.get("update"), "2025-04-15T16:18:00")

    def test_plugins_download_asset_metadata_from_file(self):

        plugin_download = self.get_plugin_download()

        tmp_dir = TemporaryDirectory()

        product = EOProduct(provider="cop_database", properties={})
        asset = Asset(product=product, key="my_asset_name")
        asset.update({"title": "asset title", "href": "http://asset.location/"})
        product.assets.update({asset.key: asset})

        filepath = os.path.join(tmp_dir.name, "file.json")
        with open(filepath, "w+") as fd:
            fd.write(json.dumps({"data": "ok"}))

        plugin_download.asset_metadata_from_file(asset, filepath)

        self.assertEqual(asset.get("type"), "application/json")
        self.assertEqual(asset.get("file:size"), 14)
        self.assertEqual(asset.get("file:checksum"), "f3d63ef7a6fe86f7bf7008afefd20e19")
        self.assertNotEqual(asset.get("update"), None)

        tmp_dir.cleanup()

    def test_plugins_download_asset_metadata_from_s3object(self):

        plugin_download = self.get_plugin_download()

        tmp_dir = TemporaryDirectory()

        product = EOProduct(provider="cop_database", properties={})
        asset = Asset(product=product, key="my_asset_name")
        asset.update({"title": "asset title", "href": "http://asset.location/"})
        product.assets.update({asset.key: asset})

        s3Object: dict = {
            "ResponseMetadata": {
                "HTTPHeaders": {
                    "Content-Length": 4,
                    "Content-Type": "text/plain",
                    "Etag": "938c2cc0dcc05f2b68c4287040cfcf71",
                    "Last-Modified": "Wed, 15 Apr 2025 16:18:00 GMT",
                }
            }
        }

        plugin_download.asset_metadata_from_s3object(asset, s3Object)

        self.assertEqual(asset.get("type"), "text/plain")
        self.assertEqual(asset.get("file:size"), 4)
        self.assertEqual(asset.get("file:checksum"), "938c2cc0dcc05f2b68c4287040cfcf71")
        self.assertEqual(asset.get("update"), "2025-04-15T16:18:00")

        tmp_dir.cleanup()

    def test_plugins_download_pack_archive(self):

        plugin_download = self.get_plugin_download()

        tmp_dir = TemporaryDirectory()
        output_dir = tmp_dir.name

        product = EOProduct(provider="cop_database", properties={})
        asset = Asset(product=product, key="my_asset_name")
        asset.update({"title": "asset title", "href": "http://asset.location/"})
        product.assets.update({asset.key: asset})

        statements = plugin_download.get_statements(
            asset, output_extension=".zip", output_dir=output_dir
        )

        local_dir = statements.get("local_path")[0:-4]  # remove .zip

        # Create directory and files
        os.makedirs(local_dir)
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
        for filename in files:
            path = os.path.join(local_dir, filename)
            with open(path, "w+") as fd:
                fd.write(files[filename])

        archive_path = plugin_download.pack_archive(asset, local_dir)
        self.assertTrue(os.path.isfile(archive_path))

        internal_filenames = []
        with zipfile.ZipFile(archive_path, "r") as zfile:
            fileinfos = zfile.infolist()
            for fileinfo in fileinfos:
                internal_filenames.append(fileinfo.filename)
        internal_filenames.sort()

        self.assertEqual(internal_filenames, ["404.html", "config.json", "file1.txt"])

        tmp_dir.cleanup()

    def test_plugins_download_unpack_archive_noextract(self):

        tmp_dir = TemporaryDirectory()
        output_dir = tmp_dir.name

        product = EOProduct(provider="cop_database", properties={})
        asset = Asset(product=product, key="my_asset_name")
        asset.update({"title": "asset title", "href": "http://asset.location/"})
        product.assets.update({asset.key: asset})

        zip_path = self.create_asset_archive(output_dir, asset)
        plugin_download = self.get_plugin_download(
            config={"extract": False, "delete_archive": False}
        )
        local_path = plugin_download.unpack_archive(asset, zip_path)
        self.assertTrue(local_path.endswith("my_asset_name.zip"))
        self.assertTrue(os.path.isfile(local_path))

        tmp_dir.cleanup()

    def test_plugins_download_unpack_archive_extract_nodelete(self):

        tmp_dir = TemporaryDirectory()
        output_dir = tmp_dir.name

        product = EOProduct(provider="cop_database", properties={})
        asset = Asset(product=product, key="my_asset_name")
        asset.update({"title": "asset title", "href": "http://asset.location/"})
        product.assets.update({asset.key: asset})

        zip_path = self.create_asset_archive(output_dir, asset)
        plugin_download = self.get_plugin_download(
            config={"extract": True, "delete_archive": False}
        )

        local_path = plugin_download.unpack_archive(asset, zip_path)

        self.assertTrue(
            os.path.isfile(zip_path), "Path {} should exists".format(zip_path)
        )
        self.assertTrue(local_path.endswith("my_asset_name"))
        self.assertTrue(os.path.isdir(local_path))

        tmp_dir.cleanup()

    def test_plugins_download_unpack_archive_extract_delete(self):

        tmp_dir = TemporaryDirectory()
        output_dir = tmp_dir.name

        product = EOProduct(provider="cop_database", properties={})
        asset = Asset(product=product, key="my_asset_name")
        asset.update({"title": "asset title", "href": "http://asset.location/"})
        product.assets.update({asset.key: asset})

        zip_path = self.create_asset_archive(output_dir, asset)
        plugin_download = self.get_plugin_download(
            config={"extract": True, "delete_archive": True}
        )

        local_path = plugin_download.unpack_archive(asset, zip_path)

        self.assertFalse(
            os.path.isfile(zip_path), "Path {} should not exists".format(zip_path)
        )
        self.assertTrue(local_path.endswith("my_asset_name"))
        self.assertTrue(os.path.isdir(local_path))

        tmp_dir.cleanup()

    def test_plugins_download_unpack_archive_resolve_depth(self):

        with TemporaryDirectory() as output_dir:

            product = EOProduct(provider="cop_database", properties={})
            asset = Asset(product=product, key="my_asset_name")
            asset.update({"title": "asset title", "href": "http://asset.location/"})
            product.assets.update({asset.key: asset})

            zip_path = self.create_asset_archive(
                output_dir, asset, prepath="subdir1/subdir2/"
            )

            plugin_download = self.get_plugin_download(
                config={"extract": True, "delete_archive": False, "archive_depth": 1}
            )
            local_path = plugin_download.unpack_archive(asset, zip_path)
            self.assertTrue(os.path.isdir(local_path))
            self.assertEqual(os.listdir(local_path), ["subdir1"])
            shutil.rmtree(local_path)

            plugin_download = self.get_plugin_download(
                config={"extract": True, "delete_archive": False, "archive_depth": 2}
            )
            local_path = plugin_download.unpack_archive(asset, zip_path)
            self.assertTrue(os.path.isdir(local_path))
            self.assertEqual(os.listdir(local_path), ["subdir2"])
            shutil.rmtree(local_path)

            plugin_download = self.get_plugin_download(
                config={"extract": True, "delete_archive": False, "archive_depth": 3}
            )
            local_path = plugin_download.unpack_archive(asset, zip_path)
            self.assertTrue(os.path.isdir(local_path))
            files = os.listdir(local_path)
            files.sort()
            self.assertEqual(files, ["404.html", "config.json", "file1.txt"])

    def test_plugins_download_download(self):

        plugin_download = self.get_plugin_download()

        product = EOProduct(provider="cop_database", properties={})
        asset = Asset(product=product, key="my_asset_name")
        asset.update({"title": "asset title", "href": "http://asset.location/"})
        product.assets.update({asset.key: asset})

        try:
            plugin_download.download(asset)
            self.fail()
        except NotImplementedError:
            pass
