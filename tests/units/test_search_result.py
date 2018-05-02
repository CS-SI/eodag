# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

import geojson
from typing import Iterable

from tests import EODagTestCase
from .context import SearchResult


class TestSearchResult(EODagTestCase):

    def setUp(self):
        super(TestSearchResult, self).setUp()
        self.search_result = SearchResult([])

    def test_search_result_geo_interface(self):
        """SearchResult must provide a FeatureCollection geo-interface"""
        geo_interface = geojson.loads(geojson.dumps(self.search_result))
        self.assertDictContainsSubset({'type': 'FeatureCollection', 'features': []}, geo_interface)

    def test_search_result_list_iterable_like(self):
        """SearchResult must have a length and be iterable"""
        self.assertEqual(len(self.search_result), 0)
        self.assertIsInstance(self.search_result, Iterable)

    def test_search_result_truth_value(self):
        """SearchResult with empty list must be False and True with non empty list"""
        self.assertFalse(self.search_result)
        self.assertTrue(SearchResult(['Mock']))

    def test_search_result_from_feature_collection(self):
        """SearchResult instances must be build-able from feature collection geojson"""
        same_search_result = SearchResult.from_geojson(geojson.loads(geojson.dumps(self.search_result)))
        self.assertEqual(len(same_search_result), len(self.search_result))
