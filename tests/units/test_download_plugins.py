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
from tempfile import NamedTemporaryFile, TemporaryDirectory, gettempdir
from typing import Any, Callable
from unittest import mock

import responses
import yaml

from eodag.api.product.metadata_mapping import DEFAULT_METADATA_MAPPING
from eodag.utils import MockResponse, ProgressCallback
from eodag.utils.exceptions import DownloadError, NoMatchingProductType, ValidationError
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
    PluginManager,
    config,
    load_default_config,
    override_config_from_mapping,
    path_to_uri,
    uri_to_path,
)


class BaseDownloadPluginTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(BaseDownloadPluginTest, cls).setUpClass()
        providers_config = load_default_config()
        cls.plugins_manager = PluginManager(providers_config)
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
            "peps",
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
    def test_plugins_download_base_prepare_download_existing(self):
        """Download._prepare_download must detect if product destination already exists"""

        product_file = NamedTemporaryFile()
        self.product.location = path_to_uri(product_file.name)
        Path(product_file.name).touch()
        self.assertNotEqual(self.product.location, self.product.remote_location)

        plugin = self.get_download_plugin(self.product)

        with self.assertLogs(level="INFO") as cm:
            fs_path, record_filename = plugin._prepare_download(self.product)
            self.assertEqual(fs_path, product_file.name)
            self.assertIsNone(record_filename)
            self.assertIn("Product already present on this platform", str(cm.output))

    def test_plugins_download_base_prepare_download_record_file(self):
        """Download._prepare_download must check existing record files"""

        self.product.location = self.product.remote_location = "http://foo.bar"
        self.product.product_type = "foo"

        with TemporaryDirectory() as output_dir:
            download_kwargs = dict(output_dir=output_dir)
            product_path_dir = Path(output_dir) / self.product.properties["title"]
            recordfile_dir = Path(output_dir) / ".downloaded"
            recordfile_dir.mkdir()

            recordfile_path = (
                recordfile_dir / hashlib.md5("foo-dummy".encode("utf-8")).hexdigest()
            )
            old_recordfile_path = (
                recordfile_dir
                / hashlib.md5("http://foo.bar".encode("utf-8")).hexdigest()
            )

            plugin = self.get_download_plugin(self.product)

            # < v3.0.0b1 formatted record file and product path exist, record file moved to new format
            product_path_dir.mkdir()
            file_in_dir = product_path_dir / "foo"
            file_in_dir.touch()
            old_recordfile_path.touch()
            with self.assertLogs(level="INFO") as cm:
                plugin._prepare_download(self.product, **download_kwargs)
                self.assertTrue(os.path.isfile(recordfile_path))
                self.assertFalse(os.path.isfile(old_recordfile_path))
                self.assertIn("Product already downloaded", str(cm.output))

            # new formatted record file and product path exist
            with self.assertLogs(level="INFO") as cm:
                plugin._prepare_download(self.product, **download_kwargs)
                self.assertTrue(os.path.isfile(recordfile_path))
                self.assertIn("Product already downloaded", str(cm.output))

            # already downloaded product without extension
            file_in_dir.unlink()
            product_path_dir.rmdir()
            product_path_dir.touch()
            with self.assertLogs(level="INFO") as cm:
                plugin._prepare_download(self.product, **download_kwargs)
                self.assertIn("Product already downloaded", str(cm.output))
                self.assertIn(
                    "Remove existing partially downloaded file", str(cm.output)
                )

            # already downloaded product with extension
            product_path_with_ext = product_path_dir.with_suffix(".xyz")
            product_path_with_ext.touch()
            with self.assertLogs(level="INFO") as cm:
                plugin._prepare_download(self.product, **download_kwargs)
                self.assertIn("Product already downloaded", str(cm.output))

    def test_plugins_download_base_prepare_download_no_url(self):
        """Download._prepare_download must return None when no download url"""

        self.assertEqual(self.product.remote_location, "")

        plugin = self.get_download_plugin(self.product)

        fs_path, record_filename = plugin._prepare_download(self.product)

        self.assertIsNone(fs_path)
        self.assertIsNone(record_filename)

    def test_plugins_download_base_prepare_download_collision_avoidance(self):
        """Download._prepare_download must use collision avoidance suffix"""

        self.product.properties["title"] = "needs sanitïze"
        self.product.properties["id"] = "alsô.zip"
        self.product.location = self.product.remote_location = "somewhere"

        plugin = self.get_download_plugin(self.product)

        fs_path, _ = plugin._prepare_download(self.product)

        self.assertEqual(fs_path, os.path.join(gettempdir(), "needs_sanitize-also.zip"))

    def test_plugins_download_base_prepare_download_dir_permission(self):
        """Download._prepare_download must check output directory permissions"""
        if os.name == "nt":
            self.skipTest("windows permissions too complex to set for this test")

        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "somewhere"
        # read only output dir
        outdir = TemporaryDirectory()
        os.chmod(outdir.name, stat.S_IREAD)

        with self.assertLogs(level="WARNING") as cm:
            fs_path, _ = plugin._prepare_download(self.product, output_dir=outdir.name)
            self.assertIn("Unable to create records directory", str(cm.output))


class TestDownloadPluginHttp(BaseDownloadPluginTest):
    def _download_response_archive(self, local_product_as_archive_path: str):
        class Response(object):
            """Emulation of a response to eodag.plugins.download.http.requests.get method for a zipped product"""

            def __init__(self):
                # Using a zipped product file
                with open(local_product_as_archive_path, "rb") as fh:
                    self.__zip_buffer = io.BytesIO(fh.read())
                cl = self.__zip_buffer.getbuffer().nbytes
                self.headers = {"content-length": cl}
                self.url = "http://foo.bar/product.zip"

            def __enter__(self):
                return self

            def __exit__(self, *args: Any):
                pass

            def iter_content(self, **kwargs: Any):
                with self.__zip_buffer as fh:
                    while True:
                        chunk = fh.read(kwargs["chunk_size"])
                        if not chunk:
                            break
                        yield chunk

            def raise_for_status(self):
                pass

            def close(self):
                pass

        return Response()

    def _set_download_simulation(
        self,
        mock_requests_session: Callable[[], None],
        local_product_as_archive_path: str,
    ):
        mock_requests_session.return_value = self._download_response_archive(
            local_product_as_archive_path
        )

    def _dummy_product(
        self, provider: str, properties: dict[str, Any], productType: str
    ):
        return EOProduct(
            provider,
            properties,
            kwargs={"productType": productType},
        )

    def _dummy_downloadable_product(
        self,
        mock_requests_session: Callable[[], None],
        local_product_as_archive_path: str,
        provider: str,
        properties: dict[str, Any],
        productType: str,
    ):
        self._set_download_simulation(
            mock_requests_session, local_product_as_archive_path
        )
        dl_config = config.PluginConfig.from_mapping(
            {
                "type": "HTTPDownload",
                "base_uri": "fake_base_uri",
                "output_dir": self.output_dir,
                "extract": False,
                "delete_archive": False,
            }
        )
        downloader = HTTPDownload(provider=provider, config=dl_config)
        product = self._dummy_product(provider, properties, productType)
        product.register_downloader(downloader, None)
        return product

    @mock.patch("eodag.plugins.download.http.requests.Session.request", autospec=True)
    def test_plugins_download_http_zip_file_ok(self, mock_requests_session):
        """HTTPDownload.download() must keep the output as it is when it is a zip file"""

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
        product_type = "S2_MSI_L1C"
        platform = "S2A"
        instrument = "MSI"

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
            "productType": product_type,
            "platform": "Sentinel-2",
            "platformSerialIdentifier": platform,
            "instrument": instrument,
            "title": local_filename,
            "downloadLink": download_url,
        }

        # Put an empty string as value of properties which are not relevant for the test
        eoproduct_props.update(
            {key: "" for key in DEFAULT_METADATA_MAPPING if key not in eoproduct_props}
        )

        product = self._dummy_downloadable_product(
            mock_requests_session,
            local_product_as_archive_path,
            provider,
            eoproduct_props,
            product_type,
        )
        path = product.download()

        expected_path = os.path.join(
            self.output_dir, product.properties["title"] + ".zip"
        )
        self.assertEqual(path, expected_path)
        self.assertTrue(os.path.isfile(path))
        self.assertTrue(zipfile.is_zipfile(path))

        # check if the hidden directory ".downloaded" have been created with the product zip file
        self.assertEqual(len(os.listdir(self.output_dir)), 2)

        mock_requests_session.assert_called_once_with(
            mock.ANY,
            "get",
            product.remote_location,
            stream=True,
            auth=None,
            params={},
            headers=USER_AGENT,
            timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
            verify=True,
        )

    @mock.patch(
        "eodag.plugins.download.http.HTTPDownload._stream_download", autospec=True
    )
    @mock.patch("eodag.plugins.download.http.HTTPDownload.stream", create=True)
    def test_plugins_download_http_nonzip_file_with_zip_extension_ok(
        self, mock_stream, mock_stream_download
    ):
        """HTTPDownload.download() must create an output directory
        when the result is a non-zip file with a '.zip' outputs extension"""

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
            None,
            progress_callback,
            output_dir=self.output_dir,
        )

    @mock.patch(
        "eodag.plugins.download.http.HTTPDownload._stream_download", autospec=True
    )
    @mock.patch("eodag.plugins.download.http.HTTPDownload.stream", create=True)
    def test_plugins_download_http_file_without_zip_extension_ok(
        self, mock_stream, mock_stream_download
    ):
        """HTTPDownload.download() must create an output directory
        when the result is a file without a '.zip' outputs extension"""

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
            None,
            progress_callback,
            output_dir=self.output_dir,
        )

    @mock.patch(
        "eodag.plugins.download.http.HTTPDownload._stream_download", autospec=True
    )
    @mock.patch("eodag.plugins.download.http.HTTPDownload.stream", create=True)
    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_ignore_assets(
        self, mock_requests_get, mock_requests_head, mock_stream, mock_stream_download
    ):
        """HTTPDownload.download() must ignore assets if configured to"""

        plugin = self.get_download_plugin(self.product)
        self.product.location = (
            self.product.remote_location
        ) = "http://somewhere/download_from_location"
        self.product.properties["id"] = "someproduct"
        self.product.assets.clear()
        self.product.assets.update({"foo": {"href": "http://somewhere/download_asset"}})
        mock_requests_get.return_value.__enter__.return_value.iter_content.side_effect = lambda *x, **y: io.BytesIO(
            b"some content"
        )

        mock_stream_download.return_value = [b"a"]
        self.product.filename = "dummy_product.nc"

        # download asset if ignore_assets = False
        plugin.config.ignore_assets = False
        path = plugin.download(self.product, output_dir=self.output_dir)
        mock_requests_get.assert_called_once_with(
            self.product.assets["foo"]["href"],
            stream=True,
            auth=None,
            params=plugin.config.dl_url_params,
            headers=USER_AGENT,
            timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
            verify=True,
        )
        mock_stream_download.assert_not_called()
        # re-enable product download
        self.product.location = self.product.remote_location
        shutil.rmtree(path)
        mock_requests_get.reset_mock()
        mock_stream_download.reset_mock()

        # download using remote_location if ignore_assets = True
        plugin.config.ignore_assets = True
        path = plugin.download(self.product, output_dir=self.output_dir)
        mock_requests_get.assert_not_called()
        mock_stream_download.assert_called_once()
        # re-enable product download
        self.product.location = self.product.remote_location
        shutil.rmtree(path)
        mock_requests_get.reset_mock()
        mock_stream_download.reset_mock()

        # download asset if ignore_assets unset
        del plugin.config.ignore_assets
        plugin.download(self.product, output_dir=self.output_dir)
        mock_requests_get.assert_called_once_with(
            self.product.assets["foo"]["href"],
            stream=True,
            auth=None,
            params=plugin.config.dl_url_params,
            headers=USER_AGENT,
            timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
            verify=True,
        )
        mock_stream_download.assert_not_called()

    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_ignore_assets_without_ssl(
        self, mock_requests_get, mock_requests_head
    ):
        """HTTPDownload.download() must ignore assets if configured to"""

        plugin = self.get_download_plugin(self.product)
        self.product.location = (
            self.product.remote_location
        ) = "http://somewhere/download_from_location"
        self.product.properties["id"] = "someproduct"
        self.product.assets.clear()
        self.product.assets.update({"foo": {"href": "http://somewhere/download_asset"}})
        mock_requests_get.return_value.__enter__.return_value.iter_content.side_effect = lambda *x, **y: io.BytesIO(
            b"some content"
        )
        # download asset if ssl_verify = False
        plugin.config.ssl_verify = False

        plugin.download(self.product, output_dir=self.output_dir)
        mock_requests_head.assert_called_once_with(
            self.product.assets["foo"]["href"],
            auth=None,
            params=plugin.config.dl_url_params,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            verify=False,
        )
        mock_requests_get.assert_called_once_with(
            self.product.assets["foo"]["href"],
            stream=True,
            auth=None,
            params=plugin.config.dl_url_params,
            headers=USER_AGENT,
            timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
            verify=False,
        )
        del plugin.config.ssl_verify

    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_assets_filename_from_href(
        self, mock_requests_get, mock_requests_head
    ):
        """HTTPDownload.download() must create an outputfile"""

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
        mock_requests_get.return_value.__enter__.return_value.headers = {
            "content-disposition": ""
        }
        mock_requests_head.return_value.headers = {"content-disposition": ""}

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
            params=plugin.config.dl_url_params,
            headers=USER_AGENT,
            timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
            verify=True,
        )
        # Check if the HEAD request has been called once for size & filename request
        mock_requests_head.assert_called_once_with(
            self.product.assets["foo"]["href"],
            auth=None,
            params=plugin.config.dl_url_params,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            verify=True,
        )

    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_assets_filename_from_get(
        self, mock_requests_get, mock_requests_head
    ):
        """HTTPDownload.download() must create an outputfile"""

        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"
        self.product.assets.clear()
        self.product.assets.update({"foo": {"href": "http://somewhere/something"}})
        mock_requests_get.return_value.__enter__.return_value.iter_content.return_value = io.BytesIO(
            b"some content"
        )
        mock_requests_get.return_value.__enter__.return_value.headers = {
            "content-disposition": '; filename = "somethingelse"'
        }
        mock_requests_head.return_value.headers = {"content-disposition": ""}

        path = plugin.download(self.product, output_dir=self.output_dir)

        self.assertEqual(path, os.path.join(self.output_dir, "dummy_product"))
        self.assertTrue(os.path.isdir(path))
        self.assertTrue(
            os.path.isfile(
                os.path.join(self.output_dir, "dummy_product", "somethingelse")
            )
        )

    @mock.patch("eodag.plugins.download.http.HTTPDownload._get_asset_sizes")
    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_assets_error(
        self, mock_requests_get, mock_requests_head, mock_asset_size
    ):
        """HTTPDownload.download() must create an outputfile"""

        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"
        self.product.assets.clear()
        self.product.assets.update({"foo": {"href": "http://somewhere/something"}})
        self.product.assets.update({"bar": {"href": "http://somewhere/anotherthing"}})
        res = MockResponse({"a": "a"}, 400)
        mock_requests_get.side_effect = res
        mock_requests_head.return_value.headers = {"content-disposition": ""}
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
        """HTTPDownload.download() must download assets to a temporary file"""

        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"
        self.product.assets.clear()
        self.product.assets.update({"foo": {"href": "http://somewhere/something"}})
        mock_requests_get.return_value.__enter__.return_value.iter_content.return_value = io.BytesIO(
            b"some content"
        )
        mock_requests_get.return_value.__enter__.return_value.headers = {
            "content-disposition": '; filename = "somethingelse"'
        }
        mock_requests_head.return_value.headers = {"content-disposition": ""}
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
        self.assertEqual(self.product.remote_location, "http://somewhere")
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
        """HTTPDownload._stream_download_dict() must raise an error if an error is returned by the provider"""

        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"
        self.product.assets.clear()
        self.product.assets.update({"foo": {"href": "http://somewhere/something"}})
        self.product.assets.update({"any": {"href": "http://somewhere/anything"}})

        # first asset returns error
        mock_requests_get.return_value = MockResponse(status_code=404)
        mock_requests_head.return_value.headers = {
            "content-disposition": "",
            "Content-length": "10",
        }

        with self.assertRaises(DownloadError):
            plugin._stream_download_dict(self.product, output_dir=self.output_dir)
        # Interrupted download
        # Product location not changed
        self.assertEqual(self.product.location, "http://somewhere")
        self.assertEqual(self.product.remote_location, "http://somewhere")

    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_assets_resume(
        self, mock_requests_get, mock_requests_head
    ):
        """HTTPDownload.download() must resume the interrupted download of assets"""

        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"
        self.product.assets.clear()
        self.product.assets.update({"foo": {"href": "http://somewhere/something"}})
        mock_requests_get.return_value.__enter__.return_value.iter_content.return_value = io.BytesIO(
            b"some content"
        )
        mock_requests_get.return_value.__enter__.return_value.headers = {
            "content-disposition": '; filename = "somethingelse"'
        }
        mock_requests_head.return_value.headers = {"content-disposition": ""}
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
        """HTTPDownload.download() must create an outputfile"""

        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
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
        mock_requests_get.return_value.__enter__.return_value.headers = {
            "content-disposition": '; filename = "somethingelse"'
        }
        mock_requests_head.return_value.headers = {"content-disposition": ""}

        path = plugin.download(self.product, output_dir=self.output_dir, asset="else.*")

        self.assertEqual(path, os.path.join(self.output_dir, "dummy_product"))
        self.assertTrue(os.path.isdir(path))
        self.assertTrue(
            os.path.isfile(
                os.path.join(self.output_dir, "dummy_product", "somethingelse")
            )
        )
        self.assertEqual(2, mock_requests_get.call_count)
        self.product.location = self.product.remote_location = "http://elsewhere"
        plugin.download(self.product, output_dir=self.output_dir)
        self.assertEqual(6, mock_requests_get.call_count)

    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_assets_filename_from_head(
        self, mock_requests_get, mock_requests_head
    ):
        """HTTPDownload.download() must create an outputfile"""

        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"
        self.product.assets.clear()
        self.product.assets.update({"foo": {"href": "http://somewhere/something"}})
        mock_requests_get.return_value.__enter__.return_value.iter_content.return_value = io.BytesIO(
            b"some content"
        )
        mock_requests_get.return_value.__enter__.return_value.headers = {
            "content-disposition": '; filename = "somethingelse"'
        }
        mock_requests_head.return_value.headers = {
            "content-disposition": '; filename = "anotherthing"'
        }

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
        """HTTPDownload.download() must get assets sizes"""

        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.assets.clear()
        self.product.assets.update(
            {
                "foo": {"href": "http://somewhere/a"},
                "bar": {"href": "http://somewhere/b"},
            }
        )

        mock_requests_head.return_value.headers = {
            "Content-length": "1",
            "content-disposition": '; size = "2"',
        }
        mock_requests_get.return_value.__enter__.return_value.iter_content.return_value = io.BytesIO(
            b"some content"
        )
        mock_requests_get.return_value.__enter__.return_value.headers = {
            "Content-length": "3",
            "content-disposition": '; size = "4"',
        }

        # size from HEAD / Content-length
        with TemporaryDirectory() as temp_dir:
            plugin.download(self.product, output_dir=temp_dir)
        mock_progress_callback_reset.assert_called_once_with(mock.ANY, total=1 + 1)

        # size from HEAD / content-disposition
        mock_requests_head.return_value.headers.pop("Content-length")
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

        # size from GET / Content-length
        mock_requests_head.return_value.headers.pop("content-disposition")
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

        # size from GET / content-disposition
        mock_requests_get.return_value.__enter__.return_value.iter_content.return_value = io.BytesIO(
            b"some content"
        )
        mock_requests_get.return_value.__enter__.return_value.headers.pop(
            "Content-length"
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
            "content-disposition"
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
        """HTTPDownload.download() must handle one local asset"""

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
        """HTTPDownload.download() must handle several local assets"""

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
        """HTTPDownload.download must order the product if needed"""

        self.product.provider = "cop_ads"
        self.product.product_type = "CAMS_EAC4"
        product_dataset = "cams-global-reanalysis-eac4"

        plugin = self.get_download_plugin(self.product)
        auth = self.get_auth_plugin(plugin, self.product)
        auth.config.credentials = {"apikey": "anicekey"}
        self.product.register_downloader(plugin, auth)

        endpoint = "https://ads.atmosphere.copernicus.eu/api/retrieve/v1"
        self.product.properties["orderLink"] = (
            f"{endpoint}/processes/{product_dataset}/execution" + '?{"foo": "bar"}'
        )
        self.product.properties["id"] = "CAMS_EAC4_ORDERABLE_12345"
        self.product.properties["storageStatus"] = "OFFLINE"
        self.product.location = self.product.remote_location = (
            NOT_AVAILABLE + '?{"foo": "bar"}'
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
                adding_headers={"content-disposition": "", "PRIVATE-TOKEN": "anicekey"},
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
            self.assertEqual(
                self.product.properties["downloadLink"], expected_remote_location
            )
            self.assertEqual(
                self.product.properties["orderStatusLink"], expected_order_status_link
            )
            self.assertEqual(path, expected_path)
            self.assertEqual(self.product.location, path_to_uri(expected_path))

        run()

    @mock.patch("eodag.plugins.download.http.requests.request", autospec=True)
    def test_plugins_download_http_order_get(self, mock_request):
        """HTTPDownload._order() must request using orderLink and GET protocol"""
        plugin = self.get_download_plugin(self.product)
        self.product.properties["downloadLink"] = "https://peps.cnes.fr/dummy"
        self.product.properties["orderLink"] = "http://somewhere/order"
        self.product.properties["storageStatus"] = OFFLINE_STATUS

        # customized timeout
        timeout_backup = getattr(plugin.config, "timeout", None)
        plugin.config.timeout = 10
        try:
            auth_plugin = self.get_auth_plugin(plugin, self.product)
            auth_plugin.config.credentials = {"username": "foo", "password": "bar"}
            auth = auth_plugin.authenticate()

            plugin._order(self.product, auth=auth)

            mock_request.assert_called_once_with(
                method="GET",
                url=self.product.properties["orderLink"],
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

    @mock.patch("eodag.plugins.download.http.requests.request", autospec=True)
    def test_plugins_download_http_order_get_raises_if_request_500(self, mock_request):
        """HTTPDownload._order() must raise an error if request to backend
        provider failed"""

        # Configure mock to raise an error
        mock_request.return_value = MockResponse(status_code=500)

        plugin = self.get_download_plugin(self.product)
        self.product.properties["downloadLink"] = "https://peps.cnes.fr/dummy"
        self.product.properties["orderLink"] = "http://somewhere/order"

        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.config.credentials = {"username": "foo", "password": "bar"}
        auth = auth_plugin.authenticate()

        # Verify that a DownloadError is raised
        with self.assertRaises(DownloadError) as context:
            plugin._order(self.product, auth=auth)
        self.assertIn("could not be ordered", str(context.exception))

        mock_request.assert_called_once_with(
            method="GET",
            url=self.product.properties["orderLink"],
            auth=auth,
            headers=USER_AGENT,
            timeout=5,
            verify=True,
        )

    @mock.patch("eodag.plugins.download.http.requests.request", autospec=True)
    def test_plugins_download_http_order_get_raises_if_request_400(self, mock_request):
        # Set up the EOProduct and the necessary properties
        plugin = self.get_download_plugin(self.product)
        self.product.properties["downloadLink"] = "https://peps.cnes.fr/dummy"
        self.product.properties["orderLink"] = "http://somewhere/order"

        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.config.credentials = {"username": "foo", "password": "bar"}

        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.config.credentials = {"username": "foo", "password": "bar"}
        auth = auth_plugin.authenticate()

        # Mock the response to raise HTTPError with a 400 status
        mock_request.return_value = MockResponse(status_code=400)

        # Test the function, expecting ValidationError to be raised
        with self.assertRaises(ValidationError) as context:
            plugin._order(self.product, auth=auth)
        self.assertIn("could not be ordered", str(context.exception))

        mock_request.assert_called_once_with(
            method="GET",
            url=self.product.properties["orderLink"],
            auth=auth,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            verify=True,
        )

    @mock.patch("eodag.plugins.download.http.requests.request", autospec=True)
    def test_plugins_download_http_order_post(self, mock_request):
        """HTTPDownload._order() must request using orderLink and POST protocol"""
        plugin = self.get_download_plugin(self.product)
        self.product.properties["downloadLink"] = "https://peps.cnes.fr/dummy"
        self.product.properties["storageStatus"] = OFFLINE_STATUS
        plugin.config.order_method = "POST"

        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.config.credentials = {"username": "foo", "password": "bar"}
        auth = auth_plugin.authenticate()

        # orderLink without query query args
        self.product.properties["orderLink"] = "http://somewhere/order"
        plugin._order(self.product, auth=auth)
        mock_request.assert_called_once_with(
            method="POST",
            url=self.product.properties["orderLink"],
            auth=auth,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            verify=True,
        )
        # orderLink with query query args
        mock_request.reset_mock()
        self.product.properties["orderLink"] = "http://somewhere/order?foo=bar"
        plugin._order(self.product, auth=auth)
        mock_request.assert_called_once_with(
            method="POST",
            url="http://somewhere/order",
            auth=auth,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            json={"foo": ["bar"]},
            verify=True,
        )

        # orderLink with JSON data containing a query string
        mock_request.reset_mock()
        self.product.properties[
            "orderLink"
        ] = 'http://somewhere/order?{"location": "dataset_id=lorem&data_version=202211", "cacheable": "true"}'
        plugin._order(self.product, auth=auth)
        mock_request.assert_called_once_with(
            method="POST",
            url="http://somewhere/order",
            auth=auth,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            json={
                "location": "dataset_id=lorem&data_version=202211",
                "cacheable": "true",
            },
            verify=True,
        )

    def test_plugins_download_http_order_status(self):
        """HTTPDownload._order_status() must request status using orderStatusLink"""
        plugin = self.get_download_plugin(self.product)
        plugin.config.order_status = {
            "metadata_mapping": {
                "percent": "$.json.progress_percentage",
                "that": "$.json.that",
            },
            "error": {"that": "failed"},
        }
        self.product.properties["orderStatusLink"] = "http://somewhere/order-status"
        self.product.properties["downloadLink"] = "https://peps.cnes.fr/dummy"

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
                plugin._order_status(self.product, auth=auth)

            self.assertIn(
                list(USER_AGENT.items())[0], responses.calls[0].request.headers.items()
            )
            self.assertEqual(len(responses.calls), 1)

        run()

    @mock.patch("eodag.plugins.download.http.requests.request", autospec=True)
    def test_plugins_download_http_order_status_get_raises_if_request_500(
        self, mock_request
    ):
        """HTTPDownload._order() must raise an error if request to backend
        provider failed"""

        # Configure mock to raise an error
        mock_request.return_value = MockResponse(status_code=500)

        plugin: HTTPDownload = self.get_download_plugin(self.product)
        self.product.properties["downloadLink"] = "https://peps.cnes.fr/dummy"
        self.product.properties["orderLink"] = "http://somewhere/order"
        self.product.properties["orderStatusLink"] = "http://somewhere/orderstatus"

        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.config.credentials = {"username": "foo", "password": "bar"}
        auth = auth_plugin.authenticate()

        # Verify that a DownloadError is raised
        with self.assertRaises(DownloadError) as context:
            plugin._order_status(self.product, auth=auth)
        self.assertIn("order status could not be checked", str(context.exception))

        mock_request.assert_called_once_with(
            method="GET",
            url=self.product.properties["orderStatusLink"],
            auth=auth,
            headers=USER_AGENT,
            timeout=5,
            allow_redirects=False,
            json=None,
        )

    @mock.patch("eodag.plugins.download.http.requests.request", autospec=True)
    def test_plugins_download_http_order_status_get_raises_if_request_400(
        self, mock_request
    ):
        # Set up the EOProduct and the necessary properties
        plugin: HTTPDownload = self.get_download_plugin(self.product)
        self.product.properties["downloadLink"] = "https://peps.cnes.fr/dummy"
        self.product.properties["orderLink"] = "http://somewhere/order"
        self.product.properties["orderStatusLink"] = "http://somewhere/orderstatus"

        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.config.credentials = {"username": "foo", "password": "bar"}

        auth_plugin = self.get_auth_plugin(plugin, self.product)
        auth_plugin.config.credentials = {"username": "foo", "password": "bar"}
        auth = auth_plugin.authenticate()

        # Mock the response to raise HTTPError with a 400 status
        mock_request.return_value = MockResponse(status_code=400)

        # Test the function, expecting ValidationError to be raised
        with self.assertRaises(ValidationError) as context:
            plugin._order_status(self.product, auth=auth)
        self.assertIn("order status could not be checked", str(context.exception))

        mock_request.assert_called_once_with(
            method="GET",
            url=self.product.properties["orderStatusLink"],
            auth=auth,
            headers=USER_AGENT,
            timeout=5,
            allow_redirects=False,
            json=None,
        )

    def test_plugins_download_http_order_status_search_again(self):
        """HTTPDownload._order_status() must search again after success if needed"""
        plugin = self.get_download_plugin(self.product)
        plugin.config.order_status = {
            "metadata_mapping": {"status": "$.json.status"},
            "success": {"status": "great-success"},
            "on_success": {
                "need_search": True,
                "result_type": "xml",
                "results_entry": "//entry",
                "metadata_mapping": {
                    "downloadLink": "foo/text()",
                },
            },
        }
        self.product.properties["orderStatusLink"] = "http://somewhere/order-status"
        self.product.properties["searchLink"] = "http://somewhere/search-again"
        self.product.properties["downloadLink"] = "https://peps.cnes.fr/dummy"

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

            plugin._order_status(self.product, auth=auth)

            self.assertEqual(
                self.product.properties["downloadLink"], "http://new-download-link"
            )
            self.assertEqual(len(responses.calls), 2)

        run()

    def test_plugins_download_http_order_status_search_again_raises_if_request_failed(
        self,
    ):
        """HTTPDownload._order_status() must raise an error if the search request after success failed"""
        plugin = self.get_download_plugin(self.product)
        plugin.config.order_status = {
            "metadata_mapping": {"status": "$.json.status"},
            "success": {"status": "great-success"},
            "on_success": {
                "need_search": True,
                "result_type": "xml",
                "results_entry": "//entry",
                "metadata_mapping": {
                    "downloadLink": "foo/text()",
                },
            },
        }
        self.product.properties["orderStatusLink"] = "http://somewhere/order-status"
        self.product.properties["searchLink"] = "http://somewhere/search-again"
        self.product.properties["downloadLink"] = "https://peps.cnes.fr/dummy"

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
                    plugin._order_status(self.product, auth=auth)
            if error_code == 400:
                with self.assertRaises(ValidationError) as context:
                    plugin._order_status(self.product, auth=auth)
            self.assertIn("order status could not be checked", str(context.exception))
            self.assertEqual(len(responses.calls), 2)

        run(error_code=500)
        run(error_code=400)


class TestDownloadPluginHttpRetry(BaseDownloadPluginTest):
    def setUp(self):
        super(TestDownloadPluginHttpRetry, self).setUp()

        self.plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"
        self.product.properties["storageStatus"] = OFFLINE_STATUS

    def test_plugins_download_http_retry_error_timeout(self):
        """HTTPDownload.download() must retry on error until timeout"""

        @responses.activate(registry=responses.registries.FirstMatchRegistry)
        def run():
            url = "http://somewhere/?issuerId=peps"
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
        """HTTPDownload.download() must retry if not ready until timeout"""

        @responses.activate(registry=responses.registries.FirstMatchRegistry)
        def run():
            url = "http://somewhere/?issuerId=peps"
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
        """HTTPDownload.download() must retry until request succeeds"""

        @responses.activate(registry=responses.registries.OrderedRegistry)
        def run():
            # fail, then succeeds
            url = "http://somewhere/?issuerId=peps"
            responses.add(responses.GET, url, status=202)
            responses.add(responses.GET, url, status=202)
            responses.add(
                responses.GET,
                "http://somewhere/?issuerId=peps",
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
        """HTTPDownload.download() must not retry on very short timeout"""

        @responses.activate(registry=responses.registries.FirstMatchRegistry)
        def run():
            url = "http://somewhere/?issuerId=peps"
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
        """HTTPDownload.download() must retry once if wait time is equal to timeout"""

        @responses.activate(registry=responses.registries.FirstMatchRegistry)
        def run():
            url = "http://somewhere/?issuerId=peps"
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
        """HTTPDownload.download() must not retry on error if timeout is disabled"""

        @responses.activate(registry=responses.registries.FirstMatchRegistry)
        def run():
            url = "http://somewhere/?issuerId=peps"
            responses.add(responses.GET, url, status=202)

            with self.assertRaisesRegex(NotAvailableError, r"^((?!timeout).)*$"):
                self.plugin.download(
                    self.product, output_dir=self.output_dir, wait=-1, timeout=-1
                )

            # there must have been only one try
            self.assertEqual(len(responses.calls), 1)

        run()


class TestDownloadPluginAws(BaseDownloadPluginTest):
    def setUp(self):
        super(TestDownloadPluginAws, self).setUp()
        self.product = EOProduct(
            "aws_eos",
            dict(
                geometry="POINT (0 0)",
                title="dummy_product",
                id="dummy",
            ),
            productType="S2_MSI_L2A",
        )
        self.product.location = (
            self.product.remote_location
        ) = "http://somebucket.somehost.com/path/to/some/product"

    def test_plugins_download_aws_get_bucket_prefix(self):
        """AwsDownload.get_product_bucket_name_and_prefix() must extract bucket & prefix from location"""

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
        "eodag.plugins.download.aws.AwsDownload.get_authenticated_objects",
        autospec=True,
    )
    @mock.patch("eodag.plugins.download.aws.requests.get", autospec=True)
    def test_plugins_download_aws_no_safe_build_no_flatten_top_dirs(
        self,
        mock_requests_get: mock.Mock,
        mock_get_authenticated_objects: mock.Mock,
        mock_get_chunk_dest_path: mock.Mock,
        mock_finalize_s2_safe_product: mock.Mock,
        mock_check_manifest_file_list: mock.Mock,
        mock_flatten_top_directories: mock.Mock,
        mock__get_unique_products: mock.Mock,
    ):
        """AwsDownload.download() must not call safe build methods if not needed"""

        plugin = self.get_download_plugin(self.product)
        self.product.properties["tileInfo"] = "http://example.com/tileInfo.json"

        # no SAFE build and no flatten_top_dirs
        plugin.config.products[self.product.product_type]["build_safe"] = False
        plugin.config.flatten_top_dirs = False

        plugin.download(self.product, output_dir=self.output_dir)

        mock_get_authenticated_objects.assert_called_once_with(
            plugin, "somebucket", "path/to/some", {}
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
        "eodag.plugins.download.aws.AwsDownload.get_authenticated_objects",
        autospec=True,
    )
    @mock.patch("eodag.plugins.download.aws.requests.get", autospec=True)
    def test_plugins_download_aws_no_safe_build_flatten_top_dirs(
        self,
        mock_requests_get: mock.Mock,
        mock_get_authenticated_objects: mock.Mock,
        mock_get_chunk_dest_path: mock.Mock,
        mock_finalize_s2_safe_product: mock.Mock,
        mock_check_manifest_file_list: mock.Mock,
        mock_flatten_top_directories: mock.Mock,
        mock__get_unique_products: mock.Mock,
    ):
        """AwsDownload.download() must not call safe build methods if not needed"""

        plugin = self.get_download_plugin(self.product)
        self.product.properties["tileInfo"] = "http://example.com/tileInfo.json"

        # no SAFE build and flatten_top_dirs
        plugin.config.products[self.product.product_type]["build_safe"] = False
        plugin.config.flatten_top_dirs = True

        plugin.download(self.product, output_dir=self.output_dir)

        mock_get_authenticated_objects.assert_called_once_with(
            plugin, "somebucket", "path/to/some", {}
        )
        self.assertEqual(mock_get_chunk_dest_path.call_count, 0)
        self.assertEqual(mock_finalize_s2_safe_product.call_count, 0)
        self.assertEqual(mock_check_manifest_file_list.call_count, 0)
        mock_flatten_top_directories.assert_called_once_with(
            os.path.join(self.output_dir, self.product.properties["title"]),
        )

    @mock.patch(
        "eodag.plugins.download.aws.open_s3_zipped_object",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload.get_authenticated_objects",
        autospec=True,
    )
    def test_plugins_download_aws_in_zip(
        self,
        mock_get_authenticated_objects: mock.Mock,
        mock_open_s3_zipped_object: mock.Mock,
    ):
        """AwsDownload.download() must handle files in zip"""

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
        plugin.s3_resource = mock.Mock()
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
            }
        )
        # no SAFE build and flatten_top_dirs
        plugin.config.products[self.product.product_type]["build_safe"] = False
        plugin.config.flatten_top_dirs = True

        path = plugin.download(self.product, output_dir=self.output_dir)

        self.assertEqual(mock_open_s3_zipped_object.call_count, 2)
        mock_open_s3_zipped_object.assert_called_with(
            "example", "path/to/foo.zip", plugin.s3_resource.meta.client, partial=False
        )
        self.assertTrue(
            os.path.isfile(
                os.path.join(path, "IMG_DATA/T31TDH_20180101T105441_B01.jp2")
            )
        )
        self.assertTrue(os.path.isfile(os.path.join(path, "MTD_TL.xml")))

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
        "eodag.plugins.download.aws.AwsDownload.get_authenticated_objects",
        autospec=True,
    )
    @mock.patch("eodag.plugins.download.aws.requests.get", autospec=True)
    def test_plugins_download_aws_safe_build(
        self,
        mock_requests_get,
        mock_get_authenticated_objects,
        mock_get_chunk_dest_path,
        mock_finalize_s2_safe_product,
        mock_check_manifest_file_list,
        mock_flatten_top_directories,
    ):
        """AwsDownload.download() must call safe build methods if needed"""

        plugin = self.get_download_plugin(self.product)
        self.product.properties["productInfo"] = "http://example.com/productInfo.json"
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
        plugin.config.products[self.product.product_type]["build_safe"] = True

        path = plugin.download(self.product, output_dir=self.output_dir)

        mock_requests_get.assert_called_once_with(
            self.product.properties["productInfo"],
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            verify=True,
        )
        self.assertEqual(mock_get_authenticated_objects.call_count, 2)
        mock_get_authenticated_objects.assert_any_call(
            plugin, "somebucket", "path/to/some", {}
        )
        mock_get_authenticated_objects.assert_any_call(plugin, "example", "here/is", {})
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
        "eodag.plugins.download.aws.AwsDownload.get_authenticated_objects",
        autospec=True,
    )
    @mock.patch("eodag.plugins.download.aws.requests.get", autospec=True)
    def test_plugins_download_aws_safe_build_assets(
        self,
        mock_requests_get,
        mock_get_authenticated_objects,
        mock_get_chunk_dest_path,
        mock_finalize_s2_safe_product,
        mock_check_manifest_file_list,
        mock_flatten_top_directories,
    ):
        """AwsDownload.download() must call safe build methods if needed"""

        plugin = self.get_download_plugin(self.product)
        self.product.properties["productInfo"] = "http://example.com/productInfo.json"
        self.product.properties["productPath"] = "http://example.com/productPath"
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
        plugin.config.products[self.product.product_type]["build_safe"] = True

        path = plugin.download(self.product, output_dir=self.output_dir)

        mock_requests_get.assert_called_once_with(
            self.product.properties["productInfo"],
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            verify=True,
        )
        mock_get_authenticated_objects.assert_called_once_with(
            plugin, "example", "", {}
        )
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
        plugin.download(self.product, output_dir=self.output_dir, asset="file1")
        # 2 additional calls
        self.assertEqual(5, mock_get_chunk_dest_path.call_count)

    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload.get_authenticated_objects",
        autospec=True,
    )
    def test_plugins_download_aws_no_matching_product_type(
        self,
        mock_get_authenticated_objects: mock.Mock,
    ):
        """AwsDownload.download() must fail if no product chunk is available"""

        plugin = self.get_download_plugin(self.product)
        self.product.properties["tileInfo"] = "http://example.com/tileInfo.json"

        # no SAFE build and flatten_top_dirs
        plugin.config.products[self.product.product_type]["build_safe"] = False
        plugin.config.flatten_top_dirs = True

        with self.assertRaises(NoMatchingProductType):
            plugin.download(self.product, outputs_prefix=self.output_dir)

    @mock.patch(
        "eodag.plugins.download.aws.AwsDownload.get_authenticated_objects",
        autospec=True,
    )
    def test_plugins_download_aws_get_rio_env(
        self,
        mock_get_authenticated_objects: mock.Mock,
    ):
        """AwsDownload.get_rio_env() must return rio env dict"""

        self.product.properties["downloadLink"] = "s3://some-bucket/some/prefix"

        plugin = self.get_download_plugin(self.product)
        auth_plugin = self.get_auth_plugin(plugin, self.product)

        # nothing needed
        rio_env_dict = plugin.get_rio_env(
            "some-bucket", "some/prefix", auth_plugin.authenticate()
        )
        self.assertDictEqual(rio_env_dict, {"aws_unsigned": True})

        # s3_endpoint
        plugin.config.s3_endpoint = "https://some.endpoint"
        rio_env_dict = plugin.get_rio_env(
            "some-bucket", "some/prefix", auth_plugin.authenticate()
        )
        self.assertDictEqual(
            rio_env_dict, {"aws_unsigned": True, "endpoint_url": "some.endpoint"}
        )

        # session initiated
        plugin.s3_session = mock.MagicMock()
        self.assertEqual(plugin.config.requester_pays, True)
        rio_env_dict = plugin.get_rio_env(
            "some-bucket", "some/prefix", auth_plugin.authenticate()
        )
        self.assertDictEqual(
            rio_env_dict,
            {
                "session": plugin.s3_session,
                "endpoint_url": "some.endpoint",
                "requester_pays": True,
            },
        )


class TestDownloadPluginS3Rest(BaseDownloadPluginTest):
    def setUp(self):
        super(TestDownloadPluginS3Rest, self).setUp()

        # manually add conf as this provider is not supported any more
        providers_config = self.plugins_manager.providers_config
        mundi_config_yaml = """
            mundi:
                products:
                    GENERIC_PRODUCT_TYPE:
                        productType: '{productType}'
                        collection: '{collection}'
                        instrument: '{instrument}'
                        processingLevel: '{processingLevel}'
                download:
                    type: S3RestDownload
                    base_uri: 'https://mundiwebservices.com/dp'
                    extract: true
                    auth_error_code: 401
                    bucket_path_level: 0
                    # order mechanism
                    order_enabled: true
                    order_method: 'POST'
                    order_headers:
                    accept: application/json
                    Content-Type: application/json
                    order_on_response:
                    metadata_mapping:
                        order_id: '{$.requestId#replace_str("Not Available","")}'
                        reorder_id: '{$.message.`sub(/.*requestId: ([a-z0-9]+)/, \\1)`#replace_str("Not Available","")}'
                        orderStatusLink: 'https://apis.mundiwebservices.com/odrapi/0.1/request/{order_id}{reorder_id}'
                    order_status_method: 'GET'
                    order_status_percent: status
                    order_status_success:
                    status: Success
                    order_status_on_success:
                    need_search: true
                    result_type: 'xml'
                    results_entry: '//ns:entry'
                    metadata_mapping:
                        downloadLink: 'ns:link[@rel="enclosure"]/@href'
                        storageStatus: 'DIAS:onlineStatus/text()'
        """
        mundi_config_dict = yaml.safe_load(mundi_config_yaml)
        override_config_from_mapping(providers_config, mundi_config_dict)
        self.plugins_manager = PluginManager(providers_config)

        self.product = EOProduct(
            "mundi",
            dict(
                geometry="POINT (0 0)",
                title="dummy_product",
                id="dummy",
                downloadLink="http://somewhere/some-bucket/path/to/the/product",
            ),
            productType="S2_MSI_L1C",
        )

    @mock.patch("eodag.plugins.download.http.HTTPDownload._order_status", autospec=True)
    @mock.patch("eodag.plugins.download.http.HTTPDownload._order", autospec=True)
    def test_plugins_download_s3rest_online(self, mock_order, mock_order_status):
        """S3RestDownload.download() must create outputfiles"""

        self.product.properties["storageStatus"] = ONLINE_STATUS

        plugin = self.get_download_plugin(self.product)
        self.product.register_downloader(plugin, None)

        @responses.activate(registry=responses.registries.OrderedRegistry)
        def run():
            # List bucket content
            responses.add(
                responses.GET,
                f"{plugin.config.base_uri}/some-bucket?prefix=path/to/the/product",
                status=200,
                body=(
                    b"<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
                    b"<ListBucketResult>"
                    b"<Contents><Key>0/1/2/3/4/5/path/to/some.file</Key><Size>2</Size></Contents>"
                    b"<Contents><Key>0/1/2/3/4/5/path/to/another.file</Key><Size>5</Size></Contents>"
                    b"</ListBucketResult>"
                ),
            )
            # 1st file download response
            responses.add(
                responses.GET,
                f"{plugin.config.base_uri}/some-bucket/0/1/2/3/4/5/path/to/some.file",
                status=200,
                content_type="application/octet-stream",
                body=b"something",
                auto_calculate_content_length=True,
            )
            # 2nd file download response
            responses.add(
                responses.GET,
                f"{plugin.config.base_uri}/some-bucket/0/1/2/3/4/5/path/to/another.file",
                status=200,
                content_type="application/octet-stream",
                body=b"something else",
                auto_calculate_content_length=True,
            )
            path = plugin.download(self.product, output_dir=self.output_dir)

            # there must have been 3 calls (list, 1st download, 2nd download)
            self.assertEqual(len(responses.calls), 3)

            self.assertEqual(path, os.path.join(self.output_dir, "product"))
            self.assertTrue(
                os.path.isfile(
                    os.path.join(self.output_dir, "product", "path", "to", "some.file")
                )
            )
            self.assertTrue(
                os.path.isfile(
                    os.path.join(
                        self.output_dir, "product", "path", "to", "another.file"
                    )
                )
            )

        run()

        mock_order.assert_not_called()
        mock_order_status.assert_not_called()

    @mock.patch("eodag.plugins.download.http.HTTPDownload._order_status", autospec=True)
    @mock.patch("eodag.plugins.download.http.HTTPDownload._order", autospec=True)
    def test_plugins_download_s3rest_offline(self, mock_order, mock_order_status):
        """S3RestDownload.download() must order offline products"""

        self.product.properties["storageStatus"] = OFFLINE_STATUS
        self.product.properties["orderLink"] = "https://some/order/api"
        self.product.properties["orderStatusLink"] = "https://some/order/status/api"

        valid_remote_location = self.product.location
        # unvalid location
        self.product.location = self.product.remote_location = "somewhere"

        plugin = self.get_download_plugin(self.product)
        self.product.register_downloader(plugin, None)

        # no retry
        @responses.activate(registry=responses.registries.OrderedRegistry)
        def run():
            # bucket list request
            responses.add(
                responses.GET,
                "https://mundiwebservices.com/dp/somewhere?prefix=",
                status=403,
            )
            with self.assertRaises(NotAvailableError):
                plugin.download(
                    self.product,
                    output_dir=self.output_dir,
                    wait=-1,
                    timeout=-1,
                )
            # there must have been 1 try
            self.assertEqual(len(responses.calls), 1)

        run()
        mock_order.assert_called_once_with(mock.ANY, self.product, auth=None)
        mock_order_status.assert_called_once_with(mock.ANY, self.product, auth=None)

        mock_order.reset_mock()
        mock_order_status.reset_mock()
        responses.calls.reset()

        # retry and success
        self.product.retries = 0

        def order_status_function(*args, **kwargs):
            if kwargs["product"].retries >= 1:
                kwargs["product"].properties["storageStatus"] = ONLINE_STATUS
                kwargs["product"].properties["downloadLink"] = kwargs[
                    "product"
                ].location = kwargs["product"].remote_location = valid_remote_location
            kwargs["product"].retries += 1

        mock_order_status.side_effect = order_status_function

        @responses.activate(registry=responses.registries.OrderedRegistry)
        def run():
            # 1st bucket list request
            responses.add(
                responses.GET,
                "https://mundiwebservices.com/dp/somewhere?prefix=",
                status=403,
            )
            # 2nd bucket list request
            responses.add(
                responses.GET,
                f"{plugin.config.base_uri}/some-bucket?prefix=path/to/the/product",
                status=200,
                body=(
                    b"<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
                    b"<ListBucketResult>"
                    b"<Contents><Key>0/1/2/3/4/5/path/to/some.file</Key><Size>2</Size></Contents>"
                    b"</ListBucketResult>"
                ),
            )
            # file download response
            responses.add(
                responses.GET,
                f"{plugin.config.base_uri}/some-bucket/0/1/2/3/4/5/path/to/some.file",
                status=200,
                content_type="application/octet-stream",
                body=b"something",
                auto_calculate_content_length=True,
            )
            path = plugin.download(
                self.product,
                output_dir=self.output_dir,
                wait=0.001 / 60,
                timeout=0.2 / 60,
            )
            # there must have been 2 tries and 1 download
            self.assertEqual(len(responses.calls), 3)

            self.assertEqual(path, os.path.join(self.output_dir, "product"))
            self.assertTrue(
                os.path.isfile(os.path.join(self.output_dir, "product", "some.file"))
            )

        run()
        mock_order.assert_called_once_with(mock.ANY, self.product, auth=None)
        self.assertEqual(mock_order_status.call_count, 2)


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
        "eodag.plugins.download.creodias_s3.CreodiasS3Download._get_authenticated_objects_from_auth_keys",
        autospec=True,
    )
    @mock.patch("eodag.plugins.download.aws.requests.get", autospec=True)
    def test_plugins_download_creodias_s3(
        self,
        mock_requests_get,
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
        product.location = product.remote_location = "a"
        assets = {
            "a1": {"title": "a1", "href": "s3://eodata/a/a1"},
            "a2": {"title": "a2", "href": "s3://eodata/a/a2"},
        }
        product.assets = assets
        plugin = self.get_download_plugin(product)
        product.properties["tileInfo"] = "http://example.com/tileInfo.json"
        # authenticated objects mock
        mock_get_authenticated_objects.return_value.keys.return_value = [
            "a1",
            "a2",
        ]
        mock_get_authenticated_objects.return_value.filter.side_effect = (
            lambda *x, **y: [mock.Mock(size=0, key=y["Prefix"])]
        )

        plugin.download(product, output_dir=self.output_dir, auth={})

        mock_get_authenticated_objects.assert_called_once_with(
            plugin, "eodata", "a", {}
        )
        self.assertEqual(mock_get_chunk_dest_path.call_count, 2)
        self.assertEqual(mock_finalize_s2_safe_product.call_count, 0)
        self.assertEqual(mock_check_manifest_file_list.call_count, 0)
        self.assertEqual(mock_flatten_top_directories.call_count, 1)

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
        "eodag.plugins.download.creodias_s3.CreodiasS3Download._get_authenticated_objects_from_auth_keys",
        autospec=True,
    )
    @mock.patch("eodag.plugins.download.aws.requests.get", autospec=True)
    def test_plugins_download_creodias_s3_without_assets(
        self,
        mock_requests_get,
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
                productIdentifier="/eodata/01/a.tar",
            ),
        )
        product.location = product.remote_location = "a"
        plugin = self.get_download_plugin(product)
        product.properties["tileInfo"] = "http://example.com/tileInfo.json"
        # authenticated objects mock
        mock_get_authenticated_objects.return_value.keys.return_value = ["a.tar"]
        mock_get_authenticated_objects.return_value.filter.side_effect = (
            lambda *x, **y: [mock.Mock(size=0, key=y["Prefix"])]
        )

        plugin.download(product, output_dir=self.output_dir, auth={})

        mock_get_authenticated_objects.assert_called_once_with(
            plugin, "eodata", "01", {}
        )
        self.assertEqual(mock_get_chunk_dest_path.call_count, 1)
        self.assertEqual(mock_finalize_s2_safe_product.call_count, 0)
        self.assertEqual(mock_check_manifest_file_list.call_count, 0)
        self.assertEqual(mock_flatten_top_directories.call_count, 1)
