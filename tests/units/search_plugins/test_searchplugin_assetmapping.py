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
from eodag.api.product import EOProduct
from tests.units.search_plugins.base import BaseSearchPluginTest


class TestSearchPluginMeteoblueSearch(BaseSearchPluginTest):
    def test_get_assets_from_mapping(self):
        search_plugin = self.get_search_plugin(provider="geodes")
        search_plugin.config.assets_mapping = {
            "one": {"href": "$.properties.href", "roles": ["a_role"], "title": "One"},
            "two": {
                "href": "https://a.static_url.com",
                "roles": ["a_role"],
                "title": "Two",
            },
        }
        provider_item = {"id": "ID123456", "properties": {"href": "a.product.com/ONE"}}
        product = EOProduct(provider="geodes", properties={})
        asset_mappings = search_plugin.get_assets_from_mapping(provider_item, product)
        self.assertEqual(2, len(asset_mappings))
        self.assertEqual("a.product.com/ONE", asset_mappings["one"]["href"])
        self.assertEqual("One", asset_mappings["one"]["title"])
        self.assertListEqual(["a_role"], asset_mappings["one"]["roles"])
        self.assertEqual("https://a.static_url.com", asset_mappings["two"]["href"])
        self.assertEqual("Two", asset_mappings["two"]["title"])
        self.assertListEqual(["a_role"], asset_mappings["two"]["roles"])
