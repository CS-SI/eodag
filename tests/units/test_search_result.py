# -*- coding: utf-8 -*-
# Copyright 2022, CS GROUP - France, https://www.csgroup.eu/
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

from tests.context import SearchResult


class TestSearchResult(unittest.TestCase):
    def setUp(self):
        super(TestSearchResult, self).setUp()
        self.search_result = SearchResult([])

    def test_search_result_geo_interface(self):
        """SearchResult must provide a FeatureCollection geo-interface"""
        geo_interface = geojson.loads(geojson.dumps(self.search_result))
        self.assertEqual(geo_interface["type"], "FeatureCollection")
        self.assertEqual(geo_interface["features"], [])

    def test_search_result_is_list_like(self):
        """SearchResult must provide a list interface"""
        self.assertIsInstance(self.search_result, UserList)

    def test_search_result_from_feature_collection(self):
        """SearchResult instances must be build-able from feature collection geojson"""
        same_search_result = SearchResult.from_geojson(
            geojson.loads(geojson.dumps(self.search_result))
        )
        self.assertEqual(len(same_search_result), len(self.search_result))
