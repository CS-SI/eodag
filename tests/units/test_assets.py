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
import unittest

from tests.context import Asset, AssetsDict, mock


class CustomAsset(Asset):
    pass


class CustomAssetsDict(AssetsDict):
    def _make_asset(self, key, value):
        return CustomAsset(self.product, key, value)


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

    def test_update_and_setitem_sort_assets_and_remove_private_fields(self):
        """Sort assets and remove private fields after updates."""
        assets = AssetsDict(object())

        assets.update(
            {
                "z": {"href": "z", "_internal": "remove"},
                "a": {"href": "a", "_internal": "remove"},
            }
        )
        assets["m"] = {"href": "m", "_internal": "remove"}

        self.assertEqual(list(assets), ["a", "m", "z"])
        self.assertDictEqual(
            {key: dict(asset) for key, asset in assets.items()},
            {
                "a": {"href": "a"},
                "m": {"href": "m"},
                "z": {"href": "z"},
            },
        )
