# -*- coding: utf-8 -*-
# Copyright 2026, CS GROUP - France, https://www.csgroup.eu/
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
import tempfile
import unittest
import warnings

from tests.context import (
    OFFLINE_STATUS,
    ONLINE_STATUS,
    Asset,
    AssetsDict,
    EOProduct,
    mock,
    path_to_uri,
)


class CustomAsset(Asset):
    pass


class CustomAssetsDict(AssetsDict):
    def _make_asset(self, key, value):
        return CustomAsset(self.product, key, value)


class HookedAssetsDict(AssetsDict):
    def __init__(self, product):
        self.setitem_keys = []
        super().__init__(product)

    def __setitem__(self, key, value):
        self.setitem_keys.append(key)
        super().__setitem__(key, value)


class TestAssetsDict(unittest.TestCase):
    @mock.patch.object(AssetsDict, "sort")
    def test_update_and_setitem_use_asset_factory_override(self, mock_sort):
        """Use the overridden asset factory and sort assets after updates."""
        assets = CustomAssetsDict(object())

        assets.update(
            {
                "z": {"href": "z"},
                "a": {"href": "a"},
            }
        )
        assets["m"] = {"href": "m"}

        mock_sort.assert_called()

        self.assertTrue(
            all(isinstance(asset, CustomAsset) for asset in assets.values())
        )

    def test_update_preserves_overridden_setitem(self):
        """Use an overridden __setitem__ when updating a subclass."""
        assets = HookedAssetsDict(object())

        assets.update({"z": {"href": "z"}, "a": {"href": "a"}})

        self.assertEqual(assets.setitem_keys, ["z", "a"])

    def test_update_and_setitem_sort_assets_and_remove_private_fields(self):
        """Sort assets and remove private fields after updates."""
        assets = AssetsDict(object())

        assets.update(
            {
                "z": {"href": "z", "type": "application/zip", "_internal": "remove"},
                "a": {"href": "a", "type": "application/json", "_internal": "remove"},
            }
        )
        assets["m"] = {"href": "m", "type": "application/zip", "_internal": "remove"}

        self.assertEqual(list(assets), ["a", "m", "z"])
        self.assertDictEqual(
            {key: dict(asset) for key, asset in assets.items()},
            {
                "a": {"href": "a", "title": "a", "type": "application/json"},
                "m": {"href": "m", "title": "m", "type": "application/zip"},
                "z": {"href": "z", "title": "z", "type": "application/zip"},
            },
        )

    def test_remove_private_fields_from_technical_assets(self):
        """Remove private fields from technical assets while sorting them first."""
        assets = AssetsDict(object())

        assets.update(
            {
                "thumbnail": {"href": "thumbnail", "_internal": "remove"},
                "download_link": {"href": "download", "_internal": "remove"},
                "quicklook": {"href": "quicklook", "_internal": "remove"},
            }
        )

        self.assertEqual(list(assets), ["download_link", "quicklook", "thumbnail"])
        self.assertTrue(all("_internal" not in asset for asset in assets.values()))


class TestAssetLocationAndOrder(unittest.TestCase):
    def setUp(self):
        self.product = EOProduct("foo", {"id": "bar", "geometry": "POINT (0 0)"})
        self.product.downloader = mock.Mock()
        self.product.downloader_auth = mock.Mock()

    def test_asset_locations_from_stac_fields(self):
        """Asset locations must be read from and written to href and file:local_path"""
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        local_path = os.path.join(temp_dir.name, "foo")
        self.product.assets["foo"] = {"href": "http://somewhere/foo"}
        asset = self.product.assets["foo"]
        self.assertEqual(asset.remote_location, "http://somewhere/foo")
        self.assertEqual(asset.location, "http://somewhere/foo")

        asset.location = path_to_uri(local_path)
        self.assertEqual(asset["file:local_path"], local_path)
        self.assertEqual(asset.location, path_to_uri(local_path))
        self.assertEqual(asset.remote_location, "http://somewhere/foo")

        asset.remote_location = "http://elsewhere/foo"
        self.assertEqual(asset["href"], "http://elsewhere/foo")

    def test_product_locations_proxy_download_link_asset(self):
        """EOProduct locations must be proxied to the download_link asset"""
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        local_path = os.path.join(temp_dir.name, "dl")
        other_path = os.path.join(temp_dir.name, "other")

        with self.assertWarnsRegex(DeprecationWarning, "EOProduct.location"):
            self.assertIsNone(self.product.location)
        with self.assertWarnsRegex(DeprecationWarning, "EOProduct.remote_location"):
            self.assertIsNone(self.product.remote_location)
        self.product.assets["download_link"] = {"href": "http://somewhere/dl"}
        with self.assertWarnsRegex(DeprecationWarning, "EOProduct.remote_location"):
            self.assertEqual(self.product.remote_location, "http://somewhere/dl")
        with self.assertWarnsRegex(DeprecationWarning, "EOProduct.location"):
            self.assertEqual(self.product.location, "http://somewhere/dl")

        with self.assertWarnsRegex(DeprecationWarning, "EOProduct.remote_location"):
            self.product.remote_location = "http://elsewhere/dl"
        self.assertEqual(
            self.product.assets["download_link"]["href"], "http://elsewhere/dl"
        )

        self.product.assets["download_link"]["file:local_path"] = local_path
        with self.assertWarnsRegex(DeprecationWarning, "EOProduct.location"):
            self.assertEqual(self.product.location, path_to_uri(local_path))

        with self.assertWarnsRegex(DeprecationWarning, "EOProduct.location"):
            self.product.location = path_to_uri(other_path)
        self.assertEqual(
            self.product.assets["download_link"]["file:local_path"], other_path
        )
        with self.assertWarnsRegex(DeprecationWarning, "EOProduct.location"):
            self.assertEqual(self.product.location, path_to_uri(other_path))
        with self.assertWarnsRegex(DeprecationWarning, "EOProduct.remote_location"):
            self.assertEqual(self.product.remote_location, "http://elsewhere/dl")
        with self.assertWarnsRegex(DeprecationWarning, "EOProduct.location"):
            self.product.location = "http://elsewhere/new"
        self.assertNotIn("file:local_path", self.product.assets["download_link"])
        self.assertEqual(
            self.product.assets["download_link"]["href"], "http://elsewhere/new"
        )
        self.assertNotIn("_location", vars(self.product))

    def test_product_location_setters_create_asset(self):
        """Deprecated setters create a download_link asset when one is missing."""
        with self.assertWarnsRegex(DeprecationWarning, "EOProduct.location"):
            self.product.location = path_to_uri("/tmp/local-product")
        self.assertEqual(
            self.product.assets["download_link"]["file:local_path"],
            "/tmp/local-product",
        )
        self.product.assets.clear()
        with self.assertWarnsRegex(DeprecationWarning, "EOProduct.remote_location"):
            self.product.remote_location = "https://example.test/product"
        self.assertEqual(
            self.product.assets["download_link"]["href"], "https://example.test/product"
        )
        self.product.assets.clear()
        with self.assertWarnsRegex(DeprecationWarning, "EOProduct.location"):
            self.product.location = ""
        self.assertNotIn("download_link", self.product.assets)

    def test_product_locations_without_href(self):
        """Order-only assets have no product location until a URL is available."""
        self.product.assets["download_link"] = {
            "eodag:order_link": "https://example.test/order"
        }
        with self.assertWarnsRegex(DeprecationWarning, "EOProduct.location"):
            self.assertIsNone(self.product.location)
        with self.assertWarnsRegex(DeprecationWarning, "EOProduct.remote_location"):
            self.assertIsNone(self.product.remote_location)

    def test_asset_locations_roundtrip_without_product_proxies(self):
        """Storage options and serialization use asset paths without deprecation warnings."""
        self.product.assets["download_link"] = {
            "href": "%(base_uri)s/product",
            "file:local_path": "/tmp/local-product",
        }
        downloader = mock.Mock()
        downloader.config.base_uri = "https://example.test"
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            self.product.register_downloader(downloader, None)
            self.assertEqual(
                self.product.get_storage_options(),
                {"path": path_to_uri("/tmp/local-product")},
            )
            serialized = self.product.as_dict()
            restored = EOProduct.from_dict(serialized)
        self.assertEqual(
            restored.assets["download_link"]["href"], "https://example.test/product"
        )
        self.assertEqual(
            restored.assets["download_link"]["file:local_path"], "/tmp/local-product"
        )
        self.assertNotIn("eodag:download_link", serialized["properties"])
        self.assertNotIn("_location", vars(restored))

    def test_asset_order(self):
        """Only assets that are not online must be ordered"""
        self.product.assets.update(
            {
                "download_link": {"eodag:order_link": "http://somewhere/order"},
                "online": {
                    "href": "http://somewhere/online",
                    "order:status": ONLINE_STATUS,
                },
                "no_status": {"href": "http://somewhere/no_status"},
            }
        )
        self.assertEqual(
            self.product.assets["download_link"]["order:status"], OFFLINE_STATUS
        )

        self.product.order(wait=1, timeout=2)

        self.product.downloader.order.assert_called_once_with(
            self.product,
            self.product.downloader_auth.authenticate.return_value,
            wait=1,
            timeout=2,
            asset="download_link",
        )

    def test_asset_order_errors(self):
        """Asset order must fail without a downloader supporting it"""
        self.product.assets["foo"] = {"eodag:order_link": "http://somewhere/order"}
        self.product.downloader = mock.Mock(spec=[])
        with self.assertRaises(NotImplementedError):
            self.product.assets["foo"].order()
        self.product.downloader = None
        with self.assertRaises(RuntimeError):
            self.product.assets["foo"].order()

    def test_register_downloader_resolves_assets(self):
        """register_downloader must resolve asset href and eodag:order_link"""
        self.product.assets.update(
            {
                "foo": {"href": "%(base_uri)s/foo"},
                "bar": {"eodag:order_link": "%(base_uri)s/order"},
            }
        )
        downloader = mock.Mock()
        downloader.config = mock.Mock(base_uri="http://somewhere")
        self.product.register_downloader(downloader, None)
        self.assertEqual(self.product.assets["foo"]["href"], "http://somewhere/foo")
        self.assertEqual(
            self.product.assets["bar"]["eodag:order_link"], "http://somewhere/order"
        )
