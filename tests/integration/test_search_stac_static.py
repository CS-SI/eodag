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
import tempfile
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
from tests.utils import mock


class TestSearchStacStatic(unittest.TestCase):
    def setUp(self):
        super(TestSearchStacStatic, self).setUp()

        # Mock home and eodag conf directory to tmp dir
        self.tmp_home_dir = tempfile.mkdtemp()
        self.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, return_value=self.tmp_home_dir
        )
        self.expanduser_mock.start()

        self.dag = EODataAccessGateway()

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

        self.stac_provider = "astraea_eod"
        self.product_type = "S2_MSI_L1C"

        self.extent_big = {"lonmin": -55, "lonmax": -53, "latmin": 2, "latmax": 5}
        self.extent_small = {"lonmin": -55, "lonmax": -54.5, "latmin": 2, "latmax": 2.5}

        self.static_stac_provider = "foo_static"
        self.dag.update_providers_config(
            f"""
            {self.static_stac_provider}:
                search:
                    type: StaticStacSearch
                    api_endpoint: {self.root_cat}
                products:
                    GENERIC_PRODUCT_TYPE:
                        productType: '{{productType}}'
                download:
                    type: HTTPDownload
                    base_uri: https://fake-endpoint
                    flatten_top_dirs: True
        """
        )
        self.dag.set_preferred_provider(self.static_stac_provider)

    def tearDown(self):
        super(TestSearchStacStatic, self).tearDown()
        # stop Mock and remove tmp config dir
        self.expanduser_mock.stop()
        try:
            shutil.rmtree(self.tmp_home_dir)
        except OSError:
            pass

    def test_search_stac_static_load_child(self):
        """load_stac_items from child catalog must provide items"""
        items = self.dag.load_stac_items(
            self.child_cat, recursive=True, provider=self.stac_provider
        )
        self.assertIsInstance(items, SearchResult)
        self.assertEqual(len(items), self.child_cat_len)
        self.assertEqual(items[0].provider, self.stac_provider)
        # if no product_type is provided, product_type should be guessed from properties
        self.assertEqual(items[0].product_type, "S2_MSI_L1C")

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

    def test_search_stac_static(self):
        """Use StaticStacSearch plugin to search all items"""
        items, nb = self.dag.search()
        self.assertEqual(len(items), self.root_cat_len)
        self.assertEqual(nb, self.root_cat_len)
        for item in items:
            self.assertEqual(item.provider, self.static_stac_provider)

    def test_search_stac_static_load_item(self):
        """load_stac_items from a single item must provide it"""
        item = self.dag.load_stac_items(self.item, provider=self.stac_provider)
        self.assertIsInstance(item, SearchResult)
        self.assertEqual(len(item), 1)
        self.assertEqual(item[0].provider, self.stac_provider)
        # if no product_type is provided, product_type should be guessed from properties
        self.assertEqual(item[0].product_type, "S2_MSI_L1C")

    def test_search_stac_static_load_item_updated_provider(self):
        """load_stac_items from a single item using updated provider"""
        item = self.dag.load_stac_items(self.item, provider=self.stac_provider)

        self.assertEqual(item[0].properties["license"], "proprietary")
        self.assertEqual(item[0].properties["platform"], "S2ST")
        self.assertEqual(item[0].properties["orbitDirection"], "descending")
        self.assertNotIn("foo", item[0].properties)

        # fake provider with mixed metadata_mapping
        self.dag.update_providers_config(
            """
            fake_provider:
                search:
                    type: StacSearch
                    api_endpoint: 'https://fake-endpoint'
                    metadata_mapping:
                        license: '{platform}'
                        foo: '{orbitDirection}'
                products:
                    GENERIC_PRODUCT_TYPE:
                        productType: '{productType}'
                download:
                    type: HTTPDownload
                    base_uri: 'https://fake-uri'
        """
        )

        item = self.dag.load_stac_items(
            self.item, provider="fake_provider", raise_errors=True
        )
        self.assertEqual(item[0].properties["platform"], "S2ST")
        self.assertEqual(item[0].properties["license"], "S2ST")
        self.assertEqual(item[0].properties["orbitDirection"], "descending")
        self.assertIn("foo", item[0].properties)
        self.assertEqual(item[0].properties["foo"], "descending")

    @unittest.skip(
        "skipped as single-file-stac has been removed and is being rethought"
    )
    def test_search_stac_static_load_singlefile_catalog(self):
        """load_stac_items from child catalog must provide items"""
        items = self.dag.load_stac_items(
            self.singlefile_cat, provider=self.stac_provider
        )
        self.assertIsInstance(items, SearchResult)
        self.assertEqual(len(items), self.singlefile_cat_len)
        self.assertEqual(items[0].provider, self.stac_provider)
        # if no product_type is provided, product_type is None
        self.assertIsNone(items[0].product_type)

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

    def test_search_stac_static_by_date(self):
        """Use StaticStacSearch plugin to search by date"""
        filtered_items, nb = self.dag.search(start="2018-01-01", end="2019-01-01")
        self.assertEqual(len(filtered_items), self.child_cat_len)
        self.assertEqual(nb, self.child_cat_len)
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

        filtered_items = items.crunch(
            FilterOverlap({"intersects": True}), geometry=self.extent_big
        )
        self.assertEqual(len(filtered_items), 3)

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

    def test_search_stac_static_by_geom(self):
        """Use StaticStacSearch plugin to search by geometry"""
        items, nb = self.dag.search(
            geom=self.extent_big,
        )
        self.assertEqual(len(items), 3)
        self.assertEqual(nb, 3)

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

    def test_search_stac_static_by_property(self):
        """Use StaticStacSearch plugin to search by property"""
        items, nb = self.dag.search(orbitNumber=110)
        self.assertEqual(len(items), 3)
        self.assertEqual(nb, 3)

    def test_search_stac_static_by_cloudcover(self):
        """Use StaticStacSearch plugin to search by cloud cover"""
        items, nb = self.dag.search(cloudCover=10)
        self.assertEqual(len(items), 1)
        self.assertEqual(nb, 1)

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
