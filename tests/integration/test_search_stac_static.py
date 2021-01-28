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
from tests.context import (
    EODataAccessGateway,
    FilterDate,
    FilterLatestByName,
    FilterOverlap,
    FilterProperty,
    SearchResult,
)


class TestSearchStacStatic(unittest.TestCase):
    def setUp(self):
        super(TestSearchStacStatic, self).setUp()

        self.dag = EODataAccessGateway()

        self.cat_dir_path = self.root_cat = os.path.join(TEST_RESOURCES_PATH, "stac")
        # paths are relative in this test catalog, chdir needed
        self._currentdir = os.getcwd()
        os.chdir(self.cat_dir_path)

        self.root_cat = os.path.join(self.cat_dir_path, "catalog.json")
        self.root_cat_len = 5
        self.child_cat = os.path.join(
            self.cat_dir_path, "country", "FRA", "year", "2018", "2018.json"
        )
        self.child_cat_len = 2

        self.stac_provider = "astraea_eod"
        self.product_type = "S2_MSI_L1C"

        self.extent_big = {"lonmin": -55, "lonmax": -53, "latmin": 2, "latmax": 5}
        self.extent_small = {"lonmin": -55, "lonmax": -54.5, "latmin": 2, "latmax": 2.5}

    def tearDown(self):
        os.chdir(self._currentdir)

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

    def test_search_stac_static_crunch_filter_date(self):
        """load_stac_items from root and filter by date"""
        items = self.dag.load_stac_items(
            self.root_cat,
            recursive=True,
            provider=self.stac_provider,
            productType=self.product_type,
        )
        filtered_items = items.crunch(
            FilterDate({"start": "2018-01-01", "end": "2019-01-01"})
        )
        self.assertEqual(len(filtered_items), self.child_cat_len)
        for item in filtered_items:
            self.assertIn("2018", item.properties["startTimeFromAscendingNode"])

    def test_search_stac_static_crunch_filter_overlap(self):
        """load_stac_items from root and filter by overlap"""
        # tests over extent_big search geometry
        items = self.dag.load_stac_items(
            self.root_cat,
            recursive=True,
            provider=self.stac_provider,
            productType=self.product_type,
            geom=self.extent_big,
        )
        self.assertEqual(len(items), self.root_cat_len)

        filtered_items = items.crunch(
            FilterOverlap({"minimum_overlap": 10}), geometry=self.extent_big
        )
        self.assertEqual(len(filtered_items), 3)

        filtered_items = items.crunch(
            FilterOverlap({"minimum_overlap": 100}), geometry=self.extent_big
        )
        self.assertEqual(len(filtered_items), 1)

        filtered_items = items.crunch(
            FilterOverlap({"within": True}), geometry=self.extent_big
        )
        self.assertEqual(len(filtered_items), 1)

        filtered_items = items.crunch(
            FilterOverlap({"contains": True}), geometry=self.extent_big
        )
        self.assertEqual(len(filtered_items), 0)

        # tests over extent_small search geometry
        items = self.dag.load_stac_items(
            self.root_cat,
            recursive=True,
            provider=self.stac_provider,
            productType=self.product_type,
            geom=self.extent_small,
        )
        self.assertEqual(len(items), self.root_cat_len)

        filtered_items = items.crunch(
            FilterOverlap({"contains": True}), geometry=self.extent_small
        )
        self.assertEqual(len(filtered_items), 1)

    def test_search_stac_static_crunch_filter_property(self):
        """load_stac_items from root and filter by property"""
        items = self.dag.load_stac_items(
            self.root_cat,
            recursive=True,
            provider=self.stac_provider,
            productType=self.product_type,
        )
        self.assertEqual(len(items), self.root_cat_len)

        filtered_items = items.crunch(FilterProperty({"orbitNumber": 110}))
        self.assertEqual(len(filtered_items), 3)

        filtered_items = items.crunch(
            FilterProperty({"platformSerialIdentifier": "S2A", "operator": "eq"})
        )
        self.assertEqual(len(filtered_items), 4)

        filtered_items = items.crunch(
            FilterProperty({"cloudCover": 10, "operator": "lt"})
        )
        self.assertEqual(len(filtered_items), 1)

    def test_search_stac_static_crunch_filter_lastest_by_name(self):
        """load_stac_items from root and filter by name"""
        items = self.dag.load_stac_items(
            self.root_cat,
            recursive=True,
            provider=self.stac_provider,
            productType=self.product_type,
        )
        self.assertEqual(len(items), self.root_cat_len)

        filtered_items = items.crunch(
            FilterLatestByName(
                {"name_pattern": r"S2[AB]_MSIL1C_20(?P<tileid>\d{6}).*T21NY.*"}
            )
        )
        self.assertEqual(len(filtered_items), 2)
