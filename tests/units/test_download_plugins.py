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
import io
import os
import shutil
import stat
import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory, gettempdir
from unittest import mock

import responses
import yaml

from tests.context import (
    DEFAULT_STREAM_REQUESTS_TIMEOUT,
    HTTP_REQ_TIMEOUT,
    OFFLINE_STATUS,
    ONLINE_STATUS,
    USER_AGENT,
    EOProduct,
    NotAvailableError,
    PluginManager,
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

    def get_download_plugin(self, product):
        return self.plugins_manager.get_download_plugin(product.provider)

    def get_auth_plugin(self, provider):
        return self.plugins_manager.get_auth_plugin(provider)


class TestDownloadPluginBase(BaseDownloadPluginTest):
    def test_plugins_download_base_prepare_download_existing(self):
        """Download._prepare_download must detect if product destination already exists"""

        product_file = NamedTemporaryFile()
        self.product.location = path_to_uri(product_file.name)
        Path(product_file.name).touch()
        self.assertNotEqual(self.product.location, self.product.remote_location)

        plugin = self.get_download_plugin(self.product.provider)

        with self.assertLogs(level="INFO") as cm:
            fs_path, record_filename = plugin._prepare_download(self.product)
            self.assertEqual(fs_path, product_file.name)
            self.assertIsNone(record_filename)
            self.assertIn("Product already present on this platform", str(cm.output))

    def test_plugins_download_base_prepare_download_no_url(self):
        """Download._prepare_download must return None when no download url"""

        self.assertEqual(self.product.remote_location, "")

        plugin = self.get_download_plugin(self.product.provider)

        fs_path, record_filename = plugin._prepare_download(self.product)

        self.assertIsNone(fs_path)
        self.assertIsNone(record_filename)

    def test_plugins_download_base_prepare_download_collision_avoidance(self):
        """Download._prepare_download must use collision avoidance suffix"""

        self.product.properties["title"] = "needs sanitïze"
        self.product.properties["id"] = "alsô"
        self.product.location = self.product.remote_location = "somewhere"

        plugin = self.get_download_plugin(self.product.provider)

        fs_path, _ = plugin._prepare_download(self.product)

        self.assertEqual(fs_path, os.path.join(gettempdir(), "needs_sanitize-also.zip"))

    def test_plugins_download_base_prepare_download_dir_permission(self):
        """Download._prepare_download must check output directory permissions"""
        if os.name == "nt":
            self.skipTest("windows permissions too complex to set for this test")

        plugin = self.get_download_plugin(self.product.provider)
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
    @mock.patch("eodag.plugins.download.http.requests.Session.request", autospec=True)
    def test_plugins_download_http_ok(self, mock_requests_session_request):
        """HTTPDownload.download() must create an outputfile"""

        plugin = self.get_download_plugin(self.product.provider)
        self.product.location = self.product.remote_location = "http://somewhere"
        self.product.properties["id"] = "someproduct"

        path = plugin.download(self.product, outputs_prefix=self.output_dir)

        self.assertEqual(path, os.path.join(self.output_dir, "dummy_product"))
        self.assertTrue(os.path.isfile(path))

        mock_requests_session_request.assert_called_once()

    @mock.patch("eodag.plugins.download.http.requests.Session.request", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_ignore_assets(
        self, mock_requests_get, mock_requests_head, mock_requests_session
    ):
        """HTTPDownload.download() must ignore assets if configured to"""

        plugin = self.get_download_plugin(self.product.provider)
        self.product.location = (
            self.product.remote_location
        ) = "http://somewhere/dowload_from_location"
        self.product.properties["id"] = "someproduct"
        self.product.assets.clear()
        self.product.assets.update({"foo": {"href": "http://somewhere/download_asset"}})
        mock_requests_get.return_value.__enter__.return_value.iter_content.side_effect = lambda *x, **y: io.BytesIO(
            b"some content"
        )

        # download asset if ignore_assets = False
        plugin.config.ignore_assets = False
        path = plugin.download(self.product, outputs_prefix=self.output_dir)
        mock_requests_get.assert_called_once_with(
            self.product.assets["foo"]["href"],
            stream=True,
            auth=None,
            params=plugin.config.dl_url_params,
            headers=USER_AGENT,
            timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
        )
        mock_requests_session.assert_not_called()
        # re-enable product download
        self.product.location = self.product.remote_location
        shutil.rmtree(path)
        mock_requests_get.reset_mock()
        mock_requests_session.reset_mock()

        # download using remote_location if ignore_assets = True
        plugin.config.ignore_assets = True
        path = plugin.download(self.product, outputs_prefix=self.output_dir)
        mock_requests_get.assert_not_called()
        mock_requests_session.assert_called_once()
        # re-enable product download
        self.product.location = self.product.remote_location
        os.remove(path)
        mock_requests_get.reset_mock()
        mock_requests_session.reset_mock()

        # download asset if ignore_assets unset
        del plugin.config.ignore_assets
        plugin.download(self.product, outputs_prefix=self.output_dir)
        mock_requests_get.assert_called_once_with(
            self.product.assets["foo"]["href"],
            stream=True,
            auth=None,
            params=plugin.config.dl_url_params,
            headers=USER_AGENT,
            timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
        )
        mock_requests_session.assert_not_called()

    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_assets_filename_from_href(
        self, mock_requests_get, mock_requests_head
    ):
        """HTTPDownload.download() must create an outputfile"""

        plugin = self.get_download_plugin(self.product.provider)
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

        path = plugin.download(self.product, outputs_prefix=self.output_dir)

        self.assertEqual(path, os.path.join(self.output_dir, "dummy_product"))
        self.assertTrue(os.path.isdir(path))
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    self.output_dir, "dummy_product", "mal_for_matted", "something"
                )
            )
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
        )
        # Check if the HEAD request has been called once for size & filename request
        mock_requests_head.assert_called_once_with(
            self.product.assets["foo"]["href"],
            auth=None,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
        )

    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_assets_filename_from_get(
        self, mock_requests_get, mock_requests_head
    ):
        """HTTPDownload.download() must create an outputfile"""

        plugin = self.get_download_plugin(self.product.provider)
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
    def test_plugins_download_http_asset_filter(
        self, mock_requests_get, mock_requests_head
    ):
        """HTTPDownload.download() must create an outputfile"""

        plugin = self.get_download_plugin(self.product.provider)
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

        path = plugin.download(
            self.product, outputs_prefix=self.output_dir, asset="else.*"
        )

        self.assertEqual(path, os.path.join(self.output_dir, "dummy_product"))
        self.assertTrue(os.path.isdir(path))
        self.assertTrue(
            os.path.isfile(
                os.path.join(self.output_dir, "dummy_product", "somethingelse")
            )
        )
        self.assertEqual(2, mock_requests_get.call_count)
        self.product.location = self.product.remote_location = "http://elsewhere"
        plugin.download(self.product, outputs_prefix=self.output_dir)
        self.assertEqual(6, mock_requests_get.call_count)

    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    def test_plugins_download_http_assets_filename_from_head(
        self, mock_requests_get, mock_requests_head
    ):
        """HTTPDownload.download() must create an outputfile"""

        plugin = self.get_download_plugin(self.product.provider)
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

        plugin = self.get_download_plugin(self.product.provider)
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
            plugin.download(self.product, outputs_prefix=temp_dir)
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
            plugin.download(self.product, outputs_prefix=temp_dir)
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
            plugin.download(self.product, outputs_prefix=temp_dir)
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
            plugin.download(self.product, outputs_prefix=temp_dir)
        mock_progress_callback_reset.assert_called_once_with(mock.ANY, total=4 + 4)

    def test_plugins_download_http_one_local_asset(
        self,
    ):
        """HTTPDownload.download() must handle one local asset"""

        plugin = self.get_download_plugin(self.product.provider)
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

        path = plugin.download(self.product, outputs_prefix=self.output_dir)

        self.assertEqual(path, uri_to_path(self.product.assets["foo"]["href"]))
        # empty product download directory should have been removed
        self.assertFalse(Path(os.path.join(self.output_dir, "dummy_product")).exists())

    def test_plugins_download_http_several_local_assets(
        self,
    ):
        """HTTPDownload.download() must handle several local assets"""

        plugin = self.get_download_plugin(self.product.provider)
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

        path = plugin.download(self.product, outputs_prefix=self.output_dir)

        # assets common path
        self.assertEqual(
            os.path.normcase(path),
            os.path.normcase(os.path.abspath(os.path.join(os.sep, "somewhere"))),
        )
        # empty product download directory should have been removed
        self.assertFalse(Path(os.path.join(self.output_dir, "dummy_product")).exists())

    @mock.patch("eodag.plugins.download.http.requests.request", autospec=True)
    def test_plugins_download_http_order_get(self, mock_request):
        """HTTPDownload.orderDownload() must request using orderLink and GET protocol"""
        plugin = self.get_download_plugin(self.product.provider)
        self.product.properties["orderLink"] = "http://somewhere/order"
        self.product.properties["storageStatus"] = OFFLINE_STATUS

        auth_plugin = self.get_auth_plugin(self.product.provider)
        auth_plugin.config.credentials = {"username": "foo", "password": "bar"}
        auth = auth_plugin.authenticate()

        plugin.orderDownload(self.product, auth=auth)

        mock_request.assert_called_once_with(
            method="get",
            url=self.product.properties["orderLink"],
            auth=auth,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
        )

    @mock.patch("eodag.plugins.download.http.requests.request", autospec=True)
    def test_plugins_download_http_order_post(self, mock_request):
        """HTTPDownload.orderDownload() must request using orderLink and POST protocol"""
        plugin = self.get_download_plugin(self.product.provider)
        self.product.properties["storageStatus"] = OFFLINE_STATUS
        plugin.config.order_method = "POST"

        auth_plugin = self.get_auth_plugin(self.product.provider)
        auth_plugin.config.credentials = {"username": "foo", "password": "bar"}
        auth = auth_plugin.authenticate()

        # orderLink without query query args
        self.product.properties["orderLink"] = "http://somewhere/order"
        plugin.orderDownload(self.product, auth=auth)
        mock_request.assert_called_once_with(
            method="post",
            url=self.product.properties["orderLink"],
            auth=auth,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
        )
        # orderLink with query query args
        mock_request.reset_mock()
        self.product.properties["orderLink"] = "http://somewhere/order?foo=bar"
        plugin.orderDownload(self.product, auth=auth)
        mock_request.assert_called_once_with(
            method="post",
            url="http://somewhere/order",
            auth=auth,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            json={"foo": ["bar"]},
        )

    def test_plugins_download_http_order_status(self):
        """HTTPDownload.orderDownloadStatus() must request status using orderStatusLink"""
        plugin = self.get_download_plugin(self.product.provider)
        plugin.config.order_status_percent = "progress_percentage"
        plugin.config.order_status_error = {"that": "failed"}
        self.product.properties["orderStatusLink"] = "http://somewhere/order-status"

        auth_plugin = self.get_auth_plugin(self.product.provider)
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

            with self.assertLogs(level="INFO") as cm:
                plugin.orderDownloadStatus(self.product, auth=auth)
                self.assertEqual(
                    [
                        f"INFO:eodag.download.http:{self.product.properties['title']} order status: 50%",
                        'WARNING:eodag.download.http:{"progress_percentage": 50, "that": "failed"}',
                    ],
                    cm.output,
                )
            self.assertIn(
                list(USER_AGENT.items())[0], responses.calls[0].request.headers.items()
            )
            self.assertEqual(len(responses.calls), 1)

        run()

    def test_plugins_download_http_order_status_search_again(self):
        """HTTPDownload.orderDownloadStatus() must search again after success if needed"""
        plugin = self.get_download_plugin(self.product.provider)
        plugin.config.order_status_success = {"status": "great-success"}
        plugin.config.order_status_on_success = {
            "need_search": True,
            "result_type": "xml",
            "results_entry": "//entry",
            "metadata_mapping": {
                "downloadLink": "foo/text()",
            },
        }
        self.product.properties["orderStatusLink"] = "http://somewhere/order-status"
        self.product.properties["searchLink"] = "http://somewhere/search-gain"

        auth_plugin = self.get_auth_plugin(self.product.provider)
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
                "http://somewhere/search-gain",
                status=200,
                body=(
                    b"<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
                    b"<feed>"
                    b"<entry><foo>http://new-download-link</foo><bar>something else</bar></entry>"
                    b"</feed>"
                ),
            )

            plugin.orderDownloadStatus(self.product, auth=auth)

            self.assertEqual(
                self.product.properties["downloadLink"], "http://new-download-link"
            )
            self.assertEqual(len(responses.calls), 2)

        run()


class TestDownloadPluginHttpRetry(BaseDownloadPluginTest):
    def setUp(self):
        super(TestDownloadPluginHttpRetry, self).setUp()

        self.plugin = self.get_download_plugin(self.product.provider)
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
        self.product.location = (
            self.product.remote_location
        ) = "http://somebucket.somehost.com/path/to/some/product"

    def test_plugins_download_aws_get_bucket_prefix(self):
        """AwsDownload.get_product_bucket_name_and_prefix() must extract bucket & prefix from location"""

        plugin = self.get_download_plugin(self.product.provider)
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
        mock_requests_get,
        mock_get_authenticated_objects,
        mock_get_chunk_dest_path,
        mock_finalize_s2_safe_product,
        mock_check_manifest_file_list,
        mock_flatten_top_directories,
    ):
        """AwsDownload.download() must not call safe build methods if not needed"""

        plugin = self.get_download_plugin(self.product.provider)
        self.product.properties["tileInfo"] = "http://example.com/tileInfo.json"

        # no SAFE build and no flatten_top_dirs
        plugin.config.products[self.product.product_type]["build_safe"] = False
        plugin.config.flatten_top_dirs = False

        plugin.download(self.product, outputs_prefix=self.output_dir)

        mock_get_authenticated_objects.assert_called_once_with(
            plugin, "somebucket", "path/to/some", None
        )
        self.assertEqual(mock_get_chunk_dest_path.call_count, 0)
        self.assertEqual(mock_finalize_s2_safe_product.call_count, 0)
        self.assertEqual(mock_check_manifest_file_list.call_count, 0)
        self.assertEqual(mock_flatten_top_directories.call_count, 0)

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
        mock_requests_get,
        mock_get_authenticated_objects,
        mock_get_chunk_dest_path,
        mock_finalize_s2_safe_product,
        mock_check_manifest_file_list,
        mock_flatten_top_directories,
    ):
        """AwsDownload.download() must not call safe build methods if not needed"""

        plugin = self.get_download_plugin(self.product.provider)
        self.product.properties["tileInfo"] = "http://example.com/tileInfo.json"

        # no SAFE build and flatten_top_dirs
        plugin.config.products[self.product.product_type]["build_safe"] = False
        plugin.config.flatten_top_dirs = True

        plugin.download(self.product, outputs_prefix=self.output_dir)

        mock_get_authenticated_objects.assert_called_once_with(
            plugin, "somebucket", "path/to/some", None
        )
        self.assertEqual(mock_get_chunk_dest_path.call_count, 0)
        self.assertEqual(mock_finalize_s2_safe_product.call_count, 0)
        self.assertEqual(mock_check_manifest_file_list.call_count, 0)
        mock_flatten_top_directories.assert_called_once_with(
            os.path.join(self.output_dir, self.product.properties["title"]),
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

        plugin = self.get_download_plugin(self.product.provider)
        self.product.properties["tileInfo"] = "http://example.com/tileInfo.json"
        execpected_output = os.path.join(
            self.output_dir, self.product.properties["title"]
        )
        # fetch_metadata return
        mock_requests_get.return_value.json.return_value = {
            "title": "foo",
            "productPath": "s3://example/here/is/productPath",
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

        path = plugin.download(self.product, outputs_prefix=self.output_dir)

        mock_requests_get.assert_called_once_with(
            self.product.properties["tileInfo"],
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
        )
        self.assertEqual(mock_get_authenticated_objects.call_count, 2)
        mock_get_authenticated_objects.assert_any_call(
            plugin, "somebucket", "path/to/some", None
        )
        mock_get_authenticated_objects.assert_any_call(
            plugin, "example", "here/is", None
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

        plugin = self.get_download_plugin(self.product.provider)
        self.product.properties["tileInfo"] = "http://example.com/tileInfo.json"
        self.product.properties["tilePath"] = "http://example.com/tilePath"
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
            "productPath": "s3://example/here/is/productPath",
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

        path = plugin.download(self.product, outputs_prefix=self.output_dir)

        mock_requests_get.assert_called_once_with(
            self.product.properties["tileInfo"],
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
        )
        mock_get_authenticated_objects.assert_called_once_with(
            plugin, "example", "", None
        )
        self.assertEqual(mock_get_chunk_dest_path.call_count, 4)
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
        plugin.download(self.product, outputs_prefix=self.output_dir, asset="file1")
        # 3 additional calls
        self.assertEqual(7, mock_get_chunk_dest_path.call_count)


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

    @mock.patch(
        "eodag.plugins.download.http.HTTPDownload.orderDownloadStatus", autospec=True
    )
    @mock.patch("eodag.plugins.download.http.HTTPDownload.orderDownload", autospec=True)
    def test_plugins_download_s3rest_online(self, mock_order, mock_order_status):
        """S3RestDownload.download() must create outputfiles"""

        self.product.properties["storageStatus"] = ONLINE_STATUS

        plugin = self.get_download_plugin(self.product.provider)
        auth = self.get_auth_plugin(self.product.provider)
        self.product.register_downloader(plugin, auth)

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
            path = plugin.download(self.product, outputs_prefix=self.output_dir)

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

    @mock.patch(
        "eodag.plugins.download.http.HTTPDownload.orderDownloadStatus", autospec=True
    )
    @mock.patch("eodag.plugins.download.http.HTTPDownload.orderDownload", autospec=True)
    def test_plugins_download_s3rest_offline(self, mock_order, mock_order_status):
        """S3RestDownload.download() must order offline products"""

        self.product.properties["storageStatus"] = OFFLINE_STATUS
        self.product.properties["orderLink"] = "https://some/order/api"
        self.product.properties["orderStatusLink"] = "https://some/order/status/api"

        valid_remote_location = self.product.location
        # unvalid location
        self.product.location = self.product.remote_location = "somewhere"

        plugin = self.get_download_plugin(self.product.provider)
        auth = self.get_auth_plugin(self.product.provider)
        self.product.register_downloader(plugin, auth)

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
                    outputs_prefix=self.output_dir,
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
                outputs_prefix=self.output_dir,
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
