# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

import unittest


try:
    from UserList import UserList
except ImportError:
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
        self.assertDictContainsSubset({'type': 'FeatureCollection', 'features': []}, geo_interface)

    def test_search_result_is_list_like(self):
        """SearchResult must provide a list interface"""
        self.assertIsInstance(self.search_result, UserList)

    def test_search_result_from_feature_collection(self):
        """SearchResult instances must be build-able from feature collection geojson"""
        same_search_result = SearchResult.from_geojson(geojson.loads(geojson.dumps(self.search_result)))
        self.assertEqual(len(same_search_result), len(self.search_result))
