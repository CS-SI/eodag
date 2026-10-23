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
import hashlib
import io
import os
import shutil
import stat
import tarfile
import unittest
import zipfile
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any
from unittest import mock

import responses
from concurrent.futures import ThreadPoolExecutor
from requests.structures import CaseInsensitiveDict

from eodag.utils import MockResponse, ProgressCallback
from eodag.utils.exceptions import (
    DownloadError,
    MisconfiguredError,
    QuotaExceededError,
    ValidationError,
)
from tests import TEST_RESOURCES_PATH
from tests.context import (
    DEFAULT_STREAM_REQUESTS_TIMEOUT,
    HTTP_REQ_TIMEOUT,
    NOT_AVAILABLE,
    OFFLINE_STATUS,
    ONLINE_STATUS,
    USER_AGENT,
    EOProduct,
    HTTPDownload,
    NotAvailableError,
    PluginConfig,
    PluginManager,
    ProvidersDict,
    S3FileInfo,
    StreamResponse,
    load_provider_configs,
    path_to_uri,
    uri_to_path,
)


class BaseDownloadPluginTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(BaseDownloadPluginTest, cls).setUpClass()
        providers = ProvidersDict.from_configs(load_provider_configs())
        cls.plugins_manager = PluginManager(providers)
        # Mock home and eodag conf directory to tmp dir
        cls.tmp_home_dir = TemporaryDirectory()
        expanduser_mock_side_effect = (
            lambda *x: x[0]
            .replace("~user", cls.tmp_home_dir.name)
            .replace("~", cls.tmp_home_dir.name)
        )
        cls.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, side_effect=expanduser_mock_side_effect
        )
        cls.expanduser_mock.start()

    @classmethod
    def tearDownClass(cls):
        super(BaseDownloadPluginTest, cls).tearDownClass()
        # stop Mock and remove tmp config dir
        cls.expanduser_mock.stop()
        cls.tmp_home_dir.cleanup()

    def setUp(self):
        super(BaseDownloadPluginTest, self).setUp()
        self.product = EOProduct(
            "wekeo_main",
            dict(
                geometry="POINT (0 0)",
                title="dummy_product",
                id="dummy",
            ),
        )
        self.tmp_dir = TemporaryDirectory()
        self.output_dir = self.tmp_dir.name

    def tearDown(self):
        super(BaseDownloadPluginTest, self).tearDown()
        self.tmp_dir.cleanup()

    def get_download_plugin(self, product: EOProduct):
        return self.plugins_manager.get_download_plugin(product)

    def get_auth_plugin(self, associated_plugin, product, not_none=True):
        plugin = self.plugins_manager.get_auth_plugin(associated_plugin, product)
        if not_none:
            assert (
                plugin is not None
            ), f"Cannot get auth plugin for {associated_plugin} and {product}"
        return plugin


class TestDownloadPluginBase(BaseDownloadPluginTest):
    """Test cases for the base download plugin."""

    def test_plugins_download_base_cached_download_link_existing(self):
        """Download._cached_download_link must detect if product destination already exists."""
        product_file = NamedTemporaryFile()
        self.product.location = path_to_uri(product_file.name)
        Path(product_file.name).touch()
        self.assertNotEqual(self.product.location, self.product.remote_location)

        plugin = self.get_download_plugin(self.product)

        with self.assertLogs(level="INFO") as cm:
            fs_path = plugin._cached_download_link(self.product)
            self.assertEqual(fs_path, product_file.name)
            self.assertIn("Product already present on this platform", str(cm.output))

    def test_plugins_download_base_cached_download_link(self):
        """Download._cached_download_link must check download_link statements and legacy records."""
        self.product.remote_location = "http://foo.bar"
        self.product.collection = "foo"
        download_link = self.product.assets["download_link"]

        with TemporaryDirectory() as output_dir:
            download_kwargs = dict(output_dir=output_dir)
            product_path_dir = Path(output_dir) / self.product.properties["title"]
            recordfile_dir = Path(output_dir) / ".downloaded"
            recordfile_dir.mkdir()
            old_recordfile_path = (
                recordfile_dir
                / hashlib.md5("http://foo.bar".encode("utf-8")).hexdigest()
            )

            plugin = self.get_download_plugin(self.product)

            # not downloaded
            self.assertIsNone(
                plugin._cached_download_link(self.product, **download_kwargs)
            )

            # < v3.0.0b1 formatted record file and product path exist, record migrated to statements
            product_path_dir.mkdir()
            (product_path_dir / "foo").touch()
            old_recordfile_path.touch()
            with self.assertLogs(level="INFO") as cm:
                fs_path = plugin._cached_download_link(self.product, **download_kwargs)
                self.assertIn("Product already downloaded", str(cm.output))
            self.assertEqual(fs_path, str(product_path_dir))
            self.assertFalse(old_recordfile_path.exists())
            self.assertEqual(download_link["file:local_path"], str(product_path_dir))
            self.assertEqual(self.product.location, path_to_uri(str(product_path_dir)))

            # statements exist
            download_link.data.pop("file:local_path")
            self.product.location = self.product.remote_location
            with self.assertLogs(level="INFO") as cm:
                fs_path = plugin._cached_download_link(self.product, **download_kwargs)
                self.assertIn("Product already downloaded", str(cm.output))
            self.assertEqual(fs_path, str(product_path_dir))

    def test_plugins_download_base_cached_download_link_collision_dir(self):
        """Download._cached_download_link must detect already-downloaded dir without collision suffix."""
        self.product.properties["title"] = "title to sanitïze"
        self.product.properties["id"] = "id alsô"
        self.product.remote_location = "http://foo.bar"
        self.product.collection = "foo"

        with TemporaryDirectory() as output_dir:
            download_kwargs = dict(output_dir=output_dir)
            # directory created without the collision-avoidance suffix
            # (e.g. extracted archive containing just the sanitized title)
            product_path_dir = Path(output_dir) / "title_to_sanitize"
            product_path_dir.mkdir()
            (product_path_dir / "foo").touch()

            recordfile_dir = Path(output_dir) / ".downloaded"
            recordfile_dir.mkdir()
            recordfile_path = (
                recordfile_dir / hashlib.md5("foo-id alsô".encode("utf-8")).hexdigest()
            )
            recordfile_path.touch()

            plugin = self.get_download_plugin(self.product)

            with self.assertLogs(level="INFO") as cm:
                fs_path = plugin._cached_download_link(self.product, **download_kwargs)
                self.assertIn("Product already downloaded", str(cm.output))
                self.assertEqual(fs_path, str(product_path_dir))

    def test_plugins_download_base_product_output_path_collision_avoidance(self):
        """Download._product_output_path must use collision avoidance suffix."""
        self.product.properties["title"] = "needs sanitïze"
        self.product.properties["id"] = "alsô.zip"

        plugin = self.get_download_plugin(self.product)

        fs_path = plugin._product_output_path(self.product, output_dir=self.output_dir)

        self.assertEqual(
            fs_path, os.path.join(self.output_dir, "needs_sanitize-also.zip")
        )

    def test_plugins_download_base_product_output_path_dir_permission(self):
        """Download._product_output_path must check output directory permissions."""
        if os.name == "nt":
            self.skipTest("windows permissions too complex to set for this test")

        plugin = self.get_download_plugin(self.product)
        # read only output dir
        outdir = TemporaryDirectory()
        os.chmod(outdir.name, stat.S_IREAD)

        with self.assertLogs(level="WARNING") as cm:
            plugin._product_output_path(self.product, output_dir=outdir.name)
            self.assertIn("Unable to create download directory", str(cm.output))

    def test_plugins_download_base_finalize_extract_not_complete(self):
        """Download._finalize must not delete archive if extract is True but file is not an archive."""
        plugin = self.get_download_plugin(self.product)

        with TemporaryDirectory() as output_dir:
            fs_path = Path(output_dir) / "FOO.bar"
            fs_path.touch()
            download_kwargs = dict(
                output_dir=output_dir, extract=True, delete_archive=True
            )

            with self.assertLogs(level="INFO") as cm:
                plugin._finalize(str(fs_path), **download_kwargs)
                self.assertIn("Archive deletion is deactivated", str(cm.output))
            self.assertTrue(os.path.isfile(fs_path))

    def test_plugins_download_base_finalize_extract_complete(self):
        """Download._finalize must delete archive if extract is True and file is an archive."""
        plugin = self.get_download_plugin(self.product)

        with TemporaryDirectory() as output_dir:
            fs_path = Path(output_dir) / "FOO.bar"
            fs_path.touch()
            arch_path = Path(output_dir) / "FOO.TGZ"
            with tarfile.open(arch_path, "w:gz") as tar:
                tar.add(fs_path, arcname="FOO.bar")
            fs_path.unlink()
            download_kwargs = dict(
                output_dir=output_dir, extract=True, delete_archive=True
            )

            with self.assertLogs(level="INFO") as cm:
                plugin._finalize(str(arch_path), **download_kwargs)
                self.assertIn("Deleting archive ", str(cm.output))
            self.assertFalse(arch_path.exists())
            self.assertTrue(os.path.isfile(Path(output_dir) / "FOO" / "FOO.bar"))

    def _get_asset_and_statement_file(self, plugin, href="http://foo/bar"):
        self.product.assets.clear()
        self.product.assets.update({"foo": {"href": href}})
        asset = self.product.assets["foo"]
        _, statement_dir = plugin._prepare_directories(output_dir=self.output_dir)
        return asset, plugin._get_statement_path(asset, statement_dir)

    def test_plugins_download_base_prepare_directories_statement_dir_error(self):
        """Download._prepare_directories must warn if statement directory cannot be created"""
        plugin = self.get_download_plugin(self.product)
        real_makedirs = os.makedirs

        def makedirs_side_effect(path, *args, **kwargs):
            if str(path).endswith(".downloaded"):
                raise OSError("denied")
            return real_makedirs(path, *args, **kwargs)

        with (
            mock.patch(
                "eodag.plugins.download.base.os.makedirs",
                side_effect=makedirs_side_effect,
            ),
            self.assertLogs("eodag.download.base", level="WARNING") as cm,
        ):
            output_dir, statement_dir = plugin._prepare_directories(
                output_dir=os.path.join(self.output_dir, "new_dir")
            )

        self.assertTrue(os.path.isdir(output_dir))
        self.assertFalse(os.path.isdir(statement_dir))
        self.assertIn("Unable to create download directory", str(cm.output))

    def test_plugins_download_base_get_statements_corrupted(self):
        """Download.get_statements must remove corrupted statement files"""
        plugin = self.get_download_plugin(self.product)
        asset, statement_file = self._get_asset_and_statement_file(plugin)
        Path(statement_file).write_text("not a json")

        with self.assertLogs("eodag.download.base", level="DEBUG") as cm:
            statements = plugin.get_statements(
                asset, output_dir=self.output_dir, output_extension=""
            )

        self.assertIn("fail to load statement file", str(cm.output))
        self.assertFalse(os.path.exists(statement_file))
        self.assertEqual(
            statements["file:local_path"],
            os.path.join(self.output_dir, "dummy_product", "foo"),
        )

    def test_plugins_download_base_get_statements_outdated(self):
        """Download.get_statements must drop statements if asset href changed"""
        plugin = self.get_download_plugin(self.product)
        asset, statement_file = self._get_asset_and_statement_file(
            plugin, href="http://foo/new"
        )
        Path(statement_file).write_bytes(
            b'{"href": "http://foo/old", "file:local_path": "/some/old/path"}'
        )

        with self.assertLogs("eodag.download.base", level="DEBUG") as cm:
            statements = plugin.get_statements(
                asset, output_dir=self.output_dir, output_extension=""
            )

        self.assertIn("Out-dated statement (href changed)", str(cm.output))
        self.assertFalse(os.path.exists(statement_file))
        self.assertEqual(statements["href"], "")
        self.assertIsNone(plugin.check_cache(asset, output_dir=self.output_dir))

    def test_plugins_download_base_get_statements_remove_error(self):
        """Download.get_statements must not fail if corrupted statement file cannot be removed"""
        plugin = self.get_download_plugin(self.product)
        asset, statement_file = self._get_asset_and_statement_file(plugin)
        Path(statement_file).write_text("not a json")

        with (
            mock.patch(
                "eodag.plugins.download.base.os.remove", side_effect=OSError("busy")
            ),
            self.assertLogs("eodag.download.base", level="DEBUG") as cm,
        ):
            plugin.get_statements(asset, output_dir=self.output_dir)

        self.assertIn("Remove corrupted asset foo statements: busy", str(cm.output))
        self.assertTrue(os.path.exists(statement_file))

    def test_plugins_download_base_get_statements_matching_file(self):
        """Download.get_statements must find an existing file with another extension"""
        plugin = self.get_download_plugin(self.product)
        asset, statement_file = self._get_asset_and_statement_file(plugin)
        product_dir = Path(self.output_dir) / "dummy_product"
        product_dir.mkdir()
        existing_file = product_dir / "foo.zip"
        existing_file.touch()

        statements = plugin.check_cache(
            asset, output_dir=self.output_dir, output_extension=".tif"
        )

        self.assertIsNotNone(statements)
        self.assertEqual(statements["file:local_path"], str(existing_file))
        self.assertEqual(asset["file:local_path"], str(existing_file))
        self.assertTrue(os.path.isfile(statement_file))

    def test_plugins_download_base_legacy_record_migration(self):
        """Download.check_cache must migrate legacy product records to download_link statements"""
        plugin = self.get_download_plugin(self.product)
        self.product.assets.clear()
        self.product.remote_location = "http://somewhere/product.zip"
        asset = self.product.assets["download_link"]
        _, statement_dir = plugin._prepare_directories(output_dir=self.output_dir)
        statement_file = plugin._get_statement_path(asset, statement_dir)
        product_dir = Path(self.output_dir) / "dummy_product"
        archive = Path(self.output_dir) / "dummy_product.zip"
        legacy_records = {
            "product hash": Path(statement_dir)
            / plugin.generate_record_hash(self.product),
            "url hash": Path(statement_dir)
            / hashlib.md5(asset["href"].encode("utf-8")).hexdigest(),
        }

        for name, record in legacy_records.items():
            for data_path in (product_dir, archive):
                with self.subTest(record=name, data_path=data_path.name):
                    if data_path.suffix:
                        data_path.touch()
                    else:
                        data_path.mkdir()
                    record.write_text(asset["href"])

                    statements = plugin.check_cache(asset, output_dir=self.output_dir)

                    self.assertEqual(statements["file:local_path"], str(data_path))
                    self.assertEqual(asset["file:local_path"], str(data_path))
                    self.assertTrue(os.path.isfile(statement_file))
                    self.assertFalse(record.exists())

                    os.remove(statement_file)
                    asset.data.pop("file:local_path")
                    if data_path.is_dir():
                        shutil.rmtree(data_path)
                    else:
                        data_path.unlink()

        # legacy record without data
        legacy_records["product hash"].write_text(asset["href"])
        self.assertIsNone(plugin.check_cache(asset, output_dir=self.output_dir))
        self.assertFalse(legacy_records["product hash"].exists())
        self.assertFalse(os.path.isfile(statement_file))

        # legacy records are only used for download_link
        self.product.assets.update({"foo": {"href": "http://somewhere/foo"}})
        legacy_records["product hash"].write_text(asset["href"])
        product_dir.mkdir()
        self.assertIsNone(
            plugin.check_cache(self.product.assets["foo"], output_dir=self.output_dir)
        )
        self.assertTrue(legacy_records["product hash"].exists())

    @mock.patch(
        "eodag.plugins.download.http.HTTPDownload._raw_stream_download", autospec=True
    )
    def test_plugins_download_base_legacy_record_download(self, mock_stream_download):
        """HTTPDownload.download must not download again a product having a legacy record"""
        plugin = self.get_download_plugin(self.product)
        self.product.assets.clear()
        self.product.remote_location = "http://somewhere/product.zip"
        _, statement_dir = plugin._prepare_directories(output_dir=self.output_dir)
        (Path(statement_dir) / plugin.generate_record_hash(self.product)).write_text(
            self.product.remote_location
        )
        product_dir = Path(self.output_dir) / "dummy_product"
        product_dir.mkdir()
        (product_dir / "file.txt").touch()

        with self.assertLogs(level="INFO") as cm:
            path = plugin.download(self.product, output_dir=self.output_dir)

        self.assertIn("Product already downloaded", str(cm.output))
        self.assertEqual(path, str(product_dir))
        self.assertEqual(self.product.location, path_to_uri(str(product_dir)))
        mock_stream_download.assert_not_called()


class TestDownloadPluginHttp(BaseDownloadPluginTest):
    """Test cases for the HTTP download plugin."""

    def _dummy_product(
        self, provider: str, properties: dict[str, Any], collection: str
    ):
        return EOProduct(
            provider,
            properties,
            kwargs={"collection": collection},
        )

    def _dummy_downloadable_product(
        self,
        provider: str,
        properties: dict[str, Any],
        collection: str,
    ):
        dl_config = PluginConfig.from_mapping(
            {
                "type": "HTTPDownload",
                "base_uri": "fake_base_uri",
                "output_dir": self.output_dir,
                "extract": False,
                "delete_archive": False,
            }
        )
        downloader = HTTPDownload(provider=provider, config=dl_config)
        product = self._dummy_product(provider, properties, collection)
        product.register_downloader(downloader, None)
        return product

    @responses.activate
    def test_plugins_download_http_zip_file_ok(self):
        """HTTPDownload.download() must keep the output as it is when it is a zip file."""
        provider = "creodias"
        download_url = (
            "https://zipper.creodias.eu/download/8ff765a2-e089-465d-a48f-cc27008a0962"
        )
        local_filename = "S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911"
        local_product_as_archive_path = os.path.abspath(
            os.path.join(
                TEST_RESOURCES_PATH,
                "products",
                "as_archive",
                "{}.zip".format(local_filename),
            )
        )
        collection = "S2_MSI_L1C"
        platform = "S2A"
        instrument = "MSI"

        with open(local_product_as_archive_path, "rb") as fh:
            archive_content = fh.read()

        responses.add(
            responses.GET,
            download_url,
            body=archive_content,
            status=200,
            content_type="application/zip",
            auto_calculate_content_length=True,
        )

        eoproduct_props = {
            "id": "9deb7e78-9341-5530-8fe8-f81fd99c9f0f",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [0.495928592903789, 44.22596415476343],
                        [1.870237286761489, 44.24783068396879],
                        [1.888683014192297, 43.25939191053712],
                        [0.536772323136669, 43.23826255332707],
                        [0.495928592903789, 44.22596415476343],
                    ]
                ],
            },
            "collection": collection,
            "constellation": "Sentinel-2",
            "platform": platform,
            "instruments": instrument,
            "title": local_filename,
        }

        product = self._dummy_downloadable_product(
            provider,
            eoproduct_props,
            collection,
        )
        product.remote_location = download_url
        path = product.download()

        expected_path = os.path.join(
            self.output_dir, product.properties["title"] + ".zip"
        )
        self.assertEqual(path, expected_path)
        self.assertTrue(os.path.isfile(path))
        self.assertTrue(zipfile.is_zipfile(path))

        # check if the hidden directory ".downloaded" have been created with the product zip file
        self.assertEqual(len(os.listdir(self.output_dir)), 2)

        # check request call
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(responses.calls[0].request.url, download_url)
        self.assertIn("get", responses.calls[0].request.method.lower())

    @mock.patch(
        "eodag.plugins.download.http.HTTPDownload._raw_stream_download", autospec=True
    )
    @mock.patch("eodag.api.product._product.EOProduct._stream", create=True)
    def test_plugins_download_http_nonzip_file_with_zip_extension_ok(
        self, mock_stream, mock_stream_download
    ):
        """HTTPDownload.download() must create an output directory in certain conditions.

        One is when the result is a non-zip file with a '.zip' outputs extension.
        """
        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"

        self.product.filename = "dummy_product.nc"
        mock_stream_download.return_value = [b"a"]
        progress_callback = ProgressCallback(disable=True)

        path = plugin.download(
            self.product,
            output_dir=self.output_dir,
            progress_callback=progress_callback,
        )

        # Verify output directory
        self.assertEqual(path, os.path.join(self.output_dir, "dummy_product"))
        self.assertTrue(os.path.isdir(path))

        # Verify output file
        file_path = os.path.join(path, os.listdir(path)[0])
        self.assertEqual(len(os.listdir(path)), 1)
        self.assertNotIn(".zip", file_path)
        self.assertFalse(zipfile.is_zipfile(file_path))
        self.assertFalse(tarfile.is_tarfile(file_path))

        # check if the hidden directory ".downloaded" have been created with the one of the product
        self.assertEqual(len(os.listdir(self.output_dir)), 2)

        mock_stream_download.assert_called_once_with(
            plugin,
            self.product,
            self.product.assets["download_link"],
            None,
            progress_callback,
            output_dir=self.output_dir,
        )

    @mock.patch(
        "eodag.plugins.download.http.HTTPDownload._raw_stream_download", autospec=True
    )
    @mock.patch("eodag.api.product._product.EOProduct._stream", create=True)
    def test_plugins_download_http_file_without_zip_extension_ok(
        self, mock_stream, mock_stream_download
    ):
        """HTTPDownload.download() must create an output directory in certain conditions.

        One is when the result is a file without a '.zip' outputs extension.
        """
        # we use a provider having '.nc' as outputs file extension in its configuration
        product = EOProduct(
            "meteoblue",
            dict(
                geometry="POINT (0 0)",
                title="dummy_product",
                id="dummy",
            ),
        )

        product.filename = "dummy_product.nc"
        mock_stream_download.return_value = [b"a"]

        plugin = self.get_download_plugin(product)
        product.location = product.remote_location = "http://somewhere"
        product.properties["id"] = "someproduct"
        progress_callback = ProgressCallback(disable=True)

        path = plugin.download(
            product, output_dir=self.output_dir, progress_callback=progress_callback
        )

        # Verify output directory
        expected_path = os.path.join(self.output_dir, "dummy_product")
        self.assertIsNotNone(path)
        self.assertEqual(path, expected_path)
        self.assertTrue(os.path.isdir(path))

        # Verify output file
        file_path = os.path.join(path, os.listdir(path)[0])
        self.assertEqual(len(os.listdir(path)), 1)
        self.assertTrue(os.path.isfile(file_path))
        self.assertNotIn(".zip", file_path)
        self.assertFalse(zipfile.is_zipfile(file_path))
        self.assertFalse(tarfile.is_tarfile(file_path))

        # check if the hidden directory ".downloaded" have been created with the one of
        # the product
        self.assertEqual(len(os.listdir(self.output_dir)), 2)

        mock_stream_download.assert_called_once_with(
            plugin,
            product,
            product.assets["download_link"],
            None,
            progress_callback,
            output_dir=self.output_dir,
        )

    @mock.patch(
        "eodag.plugins.download.http.HTTPDownload._raw_stream_download", autospec=True
    )
    @mock.patch("eodag.api.product._product.EOProduct._stream", create=True)
    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_download_link_only(
        self, mock_requests_get, mock_requests_head, mock_stream, mock_stream_download
    ):
        """HTTPDownload.download() must only download download_link asset if it exists and no filter is used."""
        plugin = self.get_download_plugin(self.product)
        self.product.properties["id"] = "someproduct"
        self.product.assets.clear()
        self.product.assets.update(
            {
                "download_link": {"href": "http://somewhere/download_from_location"},
                "foo": {"href": "http://somewhere/download_asset"},
            }
        )
        mock_requests_get.return_value.__enter__.return_value.iter_content.side_effect = lambda *x, **y: io.BytesIO(
            b"some content"
        )

        mock_stream_download.return_value = [b"a"]
        self.product.filename = "dummy_product.nc"

        # download_link only without filter
        path = plugin.download(self.product, output_dir=self.output_dir)
        mock_requests_get.assert_not_called()
        mock_stream_download.assert_called_once()
        self.assertEqual(
            mock_stream_download.call_args.args[2], self.product.assets["download_link"]
        )
        shutil.rmtree(path)
        mock_requests_get.reset_mock()
        mock_stream_download.reset_mock()

        # filtered asset download
        plugin.download(self.product, output_dir=self.output_dir, asset="foo")
        mock_requests_get.assert_called_once_with(
            self.product.assets["foo"]["href"],
            stream=True,
            auth=None,
            params=getattr(plugin.config, "dl_url_params", {}),
            headers=USER_AGENT,
            timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
            verify=True,
        )
        mock_stream_download.assert_not_called()

    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_assets_without_ssl(
        self, mock_requests_get, mock_requests_head
    ):
        """HTTPDownload.download() must not verify ssl when downloading assets if configured to."""
        plugin = self.get_download_plugin(self.product)
        self.product.properties["id"] = "someproduct"
        self.product.assets.clear()
        self.product.assets.update({"foo": {"href": "http://somewhere/download_asset"}})
        mock_requests_get.return_value.__enter__.return_value.iter_content.side_effect = lambda *x, **y: io.BytesIO(
            b"some content"
        )
        # download asset if ssl_verify = False
        plugin.config.ssl_verify = False

        try:
            plugin.download(self.product, output_dir=self.output_dir)
        finally:
            del plugin.config.ssl_verify
        mock_requests_head.assert_called_once_with(
            self.product.assets["foo"]["href"],
            auth=None,
            params=getattr(plugin.config, "dl_url_params", {}),
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            verify=False,
        )
        mock_requests_get.assert_called_once_with(
            self.product.assets["foo"]["href"],
            stream=True,
            auth=None,
            params=getattr(plugin.config, "dl_url_params", {}),
            headers=USER_AGENT,
            timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
            verify=False,
        )

    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_assets_filename_from_href(
        self, mock_requests_get, mock_requests_head
    ):
        """HTTPDownload.download() must create an output file."""
        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"
        self.product.assets.clear()
        self.product.assets.update(
            {"foo": {"href": "http://somewhere/mal:for;matted/something?foo=bar#baz"}}
        )
        mock_requests_get.return_value.__enter__.return_value.iter_content.return_value = io.BytesIO(
            b"some content"
        )
        mock_requests_get.return_value.__enter__.return_value.headers = (
            CaseInsensitiveDict({"Content-Disposition": ""})
        )
        mock_requests_head.return_value.headers = CaseInsensitiveDict(
            {"Content-Disposition": ""}
        )

        path = plugin.download(self.product, output_dir=self.output_dir)

        self.assertEqual(path, os.path.join(self.output_dir, "dummy_product"))
        self.assertTrue(os.path.isdir(path))
        self.assertTrue(
            os.path.isfile(os.path.join(self.output_dir, "dummy_product", "something"))
        )

        # Check if the GET request has been called for both size request and download request
        self.assertEqual(mock_requests_get.call_count, 2)
        mock_requests_get.assert_called_with(
            self.product.assets["foo"]["href"],
            stream=True,
            auth=None,
            params=getattr(plugin.config, "dl_url_params", {}),
            headers=USER_AGENT,
            timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
            verify=True,
        )
        # Check if the HEAD request has been called once for size & filename request
        mock_requests_head.assert_called_once_with(
            self.product.assets["foo"]["href"],
            auth=None,
            params=getattr(plugin.config, "dl_url_params", {}),
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            verify=True,
        )

    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_assets_filename_from_get(
        self, mock_requests_get, mock_requests_head
    ):
        """HTTPDownload.download() must create an outputfile."""
        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"
        self.product.assets.clear()
        self.product.assets.update({"foo": {"href": "http://somewhere/something"}})
        mock_requests_get.return_value.__enter__.return_value.iter_content.return_value = io.BytesIO(
            b"some content"
        )
        mock_requests_get.return_value.__enter__.return_value.headers = (
            CaseInsensitiveDict({"Content-Disposition": '; filename = "somethingelse"'})
        )
        mock_requests_head.return_value.headers = CaseInsensitiveDict(
            {"Content-Disposition": ""}
        )

        path = plugin.download(self.product, output_dir=self.output_dir)

        self.assertEqual(path, os.path.join(self.output_dir, "dummy_product"))
        self.assertTrue(os.path.isdir(path))
        asset_local_path = os.path.join(
            self.output_dir, "dummy_product", "somethingelse"
        )
        self.assertTrue(os.path.isfile(asset_local_path))

        statements = plugin.check_cache(
            self.product.assets["foo"], output_dir=self.output_dir
        )
        self.assertIsNotNone(statements)
        self.assertEqual(statements["href"], "http://somewhere/something")
        self.assertEqual(statements["file:local_path"], asset_local_path)

    @mock.patch("eodag.plugins.download.http.flatten_top_directories", autospec=True)
    @mock.patch(
        "eodag.plugins.download.http.HTTPDownload._raw_stream_download_assets",
        autospec=True,
    )
    def test_plugins_download_http_updates_asset_path_after_flatten(
        self, mock_raw_stream_download_assets, mock_flatten_top_directories
    ):
        """HTTPDownload._download_assets() must update cached paths after flattening"""

        plugin = self.get_download_plugin(self.product)
        self.product.assets.clear()
        self.product.assets.update({"foo": {"href": "http://somewhere/nested/file"}})
        fs_dir_path = os.path.join(self.output_dir, "dummy_product")
        old_dir = os.path.join(fs_dir_path, "nested")
        mock_flatten_top_directories.return_value = old_dir, fs_dir_path
        mock_raw_stream_download_assets.return_value = [
            StreamResponse(content=iter([b"some content"]), arcname="nested/file")
        ]

        result = plugin._download_assets(
            self.product,
            [self.product.assets["foo"]],
            progress_callback=ProgressCallback(disable=True),
            output_dir=self.output_dir,
        )

        asset = self.product.assets["foo"]
        self.assertEqual(result, fs_dir_path)
        self.assertEqual(asset["file:local_path"], os.path.join(fs_dir_path, "file"))
        mock_flatten_top_directories.assert_called_once_with(fs_dir_path)

    @mock.patch("eodag.plugins.download.http.flatten_top_directories", autospec=True)
    @mock.patch(
        "eodag.plugins.download.http.HTTPDownload._raw_stream_download_assets",
        autospec=True,
    )
    def test_plugins_download_http_assets_sequential_executor(
        self, mock_raw_stream_download_assets, mock_flatten_top_directories
    ):
        """HTTPDownload._download_assets() must set statements when downloading sequentially"""

        plugin = self.get_download_plugin(self.product)
        self.product.assets.clear()
        self.product.assets.update(
            {
                "foo": {"href": "http://somewhere/foo"},
                "bar": {"href": "http://somewhere/bar"},
            }
        )
        fs_dir_path = os.path.join(self.output_dir, "dummy_product")
        mock_flatten_top_directories.return_value = fs_dir_path, fs_dir_path
        mock_raw_stream_download_assets.side_effect = (
            lambda _self, _product, _executor, _auth, _cb, assets_values, **kw: [
                StreamResponse(content=iter([b"content"]), arcname=asset.key)
                for asset in assets_values
            ]
        )
        executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="eodag-download-all"
        )

        with mock.patch.object(
            executor, "submit", side_effect=AssertionError("must not submit")
        ):
            plugin._download_assets(
                self.product,
                list(self.product.assets.values()),
                progress_callback=ProgressCallback(disable=True),
                executor=executor,
                output_dir=self.output_dir,
            )
        executor.shutdown()

        for key in ("foo", "bar"):
            asset_path = os.path.join(fs_dir_path, key)
            self.assertTrue(os.path.isfile(asset_path))
            statements = plugin.check_cache(
                self.product.assets[key], output_dir=self.output_dir
            )
            self.assertEqual(statements["file:local_path"], asset_path)

    @mock.patch("eodag.plugins.download.http.HTTPDownload._get_asset_sizes")
    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_assets_error(
        self, mock_requests_get, mock_requests_head, mock_asset_size
    ):
        """HTTPDownload.download() must create an outputfile."""
        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"
        self.product.assets.clear()
        self.product.assets.update({"foo": {"href": "http://somewhere/something"}})
        self.product.assets.update({"bar": {"href": "http://somewhere/anotherthing"}})
        res = MockResponse({"a": "a"}, 400)
        mock_requests_get.side_effect = res
        mock_requests_head.return_value.headers = CaseInsensitiveDict(
            {"Content-Disposition": ""}
        )
        with self.assertRaises(DownloadError):
            plugin.download(self.product, output_dir=self.output_dir)

    @mock.patch(
        "eodag.plugins.download.http.ProgressCallback.__call__",
        autospec=True,
    )
    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_assets_interrupt(
        self, mock_requests_get, mock_requests_head, mock_progress_callback
    ):
        """HTTPDownload.download() must download assets to a temporary file."""
        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"
        self.product.assets.clear()
        self.product.assets.update({"foo": {"href": "http://somewhere/something"}})
        mock_requests_get.return_value.__enter__.return_value.iter_content.return_value = iter(
            [
                b"some ",
                b"content",
            ]
        )
        mock_requests_get.return_value.__enter__.return_value.headers = (
            CaseInsensitiveDict({"Content-Disposition": '; filename = "somethingelse"'})
        )
        mock_requests_head.return_value.headers = CaseInsensitiveDict(
            {"Content-Disposition": ""}
        )
        # ProgressCallback is called twice in HTTPDownload._download_assets. The
        # temporary asset file is created after the first call.
        progress_callback_exception = Exception("Interrupt assets download")
        mock_progress_callback.side_effect = [
            mock.DEFAULT,
            progress_callback_exception,
        ]
        with self.assertRaises(Exception) as cm:
            plugin.download(self.product, output_dir=self.output_dir)
        # Interrupted download
        self.assertEqual(progress_callback_exception, cm.exception)
        # Product location not changed
        self.assertEqual(self.product.location, "http://somewhere")
        # Temp file created
        self.assertTrue(
            os.path.exists(
                os.path.join(self.output_dir, "dummy_product", "somethingelse~")
            )
        )
        # Asset file not created
        self.assertFalse(
            os.path.exists(
                os.path.join(self.output_dir, "dummy_product", "somethingelse")
            )
        )

    @mock.patch(
        "eodag.plugins.download.http.ProgressCallback.__call__",
        autospec=True,
    )
    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_assets_stream_zip_interrupt(
        self, mock_requests_get, mock_requests_head, mock_progress_callback
    ):
        """HTTPDownload.stream_download must raise an error if an error is returned by the provider."""
        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"
        self.product.assets.clear()
        self.product.assets.update({"foo": {"href": "http://somewhere/something"}})
        self.product.assets.update({"any": {"href": "http://somewhere/anything"}})

        # first asset returns error
        mock_requests_get.return_value = MockResponse(status_code=404)
        mock_requests_head.return_value.headers = CaseInsensitiveDict(
            {
                "Content-Disposition": "",
                "Content-Length": "10",
            }
        )

        with self.assertRaises(DownloadError):
            plugin.stream_download(self.product, output_dir=self.output_dir)
        # Interrupted download
        # Product location not changed
        self.assertEqual(self.product.location, "http://somewhere")

    @mock.patch("eodag.plugins.download.http.HTTPDownload._get_asset_sizes")
    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_assets_too_many_requests_error(
        self, mock_requests_get, mock_requests_head, mock_asset_size
    ):
        """HTTPDownload.download() must handle a 429 (Too many requests) error."""
        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"
        self.product.assets.clear()
        self.product.assets.update({"foo": {"href": "http://somewhere/something"}})
        self.product.assets.update({"bar": {"href": "http://somewhere/anotherthing"}})
        res = MockResponse({"a": "a"}, 429)
        mock_requests_get.side_effect = res
        mock_requests_head.return_value.headers = CaseInsensitiveDict(
            {"Content-Disposition": ""}
        )
        with self.assertRaises(QuotaExceededError):
            plugin.download(self.product, output_dir=self.output_dir)

    def test_plugins_download_http_stream_dict_misconfigured(self):
        """HTTPDownload.stream_download() must raise an error if misconfigured."""
        plugin = self.get_download_plugin(self.product)
        with self.assertRaises(MisconfiguredError):
            # Wrong auth instance
            wrong_auth = "not_an_auth_instance"
            plugin.stream_download(
                self.product, auth=wrong_auth, output_dir=self.output_dir
            )

    def test_stream_download_single_asset(self):
        """HTTPDownload.stream_download() must return a response with a single asset."""
        plugin = self.get_download_plugin(self.product)

        asset = mock.MagicMock()
        asset.filename = "myfile.txt"
        asset.headers = {}
        asset.get.return_value = None

        self.product.assets = mock.Mock()
        self.product.assets.get.return_value = None
        self.product.assets.get_values.return_value = [asset]

        chunk_asset1 = mock.Mock()
        chunk_asset1.content = [b"chunk1"]
        chunk_asset1.arcname = "file1.txt"
        chunk_asset1.size = len(b"chunk1")
        plugin._raw_stream_download_assets = mock.Mock(return_value=[chunk_asset1])

        self.product.assets.__len__ = lambda self=self.product.assets: 1

        response = plugin.stream_download(self.product, output_dir=self.output_dir)

        self.assertEqual(response.arcname, "file1.txt")
        self.assertEqual(response.size, len(b"chunk1"))
        self.assertEqual(response.content, [b"chunk1"])

    def test_stream_download_multiple_assets_zip(self):
        """HTTPDownload.stream_download() must return a zipped response with multiple assets."""
        plugin = self.get_download_plugin(self.product)

        asset1 = mock.MagicMock(filename="file1.txt")
        asset2 = mock.MagicMock(filename="file2.txt")
        asset1.get.side_effect = asset2.get.side_effect = lambda key, default=None: (
            "text/plain" if key == "type" else default
        )

        self.product.assets = mock.Mock()
        self.product.assets.get.return_value = None
        self.product.assets.get_values.return_value = [asset1, asset2]

        chunk_asset1 = mock.Mock()
        chunk_asset1.content = [b"chunk1"]
        chunk_asset1.arcname = "file1.txt"
        chunk_asset1.size = len(b"chunk1")

        chunk_asset2 = mock.Mock()
        chunk_asset2.content = [b"chunk2"]
        chunk_asset2.arcname = "file2.txt"
        chunk_asset2.size = len(b"chunk2")

        plugin._raw_stream_download_assets = mock.Mock(
            return_value=[chunk_asset1, chunk_asset2]
        )
        self.product.assets.__len__ = lambda self=self.product.assets: 2

        with mock.patch("eodag.plugins.download.http.ZipStream") as mockZipStream:
            fake_zip = mock.Mock()
            fake_zip.add = mock.Mock()

            # Simulate iterator
            def fake_iter(*args, **kwargs):
                for i in range(0, 2):
                    yield i
                yield i

            fake_zip.__iter__ = fake_iter

            fake_zip.__len__ = mock.Mock(return_value=2)
            mockZipStream.return_value = fake_zip

            response = plugin.stream_download(self.product, output_dir=self.output_dir)

        self.assertIn("Content-Disposition", response.headers)
        self.assertIn(".zip", response.headers["Content-Disposition"])

    def test_stream_download_asset_not_available(self):
        """HTTPDownload.stream_download() must raise NotAvailableError if asset not available."""
        plugin = self.get_download_plugin(self.product)

        self.product.assets = mock.Mock()
        self.product.assets.get_values.side_effect = NotAvailableError("not available")
        self.product.assets.__len__ = lambda self=self.product.assets: 1

        with self.assertRaises(NotAvailableError):
            plugin.stream_download(
                self.product, asset="foo", output_dir=self.output_dir
            )

    def test_stream_download_single_asset_with_type(self):
        """HTTPDownload.stream_download() must return a response with a single asset and its type."""
        plugin = self.get_download_plugin(self.product)

        asset = mock.Mock()
        asset.filename = "myfile.txt"
        asset.headers = {}
        asset.__getitem__ = lambda self, key: "text/plain" if key == "type" else None
        asset.get.side_effect = lambda key, default=None: (
            "text/plain" if key == "type" else default
        )

        self.product.assets = mock.Mock()
        self.product.assets.get.return_value = None
        self.product.assets.get_values.return_value = [asset]
        self.product.assets.__len__ = lambda self=self.product.assets: 1

        chunk_asset1 = mock.Mock()
        chunk_asset1.content = [b"chunk1"]
        chunk_asset1.arcname = "file1.txt"
        chunk_asset1.size = len(b"chunk1")
        chunk_asset1.headers = {}

        plugin._raw_stream_download_assets = mock.Mock(return_value=[chunk_asset1])

        response = plugin.stream_download(self.product, output_dir=self.output_dir)

        self.assertEqual(response.arcname, "file1.txt")
        self.assertEqual(response.size, len(b"chunk1"))
        self.assertEqual(response.content, [b"chunk1"])

    def test_stream_download_download_link(self):
        """HTTPDownload.stream_download() must stream download_link asset with product headers."""
        plugin = self.get_download_plugin(self.product)

        self.product.assets.clear()
        self.product.remote_location = "http://somewhere"
        self.product.headers = {}

        chunk_iter = iter([b"first_chunk", b"second_chunk"])
        plugin._raw_stream_download = mock.Mock(return_value=chunk_iter)

        try:
            response = plugin.stream_download(self.product, output_dir=self.output_dir)
        finally:
            del plugin._raw_stream_download

        self.assertEqual(list(response.content), [b"first_chunk", b"second_chunk"])
        self.assertEqual(response.headers, self.product.headers)

    def test_stream_download_strips_hop_by_hop_headers(self):
        """HTTPDownload.stream_download() must strip hop-by-hop headers but keep useful ones"""

        plugin = self.get_download_plugin(self.product)
        # plugin instances are cached per provider, remove any leftover mock from other tests
        plugin.__dict__.pop("_raw_stream_download", None)

        self.product.assets.clear()
        self.product.remote_location = "http://somewhere"

        fake_response = mock.Mock()
        fake_response.headers = CaseInsensitiveDict(
            {
                # hop-by-hop headers that must be stripped
                "Connection": "keep-alive",
                "Content-Encoding": "br",
                "Transfer-Encoding": "chunked",
                "Keep-Alive": "timeout=5",
                # useful headers that must be kept
                "Content-Type": "application/octet-stream",
                "Content-Disposition": 'attachment; filename="foo.zip"',
                "ETag": '"abc123"',
                "content-length": "12",
            }
        )
        fake_response.status_code = 200
        fake_response.url = "http://somewhere/foo.zip"
        fake_response.raise_for_status = mock.Mock()
        fake_response.iter_content = mock.Mock(return_value=iter([b"some_content"]))

        with mock.patch(
            "eodag.plugins.download.http.requests.Session.request",
            return_value=fake_response,
        ):
            response = plugin.stream_download(self.product, output_dir=self.output_dir)

        for excluded_header in (
            "Connection",
            "Content-Encoding",
            "Transfer-Encoding",
            "Keep-Alive",
        ):
            self.assertNotIn(excluded_header, response.headers)

        self.assertEqual(response.headers["Content-Type"], "application/octet-stream")
        self.assertEqual(response.headers["ETag"], '"abc123"')
        # filename is derived from Content-Disposition and re-set by StreamResponse
        self.assertIn("foo.zip", response.headers["Content-Disposition"])

    def test_stream_download_product_empty_raises(self):
        """HTTPDownload.stream_download() must raise NotAvailableError if download_link is empty."""
        plugin = self.get_download_plugin(self.product)

        self.product.assets.clear()
        self.product.remote_location = "http://somewhere"
        self.product.headers = {}

        plugin._raw_stream_download = mock.Mock(return_value=iter([]))

        try:
            with self.assertRaises(NotAvailableError) as cm:
                plugin.stream_download(self.product, output_dir=self.output_dir)
        finally:
            del plugin._raw_stream_download

        self.assertIn(self.product.properties.get("id", ""), str(cm.exception))

    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_assets_resume(
        self, mock_requests_get, mock_requests_head
    ):
        """HTTPDownload.download() must resume the interrupted download of assets."""
        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"
        self.product.assets.clear()
        self.product.assets.update({"foo": {"href": "http://somewhere/something"}})
        mock_requests_get.return_value.__enter__.return_value.iter_content.return_value = io.BytesIO(
            b"some content"
        )
        mock_requests_get.return_value.__enter__.return_value.headers = (
            CaseInsensitiveDict({"Content-Disposition": '; filename = "somethingelse"'})
        )
        mock_requests_head.return_value.headers = CaseInsensitiveDict(
            {"Content-Disposition": ""}
        )
        # Create directory structure and temp file
        os.makedirs(os.path.join(self.output_dir, "dummy_product"))
        with open(
            os.path.join(self.output_dir, "dummy_product", "somethingelse~"),
            "w",
        ):
            pass
        path = plugin.download(self.product, output_dir=self.output_dir)
        # Product directory created
        self.assertEqual(path, os.path.join(self.output_dir, "dummy_product"))
        self.assertTrue(os.path.isdir(path))
        # Asset file created
        self.assertTrue(
            os.path.isfile(
                os.path.join(self.output_dir, "dummy_product", "somethingelse")
            )
        )
        # Temp file removed
        self.assertFalse(
            os.path.exists(
                os.path.join(self.output_dir, "dummy_product", "somethingelse~")
            )
        )

    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_asset_filter(
        self, mock_requests_get, mock_requests_head
    ):
        """HTTPDownload.download() must create an outputfile."""
        plugin = self.get_download_plugin(self.product)
        self.product.collection = "FOO"
        self.product.location = self.product.remote_location = "http://foo"
        self.product.properties["id"] = "someproduct"
        self.product.assets.clear()
        self.product.assets.update(
            {
                "somewhere": {"href": "http://somewhere/something", "title": "foo"},
                "elsewhere": {"href": "http://elsewhere/anything", "title": "boo"},
            }
        )
        mock_requests_get.return_value.__enter__.return_value.iter_content.return_value = io.BytesIO(
            b"some content"
        )
        mock_requests_get.return_value.__enter__.return_value.headers = (
            CaseInsensitiveDict({"Content-Disposition": '; filename = "somethingelse"'})
        )
        mock_requests_head.return_value.headers = CaseInsensitiveDict(
            {"Content-Disposition": ""}
        )
        expected_hashes = {
            "somewhere": hashlib.md5(
                "FOO-someproduct-somewhere".encode("utf-8")
            ).hexdigest(),
            "elsewhere": hashlib.md5(
                "FOO-someproduct-elsewhere".encode("utf-8")
            ).hexdigest(),
        }
        cache_dir = Path(self.output_dir) / ".downloaded"
        product_output_dir = Path(self.output_dir) / "dummy_product"

        # Call download() with asset specified using pattern -----------------------------------------------------------
        path = plugin.download(self.product, output_dir=self.output_dir, asset="else.*")

        # 2 requests.get calls for 'elsewhere' asset:
        # 1. fetch_asset_size / 2. _raw_stream_download_assets
        self.assertEqual(2, mock_requests_get.call_count)
        self.assertTrue(
            all(
                mock_call.args == ("http://elsewhere/anything",)
                for mock_call in mock_requests_get.call_args_list
            )
        )
        # statements for the asset should be stored in the cache
        self.assertFalse(
            os.path.isfile(cache_dir / f"{expected_hashes['somewhere']}.json")
        )
        self.assertTrue(
            os.path.isfile(cache_dir / f"{expected_hashes['elsewhere']}.json")
        )
        somewhere_statements = plugin.check_cache(
            self.product.assets["somewhere"], output_dir=self.output_dir
        )
        self.assertIsNone(somewhere_statements)
        elsewhere_statements = plugin.check_cache(
            self.product.assets["elsewhere"], output_dir=self.output_dir
        )
        self.assertEqual(elsewhere_statements["href"], "http://elsewhere/anything")
        self.assertEqual(
            elsewhere_statements["file:local_path"],
            str(product_output_dir / "somethingelse"),
        )

        # output file and dir created
        self.assertEqual(path, str(product_output_dir))
        self.assertTrue(os.path.isdir(path))
        self.assertTrue(os.path.isfile(product_output_dir / "somethingelse"))

        # Another download() call without asset specified: should only download remaining asset ------------------------
        plugin.download(self.product, output_dir=self.output_dir)

        # 2 more requests.get calls for 'somewhere' asset:
        # 1. fetch_asset_size / 2. _raw_stream_download_assets
        self.assertEqual(4, mock_requests_get.call_count)
        self.assertTrue(
            all(
                mock_call.args == ("http://somewhere/something",)
                for mock_call in mock_requests_get.call_args_list[2:]
            )
        )
        # statements for the asset should be stored in the cache
        self.assertTrue(
            os.path.isfile(cache_dir / f"{expected_hashes['somewhere']}.json")
        )
        self.assertTrue(
            os.path.isfile(cache_dir / f"{expected_hashes['elsewhere']}.json")
        )
        somewhere_statements = plugin.check_cache(
            self.product.assets["somewhere"], output_dir=self.output_dir
        )
        self.assertEqual(somewhere_statements["href"], "http://somewhere/something")
        self.assertEqual(
            somewhere_statements["file:local_path"],
            str(product_output_dir / "somethingelse"),
        )
        elsewhere_statements = plugin.check_cache(
            self.product.assets["elsewhere"], output_dir=self.output_dir
        )
        self.assertEqual(elsewhere_statements["href"], "http://elsewhere/anything")
        self.assertEqual(
            elsewhere_statements["file:local_path"],
            str(product_output_dir / "somethingelse"),
        )

    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_assets_filename_from_head(
        self, mock_requests_get, mock_requests_head
    ):
        """HTTPDownload.download() must create an outputfile."""
        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"
        self.product.assets.clear()
        self.product.assets.update({"foo": {"href": "http://somewhere/something"}})
        mock_requests_get.return_value.__enter__.return_value.iter_content.return_value = io.BytesIO(
            b"some content"
        )
        mock_requests_get.return_value.__enter__.return_value.headers = (
            CaseInsensitiveDict({"Content-Disposition": '; filename = "somethingelse"'})
        )
        mock_requests_head.return_value.headers = CaseInsensitiveDict(
            {"Content-Disposition": '; filename = "anotherthing"'}
        )

        path = plugin.download(self.product, output_dir=self.output_dir)

        self.assertEqual(path, os.path.join(self.output_dir, "dummy_product"))
        self.assertTrue(os.path.isdir(path))
        self.assertTrue(
            os.path.isfile(
                os.path.join(self.output_dir, "dummy_product", "anotherthing")
            )
        )

    @mock.patch("eodag.utils.ProgressCallback.reset", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_assets_size(
        self, mock_requests_get, mock_requests_head, mock_progress_callback_reset
    ):
        """HTTPDownload.download() must get assets sizes."""
        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.assets.clear()
        self.product.assets.update(
            {
                "foo": {"href": "http://somewhere/a"},
                "bar": {"href": "http://somewhere/b"},
            }
        )

        mock_requests_head.return_value.headers = CaseInsensitiveDict(
            {
                "Content-Length": "1",
                "Content-Disposition": '; size = "2"',
            }
        )
        mock_requests_get.return_value.__enter__.return_value.iter_content.return_value = io.BytesIO(
            b"some content"
        )
        mock_requests_get.return_value.__enter__.return_value.headers = (
            CaseInsensitiveDict(
                {
                    "Content-Length": "3",
                    "Content-Disposition": '; size = "4"',
                }
            )
        )

        # size from HEAD / Content-Length
        with TemporaryDirectory() as temp_dir:
            plugin.download(self.product, output_dir=temp_dir)
        mock_progress_callback_reset.assert_called_once_with(mock.ANY, total=1 + 1)

        # size from HEAD / Content-Disposition
        mock_requests_head.return_value.headers.pop("Content-Length")
        mock_progress_callback_reset.reset_mock()
        self.product.location = "http://somewhere"
        self.product.assets.clear()
        self.product.assets.update(
            {
                "foo": {"href": "http://somewhere/a"},
                "bar": {"href": "http://somewhere/b"},
            }
        )
        with TemporaryDirectory() as temp_dir:
            plugin.download(self.product, output_dir=temp_dir)
        mock_progress_callback_reset.assert_called_once_with(mock.ANY, total=2 + 2)

        # size from GET / Content-Length
        mock_requests_head.return_value.headers.pop("Content-Disposition")
        mock_progress_callback_reset.reset_mock()
        self.product.location = "http://somewhere"
        self.product.assets.clear()
        self.product.assets.update(
            {
                "foo": {"href": "http://somewhere/a"},
                "bar": {"href": "http://somewhere/b"},
            }
        )
        with TemporaryDirectory() as temp_dir:
            plugin.download(self.product, output_dir=temp_dir)
        mock_progress_callback_reset.assert_called_once_with(mock.ANY, total=3 + 3)

        # size from GET / Content-Disposition
        mock_requests_get.return_value.__enter__.return_value.iter_content.return_value = io.BytesIO(
            b"some content"
        )
        mock_requests_get.return_value.__enter__.return_value.headers.pop(
            "Content-Length"
        )
        mock_progress_callback_reset.reset_mock()
        self.product.location = "http://somewhere"
        self.product.assets.clear()
        self.product.assets.update(
            {
                "foo": {"href": "http://somewhere/a"},
                "bar": {"href": "http://somewhere/b"},
            }
        )
        with TemporaryDirectory() as temp_dir:
            plugin.download(self.product, output_dir=temp_dir)
        mock_progress_callback_reset.assert_called_once_with(mock.ANY, total=4 + 4)

        # unknown size
        mock_requests_get.return_value.__enter__.return_value.headers.pop(
            "Content-Disposition"
        )
        mock_progress_callback_reset.reset_mock()
        self.product.location = "http://somewhere"
        self.product.assets.clear()
        self.product.assets.update(
            {
                "foo": {"href": "http://somewhere/a"},
                "bar": {"href": "http://somewhere/b"},
            }
        )
        with TemporaryDirectory() as temp_dir:
            plugin.download(self.product, output_dir=temp_dir)
        mock_progress_callback_reset.assert_called_once_with(mock.ANY, total=None)

    def test_plugins_download_http_one_local_asset(
        self,
    ):
        """HTTPDownload.download() must handle one local asset."""
        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"
        self.product.assets.clear()
        self.product.assets.update(
            {
                "foo": {
                    "href": path_to_uri(
                        os.path.abspath(os.path.join(os.sep, "somewhere", "something"))
                    )
                }
            }
        )

        path = plugin.download(self.product, output_dir=self.output_dir)

        self.assertEqual(path, uri_to_path(self.product.assets["foo"]["href"]))
        # empty product download directory should have been removed
        self.assertFalse(Path(os.path.join(self.output_dir, "dummy_product")).exists())

    def test_plugins_download_http_several_local_assets(
        self,
    ):
        """HTTPDownload.download() must handle several local assets."""
        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"
        self.product.assets.clear()
        self.product.assets.update(
            {
                "foo": {
                    "href": path_to_uri(
                        os.path.abspath(os.path.join(os.sep, "somewhere", "onething"))
                    )
                },
                "bar": {
                    "href": path_to_uri(
                        os.path.abspath(
                            os.path.join(os.sep, "somewhere", "something", "else")
                        )
                    )
                },
                "baz": {
                    "href": path_to_uri(
                        os.path.abspath(
                            os.path.join(os.sep, "somewhere", "another", "thing")
                        )
                    )
                },
            }
        )

        path = plugin.download(self.product, output_dir=self.output_dir)

        # assets common path
        self.assertEqual(
            os.path.normcase(path),
            os.path.normcase(os.path.abspath(os.path.join(os.sep, "somewhere"))),
        )
        # empty product download directory should have been removed
        self.assertFalse(Path(os.path.join(self.output_dir, "dummy_product")).exists())

    def test_plugins_download_http_order_download_cop_ads(
        self,
    ):
        """HTTPDownload.download must order the product if needed."""
        self.product.provider = "cop_ads"
        self.product.collection = "CAMS_EAC4"
        product_dataset = "cams-global-reanalysis-eac4"

        plugin = self.get_download_plugin(self.product)
        auth = self.get_auth_plugin(plugin, self.product)
        auth.config.credentials = {"apikey": "anicekey"}
        self.product.register_downloader(plugin, auth)

        endpoint = "https://ads.atmosphere.copernicus.eu/api/retrieve/v1"
        self.product.properties["id"] = "CAMS_EAC4_ORDERABLE_12345"
        self.product.assets["download_link"] = {
            "href": NOT_AVAILABLE + '?{"foo": "bar"}',
            "eodag:order_link": f"{endpoint}/processes/{product_dataset}/execution"
            + '?{"foo": "bar"}',
        }
        self.assertEqual(
            self.product.assets["download_link"]["order:status"], OFFLINE_STATUS
        )

        @responses.activate(registry=responses.registries.OrderedRegistry)
        def run():
            responses.add(
                responses.POST,
                f"{endpoint}/processes/{product_dataset}/execution",
                status=200,
                content_type="application/json",
                body=b'{"status": "accepted", "jobID": "dummy_request_id"}',
                auto_calculate_content_length=True,
            )
            responses.add(
                responses.GET,
                f"{endpoint}/jobs/dummy_request_id",
                status=200,
                content_type="application/json",
                body=b'{"status": "running", "jobID": "dummy_request_id"}',
                auto_calculate_content_length=True,
            )
            responses.add(
                responses.GET,
                f"{endpoint}/jobs/dummy_request_id",
                status=200,
                content_type="application/json",
                body=(b'{"status": "successful", "jobID": "dummy_request_id"}'),
                auto_calculate_content_length=True,
            )
            responses.add(
                responses.GET,
                f"{endpoint}/jobs/dummy_request_id/results",
                status=200,
                content_type="application/json",
                body=(
                    b'{"asset": {"value": {"href": "http://somewhere/download/dummy_request_id"}}}'
                ),
                auto_calculate_content_length=True,
            )
            responses.add(
                responses.GET,
                "http://somewhere/download/dummy_request_id",
                status=200,
                content_type="application/octet-stream",
                adding_headers=CaseInsensitiveDict(
                    {"Content-Disposition": "", "PRIVATE-TOKEN": "anicekey"}
                ),
                body=b"some content",
                auto_calculate_content_length=True,
            )

            output_data_path = self.output_dir

            # expected values
            expected_remote_location = "http://somewhere/download/dummy_request_id"
            expected_order_status_link = (
                f"{endpoint}/jobs/dummy_request_id?request=true"
            )
            expected_path = os.path.join(output_data_path, "CAMS_EAC4_dummy_request_id")
            # download
            path = self.product.download(
                output_dir=output_data_path,
                wait=0.001 / 60,
                timeout=0.2 / 60,
            )
            self.assertEqual(self.product.remote_location, expected_remote_location)
            download_link = self.product.assets["download_link"]
            self.assertEqual(download_link["href"], expected_remote_location)
            self.assertEqual(
                download_link["eodag:status_link"], expected_order_status_link
            )
            self.assertEqual(download_link["order:id"], "dummy_request_id")
            self.assertEqual(download_link["order:status"], ONLINE_STATUS)
            self.assertNotIn("eodag:status_link", self.product.properties)
            self.assertEqual(path, expected_path)
            self.assertEqual(self.product.location, path_to_uri(expected_path))

        run()

    @mock.patch(
        "eodag.plugins.authentication.token.TokenAuth.authenticate", autospec=True
    )
    @mock.patch("eodag.plugins.download.http.requests.request", autospec=True)
    def test_plugins_download_http_order_get(self, mock_request, mock_auth_request):
        """HTTPDownload._order() must request using eodag:order_link and GET protocol."""
        plugin = self.get_download_plugin(self.product)
        plugin.config.order_method = "GET"
        self.product.assets["download_link"] = {
            "href": "https://copernicus.nci.org.au/dummy",
            "eodag:order_link": "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/download",
        }
        asset = self.product.assets["download_link"]

        # customized timeout
        timeout_backup = getattr(plugin.config, "timeout", None)
        plugin.config.timeout = 10
        try:
            auth_plugin = self.get_auth_plugin(plugin, self.product)
            auth_plugin.config.credentials = {"username": "foo", "password": "bar"}
            auth = auth_plugin.authenticate()

            plugin._order(asset, auth=auth)

            mock_request.assert_called_once_with(
                method="GET",
                url=asset["eodag:order_link"],
                auth=auth,
                headers=USER_AGENT,
                timeout=10,
                verify=True,
            )
        finally:
            if timeout_backup:
                plugin.config.timeout = timeout_backup
            else:
                del plugin.config.timeout

    @mock.patch(
        "eodag.plugins.authentication.token.TokenAuth.authenticate", autospec=True
    )
    @mock.patch("eodag.plugins.download.http.requests.request", autospec=True)
    def test_plugins_download_http_order_get_raises_if_request_500(
        self, mock_request, mock_auth_request
    ):
        """HTTPDownload._order() must raise an error if request to backend provider failed."""
        # Configure mock to raise an error
        mock_request.return_value = MockResponse(status_code=500)

        plugin = self.get_download_plugin(self.product)
        plugin.config.order_method = "GET"
        self.product.assets["download_link"] = {
            "href": "https://copernicus.nci.org.au/dummy",
            "eodag:order_link": "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/download",
        }
        asset = self.product.assets["download_link"]

        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.config.credentials = {"username": "foo", "password": "bar"}
        auth = auth_plugin.authenticate()

        # Verify that a DownloadError is raised
        with self.assertRaises(DownloadError) as context:
            plugin._order(asset, auth=auth)
        self.assertIn("could not be ordered", str(context.exception))

        mock_request.assert_called_once_with(
            method="GET",
            url=asset["eodag:order_link"],
            auth=auth,
            headers=USER_AGENT,
            timeout=5,
            verify=True,
        )

    @mock.patch("eodag.plugins.download.http.requests.request", autospec=True)
    @mock.patch(
        "eodag.plugins.authentication.token.TokenAuth.authenticate", autospec=True
    )
    def test_plugins_download_http_order_get_raises_if_request_400(
        self, mock_auth_request, mock_request
    ):
        # Set up the EOProduct and the necessary properties
        plugin = self.get_download_plugin(self.product)
        plugin.config.order_method = "GET"
        self.product.assets["download_link"] = {
            "href": "https://copernicus.nci.org.au/dummy",
            "eodag:order_link": "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/download",
        }
        asset = self.product.assets["download_link"]

        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.config.credentials = {"username": "foo", "password": "bar"}

        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.config.credentials = {"username": "foo", "password": "bar"}
        auth = auth_plugin.authenticate()

        # Mock the response to raise HTTPError with a 400 status
        mock_request.return_value = MockResponse(status_code=400)

        # Test the function, expecting ValidationError to be raised
        with self.assertRaises(ValidationError) as context:
            plugin._order(asset, auth=auth)
        self.assertIn("could not be ordered", str(context.exception))

        mock_request.assert_called_once_with(
            method="GET",
            url=asset["eodag:order_link"],
            auth=auth,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            verify=True,
        )

    @mock.patch("eodag.plugins.download.http.requests.request", autospec=True)
    @mock.patch(
        "eodag.plugins.authentication.token.TokenAuth.authenticate", autospec=True
    )
    def test_plugins_download_http_order_post(self, mock_auth_request, mock_request):
        """HTTPDownload._order() must request using eodag:order_link and POST protocol."""
        plugin = self.get_download_plugin(self.product)
        plugin.config.order_method = "POST"
        self.product.assets["download_link"] = {
            "href": "https://copernicus.nci.org.au/dummy",
            "eodag:order_link": "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/download",
        }
        asset = self.product.assets["download_link"]

        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.config.credentials = {"username": "foo", "password": "bar"}
        auth = auth_plugin.authenticate()

        # eodag:order_link without query query args
        plugin._order(asset, auth=auth)
        mock_request.assert_called_once_with(
            method="POST",
            url=asset["eodag:order_link"],
            auth=auth,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            verify=True,
        )
        # eodag:order_link with query query args
        mock_request.reset_mock()
        asset["eodag:order_link"] = (
            "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/download?foo=bar"
        )
        plugin._order(asset, auth=auth)
        mock_request.assert_called_once_with(
            method="POST",
            url="https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/download",
            auth=auth,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            json={"foo": ["bar"]},
            verify=True,
        )

        # eodag:order_link with JSON data containing a query string
        mock_request.reset_mock()
        asset["eodag:order_link"] = (
            "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/download?"
            '{"location": "dataset_id=lorem&data_version=202211", "cacheable": "true"}'
        )
        plugin._order(asset, auth=auth)
        mock_request.assert_called_once_with(
            method="POST",
            url="https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/download",
            auth=auth,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            json={
                "location": "dataset_id=lorem&data_version=202211",
                "cacheable": "true",
            },
            verify=True,
        )

    @mock.patch(
        "eodag.plugins.authentication.token.TokenAuth.authenticate", autospec=True
    )
    def test_plugins_download_http_order_status(self, mock_auth_request):
        """HTTPDownload._order_status() must request status using eodag:status_link."""
        plugin = self.get_download_plugin(self.product)
        plugin.config.order_status = {
            "asset_mapping": {
                "eodag:order_percent": "$.json.progress_percentage",
            },
            "metadata_mapping": {
                "that": "$.json.that",
            },
            "error": {"that": "failed"},
        }
        self.product.assets["download_link"] = {
            "href": "https://copernicus.nci.org.au/dummy",
            "eodag:order_link": "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/download",
            "eodag:status_link": "http://somewhere/order-status",
        }
        asset = self.product.assets["download_link"]

        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.config.credentials = {"username": "foo", "password": "bar"}
        auth = auth_plugin.authenticate()

        @responses.activate(registry=responses.registries.FirstMatchRegistry)
        def run():
            url = "http://somewhere/order-status"
            responses.add(
                responses.GET,
                url,
                status=200,
                json={"progress_percentage": 50, "that": "failed"},
            )

            with self.assertRaises(DownloadError):
                plugin._order_status(asset, auth=auth)

            self.assertEqual(asset["eodag:order_percent"], 50)
            self.assertEqual(self.product.properties["that"], "failed")
            self.assertIn(
                list(USER_AGENT.items())[0], responses.calls[0].request.headers.items()
            )
            self.assertEqual(len(responses.calls), 1)

        run()

    @mock.patch("eodag.plugins.download.http.requests.request", autospec=True)
    def test_plugins_download_http_order_status_from_head_headers(self, mock_request):
        """HTTPDownload._order_status() must not parse an empty HEAD response."""
        plugin = HTTPDownload(
            provider=self.product.provider,
            config=PluginConfig.from_mapping(
                {
                    "type": "HTTPDownload",
                    "order_status": {
                        "success": {"http_code": 200},
                        "on_success": {
                            "asset_mapping": {
                                "href": "$.headers.location",
                            },
                        },
                    },
                },
            ),
        )
        self.product.assets["download_link"] = {
            "eodag:order_link": "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/download",
            "eodag:status_link": "http://somewhere/order-status",
        }
        asset = self.product.assets["download_link"]
        response = mock_request.return_value
        response.status_code = 200
        # Use different case for header keys to test that case-insensitivity is preserved
        response.headers = CaseInsensitiveDict(
            {
                "Content-Type": "application/json",
                "Location": "http://somewhere/download",
            }
        )
        response.json.side_effect = ValueError("empty response")

        plugin._order_status(asset)

        self.assertEqual(asset["href"], "http://somewhere/download")
        self.assertEqual(asset["order:status"], ONLINE_STATUS)
        self.assertEqual(self.product.remote_location, "http://somewhere/download")
        response.json.assert_not_called()

    @mock.patch("eodag.plugins.download.http.requests.request", autospec=True)
    def test_plugins_download_http_order_success_body_mappings(self, mock_request):
        """Either success mapping can require a GET after HEAD."""
        for href_mapping, published_mapping in (
            ("$.json.href", "$.headers.Finished"),
            ("$.headers.Location", "{$.json.finished#to_iso_utc_datetime}"),
        ):
            with self.subTest(href=href_mapping, published=published_mapping):
                on_success = {
                    "asset_mapping": {
                        "href": href_mapping,
                        "custom:field": "{published}",
                    },
                    "metadata_mapping": {"published": published_mapping},
                }
                plugin = HTTPDownload(
                    self.product.provider,
                    PluginConfig.from_mapping(
                        {
                            "type": "HTTPDownload",
                            "order_status": {
                                "asset_mapping": {"order:date": "$.json.created"},
                                "metadata_mapping": {"created": "$.json.created"},
                                "success": {"http_code": 200},
                                "on_success": on_success,
                            },
                        }
                    ),
                )
                self.product.assets.clear()
                self.product.assets["download_link"] = {
                    "href": "https://example.test/pending",
                    "eodag:status_link": "https://example.test/status",
                }
                asset = self.product.assets["download_link"]
                head_response = mock.Mock(status_code=200)
                head_response.json.side_effect = ValueError("empty HEAD response")
                get_response = mock.Mock(
                    status_code=200,
                    headers=CaseInsensitiveDict(
                        {
                            "Content-Type": "application/json",
                            "Location": "https://example.test/download",
                            "Finished": "2026-01-02T00:00:00.000Z",
                        }
                    ),
                )
                get_response.json.return_value = {
                    "href": "https://example.test/download",
                    "created": "2026-01-01",
                    "finished": "2026-01-02",
                }
                mock_request.reset_mock()
                mock_request.side_effect = [head_response, get_response]

                plugin._order_status(asset)

                self.assertEqual(
                    [
                        request.kwargs["method"]
                        for request in mock_request.call_args_list
                    ],
                    ["HEAD", "GET"],
                )
                head_response.json.assert_not_called()
                self.assertEqual(asset["href"], "https://example.test/download")
                self.assertEqual(asset["order:date"], "2026-01-01")
                self.assertEqual(self.product.properties["created"], "2026-01-01")
                self.assertEqual(
                    self.product.properties["published"], "2026-01-02T00:00:00.000Z"
                )
                self.assertEqual(
                    asset["custom:field"], self.product.properties["published"]
                )
                self.assertNotIn("published", asset)
                self.assertNotIn("order:date", self.product.properties)

    @mock.patch(
        "eodag.plugins.authentication.token.TokenAuth.authenticate", autospec=True
    )
    @mock.patch("eodag.plugins.download.http.requests.request", autospec=True)
    def test_plugins_download_http_order_status_get_raises_if_request_500(
        self, mock_request, mock_auth_request
    ):
        """HTTPDownload._order() must raise an error if request to backend provider failed."""
        # Configure mock to raise an error
        mock_request.return_value = MockResponse(status_code=500)

        plugin: HTTPDownload = self.get_download_plugin(self.product)
        self.product.assets["download_link"] = {
            "href": "https://copernicus.nci.org.au/dummy",
            "eodag:order_link": "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/download",
            "eodag:status_link": "http://somewhere/orderstatus",
        }
        asset = self.product.assets["download_link"]

        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.config.credentials = {"username": "foo", "password": "bar"}
        auth = auth_plugin.authenticate()

        # Verify that a DownloadError is raised
        with self.assertRaises(DownloadError) as context:
            plugin._order_status(asset, auth=auth)
        self.assertIn("order status could not be checked", str(context.exception))

        mock_request.assert_called_once_with(
            method="GET",
            url=asset["eodag:status_link"],
            auth=auth,
            headers=USER_AGENT,
            timeout=5,
            allow_redirects=False,
            json=None,
        )

    @mock.patch(
        "eodag.plugins.authentication.token.TokenAuth.authenticate", autospec=True
    )
    @mock.patch("eodag.plugins.download.http.requests.request", autospec=True)
    def test_plugins_download_http_order_status_get_raises_if_request_400(
        self, mock_request, mock_auth_request
    ):
        # Set up the EOProduct and the necessary properties
        plugin: HTTPDownload = self.get_download_plugin(self.product)
        self.product.assets["download_link"] = {
            "href": "https://copernicus.nci.org.au/dummy",
            "eodag:order_link": "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/download",
            "eodag:status_link": "http://somewhere/orderstatus",
        }
        asset = self.product.assets["download_link"]

        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.config.credentials = {"username": "foo", "password": "bar"}

        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.config.credentials = {"username": "foo", "password": "bar"}
        auth = auth_plugin.authenticate()

        # Mock the response to raise HTTPError with a 400 status
        mock_request.return_value = MockResponse(status_code=400)

        # Test the function, expecting ValidationError to be raised
        with self.assertRaises(ValidationError) as context:
            plugin._order_status(asset, auth=auth)
        self.assertIn("order status could not be checked", str(context.exception))

        mock_request.assert_called_once_with(
            method="GET",
            url=asset["eodag:status_link"],
            auth=auth,
            headers=USER_AGENT,
            timeout=5,
            allow_redirects=False,
            json=None,
        )

    @mock.patch(
        "eodag.plugins.authentication.token.TokenAuth.authenticate", autospec=True
    )
    def test_plugins_download_http_order_status_search_again(self, mock_auth_request):
        """HTTPDownload._order_status() must search again after success if needed"""
        plugin = self.get_download_plugin(self.product)
        plugin.config.order_status = {
            "asset_mapping": {"eodag:order_status": "$.json.status"},
            "success": {"eodag:order_status": "great-success"},
            "on_success": {
                "need_search": True,
                "result_type": "xml",
                "results_entry": "//entry",
                "asset_mapping": {
                    "href": "foo/text()",
                },
                "metadata_mapping": {"published": "bar/text()"},
            },
        }
        self.product.assets["download_link"] = {
            "href": "https://copernicus.nci.org.au/dummy",
            "eodag:order_link": "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/download",
            "eodag:status_link": "http://somewhere/order-status",
            "eodag:search_link": "http://somewhere/search-again",
        }
        asset = self.product.assets["download_link"]

        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.config.credentials = {"username": "foo", "password": "bar"}
        auth = auth_plugin.authenticate()

        @responses.activate(registry=responses.registries.OrderedRegistry)
        def run():
            responses.add(
                responses.GET,
                "http://somewhere/order-status",
                status=200,
                json={"status": "great-success"},
            )
            responses.add(
                responses.GET,
                "http://somewhere/search-again",
                status=200,
                body=(
                    b"<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
                    b"<feed>"
                    b"<entry><foo>http://new-download-link</foo><bar>something else</bar></entry>"
                    b"</feed>"
                ),
            )

            plugin._order_status(asset, auth=auth)

            self.assertEqual(asset["href"], "http://new-download-link")
            self.assertEqual(asset["eodag:order_status"], "great-success")
            self.assertEqual(self.product.properties["published"], "something else")
            self.assertNotIn("published", asset)
            self.assertEqual(len(responses.calls), 2)

        run()

    @mock.patch(
        "eodag.plugins.authentication.token.TokenAuth.authenticate", autospec=True
    )
    def test_plugins_download_http_order_status_search_again_raises_if_request_failed(
        self, mock_auth_request
    ):
        """HTTPDownload._order_status() must raise an error if the search request after success failed."""
        plugin = self.get_download_plugin(self.product)
        plugin.config.order_status = {
            "asset_mapping": {"eodag:order_status": "$.json.status"},
            "success": {"eodag:order_status": "great-success"},
            "on_success": {
                "need_search": True,
                "result_type": "xml",
                "results_entry": "//entry",
                "asset_mapping": {
                    "href": "foo/text()",
                },
            },
        }
        self.product.assets["download_link"] = {
            "href": "https://copernicus.nci.org.au/dummy",
            "eodag:order_link": "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/download",
            "eodag:status_link": "http://somewhere/order-status",
            "eodag:search_link": "http://somewhere/search-again",
        }
        asset = self.product.assets["download_link"]

        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.config.credentials = {"username": "foo", "password": "bar"}
        auth = auth_plugin.authenticate()

        @responses.activate(registry=responses.registries.OrderedRegistry)
        def run(error_code: int):
            responses.add(
                responses.GET,
                "http://somewhere/order-status",
                status=200,
                json={"status": "great-success"},
            )
            responses.add(
                responses.GET,
                "http://somewhere/search-again",
                status=error_code,
            )
            if error_code == 500:
                with self.assertRaises(DownloadError) as context:
                    plugin._order_status(asset, auth=auth)
            if error_code == 400:
                with self.assertRaises(ValidationError) as context:
                    plugin._order_status(asset, auth=auth)
            self.assertIn("order status could not be checked", str(context.exception))
            self.assertEqual(len(responses.calls), 2)

        run(error_code=500)
        run(error_code=400)

    def test_plugins_download_http_update_from_order(self):
        """Order fields are stored according to their mapping, not their names."""
        self.product.assets.update(
            {
                "download_link": {"eodag:order_link": "http://somewhere/order"},
                "foo": {"eodag:order_link": "http://somewhere/order-foo"},
            }
        )
        HTTPDownload._update_from_order(
            self.product.assets["download_link"],
            {
                "order:id": 123,
                "eodag:status_link": "http://somewhere/status",
                "href": "http://somewhere/download",
                "order:date": "2026-01-01",
                "custom:field": "asset value",
                "_private": "skipped",
                "missing:asset": NOT_AVAILABLE,
            },
            {
                "created": "2026-01-02",
                "eodag:custom": "product value",
                "_private": "skipped",
                "missing:product": NOT_AVAILABLE,
            },
        )
        download_link = self.product.assets["download_link"]
        self.assertEqual(download_link["order:id"], "123")
        self.assertEqual(download_link["eodag:status_link"], "http://somewhere/status")
        self.assertEqual(download_link["href"], "http://somewhere/download")
        self.assertEqual(download_link["order:date"], "2026-01-01")
        self.assertEqual(download_link["custom:field"], "asset value")
        self.assertNotIn("_private", download_link)
        self.assertNotIn("missing:asset", download_link)
        self.assertEqual(self.product.properties["created"], "2026-01-02")
        self.assertEqual(self.product.properties["eodag:custom"], "product value")
        self.assertNotIn("_private", self.product.properties)
        self.assertNotIn("missing:product", self.product.properties)
        self.assertEqual(self.product.location, "http://somewhere/download")

        # non download_link asset does not change product location
        HTTPDownload._update_from_order(
            self.product.assets["foo"],
            {"href": "http://somewhere/download-foo"},
            {},
        )
        self.assertEqual(
            self.product.assets["foo"]["href"], "http://somewhere/download-foo"
        )
        self.assertEqual(self.product.location, "http://somewhere/download")

    def test_plugins_download_http_order_response_mappings(self):
        """Order mappings share placeholders but update separate destinations."""
        plugin = self.get_download_plugin(self.product)
        self.product.assets["download_link"] = {"href": "https://example.test/pending"}
        config = {
            "asset_mapping": {
                "order:id": "$.json.jobID",
                "href": "{_base}/{order:id}?published={published}",
                "custom:field": "$.json.asset_field",
            },
            "metadata_mapping": {
                "published": "$.json.date",
                "_base": "$.json.base",
                "eodag:custom": "$.json.product_field",
            },
        }
        response = mock.Mock(headers={})
        response.json.return_value = {
            "jobID": 123,
            "base": "https://example.test/download",
            "date": "2026-01-01",
            "asset_field": "asset value",
            "product_field": "product value",
        }
        asset = self.product.assets["download_link"]
        with mock.patch.object(plugin.config, "order_on_response", config, create=True):
            self.assertEqual(
                plugin.order_response_process(response, asset),
                response.json.return_value,
            )
        self.assertEqual(asset["order:id"], "123")
        self.assertEqual(
            asset["href"], "https://example.test/download/123?published=2026-01-01"
        )
        self.assertEqual(asset["custom:field"], "asset value")
        self.assertEqual(self.product.properties["published"], "2026-01-01")
        self.assertEqual(self.product.properties["eodag:custom"], "product value")
        self.assertNotIn("published", asset)
        self.assertNotIn("custom:field", self.product.properties)
        self.assertNotIn("_base", self.product.properties)

    def test_plugins_download_http_provider_order_mappings(self):
        """Provider order mappings resolve asset fields without product leakage."""
        configs = load_provider_configs()
        for provider, status_link in (
            (
                "cop_ads",
                "https://ads.atmosphere.copernicus.eu/api/retrieve/v1/jobs/123?request=true",
            ),
            (
                "cop_cds",
                "https://cds.climate.copernicus.eu/api/retrieve/v1/jobs/123?request=true",
            ),
            (
                "cop_ewds",
                "https://ewds.climate.copernicus.eu/api/retrieve/v1/jobs/123?request=true",
            ),
            ("dedl", "https://example.test/order/123"),
            (
                "dedt_lumi",
                "https://polytope.lumi.apps.dte.destination-earth.eu/api/v1/requests/a1b2c3",
            ),
            (
                "dedt_mn5",
                "https://polytope.mn5.apps.dte.destination-earth.eu/api/v1/requests/a1b2c3",
            ),
            (
                "dedt_leonardo",
                "https://polytope.leonardo.apps.dte.destination-earth.eu/api/v1/requests/a1b2c3",
            ),
            ("meteoblue", "http://my.meteoblue.com/queue/status/123"),
            (
                "wekeo_main",
                "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/downloads?download_id=123",
            ),
            (
                "wekeo_ecmwf",
                "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/downloads?download_id=123",
            ),
            (
                "wekeo_cmems",
                "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/downloads?download_id=123",
            ),
        ):
            with self.subTest(provider=provider):
                plugin = HTTPDownload(provider, configs[provider].download)
                product = EOProduct(
                    provider, {"id": "product", "geometry": "POINT (0 0)"}
                )
                product.assets["ordered"] = {"href": "https://example.test/pending"}
                asset = product.assets["ordered"]
                response = mock.Mock(
                    headers={"Location": "https://example.test/jobs/a1b2c3"}
                )
                response.json.return_value = {
                    "jobID": 123,
                    "download_id": 123,
                    "id": 123,
                    "links": [
                        {"rel": "self", "href": "https://example.test/order/123"}
                    ],
                    "properties": {"order:status": OFFLINE_STATUS},
                }

                plugin.order_response_process(response, asset)

                self.assertEqual(asset["eodag:status_link"], status_link)
                if provider != "dedl":
                    self.assertEqual(
                        asset["order:id"],
                        "a1b2c3" if provider.startswith("dedt_") else "123",
                    )
                self.assertFalse(any(key.startswith("_") for key in asset))
                self.assertNotIn("order:id", product.properties)
                self.assertNotIn("eodag:status_link", product.properties)
                for stage in (
                    plugin.config.order_on_response,
                    plugin.config.order_status,
                    plugin.config.order_status.get("on_success", {}),
                ):
                    self.assertNotIn(
                        "eodag:download_link", stage.get("asset_mapping", {})
                    )
                    self.assertNotIn("eodag:order_id", stage.get("asset_mapping", {}))
                    self.assertLessEqual(
                        set(stage.get("metadata_mapping", {})),
                        {
                            "created",
                            "published",
                            "updated",
                            "ecmwf:dataset",
                            "eodag:request_params",
                        },
                    )

    def test_plugins_download_http_order_assets(self):
        """HTTPDownload.order() must order matching assets that are not online"""
        plugin = self.get_download_plugin(self.product)
        self.product.assets.update(
            {
                "download_link": {"eodag:order_link": "http://somewhere/order"},
                "foo": {"eodag:order_link": "http://somewhere/order-foo"},
                "online": {
                    "href": "http://somewhere/online",
                    "order:status": ONLINE_STATUS,
                },
            }
        )

        def order(asset, auth=None):
            asset["order:status"] = ONLINE_STATUS

        with mock.patch.object(
            plugin, "_order", autospec=True, side_effect=order
        ) as mock_order:
            plugin.order(self.product, wait=0.001 / 60, timeout=0.2 / 60, asset="foo")
            mock_order.assert_called_once_with(
                asset=self.product.assets["foo"], auth=None
            )

            mock_order.reset_mock()
            plugin.order(self.product, wait=0.001 / 60, timeout=0.2 / 60)
            mock_order.assert_called_once_with(
                asset=self.product.assets["download_link"], auth=None
            )

    @mock.patch(
        "eodag.plugins.download.http.HTTPDownload._raw_stream_download_assets",
        autospec=True,
    )
    def test_plugins_download_http_order_filtered_assets(
        self, mock_raw_stream_download_assets
    ):
        """HTTPDownload.download() must order filtered assets before downloading them"""
        plugin = self.get_download_plugin(self.product)
        self.product.assets.clear()
        self.product.assets.update(
            {
                "download_link": {"eodag:order_link": "http://somewhere/order"},
                "foo": {"eodag:order_link": "http://somewhere/order-foo"},
            }
        )

        def order(asset, auth=None):
            asset["href"] = "http://somewhere/foo"
            asset["order:status"] = ONLINE_STATUS

        mock_raw_stream_download_assets.side_effect = (
            lambda _self, _product, _executor, _auth, _cb, assets_values, **kw: [
                StreamResponse(content=iter([b"content"]), arcname=asset.key)
                for asset in assets_values
            ]
        )
        with mock.patch.object(
            plugin, "_order", autospec=True, side_effect=order
        ) as mock_order:
            path = plugin.download(
                self.product,
                output_dir=self.output_dir,
                asset="foo",
                wait=0.001 / 60,
                timeout=0.2 / 60,
            )

        mock_order.assert_called_once_with(asset=self.product.assets["foo"], auth=None)
        self.assertTrue(os.path.isfile(os.path.join(path, "foo")))
        self.assertEqual(
            self.product.assets["download_link"]["order:status"], OFFLINE_STATUS
        )


class TestDownloadPluginHttpRetry(BaseDownloadPluginTest):
    """Test cases for the HTTP download plugin with retry logic."""

    def setUp(self):
        super(TestDownloadPluginHttpRetry, self).setUp()

        self.plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"
        self.product.assets["download_link"]["order:status"] = OFFLINE_STATUS

    def test_plugins_download_http_retry_error_timeout(self):
        """HTTPDownload.download() must retry on error until timeout."""

        @responses.activate(registry=responses.registries.FirstMatchRegistry)
        def run():
            url = "http://somewhere/"
            responses.add(responses.GET, url, status=500)

            with self.assertRaisesRegex(NotAvailableError, r".*timeout reached"):
                self.plugin.download(
                    self.product,
                    output_dir=self.output_dir,
                    wait=0.001 / 60,
                    timeout=0.2 / 60,
                )

            # there must have been many retries
            self.assertGreater(len(responses.calls), 2)
            quick_retry_call_count = len(responses.calls)

            # Same test with longer wait time
            responses.calls.reset()
            with self.assertRaisesRegex(NotAvailableError, r".*timeout reached"):
                self.plugin.download(
                    self.product,
                    output_dir=self.output_dir,
                    wait=0.09 / 60,
                    timeout=0.2 / 60,
                )

            # there must have been many retries, but less than before
            self.assertGreater(len(responses.calls), 2)
            self.assertLess(len(responses.calls), quick_retry_call_count)

        run()

    def test_plugins_download_http_retry_notready_timeout(self):
        """HTTPDownload.download() must retry if not ready until timeout."""

        @responses.activate(registry=responses.registries.FirstMatchRegistry)
        def run():
            url = "http://somewhere/"
            responses.add(responses.GET, url, status=202)

            with self.assertRaisesRegex(NotAvailableError, r".*timeout reached"):
                self.plugin.download(
                    self.product,
                    output_dir=self.output_dir,
                    wait=0.001 / 60,
                    timeout=0.2 / 60,
                )

            # there must have been many retries
            self.assertGreater(len(responses.calls), 2)

        run()

    def test_plugins_download_http_retry_ok(self):
        """HTTPDownload.download() must retry until request succeeds."""

        @responses.activate(registry=responses.registries.OrderedRegistry)
        def run():
            # fail, then succeeds
            url = "http://somewhere/"
            responses.add(responses.GET, url, status=202)
            responses.add(responses.GET, url, status=202)
            responses.add(
                responses.GET,
                "http://somewhere/",
                status=200,
                content_type="application/octet-stream",
                body=b"something",
                auto_calculate_content_length=True,
            )

            self.plugin.download(
                self.product,
                output_dir=self.output_dir,
                wait=0.001 / 60,
                timeout=0.2 / 60,
            )

            # there must have been 2 retries
            self.assertEqual(len(responses.calls), 3)

        run()

    def test_plugins_download_http_retry_short_timeout(self):
        """HTTPDownload.download() must not retry on very short timeout."""

        @responses.activate(registry=responses.registries.FirstMatchRegistry)
        def run():
            url = "http://somewhere/"
            responses.add(responses.GET, url, status=202)

            with self.assertRaisesRegex(NotAvailableError, r".*timeout reached"):
                self.plugin.download(
                    self.product,
                    output_dir=self.output_dir,
                    wait=0.1 / 60,
                    timeout=1e-9 / 60,
                )

            # there must have been only one try
            self.assertEqual(len(responses.calls), 1)

        run()

    def test_plugins_download_http_retry_once_timeout(self):
        """HTTPDownload.download() must retry once if wait time is equal to timeout."""

        @responses.activate(registry=responses.registries.FirstMatchRegistry)
        def run():
            url = "http://somewhere/"
            responses.add(responses.GET, url, status=202)

            with self.assertRaisesRegex(NotAvailableError, r".*timeout reached"):
                self.plugin.download(
                    self.product,
                    output_dir=self.output_dir,
                    wait=0.1 / 60,
                    timeout=0.1 / 60,
                )

            # there must have been one retry
            self.assertEqual(len(responses.calls), 2)

        run()

    def test_plugins_download_http_retry_timeout_disabled(self):
        """HTTPDownload.download() must not retry on error if timeout is disabled."""

        @responses.activate(registry=responses.registries.FirstMatchRegistry)
        def run():
            url = "http://somewhere/"
            responses.add(responses.GET, url, status=202)

            with self.assertRaisesRegex(NotAvailableError, r"^((?!timeout).)*$"):
                self.plugin.download(
                    self.product, output_dir=self.output_dir, wait=-1, timeout=-1
                )

            # there must have been only one try
            self.assertEqual(len(responses.calls), 1)

        run()


class TestDownloadPluginAws(BaseDownloadPluginTest):
    """Test cases for the AWS download plugin."""

    def setUp(self):
        super(TestDownloadPluginAws, self).setUp()
        # fresh manager: tests mutate plugin configs and mock AwsAuth.__init__ on cached instances
        self.plugins_manager = PluginManager(
            ProvidersDict.from_configs(load_provider_configs())
        )
        self.product = EOProduct(
            "aws_eos",
            dict(
                geometry="POINT (0 0)",
                title="dummy_product",
                id="dummy",
            ),
            collection="S2_MSI_L2A",
        )
        self.product.remote_location = "s3://sentinel-s2-l2a/123"
        self.product.location = "http://somebucket.somehost.com/path/to/some/product"

    def test_plugins_download_aws_get_bucket_names_and_prefixes(self):
        """AwsDownload._get_bucket_names_and_prefixes() must return the given assets buckets and prefixes"""

        plugin = self.get_download_plugin(self.product)
        self.product.assets.clear()
        self.product.assets.update(
            {
                "somewhere": {"href": "s3://eodata/somewhere/something"},
                "elsewhere": {"href": "s3://eodata/elsewhere/anything"},
            }
        )

        self.assertEqual(
            plugin._get_bucket_names_and_prefixes(
                self.product, [self.product.assets["elsewhere"]], []
            ),
            [("eodata", "elsewhere/anything")],
        )
        self.assertEqual(
            plugin._get_bucket_names_and_prefixes(
                self.product, plugin._select_assets(self.product, "some.*"), []
            ),
            [("eodata", "somewhere/something")],
        )
        with self.assertRaises(NotAvailableError):
            plugin._select_assets(self.product, "nothing")

    def test_plugins_download_aws_get_bucket_prefix(self):
        """AwsDownload.get_product_bucket_name_and_prefix() must extract bucket & prefix from location."""
        plugin = self.get_download_plugin(self.product)
        plugin.config.products["S2_MSI_L2A"]["default_bucket"] = "default_bucket"

        bucket, prefix = plugin.get_product_bucket_name_and_prefix(self.product)
        self.assertEqual((bucket, prefix), ("somebucket", "path/to/some/product"))

        plugin.config.bucket_path_level = 1
        bucket, prefix = plugin.get_product_bucket_name_and_prefix(self.product)
        self.assertEqual((bucket, prefix), ("to", "some/product"))
        del plugin.config.bucket_path_level

        bucket, prefix = plugin.get_product_bucket_name_and_prefix(
            self.product, url="/somewhere/else"
        )
        self.assertEqual((bucket, prefix), ("default_bucket", "somewhere/else"))

    def test_plugins_download_aws_get_commonpath(self):
        """AwsDownload._get_commonpath() must return common chunk destination path."""
        plugin = self.get_download_plugin(self.product)
        product_chunks = {
            mock.Mock(key="path/to/some/product/file1.tif"),
            mock.Mock(key="path/to/some/product/sub/file2.tif"),
        }

        common_path = plugin._get_commonpath(
            self.product, product_chunks, build_safe=False
        )

        self.assertEqual(common_path, "path/to/some/product")

    def test_plugins_download_aws_extract_setting(self):
        """AwsDownload.download() must honor the configured extract setting."""
        plugin = self.get_download_plugin(self.product)
        product_path = os.path.join(self.output_dir, "product")
        os.makedirs(product_path)
        archive_path = os.path.join(product_path, "archive.zip")
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("data.txt", "content")

        progress_callback = ProgressCallback(disable=True)
        plugin.config.extract = False
        plugin._finalize_archives(
            product_path,
            progress_callback=progress_callback,
            output_dir=self.output_dir,
        )
        self.assertTrue(os.path.isfile(archive_path))
        self.assertFalse(os.path.exists(os.path.join(product_path, "archive")))

        plugin.config.extract = True
        plugin._finalize_archives(
            product_path,
            progress_callback=progress_callback,
            output_dir=self.output_dir,
        )
        self.assertFalse(os.path.exists(archive_path))
        with open(os.path.join(product_path, "archive", "data.txt")) as extracted:
            self.assertEqual(extracted.read(), "content")

    def test_plugins_download_aws_extract_single_product_archive(self):
        """Archive finalization must honor archive depth and retention settings."""
        plugin = self.get_download_plugin(self.product)
        for extension in (".zip", ".tar", ".tar.gz", ".tgz"):
            for delete_archive in (True, False):
                for archive_depth in (1, 2):
                    with (
                        self.subTest(
                            extension=extension,
                            delete_archive=delete_archive,
                            archive_depth=archive_depth,
                        ),
                        TemporaryDirectory(dir=self.output_dir) as output_dir,
                    ):
                        product_path = os.path.join(output_dir, "product")
                        os.makedirs(product_path)
                        archive_path = os.path.join(product_path, "product" + extension)
                        if extension == ".zip":
                            with zipfile.ZipFile(archive_path, "w") as archive:
                                archive.writestr(
                                    "product.SAFE/manifest.safe", "content"
                                )
                        else:
                            mode = "w" if extension == ".tar" else "w:gz"
                            with tarfile.open(archive_path, mode) as archive:
                                member = tarfile.TarInfo("product.SAFE/manifest.safe")
                                member.size = len(b"content")
                                archive.addfile(member, io.BytesIO(b"content"))

                        with mock.patch.object(
                            plugin.config, "archive_depth", archive_depth, create=True
                        ):
                            plugin._finalize_archives(
                                product_path,
                                progress_callback=ProgressCallback(disable=True),
                                output_dir=output_dir,
                                extract=True,
                                delete_archive=delete_archive,
                            )

                        expected_name = (
                            "product.SAFE" if archive_depth == 1 else "manifest.safe"
                        )
                        extraction_path = os.path.splitext(archive_path)[0]
                        expected_entries = [os.path.basename(extraction_path)]
                        if not delete_archive:
                            expected_entries.append("product" + extension)
                        self.assertCountEqual(
                            os.listdir(product_path), expected_entries
                        )
                        manifest_path = os.path.join(extraction_path, expected_name)
                        if archive_depth == 1:
                            manifest_path = os.path.join(manifest_path, "manifest.safe")
                        with open(manifest_path) as extracted:
                            self.assertEqual(extracted.read(), "content")

    def test_plugins_download_aws_extract_flatten_top_dirs(self):
        """Flatten extracted archives using collection or provider configuration."""
        plugin = self.get_download_plugin(self.product)
        auth_plugin = self.get_auth_plugin(plugin, self.product)
        self.product.downloader_auth = auth_plugin
        for provider_flatten, collection_flatten, expected_flatten in (
            (True, None, True),
            (False, None, False),
            (False, True, True),
            (True, False, False),
        ):
            with (
                self.subTest(provider=provider_flatten, collection=collection_flatten),
                TemporaryDirectory(dir=self.output_dir) as output_dir,
            ):
                product_path = os.path.join(output_dir, "product")
                os.makedirs(product_path)
                archive_path = os.path.join(product_path, "product.zip")
                with zipfile.ZipFile(archive_path, "w") as archive:
                    archive.writestr("product.SAFE/manifest.safe", "content")
                product_config = {"build_safe": False}
                if collection_flatten is not None:
                    product_config["flatten_top_dirs"] = collection_flatten

                with (
                    mock.patch.dict(
                        plugin.config.products,
                        {self.product.collection: product_config},
                    ),
                    mock.patch.object(
                        plugin.config, "flatten_top_dirs", provider_flatten, create=True
                    ),
                    mock.patch.object(
                        plugin, "_create_product_dir", return_value=product_path
                    ),
                    mock.patch.object(
                        auth_plugin, "authenticate_objects", return_value={}
                    ),
                    mock.patch.object(plugin, "_download_file_in_zip", return_value=[]),
                    mock.patch.object(plugin, "_get_unique_products", return_value=[]),
                ):
                    result = plugin.download(
                        self.product,
                        output_dir=output_dir,
                        extract=True,
                        delete_archive=True,
                    )

                self.assertEqual(result, product_path)
                expected_path = (
                    os.path.join(product_path, "manifest.safe")
                    if expected_flatten
                    else os.path.join(
                        product_path, "product", "product.SAFE", "manifest.safe"
                    )
                )
                with open(expected_path) as extracted:
                    self.assertEqual(extracted.read(), "content")
                if expected_flatten:
                    self.assertEqual(os.listdir(product_path), ["manifest.safe"])

    def test_plugins_download_aws_single_archive(self):
        """A single archive must be stored and finalized like with HTTPDownload."""
        plugin = self.get_download_plugin(self.product)
        auth_plugin = self.get_auth_plugin(plugin, self.product)
        self.product.downloader_auth = auth_plugin

        def download_file(key, dest, **kwargs):
            with zipfile.ZipFile(dest, "w") as archive:
                archive.writestr("product.SAFE/manifest.safe", "content")

        chunk = mock.Mock(key="path/to/remote_name.zip", bucket_name="bucket", size=1)
        chunk.Bucket.return_value.download_file.side_effect = download_file

        for extract in (False, True):
            with (
                self.subTest(extract=extract),
                TemporaryDirectory(dir=self.output_dir) as output_dir,
            ):
                product_path = os.path.join(output_dir, "product")
                os.makedirs(product_path)
                with (
                    mock.patch.dict(
                        plugin.config.products,
                        {self.product.collection: {"build_safe": False}},
                    ),
                    mock.patch.object(
                        plugin.config, "flatten_top_dirs", True, create=True
                    ),
                    mock.patch.object(
                        plugin, "_create_product_dir", return_value=product_path
                    ),
                    mock.patch.object(
                        auth_plugin, "authenticate_objects", return_value={}
                    ),
                    mock.patch.object(
                        plugin,
                        "_download_file_in_zip",
                        side_effect=lambda _auth, packs, *args, **kwargs: packs,
                    ),
                    mock.patch.object(
                        plugin, "_get_unique_products", return_value={chunk}
                    ),
                ):
                    result = plugin.download(
                        self.product, output_dir=output_dir, extract=extract
                    )

                self.assertEqual(self.product.location, path_to_uri(result))
                self.assertEqual(
                    self.product.assets["download_link"]["file:local_path"], result
                )
                if extract:
                    self.assertEqual(result, product_path)
                    self.assertCountEqual(
                        os.listdir(output_dir), ["product", ".downloaded"]
                    )
                    self.assertEqual(os.listdir(product_path), ["manifest.safe"])
                else:
                    self.assertEqual(result, product_path + ".zip")
                    self.assertTrue(zipfile.is_zipfile(result))
                    self.assertFalse(os.path.exists(product_path))

    def test_plugins_download_aws_extract_multiple_archives(self):
        """Multiple archives must keep separate extraction directories."""
        plugin = self.get_download_plugin(self.product)
        product_path = os.path.join(self.output_dir, "product")
        os.makedirs(product_path)
        for name in ("first", "second"):
            with zipfile.ZipFile(
                os.path.join(product_path, name + ".zip"), "w"
            ) as archive:
                archive.writestr("data.txt", name)

        plugin._finalize_archives(
            product_path,
            progress_callback=ProgressCallback(disable=True),
            output_dir=self.output_dir,
            extract=True,
        )

        self.assertCountEqual(os.listdir(product_path), ["first", "second"])
        for name in ("first", "second"):
            with open(os.path.join(product_path, name, "data.txt")) as extracted:
                self.assertEqual(extracted.read(), name)

    def test_plugins_download_aws_ignores_directory_markers_and_sibling_files(self):
        """AwsDownload._get_unique_products() must ignore S3 directory markers and sibling files.

        Objects that should be included are only:
        - exact object at the product prefix which does not have any child object, even if it has zero size
        - exact object at the product prefix which has children objects, but it must have a non-zero size
        - actual product files (child below the product folder), even if they have zero size.
        """
        plugin = self.get_download_plugin(self.product)

        # Test the case where the S3 bucket contains a mix of directory markers, actual product files, and sibling files

        # Setup mock S3 objects representing directory markers and actual files:
        # - Exact directory marker (zero-size object at the prefix itself)
        # - Exact directory marker with non-zero size (exact object at the prefix itself)
        # - Slash directory marker (object with trailing slash)
        # - Actual product file with non-zero size (child below the product folder)
        # - Actual product file with zero size (child below the product folder)
        # - Sibling file outside the product directory with similar prefix
        exact_directory_marker_zero_size = mock.Mock(key="path/to/some/product", size=0)
        exact_directory_marker_non_zero_size = mock.Mock(
            key="path/to/some/product", size=1
        )
        slash_directory_marker = mock.Mock(key="path/to/some/product/", size=1)
        product_file_zero_size = mock.Mock(key="path/to/some/product/file2.tif", size=0)
        product_file_non_zero_size = mock.Mock(
            key="path/to/some/product/file1.tif", size=1
        )
        sibling_file = mock.Mock(key="path/to/some/product.txt", size=1)
        bucket_objects = mock.Mock()
        bucket_objects.filter.side_effect = lambda Prefix: [
            chunk
            for chunk in (
                exact_directory_marker_zero_size,
                exact_directory_marker_non_zero_size,
                slash_directory_marker,
                product_file_zero_size,
                product_file_non_zero_size,
                sibling_file,
            )
            if chunk.key.startswith(Prefix)
        ]

        product_chunks = plugin._get_unique_products(
            [("somebucket", "path/to/some/product")],
            {"somebucket": bucket_objects},
            self.product,
        )

        bucket_objects.filter.assert_called_once_with(Prefix="path/to/some/product")

        # Check the files that should be included in the product chunks are:
        # - child below the product directory (actual product files), zero size included
        # - non-empty folder with children objects (not a directory marker)
        self.assertSetEqual(
            product_chunks,
            {
                product_file_non_zero_size,
                product_file_zero_size,
                exact_directory_marker_non_zero_size,
            },
        )

        # Test the case where the exact zero-size object is the only one
        # matching the prefix (it does not have any child object).
        bucket_objects.reset_mock()
        bucket_objects.filter.side_effect = lambda Prefix: (
            []
            if Prefix == "path/to/some/product"
            else [exact_directory_marker_zero_size]
        )

        product_chunks = plugin._get_unique_products(
            [("somebucket", "path/to/some/product")],
            {"somebucket": bucket_objects},
            self.product,
        )

        # Check that when an exact object does not have any child object, it is still included
        # in the product chunks, even it is zero-size (it is not an directory marker anymore).
        self.assertSetEqual(product_chunks, {exact_directory_marker_zero_size})

    def test_plugins_download_aws_falls_back_to_slash_prefix(self):
        """AwsDownload._get_unique_products() must support backends requiring slash prefix."""
        plugin = self.get_download_plugin(self.product)
        product_file = mock.Mock(key="path/to/some/product/file.tif", size=1)
        bucket_objects = mock.Mock()
        bucket_objects.filter.side_effect = lambda Prefix: (
            [] if Prefix == "path/to/some/product" else [product_file]
        )

        product_chunks = plugin._get_unique_products(
            [("somebucket", "path/to/some/product")],
            {"somebucket": bucket_objects},
            self.product,
        )

        bucket_objects.filter.assert_has_calls(
            [
                mock.call(Prefix="path/to/some/product"),
                mock.call(Prefix="path/to/some/product/"),
            ]
        )
        self.assertSetEqual(product_chunks, {product_file})

    @mock.patch("eodag.plugins.download.aws.stream_download_from_s3", autospec=True)
    def test_plugins_download_aws_stream_download(self, mock_stream_download_from_s3):
        """AwsDownload.stream_download() must stream S3 objects with flattened paths."""
        expected_response = StreamResponse(iter([b"content"]))
        mock_stream_download_from_s3.return_value = expected_response
        plugin = self.get_download_plugin(self.product)
        plugin.config.flatten_top_dirs = True
        plugin.config.products[self.product.collection]["build_safe"] = False
        plugin.config.products[self.product.collection]["complementary_url_key"] = []
        s3_client = mock.Mock()
        s3_resource = mock.Mock()
        s3_resource.meta.client = s3_client
        product_chunks = [
            mock.Mock(
                bucket_name="somebucket",
                key="path/to/some/product/file1.tif",
                size=1,
            ),
            mock.Mock(
                bucket_name="somebucket",
                key="path/to/some/product/sub/file2.tif",
                size=2,
            ),
        ]
        authenticated_objects = {"somebucket": mock.Mock()}
        authenticated_objects["somebucket"].filter.side_effect = lambda Prefix: [
            chunk for chunk in product_chunks if chunk.key.startswith(Prefix)
        ]
        auth_plugin = mock.Mock()
        auth_plugin.authenticate_objects.return_value = authenticated_objects
        self.product.downloader_auth = auth_plugin
        self.product.assets.clear()
        self.product.assets.update(
            {
                "file1": {
                    "href": "s3://somebucket/path/to/some/product/file1.tif",
                    "type": "image/tiff",
                },
                "file2": {
                    "href": "s3://somebucket/path/to/some/product/sub/file2.tif",
                },
            }
        )

        response = plugin.stream_download(
            self.product,
            auth=s3_resource,
            byte_range=(0, 10),
            compress="zip",
        )

        self.assertIs(response, expected_response)
        auth_plugin.authenticate_objects.assert_called_once_with(
            [
                ("somebucket", "path/to/some/product/file1.tif"),
                ("somebucket", "path/to/some/product/sub/file2.tif"),
            ]
        )
        mock_stream_download_from_s3.assert_called_once()
        args = mock_stream_download_from_s3.call_args.args
        self.assertIs(args[0], s3_client)
        files_info = sorted(args[1], key=lambda file_info: file_info.key)
        self.assertEqual(
            files_info,
            [
                S3FileInfo(
                    key="path/to/some/product/file1.tif",
                    size=1,
                    bucket_name="somebucket",
                    rel_path="dummy_product/file1.tif",
                    data_type="image/tiff",
                ),
                S3FileInfo(
                    key="path/to/some/product/sub/file2.tif",
                    size=2,
                    bucket_name="somebucket",
                    rel_path="dummy_product/sub/file2.tif",
                    data_type="image/tiff",
                ),
            ],
        )
        self.assertEqual(args[2], (0, 10))
        self.assertEqual(args[3], "zip")
        self.assertEqual(args[4], "dummy_product")

    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload._get_unique_products", autospec=True
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth._get_authenticated_objects",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth.__init__",
        autospec=True,
    )
    def test_plugins_download_aws_assets_statements_cache(
        self,
        mock_aws_auth_init: mock.Mock,
        mock_get_authenticated_objects: mock.Mock,
        mock__get_unique_products: mock.Mock,
    ):
        """AwsDownload.download() must skip cached assets and write statements for downloaded ones"""

        mock_aws_auth_init.return_value = None
        plugin = self.get_download_plugin(self.product)
        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.s3_resource = mock.Mock()
        self.product.downloader_auth = auth_plugin
        plugin.config.products[self.product.collection]["build_safe"] = False

        self.product.assets.clear()
        self.product.assets.update(
            {
                "somewhere": {"href": "s3://eodata/somewhere/something"},
                "elsewhere": {"href": "s3://eodata/elsewhere/anything"},
            }
        )

        cached_asset_path = os.path.join(
            self.output_dir,
            self.product.properties["title"],
            "elsewhere_cached",
        )
        os.makedirs(os.path.dirname(cached_asset_path), exist_ok=True)
        Path(cached_asset_path).touch()

        plugin.set_statements(
            self.product.assets["elsewhere"],
            {
                **self.product.assets["elsewhere"].as_dict(),
                "file:local_path": cached_asset_path,
            },
            output_dir=self.output_dir,
        )

        mock_get_authenticated_objects.return_value.keys.return_value = ["eodata"]
        mock__get_unique_products.return_value = set()

        path = plugin.download(self.product, output_dir=self.output_dir)

        mock_get_authenticated_objects.assert_called_once_with(
            auth_plugin, "eodata", "somewhere"
        )
        self.assertEqual(
            path, os.path.join(self.output_dir, self.product.properties["title"])
        )

        somewhere_local_path = os.path.join(path, "somewhere")
        Path(somewhere_local_path).touch()
        somewhere_statements = plugin.check_cache(
            self.product.assets["somewhere"], output_dir=self.output_dir
        )
        self.assertIsNotNone(somewhere_statements)
        self.assertEqual(
            somewhere_statements["href"], "s3://eodata/somewhere/something"
        )
        self.assertEqual(somewhere_statements["file:local_path"], somewhere_local_path)

        elsewhere_statements = plugin.check_cache(
            self.product.assets["elsewhere"], output_dir=self.output_dir
        )
        self.assertIsNotNone(elsewhere_statements)
        self.assertEqual(elsewhere_statements["href"], "s3://eodata/elsewhere/anything")
        self.assertEqual(elsewhere_statements["file:local_path"], cached_asset_path)

    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth._get_authenticated_objects",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth.__init__",
        autospec=True,
    )
    def test_plugins_download_aws_all_assets_cached(
        self,
        mock_aws_auth_init: mock.Mock,
        mock_get_authenticated_objects: mock.Mock,
    ):
        """AwsDownload.download() must not download anything if all assets are cached"""

        mock_aws_auth_init.return_value = None
        plugin = self.get_download_plugin(self.product)
        auth_plugin = self.get_auth_plugin(plugin, self.product)
        self.product.downloader_auth = auth_plugin
        plugin.config.products[self.product.collection]["build_safe"] = False

        self.product.assets.clear()
        self.product.assets.update(
            {
                "somewhere": {"href": "s3://eodata/somewhere/something"},
                "elsewhere": {"href": "s3://eodata/elsewhere/anything"},
            }
        )
        product_local_path = os.path.join(
            self.output_dir, self.product.properties["title"]
        )
        os.makedirs(product_local_path, exist_ok=True)
        for key, asset in self.product.assets.items():
            cached_asset_path = os.path.join(product_local_path, f"{key}_cached")
            Path(cached_asset_path).touch()
            plugin.set_statements(
                asset,
                {**asset.as_dict(), "file:local_path": cached_asset_path},
                output_dir=self.output_dir,
            )
        remote_location = self.product.location

        # with asset filter: product location is not updated
        path = plugin.download(
            self.product, output_dir=self.output_dir, asset="somewhere"
        )
        self.assertEqual(path, product_local_path)
        self.assertEqual(self.product.location, remote_location)

        # without asset filter: product location is updated
        path = plugin.download(self.product, output_dir=self.output_dir)
        self.assertEqual(path, product_local_path)
        self.assertEqual(self.product.location, path_to_uri(product_local_path))

        mock_get_authenticated_objects.assert_not_called()

    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload.get_chunk_dest_path", autospec=True
    )
    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload._get_unique_products", autospec=True
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth._get_authenticated_objects",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth.__init__",
        autospec=True,
    )
    def test_plugins_download_aws_assets_statements_from_chunks(
        self,
        mock_aws_auth_init: mock.Mock,
        mock_get_authenticated_objects: mock.Mock,
        mock__get_unique_products: mock.Mock,
        mock_get_chunk_dest_path: mock.Mock,
    ):
        """AwsDownload.download() must write asset statements once all its chunks are downloaded"""

        mock_aws_auth_init.return_value = None
        plugin = self.get_download_plugin(self.product)
        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.s3_resource = mock.Mock()
        self.product.downloader_auth = auth_plugin
        plugin.config.products[self.product.collection]["build_safe"] = False
        plugin.config.flatten_top_dirs = False

        self.product.assets.clear()
        self.product.assets.update(
            {
                "somewhere": {"href": "s3://eodata/somewhere/something"},
                "elsewhere": {"href": "s3://eodata/elsewhere/anything"},
            }
        )
        somewhere_chunks = [
            mock.Mock(bucket_name="eodata", key=f"somewhere/something/{name}", size=1)
            for name in ("a.tif", "b.tif")
        ]
        elsewhere_chunk = mock.Mock(
            bucket_name="eodata", key="elsewhere/anything", size=1
        )
        mock__get_unique_products.return_value = [*somewhere_chunks, elsewhere_chunk]

        def chunk_dest_path(_self, product, chunk, build_safe=False):
            if chunk is elsewhere_chunk:
                raise NotAvailableError("out of SAFE chunk")
            return chunk.key

        mock_get_chunk_dest_path.side_effect = chunk_dest_path
        executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="eodag-download-all"
        )

        with mock.patch.object(
            executor, "submit", side_effect=AssertionError("must not submit")
        ):
            path = plugin.download(
                self.product, output_dir=self.output_dir, executor=executor
            )
        executor.shutdown()

        self.assertEqual(mock_get_chunk_dest_path.call_count, 3)
        for chunk in somewhere_chunks:
            chunk.Bucket.return_value.download_file.assert_called_once()
        elsewhere_chunk.Bucket.return_value.download_file.assert_not_called()

        statement_dir = os.path.join(self.output_dir, ".downloaded")
        # asset with all chunks downloaded: statement written with first chunk path
        somewhere_asset = self.product.assets["somewhere"]
        self.assertTrue(
            os.path.isfile(plugin._get_statement_path(somewhere_asset, statement_dir))
        )
        self.assertEqual(
            somewhere_asset["file:local_path"],
            os.path.join(path, "somewhere/something/a.tif"),
        )
        # asset whose only chunk was skipped: no statement written
        elsewhere_asset = self.product.assets["elsewhere"]
        self.assertFalse(
            os.path.isfile(plugin._get_statement_path(elsewhere_asset, statement_dir))
        )
        self.assertNotIn("file:local_path", elsewhere_asset)

    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload._get_unique_products", autospec=True
    )
    @mock.patch("eodag.plugins.download.aws.flatten_top_directories", autospec=True)
    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload.check_manifest_file_list", autospec=True
    )
    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload.finalize_s2_safe_product", autospec=True
    )
    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload.get_chunk_dest_path", autospec=True
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth._get_authenticated_objects",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth.__init__",
        autospec=True,
    )
    @mock.patch("eodag.plugins.download.aws.requests.get", autospec=True)
    def test_plugins_download_aws_no_safe_build_no_flatten_top_dirs(
        self,
        mock_requests_get: mock.Mock,
        mock_aws_auth_init: mock.Mock,
        mock_get_authenticated_objects: mock.Mock,
        mock_get_chunk_dest_path: mock.Mock,
        mock_finalize_s2_safe_product: mock.Mock,
        mock_check_manifest_file_list: mock.Mock,
        mock_flatten_top_directories: mock.Mock,
        mock__get_unique_products: mock.Mock,
    ):
        """AwsDownload.download() must not call safe build methods if not needed."""
        mock_aws_auth_init.return_value = None

        plugin = self.get_download_plugin(self.product)
        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.s3_resource = mock.Mock()
        self.product.downloader_auth = auth_plugin
        self.product.remote_location = (
            "http://somebucket.somehost.com/path/to/some/product"
        )

        # no SAFE build and no flatten_top_dirs
        plugin.config.products[self.product.collection]["build_safe"] = False
        plugin.config.flatten_top_dirs = False

        plugin.download(self.product, output_dir=self.output_dir)

        mock_get_authenticated_objects.assert_called_once_with(
            auth_plugin, "somebucket", "path/to/some"
        )
        self.assertEqual(mock_get_chunk_dest_path.call_count, 0)
        self.assertEqual(mock_finalize_s2_safe_product.call_count, 0)
        self.assertEqual(mock_check_manifest_file_list.call_count, 0)
        self.assertEqual(mock_flatten_top_directories.call_count, 0)

    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload._get_unique_products", autospec=True
    )
    @mock.patch("eodag.plugins.download.aws.flatten_top_directories", autospec=True)
    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload.check_manifest_file_list", autospec=True
    )
    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload.finalize_s2_safe_product", autospec=True
    )
    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload.get_chunk_dest_path", autospec=True
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth._get_authenticated_objects",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth.__init__",
        autospec=True,
    )
    @mock.patch("eodag.plugins.download.aws.requests.get", autospec=True)
    def test_plugins_download_aws_no_safe_build_flatten_top_dirs(
        self,
        mock_requests_get: mock.Mock,
        mock_aws_auth_init: mock.Mock,
        mock_get_authenticated_objects: mock.Mock,
        mock_get_chunk_dest_path: mock.Mock,
        mock_finalize_s2_safe_product: mock.Mock,
        mock_check_manifest_file_list: mock.Mock,
        mock_flatten_top_directories: mock.Mock,
        mock__get_unique_products: mock.Mock,
    ):
        """AwsDownload.download() must not call safe build methods if not needed."""
        mock_aws_auth_init.return_value = None
        plugin = self.get_download_plugin(self.product)
        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.s3_resource = mock.Mock()
        self.product.downloader_auth = auth_plugin
        self.product.remote_location = (
            "http://somebucket.somehost.com/path/to/some/product"
        )

        # no SAFE build and flatten_top_dirs
        plugin.config.products[self.product.collection]["build_safe"] = False
        plugin.config.flatten_top_dirs = True
        product_local_path = os.path.join(
            self.output_dir, self.product.properties["title"]
        )
        mock_flatten_top_directories.return_value = (
            product_local_path,
            product_local_path,
        )

        plugin.download(self.product, output_dir=self.output_dir)

        mock_get_authenticated_objects.assert_called_once_with(
            auth_plugin,
            "somebucket",
            "path/to/some",
        )
        self.assertEqual(mock_get_chunk_dest_path.call_count, 0)
        self.assertEqual(mock_finalize_s2_safe_product.call_count, 0)
        self.assertEqual(mock_check_manifest_file_list.call_count, 0)
        mock_flatten_top_directories.assert_called_once_with(
            os.path.join(self.output_dir, self.product.properties["title"]),
        )

    @mock.patch(
        "eodag.plugins.authentication.aws_auth.create_s3_session",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth._create_s3_resource",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth.get_s3_client",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.download.aws.open_s3_zipped_object",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth._get_authenticated_objects",
        autospec=True,
    )
    def test_plugins_download_aws_in_zip(
        self,
        mock_get_authenticated_objects: mock.Mock,
        mock_open_s3_zipped_object: mock.Mock,
        mock_s3_client: mock.Mock,
        mock_s3_resource: mock.Mock,
        mock_s3_session: mock.Mock,
    ):
        """AwsDownload.download() must handle files in zip."""

        def _open_zip(*args, **kwargs):
            return zipfile.ZipFile(
                os.path.join(
                    TEST_RESOURCES_PATH,
                    "products",
                    "as_archive",
                    "S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911.zip",
                )
            )

        mock_open_s3_zipped_object.side_effect = _open_zip

        plugin = self.get_download_plugin(self.product)
        auth_plugin = self.get_auth_plugin(plugin, self.product)
        self.product.downloader_auth = auth_plugin
        self.product.assets.clear()
        self.product.assets.update(
            {
                "file1": {
                    "href": (
                        "http://example.com/path/to/foo.zip!"
                        "GRANULE/L1C_T31TDH_A013204_20180101T105435/IMG_DATA/T31TDH_20180101T105441_B01.jp2"
                    )
                },
                "file2": {
                    "href": "http://example.com/path/to/foo.zip!GRANULE/L1C_T31TDH_A013204_20180101T105435/MTD_TL.xml"
                },
                "cached": {"href": "http://example.com/path/to/cached.tif"},
            }
        )
        cached_asset_path = os.path.join(
            self.output_dir,
            self.product.properties["title"],
            "GRANULE/L1C_T31TDH_A013204_20180101T105435/cached.tif",
        )
        os.makedirs(os.path.dirname(cached_asset_path), exist_ok=True)
        Path(cached_asset_path).touch()
        plugin.set_statements(
            self.product.assets["cached"],
            {
                **self.product.assets["cached"].as_dict(),
                "file:local_path": cached_asset_path,
            },
            output_dir=self.output_dir,
        )
        # no SAFE build and flatten_top_dirs
        plugin.config.products[self.product.collection]["build_safe"] = False
        plugin.config.flatten_top_dirs = True
        auth = auth_plugin.authenticate()

        path = plugin.download(self.product, output_dir=self.output_dir, auth=auth)

        self.assertEqual(mock_open_s3_zipped_object.call_count, 2)
        mock_open_s3_zipped_object.assert_called_with(
            "example", "path/to/foo.zip", auth_plugin.get_s3_client(), partial=False
        )
        self.assertTrue(
            os.path.isfile(
                os.path.join(path, "IMG_DATA/T31TDH_20180101T105441_B01.jp2")
            )
        )
        self.assertTrue(os.path.isfile(os.path.join(path, "MTD_TL.xml")))
        file1_statements = plugin.get_statements(
            self.product.assets["file1"], output_dir=self.output_dir
        )
        self.assertEqual(
            file1_statements["file:local_path"],
            os.path.normpath(
                os.path.join(path, "IMG_DATA/T31TDH_20180101T105441_B01.jp2")
            ),
        )
        file2_statements = plugin.get_statements(
            self.product.assets["file2"], output_dir=self.output_dir
        )
        self.assertEqual(
            file2_statements["file:local_path"],
            os.path.normpath(os.path.join(path, "MTD_TL.xml")),
        )
        cached_statements = plugin.get_statements(
            self.product.assets["cached"], output_dir=self.output_dir
        )
        self.assertEqual(
            cached_statements["file:local_path"],
            os.path.normpath(os.path.join(path, "cached.tif")),
        )

    @mock.patch("eodag.plugins.download.aws.flatten_top_directories", autospec=True)
    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload.check_manifest_file_list", autospec=True
    )
    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload.finalize_s2_safe_product", autospec=True
    )
    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload.get_chunk_dest_path", autospec=True
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth._get_authenticated_objects",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth.__init__",
        autospec=True,
    )
    @mock.patch("eodag.plugins.download.aws.requests.get", autospec=True)
    def test_plugins_download_aws_safe_build(
        self,
        mock_requests_get,
        mock_aws_auth_init,
        mock_get_authenticated_objects,
        mock_get_chunk_dest_path,
        mock_finalize_s2_safe_product,
        mock_check_manifest_file_list,
        mock_flatten_top_directories,
    ):
        """AwsDownload.download() must call safe build methods if needed."""
        mock_aws_auth_init.return_value = None
        plugin = self.get_download_plugin(self.product)
        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.s3_resource = mock.Mock()
        self.product.downloader_auth = auth_plugin
        self.product.remote_location = (
            "http://somebucket.somehost.com/path/to/some/product"
        )
        self.product.properties["eodag:product_info"] = (
            "http://example.com/productInfo.json"
        )
        execpected_output = os.path.join(
            self.output_dir, self.product.properties["title"]
        )
        # fetch_metadata return
        mock_requests_get.return_value.json.return_value = {
            "title": "foo",
            "path": "s3://example/here/is/productPath",
        }
        # authenticated objects mock
        mock_get_authenticated_objects.return_value.keys.return_value = [
            "somebucket",
            "example",
        ]
        mock_get_authenticated_objects.return_value.filter.side_effect = (
            lambda *x, **y: [mock.Mock(size=0, key=y["Prefix"])]
        )
        # # chunk dest path mock
        mock_get_chunk_dest_path.side_effect = lambda *x, **y: x[2].key

        # SAFE build
        plugin.config.products[self.product.collection]["build_safe"] = True

        path = plugin.download(self.product, output_dir=self.output_dir)

        mock_requests_get.assert_called_once_with(
            self.product.properties["eodag:product_info"],
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            verify=True,
        )
        self.assertEqual(mock_get_authenticated_objects.call_count, 2)
        mock_get_authenticated_objects.assert_any_call(
            auth_plugin, "somebucket", "path/to/some"
        )
        mock_get_authenticated_objects.assert_any_call(
            auth_plugin, "example", "here/is"
        )
        self.assertEqual(mock_get_chunk_dest_path.call_count, 2)
        mock_get_chunk_dest_path.assert_any_call(
            plugin, product=self.product, chunk=mock.ANY, build_safe=True
        )
        mock_finalize_s2_safe_product.assert_called_once_with(plugin, execpected_output)
        mock_check_manifest_file_list.assert_called_once_with(plugin, execpected_output)
        self.assertEqual(mock_flatten_top_directories.call_count, 0)

        self.assertEqual(path, execpected_output)

    @mock.patch("eodag.plugins.download.aws.flatten_top_directories", autospec=True)
    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload.check_manifest_file_list", autospec=True
    )
    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload.finalize_s2_safe_product", autospec=True
    )
    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload.get_chunk_dest_path", autospec=True
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth._get_authenticated_objects",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth.__init__",
        autospec=True,
    )
    @mock.patch("eodag.plugins.download.aws.requests.get", autospec=True)
    def test_plugins_download_aws_safe_build_assets(
        self,
        mock_requests_get,
        mock_aws_auth_init,
        mock_get_authenticated_objects,
        mock_get_chunk_dest_path,
        mock_finalize_s2_safe_product,
        mock_check_manifest_file_list,
        mock_flatten_top_directories,
    ):
        """AwsDownload.download() must call safe build methods if needed."""
        mock_aws_auth_init.return_value = None
        plugin = self.get_download_plugin(self.product)
        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.s3_resource = mock.Mock()
        self.product.downloader_auth = auth_plugin
        self.product.properties["eodag:product_info"] = (
            "http://example.com/productInfo.json"
        )
        self.product.properties["eodag:product_path"] = "http://example.com/productPath"
        self.product.assets.clear()
        self.product.assets.update(
            {
                "file1": {"href": "http://example.com/path/to/file1"},
                "file2": {"href": "http://example.com/path/to/file2"},
            }
        )
        execpected_output = os.path.join(
            self.output_dir, self.product.properties["title"]
        )
        mock_flatten_top_directories.return_value = (
            execpected_output,
            execpected_output,
        )
        # fetch_metadata return
        mock_requests_get.return_value.json.return_value = {
            "title": "foo",
            "path": "s3://example/here/is/productPath",
        }
        # authenticated objects mock
        mock_get_authenticated_objects.return_value.keys.return_value = [
            "somebucket",
            "example",
        ]
        mock_get_authenticated_objects.return_value.filter.side_effect = (
            lambda *x, **y: [mock.Mock(size=0, key=y["Prefix"])]
        )
        # chunk dest path mock
        mock_get_chunk_dest_path.side_effect = lambda *x, **y: x[2].key

        # SAFE build
        plugin.config.products[self.product.collection]["build_safe"] = True

        path = plugin.download(self.product, output_dir=self.output_dir)

        mock_requests_get.assert_called_once_with(
            self.product.properties["eodag:product_info"],
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            verify=True,
        )
        mock_get_authenticated_objects.assert_called_once_with(
            auth_plugin, "example", ""
        )
        # 3 calls : one for each asset plus one for the product path
        self.assertEqual(mock_get_chunk_dest_path.call_count, 3)
        mock_get_chunk_dest_path.assert_any_call(
            plugin, product=self.product, chunk=mock.ANY, build_safe=True
        )
        mock_finalize_s2_safe_product.assert_called_once_with(plugin, execpected_output)
        mock_check_manifest_file_list.assert_called_once_with(plugin, execpected_output)
        self.assertEqual(mock_flatten_top_directories.call_count, 0)

        self.assertEqual(path, execpected_output)

        # with filter for assets
        self.product.properties["title"] = "newTitle"
        setattr(self.product, "location", "file://path/to/file")
        # remove saved asset statements to force a fresh download on retry
        for asset in self.product.assets.values():
            statement_path = plugin._get_statement_path(
                asset, os.path.join(self.output_dir, ".downloaded")
            )
            if os.path.isfile(statement_path):
                os.remove(statement_path)
        plugin.download(self.product, output_dir=self.output_dir, asset="file1")
        # 2 additional calls : one for the filtered asset plus one for the product path
        self.assertEqual(5, mock_get_chunk_dest_path.call_count)

    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth._get_authenticated_objects",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth.__init__",
        autospec=True,
    )
    def test_plugins_download_aws_no_matching_collection(
        self,
        mock_aws_auth_init,
        mock_get_authenticated_objects: mock.Mock,
    ):
        """AwsDownload.download() must fail if no product chunk is available."""
        mock_aws_auth_init.return_value = None
        plugin = self.get_download_plugin(self.product)
        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.s3_resource = mock.Mock()
        self.product.downloader_auth = auth_plugin

        # no SAFE build and flatten_top_dirs
        plugin.config.products[self.product.collection]["build_safe"] = False
        plugin.config.flatten_top_dirs = True

        with self.assertRaises(NotAvailableError):
            plugin.download(self.product, outputs_prefix=self.output_dir)

    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth.get_s3_client",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.create_s3_session",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth._get_authenticated_objects",
        autospec=True,
    )
    def test_plugins_download_aws_get_rio_env(
        self,
        mock_get_authenticated_objects: mock.Mock,
        mock_s3_session: mock.Mock,
        mock_s3_client: mock.Mock,
    ):
        """AwsDownload.get_rio_env() must return rio env dict."""
        plugin = self.get_download_plugin(self.product)
        auth_plugin = self.get_auth_plugin(plugin, self.product)
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


class TestDownloadPluginCreodiasS3(BaseDownloadPluginTest):
    @mock.patch("eodag.plugins.download.aws.flatten_top_directories", autospec=True)
    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload.check_manifest_file_list", autospec=True
    )
    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload.finalize_s2_safe_product", autospec=True
    )
    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload.get_chunk_dest_path", autospec=True
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth._get_authenticated_objects",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.create_s3_session",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth._create_s3_resource",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.authentication.aws_auth.AwsAuth.get_s3_client",
        autospec=True,
    )
    @mock.patch("eodag.plugins.download.aws.requests.get", autospec=True)
    def test_plugins_download_creodias_s3(
        self,
        mock_requests_get,
        mock_s3_client,
        mock_s3_resource,
        mock_s3_session,
        mock_get_authenticated_objects,
        mock_get_chunk_dest_path,
        mock_finalize_s2_safe_product,
        mock_check_manifest_file_list,
        mock_flatten_top_directories,
    ):
        product = EOProduct(
            "creodias_s3",
            dict(
                geometry="POINT (0 0)",
                title="dummy_product",
                id="dummy",
            ),
        )
        assets = {
            "a1": {"title": "a1", "href": "s3://eodata/a/a1"},
            "a2": {"title": "a2", "href": "s3://eodata/a/a2"},
        }
        product.assets.update(assets)
        plugin = self.get_download_plugin(product)
        auth_plugin = self.get_auth_plugin(associated_plugin=plugin, product=product)
        product.downloader_auth = auth_plugin
        # authenticated objects mock
        mock_get_authenticated_objects.return_value.keys.return_value = [
            "a1",
            "a2",
        ]
        mock_get_authenticated_objects.return_value.filter.side_effect = (
            lambda *x, **y: [mock.Mock(size=0, key=y["Prefix"])]
        )
        product_local_path = os.path.join(self.output_dir, product.properties["title"])
        mock_flatten_top_directories.return_value = (
            product_local_path,
            product_local_path,
        )

        plugin.download(product, output_dir=self.output_dir, auth={})

        mock_get_authenticated_objects.assert_called_once_with(
            auth_plugin, "eodata", "a"
        )
        self.assertEqual(mock_get_chunk_dest_path.call_count, 2)
        self.assertEqual(mock_finalize_s2_safe_product.call_count, 0)
        self.assertEqual(mock_check_manifest_file_list.call_count, 0)
        self.assertEqual(mock_flatten_top_directories.call_count, 1)
