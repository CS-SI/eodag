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

import unittest
from collections import UserList

import geojson
from shapely.geometry.collection import GeometryCollection

from tests.context import EOProduct, SearchResult


class TestSearchResult(unittest.TestCase):
    def setUp(self):
        super(TestSearchResult, self).setUp()
        self.search_result = SearchResult([])
        self.search_result2 = SearchResult(
            [
                EOProduct(
                    provider=None,
                    properties={"geometry": "POINT (0 0)", "storageStatus": "ONLINE"},
                ),
                EOProduct(
                    provider=None,
                    properties={"geometry": "POINT (0 0)", "storageStatus": "OFFLINE"},
                ),
            ]
        )

    def test_search_result_filter_online(self):
        """SearchResult.filter_online must only keep online results"""
        filtered_products = self.search_result2.filter_online()
        origin_size = len(self.search_result2)
        filtered_size = len(filtered_products)
        self.assertFalse(origin_size == filtered_size)
        for product in filtered_products:
            assert product.properties["storageStatus"] == "ONLINE"

    def test_search_result_geo_interface(self):
        """SearchResult must provide a FeatureCollection geo-interface"""
        geo_interface = geojson.loads(geojson.dumps(self.search_result))
        self.assertEqual(geo_interface["type"], "FeatureCollection")
        self.assertEqual(geo_interface["features"], [])

    def test_search_result_as_geojson_object(self):
        geojson_object = self.search_result.as_geojson_object()
        self.assertIsInstance(geojson_object, dict)
        self.assertTrue("type" in geojson_object)
        self.assertTrue("features" in geojson_object)

    def test_search_result_as_shapely_geometry_object(self):
        shapely_geometry_object = self.search_result.as_shapely_geometry_object()
        self.assertIsInstance(shapely_geometry_object, GeometryCollection)

    def test_search_result_as_wkt_object(self):
        wkt_object = self.search_result.as_wkt_object()
        self.assertIsInstance(wkt_object, str)
        self.assertTrue(wkt_object.startswith("GEOMETRYCOLLECTION"))

    def test_search_result_is_list_like(self):
        """SearchResult must provide a list interface"""
        self.assertIsInstance(self.search_result, UserList)

    def test_search_result_from_feature_collection(self):
        """SearchResult instances must be build-able from feature collection geojson"""
        same_search_result = SearchResult.from_geojson(
            geojson.loads(geojson.dumps(self.search_result))
        )
        self.assertEqual(len(same_search_result), len(self.search_result))
