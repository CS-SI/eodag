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
from tests.context import fetch_stac_items


class TestStacReader(unittest.TestCase):
    def setUp(self):
        super(TestStacReader, self).setUp()

        self.cat_dir_path = self.root_cat = os.path.join(TEST_RESOURCES_PATH, "stac")
        # paths are relative in this test catalog, chdir needed
        os.chdir(self.cat_dir_path)

        self.root_cat = os.path.join(self.cat_dir_path, "catalog.json")
        self.root_cat_len = 5
        self.child_cat = os.path.join(
            self.cat_dir_path, "country", "FRA", "year", "2018", "2018.json"
        )
        self.child_cat_len = 2

    def test_stac_reader_fetch_child(self):
        """fetch_stac_items from child catalog must provide items"""
        items = fetch_stac_items(self.child_cat)
        self.assertIsInstance(items, list)
        self.assertEqual(len(items), self.child_cat_len)
        self.assertDictContainsSubset(
            {"type": "Feature", "collection": "S2_MSI_L1C"}, items[0],
        )

    def test_stac_reader_fetch_root_not_recursive(self):
        """fetch_stac_items from root must provide an empty list when no recursive"""
        items = fetch_stac_items(self.root_cat, recursive=False)
        self.assertListEqual(items, [])

    def test_stac_reader_fetch_root_recursive(self):
        """fetch_stac_items from root must provide items when recursive"""
        items = fetch_stac_items(self.root_cat, recursive=True)
        self.assertEqual(len(items), self.root_cat_len)
        for item in items:
            self.assertDictContainsSubset(
                {"type": "Feature", "collection": "S2_MSI_L1C"}, item
            )
