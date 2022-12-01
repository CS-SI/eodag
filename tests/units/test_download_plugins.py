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
import os
import shutil
import stat
import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory, gettempdir, mkdtemp
from unittest import mock

import responses

from tests.context import (
    OFFLINE_STATUS,
    EOProduct,
    NotAvailableError,
    PluginManager,
    load_default_config,
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
        self.output_dir = mkdtemp()

    def tearDown(self):
        super(BaseDownloadPluginTest, self).tearDown()
        if os.path.isdir(self.output_dir):
            shutil.rmtree(self.output_dir)

    def get_download_plugin(self, product):
        return self.plugins_manager.get_download_plugin(product)

    def get_auth_plugin(self, provider):
        return self.plugins_manager.get_auth_plugin(provider)


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
        self.product.properties["id"] = "alsô"
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
            fs_path, _ = plugin._prepare_download(
                self.product, outputs_prefix=outdir.name
            )
            self.assertIn("Unable to create records directory", str(cm.output))


class TestDownloadPluginHttp(BaseDownloadPluginTest):
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_ok(self, mock_requests_get):
        """HTTPDownload.download() must create an outputfile"""

        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"

        path = plugin.download(self.product, outputs_prefix=self.output_dir)

        self.assertEqual(path, os.path.join(self.output_dir, "dummy_product"))
        self.assertTrue(os.path.isfile(path))

    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_assets_filename_from_href(
        self, mock_requests_get, mock_requests_head
    ):
        """HTTPDownload.download() must create an outputfile"""

        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"
        self.product.assets = {
            "foo": {"href": "http://somewhere/something?foo=bar#baz"}
        }
        mock_requests_get.return_value.__enter__.return_value.headers = {
            "content-disposition": ""
        }
        mock_requests_head.return_value.headers = {"content-disposition": ""}

        path = plugin.download(self.product, outputs_prefix=self.output_dir)

        self.assertEqual(path, os.path.join(self.output_dir, "dummy_product"))
        self.assertTrue(os.path.isdir(path))
        self.assertTrue(
            os.path.isfile(os.path.join(self.output_dir, "dummy_product", "something"))
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
        self.product.assets = {"foo": {"href": "http://somewhere/something"}}
        mock_requests_get.return_value.__enter__.return_value.headers = {
            "content-disposition": '; filename = "somethingelse"'
        }
        mock_requests_head.return_value.headers = {"content-disposition": ""}

        path = plugin.download(self.product, outputs_prefix=self.output_dir)

        self.assertEqual(path, os.path.join(self.output_dir, "dummy_product"))
        self.assertTrue(os.path.isdir(path))
        self.assertTrue(
            os.path.isfile(
                os.path.join(self.output_dir, "dummy_product", "somethingelse")
            )
        )

    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_assets_filename_from_head(
        self, mock_requests_get, mock_requests_head
    ):
        """HTTPDownload.download() must create an outputfile"""

        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"
        self.product.assets = {"foo": {"href": "http://somewhere/something"}}
        mock_requests_get.return_value.__enter__.return_value.headers = {
            "content-disposition": '; filename = "somethingelse"'
        }
        mock_requests_head.return_value.headers = {
            "content-disposition": '; filename = "anotherthing"'
        }

        path = plugin.download(self.product, outputs_prefix=self.output_dir)

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
        self.product.assets = {
            "foo": {"href": "http://somewhere/a"},
            "bar": {"href": "http://somewhere/b"},
        }

        mock_requests_head.return_value.headers = {
            "Content-length": "1",
            "content-disposition": '; size = "2"',
        }
        mock_requests_get.return_value.__enter__.return_value.headers = {
            "Content-length": "3",
            "content-disposition": '; size = "4"',
        }

        # size from HEAD / Content-length
        with TemporaryDirectory() as temp_dir:
            plugin.download(self.product, outputs_prefix=temp_dir)
        mock_progress_callback_reset.assert_called_once_with(mock.ANY, total=1 + 1)

        # size from HEAD / content-disposition
        mock_requests_head.return_value.headers.pop("Content-length")
        mock_progress_callback_reset.reset_mock()
        self.product.location = "http://somewhere"
        self.product.assets = {
            "foo": {"href": "http://somewhere/a"},
            "bar": {"href": "http://somewhere/b"},
        }
        with TemporaryDirectory() as temp_dir:
            plugin.download(self.product, outputs_prefix=temp_dir)
        mock_progress_callback_reset.assert_called_once_with(mock.ANY, total=2 + 2)

        # size from GET / Content-length
        mock_requests_head.return_value.headers.pop("content-disposition")
        mock_progress_callback_reset.reset_mock()
        self.product.location = "http://somewhere"
        self.product.assets = {
            "foo": {"href": "http://somewhere/a"},
            "bar": {"href": "http://somewhere/b"},
        }
        with TemporaryDirectory() as temp_dir:
            plugin.download(self.product, outputs_prefix=temp_dir)
        mock_progress_callback_reset.assert_called_once_with(mock.ANY, total=3 + 3)

        # size from GET / content-disposition
        mock_requests_get.return_value.__enter__.return_value.headers.pop(
            "Content-length"
        )
        mock_progress_callback_reset.reset_mock()
        self.product.location = "http://somewhere"
        self.product.assets = {
            "foo": {"href": "http://somewhere/a"},
            "bar": {"href": "http://somewhere/b"},
        }
        with TemporaryDirectory() as temp_dir:
            plugin.download(self.product, outputs_prefix=temp_dir)
        mock_progress_callback_reset.assert_called_once_with(mock.ANY, total=4 + 4)

    def test_plugins_download_http_one_local_asset(
        self,
    ):
        """HTTPDownload.download() must handle one local asset"""

        plugin = self.get_download_plugin(self.product)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"
        self.product.assets = {
            "foo": {
                "href": path_to_uri(
                    os.path.abspath(os.path.join(os.sep, "somewhere", "something"))
                )
            }
        }

        path = plugin.download(self.product, outputs_prefix=self.output_dir)

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
        self.product.assets = {
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

        path = plugin.download(self.product, outputs_prefix=self.output_dir)

        # assets common path
        self.assertEqual(path, os.path.abspath(os.path.join(os.sep, "somewhere")))
        # empty product download directory should have been removed
        self.assertFalse(Path(os.path.join(self.output_dir, "dummy_product")).exists())


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
                    outputs_prefix=self.output_dir,
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
                    outputs_prefix=self.output_dir,
                    wait=0.1 / 60,
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
                    outputs_prefix=self.output_dir,
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
                outputs_prefix=self.output_dir,
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
                    outputs_prefix=self.output_dir,
                    wait=0.1 / 60,
                    timeout=0.001 / 60,
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
                    outputs_prefix=self.output_dir,
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
                    self.product, outputs_prefix=self.output_dir, wait=-1, timeout=-1
                )

            # there must have been only one try
            self.assertEqual(len(responses.calls), 1)

        run()


class TestDownloadPluginAws(BaseDownloadPluginTest):
    def setUp(self):
        super(TestDownloadPluginAws, self).setUp()
        self.product = EOProduct(
            "astraea_eod",
            dict(
                geometry="POINT (0 0)",
                title="dummy_product",
                id="dummy",
            ),
            productType="S2_MSI_L2A",
        )

    def test_plugins_download_aws_get_bucket_prefix(self):
        """AwsDownload.get_bucket_name_and_prefix() must extract bucket & prefix from location"""

        plugin = self.get_download_plugin(self.product)
        plugin.config.products["S2_MSI_L2A"]["default_bucket"] = "default_bucket"
        self.product.properties["id"] = "someproduct"

        self.product.location = (
            self.product.remote_location
        ) = "http://somebucket.somehost.com/path/to/some/product"
        bucket, prefix = plugin.get_bucket_name_and_prefix(self.product)
        self.assertEqual((bucket, prefix), ("somebucket", "path/to/some/product"))

        plugin.config.bucket_path_level = 1
        bucket, prefix = plugin.get_bucket_name_and_prefix(self.product)
        self.assertEqual((bucket, prefix), ("to", "some/product"))
        del plugin.config.bucket_path_level

        bucket, prefix = plugin.get_bucket_name_and_prefix(
            self.product, url="/somewhere/else"
        )
        self.assertEqual((bucket, prefix), ("default_bucket", "somewhere/else"))
