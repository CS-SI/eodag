# -*- coding: utf-8 -*-
# Copyright 2020, CS GROUP - France, http://www.c-s.fr
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
import unittest

from tests import TEST_RESOURCES_PATH
from tests.context import EODataAccessGateway, SearchResult


class TestSearchStacStatic(unittest.TestCase):
    def setUp(self):
        super(TestSearchStacStatic, self).setUp()

        self.dag = EODataAccessGateway()

        self.cat_dir_path = self.root_cat = os.path.join(TEST_RESOURCES_PATH, "stac")
        # paths are relative in this test catalog, chdir needed
        os.chdir(self.cat_dir_path)

        self.root_cat = os.path.join(self.cat_dir_path, "catalog.json")
        self.root_cat_len = 5
        self.child_cat = os.path.join(
            self.cat_dir_path, "country", "FRA", "year", "2018", "2018.json"
        )
        self.child_cat_len = 2

        self.stac_provider = "astraea_eod"
        self.product_type = "S2_MSI_L1C"

    def test_search_stac_static_load_child(self):
        """load_stac_items from child catalog must provide items"""
        items = self.dag.load_stac_items(
            self.child_cat, recursive=True, provider=self.stac_provider
        )
        self.assertIsInstance(items, SearchResult)
        self.assertEqual(len(items), self.child_cat_len)
        self.assertEqual(items[0].provider, self.stac_provider)
        # if no product_type is provided, product_type is None
        self.assertIsNone(items[0].product_type)

    def test_search_stac_static_load_root_not_recursive(self):
        """load_stac_items from root must provide an empty list when no recursive"""
        items = self.dag.load_stac_items(
            self.root_cat, recursive=False, provider=self.stac_provider
        )
        self.assertEqual(len(items), 0)

    def test_search_stac_static_load_root_recursive(self):
        """load_stac_items from root must provide items when recursive"""
        items = self.dag.load_stac_items(
            self.root_cat,
            recursive=True,
            provider=self.stac_provider,
            productType=self.product_type,
        )
        self.assertEqual(len(items), self.root_cat_len)
        for item in items:
            self.assertEqual(item.provider, self.stac_provider)
            self.assertEqual(item.product_type, self.product_type)
