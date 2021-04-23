# -*- coding: utf-8 -*-
# Copyright 2021, CS GROUP - France, http://www.c-s.fr
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
        self.root_cat = os.path.join(self.cat_dir_path, "catalog.json")
        self.root_cat_len = 5
        self.child_cat = os.path.join(
            self.cat_dir_path, "country", "FRA", "year", "2018", "2018.json"
        )
        self.child_cat_len = 2
        self.item = os.path.join(
            os.path.dirname(self.child_cat),
            "items",
            "S2A_MSIL1C_20181231T141041_N0207_R110_T21NYF_20181231T155050",
            "S2A_MSIL1C_20181231T141041_N0207_R110_T21NYF_20181231T155050.json",
        )
        self.singlefile_cat = os.path.join(TEST_RESOURCES_PATH, "stac_singlefile.json")
        self.singlefile_cat_len = 5

    def test_stac_reader_fetch_child(self):
        """fetch_stac_items from child catalog must provide items"""
        items = fetch_stac_items(self.child_cat)
        self.assertIsInstance(items, list)
        self.assertEqual(len(items), self.child_cat_len)
        self.assertEqual(items[0]["type"], "Feature")
        self.assertEqual(items[0]["collection"], "S2_MSI_L1C")

    def test_stac_reader_fetch_root_not_recursive(self):
        """fetch_stac_items from root must provide an empty list when no recursive"""
        items = fetch_stac_items(self.root_cat, recursive=False)
        self.assertListEqual(items, [])

    def test_stac_reader_fetch_root_recursive(self):
        """fetch_stac_items from root must provide items when recursive"""
        items = fetch_stac_items(self.root_cat, recursive=True)
        self.assertEqual(len(items), self.root_cat_len)
        for item in items:
            self.assertEqual(item["type"], "Feature")
            self.assertEqual(item["collection"], "S2_MSI_L1C")

    def test_stac_reader_fetch_item(self):
        """fetch_stac_items from an item must return it"""
        item = fetch_stac_items(self.item)
        self.assertIsInstance(item, list)
        self.assertEqual(len(item), 1)
        self.assertEqual(item[0]["type"], "Feature")
        self.assertEqual(item[0]["collection"], "S2_MSI_L1C")

    def test_stact_reader_fetch_singlefile_catalog(self):
        """fetch_stact_items must return all the items from a single file catalog"""
        items = fetch_stac_items(self.singlefile_cat)
        self.assertIsInstance(items, list)
        self.assertEqual(len(items), self.singlefile_cat_len)
        self.assertEqual(items[0]["type"], "Feature")
