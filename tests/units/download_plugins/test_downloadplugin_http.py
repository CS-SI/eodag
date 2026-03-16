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
import json
import os
import zipfile
from tempfile import TemporaryDirectory
from typing import Optional

import requests
import responses

from eodag.api.product import Asset, EOProduct
from eodag.config import PluginConfig
from eodag.plugins.download import HTTPDownload, StreamResponse
from eodag.utils.exceptions import (
    DownloadError,
    MisconfiguredError,
    NotAvailableError,
    QuotaExceededError,
)
from tests.units.download_plugins.base import BaseDownloadPluginTest


class TestDownloadPluginHttp(BaseDownloadPluginTest):
    def setUp(self):
        super().setUp()
        self.tmp = TemporaryDirectory()
        self.output_dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()
        super().tearDown()

    def get_plugin_download(
        self, provider: str = "cop_database", config: Optional[dict] = None
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

        return HTTPDownload(
            provider=provider,
            config=PluginConfig.from_mapping(plugin_config_dict),
        )

    @responses.activate
    def test_download_plugin_download_zipfile_ok(self):

        tmp_dir = TemporaryDirectory()
        test_dir = tmp_dir.name
        output_dir = os.path.join(test_dir, "output")
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)

        # Fake local product / asset
        product = EOProduct(provider="cop_dataspace", properties={})
        product.register_plugin_manager(self.plugins_manager)
        asset = Asset(product=product, key="my_asset_name")
        asset.update({"title": "asset title", "href": "http://asset.location/"})
        product.assets.update({asset.key: asset})

        # Fake online file
        zip_file = os.path.join(test_dir, "archive.zip")
        self.create_zip_file(zip_file)
        stat = os.stat(zip_file)
        with open(zip_file, "rb") as fd:
            content = fd.read()
        hash_md5 = hashlib.md5(content).hexdigest()
        filesize = stat.st_size

        responses.add(
            responses.GET,
            "http://asset.location/",
            body=content,
            status=200,
            content_type="application/zip",
            auto_calculate_content_length=True,
            adding_headers={
                "Last-Modified": datetime.datetime.fromtimestamp(
                    stat.st_mtime
                ).strftime("%a, %d %b %Y %H:%M:%S GMT"),
                "Etag": hash_md5,
            },
        )

        # Basic download
        downloader = self.get_plugin_download(
            provider="cop_dataspace",
            config={
                "extract": False,
                "delete_archive": False,
                "max_workers": 4,
                "output_extension": ".zip",
                "output_dir": output_dir,
            },
        )

        # Has no cache
        path = downloader.download(asset, output_dir=self.output_dir)
        self.assertEqual(len(responses.calls), 1)
        self.assertTrue(os.path.isfile(path))
        self.assertTrue(zipfile.is_zipfile(path))

        # Check for asset update
        self.assertIn(
            asset.get("type"), ["application/zip", "application/x-zip-compressed"]
        )
        self.assertEqual(asset.get("file:size"), filesize)
        self.assertEqual(asset.get("file:checksum"), hash_md5)

        # Now has cache
        path = downloader.download(asset, output_dir=self.output_dir)
        self.assertEqual(len(responses.calls), 1)
        self.assertTrue(os.path.isfile(path))
        self.assertTrue(zipfile.is_zipfile(path))

        os.remove(path)

        # Stream download
        response: StreamResponse = downloader.download(
            asset, stream=True, output_dir=self.output_dir
        )
        stream_file = os.path.join(test_dir, "stream.zip")
        with open(stream_file, "wb") as fd:
            for chunk in response.content:
                fd.write(chunk)

        self.assertEqual(len(responses.calls), 2)
        self.assertTrue(os.path.isfile(stream_file))
        self.assertTrue(zipfile.is_zipfile(stream_file))
        os.remove(stream_file)

        # Stream download with cache
        response: StreamResponse = downloader.download(
            asset, stream=True, output_dir=self.output_dir
        )
        with open(stream_file, "wb") as fd:
            for chunk in response.content:
                fd.write(chunk)

        self.assertEqual(len(responses.calls), 2)
        self.assertTrue(os.path.isfile(stream_file))
        self.assertTrue(zipfile.is_zipfile(stream_file))
        os.remove(stream_file)

        tmp_dir.cleanup()

    def test_download_plugin_download_zipfile_404(self):

        tmp_dir = TemporaryDirectory()
        test_dir = tmp_dir.name

        # Fake local product / asset
        product = EOProduct(provider="cop_dataspace", properties={})
        product.register_plugin_manager(self.plugins_manager)
        asset = Asset(product=product, key="my_asset_name")
        asset.update({"title": "asset title", "href": "http://asset.location/"})
        product.assets.update({asset.key: asset})

        # Basic download
        downloader = self.get_plugin_download(
            provider="cop_dataspace",
            config={
                "extract": False,
                "delete_archive": False,
                "max_workers": 4,
                "output_extension": ".zip",
                "output_dir": test_dir,
            },
        )

        # Basic download
        try:
            _ = downloader.download(asset, output_dir=self.output_dir)
            self.fail("Should raise Download error")
        except DownloadError:
            pass
        except Exception as e:
            self.fail(e)

        # Stream download
        try:
            _ = downloader.download(asset, stream=True, output_dir=self.output_dir)
            self.fail("Should raise Download error")
        except DownloadError:
            pass
        except Exception as e:
            self.fail(e)

        tmp_dir.cleanup()

    @responses.activate
    def test_download_plugin_download(self):

        tmp_dir = TemporaryDirectory()
        test_dir = tmp_dir.name
        output_dir = os.path.join(test_dir, "output")
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)

        # Fake local product / asset
        product = EOProduct(provider="cop_dataspace", properties={})
        product.register_plugin_manager(self.plugins_manager)
        asset = Asset(product=product, key="my_asset_name")
        asset.update({"title": "asset title", "href": "http://asset.location/"})
        product.assets.update({asset.key: asset})

        # Fake online file
        json_file = os.path.join(test_dir, "manifest.json")
        with open(json_file, "w+") as fd:
            fd.write(json.dumps({"data": "ok"}))

        stat = os.stat(json_file)
        with open(json_file, "rb") as fd:
            content = fd.read()
        hash_md5 = hashlib.md5(content).hexdigest()
        filesize = stat.st_size

        responses.add(
            responses.GET,
            "http://asset.location/",
            body=content,
            status=200,
            content_type="application/json",
            auto_calculate_content_length=True,
            adding_headers={
                "Last-Modified": datetime.datetime.fromtimestamp(
                    stat.st_mtime
                ).strftime("%a, %d %b %Y %H:%M:%S GMT"),
                "Etag": hash_md5,
            },
        )

        # Basic download
        downloader = self.get_plugin_download(
            provider="cop_dataspace",
            config={
                "extract": False,
                "delete_archive": False,
                "max_workers": 4,
                "output_dir": output_dir,
            },
        )

        # Has no cache
        path = downloader.download(asset, output_dir=self.output_dir)
        self.assertEqual(len(responses.calls), 1)
        self.assertTrue(os.path.isfile(path))

        # Check for asset update
        self.assertEqual(asset.get("type"), "application/octet-stream")
        self.assertEqual(asset.get("file:size"), filesize)
        self.assertEqual(asset.get("file:checksum"), hash_md5)

        # Now has cache
        path = downloader.download(asset, output_dir=self.output_dir)
        self.assertEqual(len(responses.calls), 1)
        self.assertTrue(os.path.isfile(path))

        os.remove(path)

        # Stream download
        response: StreamResponse = downloader.download(
            asset, stream=True, output_dir=self.output_dir
        )
        stream_file = os.path.join(test_dir, "stream.json")
        with open(stream_file, "wb") as fd:
            for chunk in response.content:
                fd.write(chunk)

        self.assertEqual(len(responses.calls), 2)
        self.assertTrue(os.path.isfile(stream_file))
        os.remove(stream_file)

        # Stream download with cache
        response: StreamResponse = downloader.download(
            asset, stream=True, output_dir=self.output_dir
        )
        with open(stream_file, "wb") as fd:
            for chunk in response.content:
                fd.write(chunk)

        self.assertEqual(len(responses.calls), 2)
        self.assertTrue(os.path.isfile(stream_file))
        os.remove(stream_file)

        tmp_dir.cleanup()

    @responses.activate
    def test_download_plugin_download_404(self):

        # Fake local product / asset
        product = EOProduct(provider="cop_dataspace", properties={})
        product.register_plugin_manager(self.plugins_manager)
        asset = Asset(product=product, key="my_asset_name")
        asset.update({"title": "asset title", "href": "http://asset.location/"})
        product.assets.update({asset.key: asset})

        responses.add(
            responses.GET,
            "http://asset.location/",
            body=b"",
            status=404,
            content_type="application/octet-stream",
            auto_calculate_content_length=True,
        )

        # Basic download
        downloader = self.get_plugin_download(provider="cop_dataspace")
        try:
            downloader.download(asset, no_cache=True, output_dir=self.output_dir)
            self.fail("except DoxnloadError")
        except DownloadError:
            pass

    @responses.activate
    def test_download_plugin_download_422_gone(self):

        # Fake local product / asset
        product = EOProduct(provider="cop_dataspace", properties={})
        product.register_plugin_manager(self.plugins_manager)
        asset = Asset(product=product, key="my_asset_name")
        asset.update({"title": "asset title", "href": "http://asset.location/"})
        product.assets.update({asset.key: asset})

        responses.add(
            responses.GET,
            "http://asset.location/",
            status=422,
            content_type="text/html",
            body=b"<!doctype html><html><body>422 Gone</hr ></body></html>",
            auto_calculate_content_length=True,
        )

        # Basic download
        downloader = self.get_plugin_download(provider="cop_dataspace")
        try:
            downloader.download(asset, no_cache=True, output_dir=self.output_dir)
            self.fail("except NotAvailableError")
        except NotAvailableError:
            pass

    def test_download_plugins_download_misconfigured(self):
        """HTTPDownload.stream_download() must raise an error if misconfigured"""

        # Fake local product / asset
        product = EOProduct(provider="cop_dataspace", properties={})
        product.register_plugin_manager(self.plugins_manager)
        asset = Asset(product=product, key="my_asset_name")
        asset.update({"title": "asset title", "href": "http://asset.location/"})
        product.assets.update({asset.key: asset})

        plugin = self.get_plugin_download(provider="cop_dataspace")
        with self.assertRaises(MisconfiguredError):
            # Wrong auth instance
            wrong_auth = "not_an_auth_instance"
            plugin.download(asset, auth=wrong_auth, output_dir=self.output_dir)

    @responses.activate
    def test_plugins_download_http_assets_too_many_requests_error(self):
        """HTTPDownload.download() must handle a 429 (Too many requests) error"""
        product = EOProduct(provider="cop_dataspace", properties={})
        product.register_plugin_manager(self.plugins_manager)
        asset = Asset(product=product, key="my_asset_name")
        asset.update({"title": "asset title", "href": "http://asset.location/"})
        product.assets.update({asset.key: asset})

        plugin = self.get_plugin_download()

        responses.add(
            responses.GET,
            "http://asset.location/",
            status=429,
            content_type="text/html",
            body=b"<!doctype html><html><body>429 Quota Excedded</hr ></body></html>",
            auto_calculate_content_length=True,
        )
        with self.assertRaises(QuotaExceededError):
            plugin.download(asset, output_dir=self.output_dir)

    @responses.activate
    def test_downloed_plugins_download_202_retry(self):

        # Fake local product / asset
        product = EOProduct(provider="cop_dataspace", properties={})
        product.register_plugin_manager(self.plugins_manager)
        asset = Asset(product=product, key="my_asset_name")
        asset.update({"title": "asset title", "href": "http://asset.location/"})
        product.assets.update({asset.key: asset})

        # Fake online file
        json_file = os.path.join(self.output_dir, "manifest.json")
        with open(json_file, "w+") as fd:
            fd.write(json.dumps({"data": "ok"}))

        stat = os.stat(json_file)
        with open(json_file, "rb") as fd:
            content = fd.read()
        hash_md5 = hashlib.md5(content).hexdigest()
        filesize = stat.st_size

        responses.add(
            responses.GET,
            "http://asset.location/",
            body=content,
            status=202,
            auto_calculate_content_length=True,
        )
        responses.add(
            responses.GET,
            "http://asset.location/",
            body=content,
            status=200,
            content_type="application/json",
            auto_calculate_content_length=True,
            adding_headers={
                "Last-Modified": datetime.datetime.fromtimestamp(
                    stat.st_mtime
                ).strftime("%a, %d %b %Y %H:%M:%S GMT"),
                "Etag": hash_md5,
            },
        )

        # Basic download
        downloader = self.get_plugin_download(
            provider="cop_dataspace",
            config={
                "extract": False,
                "delete_archive": False,
                "max_workers": 4,
                "output_dir": self.output_dir,
            },
        )

        # Has no cache
        path = downloader.download(asset, wait=0.01, timeout=0.1)
        self.assertEqual(len(responses.calls), 2)
        self.assertTrue(os.path.isfile(path))

        # Check for asset update
        self.assertEqual(asset.get("type"), "application/octet-stream")
        self.assertEqual(asset.get("file:size"), filesize)
        self.assertEqual(asset.get("file:checksum"), hash_md5)

    @responses.activate
    def test_downloed_plugins_download_429(self):

        # Fake local product / asset
        product = EOProduct(provider="cop_dataspace", properties={})
        product.register_plugin_manager(self.plugins_manager)
        asset = Asset(product=product, key="my_asset_name")
        asset.update({"title": "asset title", "href": "http://asset.location/"})
        product.assets.update({asset.key: asset})

        responses.add(
            responses.GET,
            "http://asset.location/",
            status=429,
            adding_headers={"Retry-After": "1"},
        )

        # Basic download
        downloader = self.get_plugin_download(
            provider="cop_dataspace",
            config={
                "extract": False,
                "delete_archive": False,
                "max_workers": 4,
                "output_dir": self.output_dir,
            },
        )

        # Has no cache
        try:
            downloader.download(asset, wait=0.01, timeout=0.1)
            self.fail("Expect QuotaExceededError")
        except QuotaExceededError:
            pass
        self.assertEqual(len(responses.calls), 1)

    @responses.activate
    def test_downloed_plugins_download_timeout_retry(self):

        tmp_dir = TemporaryDirectory()
        test_dir = tmp_dir.name
        output_dir = os.path.join(test_dir, "output")
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)

        # Fake local product / asset
        product = EOProduct(provider="cop_dataspace", properties={})
        product.register_plugin_manager(self.plugins_manager)
        asset = Asset(product=product, key="my_asset_name")
        asset.update({"title": "asset title", "href": "http://asset.location/"})
        product.assets.update({asset.key: asset})

        # Fake online file
        json_file = os.path.join(test_dir, "manifest.json")
        with open(json_file, "w+") as fd:
            fd.write(json.dumps({"data": "ok"}))

        stat = os.stat(json_file)
        with open(json_file, "rb") as fd:
            content = fd.read()
        hash_md5 = hashlib.md5(content).hexdigest()
        filesize = stat.st_size

        responses.add(
            responses.GET,
            "http://asset.location/",
            body=requests.exceptions.Timeout(),
        )
        responses.add(
            responses.GET,
            "http://asset.location/",
            body=content,
            status=200,
            content_type="application/json",
            auto_calculate_content_length=True,
            adding_headers={
                "Last-Modified": datetime.datetime.fromtimestamp(
                    stat.st_mtime
                ).strftime("%a, %d %b %Y %H:%M:%S GMT"),
                "Etag": hash_md5,
            },
        )

        # Basic download
        downloader = self.get_plugin_download(
            provider="cop_dataspace",
            config={
                "extract": False,
                "delete_archive": False,
                "max_workers": 4,
                "output_dir": output_dir,
            },
        )

        # Has no cache
        path = downloader.download(asset, wait=0.01, timeout=0.1)
        self.assertEqual(len(responses.calls), 2)
        self.assertTrue(os.path.isfile(path))

        # Check for asset update
        self.assertEqual(asset.get("type"), "application/octet-stream")
        self.assertEqual(asset.get("file:size"), filesize)
        self.assertEqual(asset.get("file:checksum"), hash_md5)

        tmp_dir.cleanup()

    @responses.activate
    def test_plugins_download_http_order_download_cop_ads(self):

        tmp_dir = TemporaryDirectory()
        test_dir = tmp_dir.name
        output_dir = os.path.join(test_dir, "output")
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)

        # Fake local product / asset
        product = EOProduct(provider="cop_ads", properties={})
        product.register_plugin_manager(self.plugins_manager)
        asset = Asset(product=product, key="my_asset_name")
        asset.update(
            {
                "title": "asset title",
                "type": "application/json",
                "order_link": "http://asset.order.location/request",
            }
        )
        product.assets.update({asset.key: asset})

        # Fake online file
        json_file = os.path.join(test_dir, "manifest.json")
        with open(json_file, "w+") as fd:
            fd.write(json.dumps({"data": "ok"}))

        stat = os.stat(json_file)
        with open(json_file, "rb") as fd:
            content = fd.read()
        hash_md5 = hashlib.md5(content).hexdigest()

        # Order request sequence
        responses.add(
            responses.POST,
            "http://asset.order.location/request",
            status=200,
            content_type="application/json",
            body=b'{"status": "accepted", "jobID": "request-id"}',
            auto_calculate_content_length=True,
        )
        responses.add(
            responses.GET,
            "http://asset.order.location/request-id?request=true",
            status=200,
            content_type="application/json",
            body=b'{"status": "running", "jobID": "request-id"}',
            auto_calculate_content_length=True,
        )
        responses.add(
            responses.GET,
            "http://asset.order.location/request-id?request=true",
            status=200,
            content_type="application/json",
            body=(b'{"status": "successful", "jobID": "request-id"}'),
            auto_calculate_content_length=True,
        )
        responses.add(
            responses.GET,
            "http://asset.order.location/request-id/results",
            status=200,
            content_type="application/json",
            body=(b'{"asset": {"value": {"href": "http://asset.location/"}}}'),
            auto_calculate_content_length=True,
        )

        # Download request
        responses.add(
            responses.GET,
            "http://asset.location/",
            status=200,
            content_type="application/octet-stream",
            adding_headers={
                "Last-Modified": datetime.datetime.fromtimestamp(
                    stat.st_mtime
                ).strftime("%a, %d %b %Y %H:%M:%S GMT"),
                "Etag": hash_md5,
            },
            body=content,
            auto_calculate_content_length=True,
        )

        # Should not try order if order_enabled is False
        downloader = self.get_plugin_download(
            provider="cop_dataspace",
            config={
                "extract": False,
                "delete_archive": False,
                "order_enabled": False,
                "max_workers": 4,
                "output_dir": output_dir,
            },
        )
        try:
            _ = downloader.download(asset, no_cache=True)
            self.fail("Except NotAvailableError")
        except NotAvailableError:
            pass

        # Basic download
        downloader = self.get_plugin_download(
            provider="cop_ads",
            config={
                "type": "HTTPDownload",
                "extract": False,
                "delete_archive": False,
                "order_enabled": True,
                "max_workers": 4,
                "output_dir": output_dir,
                "timeout": 30,
                "ssl_verify": True,
                "auth_error_code": 401,
                "order_enabled": True,
                "order_method": "POST",
                "order_on_response": {
                    "metadata_mapping": {
                        "eodag:order_id": "$.json.jobID",
                        "eodag:status_link": "http://asset.order.location/"
                        + "{"
                        + "eodag:order_id"
                        + "}"
                        + "?request=true",
                        "eodag:search_link": "http://asset.order.location/"
                        + "{"
                        + "eodag:order_id"
                        + "}"
                        + "/results",
                    }
                },
                "order_status": {
                    "request": {"method": "GET"},
                    "metadata_mapping": {
                        "eodag:order_status": "$.json.status",
                        "order:date": "$.json.created",
                        "created": "$.json.created",
                        "published": "$.json.finished",
                        "updated": "$.json.updated",
                        "ecmwf:dataset": "$.json.processID",
                        "eodag:request_params": "$.json.metadata.request.ids",
                    },
                    "error": {"eodag:order_status": "failed"},
                    "success": {"eodag:order_status": "successful"},
                    "on_success": {
                        "need_search": True,
                        "metadata_mapping": {"href": "$.json.asset.value.href"},
                    },
                },
            },
        )
        path = downloader.download(asset, wait=0.01, timeout=0.1, no_cache=True)

        self.assertTrue(path.endswith("my_asset_name.json"))
        self.assertTrue(os.path.isfile(path))
        data = ""
        with open(path) as fd:
            data = fd.read()
        self.assertEqual(data, '{"data": "ok"}')

        self.assertEqual(asset.get("href"), "http://asset.location/")
        self.assertEqual(asset.get("eodag:order_id"), "request-id")
        self.assertEqual(
            asset.get("eodag:status_link"),
            "http://asset.order.location/request-id?request=true",
        )
        self.assertEqual(
            asset.get("eodag:search_link"),
            "http://asset.order.location/request-id/results",
        )
        self.assertEqual(asset.get("eodag:order_status"), "successful")
        self.assertEqual(asset.get("file:size"), 14)
        self.assertEqual(asset.get("file:checksum"), "f3d63ef7a6fe86f7bf7008afefd20e19")

    @responses.activate
    def test_plugins_download_http_order_download_cop_ads_request_500(self):

        # Fake local product / asset
        product = EOProduct(provider="cop_ads", properties={})
        product.register_plugin_manager(self.plugins_manager)
        asset = Asset(product=product, key="my_asset_name")
        asset.update(
            {
                "title": "asset title",
                "type": "application/json",
                "order_link": "http://asset.order.location/request",
            }
        )
        product.assets.update({asset.key: asset})

        # Order request sequence
        responses.add(
            responses.POST,
            "http://asset.order.location/request",
            status=500,
            content_type="application/octet-stream",
            body=b"",
            auto_calculate_content_length=True,
        )

        # Basic download
        downloader = self.get_plugin_download(
            provider="cop_ads",
            config={
                "type": "HTTPDownload",
                "extract": False,
                "delete_archive": False,
                "order_enabled": True,
                "max_workers": 4,
                "timeout": 30,
                "ssl_verify": True,
                "auth_error_code": 401,
                "order_enabled": True,
                "order_method": "POST",
                "order_on_response": {
                    "metadata_mapping": {
                        "eodag:order_id": "$.json.jobID",
                        "eodag:status_link": "http://asset.order.location/"
                        + "{"
                        + "eodag:order_id"
                        + "}"
                        + "?request=true",
                        "eodag:search_link": "http://asset.order.location/"
                        + "{"
                        + "eodag:order_id"
                        + "}"
                        + "/results",
                    }
                },
                "order_status": {
                    "request": {"method": "GET"},
                    "metadata_mapping": {
                        "eodag:order_status": "$.json.status",
                        "order:date": "$.json.created",
                        "created": "$.json.created",
                        "published": "$.json.finished",
                        "updated": "$.json.updated",
                        "ecmwf:dataset": "$.json.processID",
                        "eodag:request_params": "$.json.metadata.request.ids",
                    },
                    "error": {"eodag:order_status": "failed"},
                    "success": {"eodag:order_status": "successful"},
                    "on_success": {
                        "need_search": True,
                        "metadata_mapping": {"href": "$.json.asset.value.href"},
                    },
                },
            },
        )
        try:
            _ = downloader.download(asset, wait=0.01, timeout=0.1, no_cache=True)
            self.fail("except DownloadError")
        except DownloadError:
            pass

    @responses.activate
    def test_plugins_download_http_order_download_cop_ads_job_failed(self):

        # Fake local product / asset
        product = EOProduct(provider="cop_ads", properties={})
        product.register_plugin_manager(self.plugins_manager)
        asset = Asset(product=product, key="my_asset_name")
        asset.update(
            {
                "title": "asset title",
                "type": "application/json",
                "order_link": "http://asset.order.location/request",
            }
        )
        product.assets.update({asset.key: asset})

        # Order request sequence
        responses.add(
            responses.POST,
            "http://asset.order.location/request",
            status=200,
            content_type="application/json",
            body=b'{"status": "accepted", "jobID": "request-id"}',
            auto_calculate_content_length=True,
        )
        responses.add(
            responses.GET,
            "http://asset.order.location/request-id?request=true",
            status=200,
            content_type="application/json",
            body=b'{"status": "running", "jobID": "request-id"}',
            auto_calculate_content_length=True,
        )
        responses.add(
            responses.GET,
            "http://asset.order.location/request-id?request=true",
            status=422,
            content_type="application/json",
            body=(b'{"status": "failed", "jobID": "request-id"}'),
            auto_calculate_content_length=True,
        )

        # Should not try order if order_enabled is False
        downloader = self.get_plugin_download(
            provider="cop_dataspace",
            config={
                "extract": False,
                "delete_archive": False,
                "order_enabled": False,
                "max_workers": 4,
            },
        )
        try:
            _ = downloader.download(asset, no_cache=True)
            self.fail("Except NotAvailableError")
        except NotAvailableError:
            pass

        # Basic download
        downloader = self.get_plugin_download(
            provider="cop_ads",
            config={
                "type": "HTTPDownload",
                "extract": False,
                "delete_archive": False,
                "order_enabled": True,
                "max_workers": 4,
                "timeout": 30,
                "ssl_verify": True,
                "auth_error_code": 401,
                "order_enabled": True,
                "order_method": "POST",
                "order_on_response": {
                    "metadata_mapping": {
                        "eodag:order_id": "$.json.jobID",
                        "eodag:status_link": "http://asset.order.location/"
                        + "{"
                        + "eodag:order_id"
                        + "}"
                        + "?request=true",
                        "eodag:search_link": "http://asset.order.location/"
                        + "{"
                        + "eodag:order_id"
                        + "}"
                        + "/results",
                    }
                },
                "order_status": {
                    "request": {"method": "GET"},
                    "metadata_mapping": {
                        "eodag:order_status": "$.json.status",
                        "order:date": "$.json.created",
                        "created": "$.json.created",
                        "published": "$.json.finished",
                        "updated": "$.json.updated",
                        "ecmwf:dataset": "$.json.processID",
                        "eodag:request_params": "$.json.metadata.request.ids",
                    },
                    "error": {"eodag:order_status": "failed"},
                    "success": {"eodag:order_status": "successful"},
                    "on_success": {
                        "need_search": True,
                        "metadata_mapping": {"href": "$.json.asset.value.href"},
                    },
                },
            },
        )

        try:
            _ = downloader.download(asset, wait=0.01, timeout=0.1, no_cache=True)
            self.fail("except Download error")
        except DownloadError:
            pass

    @responses.activate
    def test_plugins_download_http_order_download_cop_ads_timeout(self):

        # Fake local product / asset
        product = EOProduct(provider="cop_ads", properties={})
        product.register_plugin_manager(self.plugins_manager)
        asset = Asset(product=product, key="my_asset_name")
        asset.update(
            {
                "title": "asset title",
                "type": "application/json",
                "order_link": "http://asset.order.location/request",
            }
        )
        product.assets.update({asset.key: asset})

        # Order request sequence
        responses.add(
            responses.POST,
            "http://asset.order.location/request",
            status=200,
            content_type="application/json",
            body=b'{"status": "accepted", "jobID": "request-id"}',
            auto_calculate_content_length=True,
        )
        responses.add(
            responses.GET,
            "http://asset.order.location/request-id?request=true",
            status=200,
            content_type="application/json",
            body=b'{"status": "running", "jobID": "request-id"}',
            auto_calculate_content_length=True,
        )
        responses.add(
            responses.GET,
            "http://asset.order.location/request-id?request=true",
            status=200,
            content_type="application/json",
            body=b'{"status": "running", "jobID": "request-id"}',
            auto_calculate_content_length=True,
        )
        responses.add(
            responses.GET,
            "http://asset.order.location/request-id?request=true",
            status=200,
            content_type="application/json",
            body=b'{"status": "running", "jobID": "request-id"}',
            auto_calculate_content_length=True,
        )

        # Should not try order if order_enabled is False
        downloader = self.get_plugin_download(
            provider="cop_dataspace",
            config={
                "extract": False,
                "delete_archive": False,
                "order_enabled": False,
                "max_workers": 4,
            },
        )
        try:
            _ = downloader.download(asset, no_cache=True)
            self.fail("Except NotAvailableError")
        except NotAvailableError:
            pass

        # Basic download
        downloader = self.get_plugin_download(
            provider="cop_ads",
            config={
                "type": "HTTPDownload",
                "extract": False,
                "delete_archive": False,
                "order_enabled": True,
                "max_workers": 4,
                "timeout": 30,
                "ssl_verify": True,
                "auth_error_code": 401,
                "order_enabled": True,
                "order_method": "POST",
                "order_on_response": {
                    "metadata_mapping": {
                        "eodag:order_id": "$.json.jobID",
                        "eodag:status_link": "http://asset.order.location/"
                        + "{"
                        + "eodag:order_id"
                        + "}"
                        + "?request=true",
                        "eodag:search_link": "http://asset.order.location/"
                        + "{"
                        + "eodag:order_id"
                        + "}"
                        + "/results",
                    }
                },
                "order_status": {
                    "request": {"method": "GET"},
                    "metadata_mapping": {
                        "eodag:order_status": "$.json.status",
                        "order:date": "$.json.created",
                        "created": "$.json.created",
                        "published": "$.json.finished",
                        "updated": "$.json.updated",
                        "ecmwf:dataset": "$.json.processID",
                        "eodag:request_params": "$.json.metadata.request.ids",
                    },
                    "error": {"eodag:order_status": "failed"},
                    "success": {"eodag:order_status": "successful"},
                    "on_success": {
                        "need_search": True,
                        "metadata_mapping": {"href": "$.json.asset.value.href"},
                    },
                },
            },
        )

        try:
            _ = downloader.download(asset, wait=0.1, timeout=0.3, no_cache=True)
            self.fail("except NotAvailableError")
        except NotAvailableError:
            pass

    @responses.activate
    def test_plugins_download_http_order_download_cop_ads_fail_retreive(self):

        # Fake local product / asset
        product = EOProduct(provider="cop_ads", properties={})
        product.register_plugin_manager(self.plugins_manager)
        asset = Asset(product=product, key="my_asset_name")
        asset.update(
            {
                "title": "asset title",
                "type": "application/json",
                "order_link": "http://asset.order.location/request",
            }
        )
        product.assets.update({asset.key: asset})

        # Order request sequence
        responses.add(
            responses.POST,
            "http://asset.order.location/request",
            status=200,
            content_type="application/json",
            body=b'{"status": "accepted", "jobID": "request-id"}',
            auto_calculate_content_length=True,
        )
        responses.add(
            responses.GET,
            "http://asset.order.location/request-id?request=true",
            status=200,
            content_type="application/json",
            body=b'{"status": "running", "jobID": "request-id"}',
            auto_calculate_content_length=True,
        )
        responses.add(
            responses.GET,
            "http://asset.order.location/request-id?request=true",
            status=200,
            content_type="application/json",
            body=(b'{"status": "successful", "jobID": "request-id"}'),
            auto_calculate_content_length=True,
        )
        responses.add(
            responses.GET,
            "http://asset.order.location/request-id/results",
            status=410,
            content_type="application/octet-stream",
            body=(b""),
            auto_calculate_content_length=True,
        )

        # Basic download
        downloader = self.get_plugin_download(
            provider="cop_ads",
            config={
                "type": "HTTPDownload",
                "extract": False,
                "delete_archive": False,
                "order_enabled": True,
                "max_workers": 4,
                "timeout": 30,
                "ssl_verify": True,
                "auth_error_code": 401,
                "order_enabled": True,
                "order_method": "POST",
                "order_on_response": {
                    "metadata_mapping": {
                        "eodag:order_id": "$.json.jobID",
                        "eodag:status_link": "http://asset.order.location/"
                        + "{"
                        + "eodag:order_id"
                        + "}"
                        + "?request=true",
                        "eodag:search_link": "http://asset.order.location/"
                        + "{"
                        + "eodag:order_id"
                        + "}"
                        + "/results",
                    }
                },
                "order_status": {
                    "request": {"method": "GET"},
                    "metadata_mapping": {
                        "eodag:order_status": "$.json.status",
                        "order:date": "$.json.created",
                        "created": "$.json.created",
                        "published": "$.json.finished",
                        "updated": "$.json.updated",
                        "ecmwf:dataset": "$.json.processID",
                        "eodag:request_params": "$.json.metadata.request.ids",
                    },
                    "error": {"eodag:order_status": "failed"},
                    "success": {"eodag:order_status": "successful"},
                    "on_success": {
                        "need_search": True,
                        "metadata_mapping": {"href": "$.json.asset.value.href"},
                    },
                },
            },
        )

        try:
            _ = downloader.download(asset, wait=0.01, timeout=0.1, no_cache=True)
            self.fail("except DownloadError")
        except DownloadError:
            pass
