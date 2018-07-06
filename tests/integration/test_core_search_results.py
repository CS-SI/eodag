# -*- coding: utf-8 -*-
# Copyright 2018, CS Systemes d'Information, http://www.c-s.fr
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
from __future__ import unicode_literals

import json
import os
import tempfile
import unittest

from shapely import geometry

from tests import TEST_RESOURCES_PATH
from tests.context import SatImagesAPI, SearchResult


class TestCoreSearchResults(unittest.TestCase):

    def setUp(self):
        self.dag = SatImagesAPI()
        self.maxDiff = None
        self.geojson_repr = {
            'features': [{
                'properties': {
                    'snowCover': None,
                    'resolution': None,
                    'completionTimeFromAscendingNode': '2018-02-16T00:12:14.035Z',
                    'keyword': {},
                    'productType': 'OCN',
                    'eodag_download_url': ('https://peps.cnes.fr/resto/collections/S1/578f1768-e66e-5b86-9363-b19f8931c'
                                           'c7b/download'),
                    'eodag_provider': 'peps',
                    'eodag_product_type': 'S1_OCN',
                    'platformSerialIdentifier': 'S1A',
                    'cloudCover': 0,
                    'title': 'S1A_WV_OCN__2SSV_20180215T235323_20180216T001213_020624_023501_0FD3',
                    'orbitNumber': 20624,
                    'instrument': 'SAR-C SAR',
                    'abstract': None,
                    'eodag_search_intersection': {
                        'coordinates': [
                            [
                                [
                                    89.590721,
                                    2.614019
                                ],
                                [
                                    89.771805,
                                    2.575546
                                ],
                                [
                                    89.809341,
                                    2.756323
                                ],
                                [
                                    89.628258,
                                    2.794767
                                ],
                                [
                                    89.590721,
                                    2.614019
                                ]
                            ]
                        ],
                        'type': 'Polygon'
                    },
                    'organisationName': None,
                    'startTimeFromAscendingNode': '2018-02-15T23:53:22.871Z',
                    'platform': None,
                    'sensorType': None,
                    'processingLevel': None,
                    'orbitType': None,
                    'topicCategory': None,
                    'orbitDirection': None,
                    'parentIdentifier': None,
                    'sensorMode': None,
                },
                'id': '578f1768-e66e-5b86-9363-b19f8931cc7b',
                'type': 'Feature',
                'geometry': {
                    'coordinates': [
                        [
                            [
                                89.590721,
                                2.614019
                            ],
                            [
                                89.771805,
                                2.575546
                            ],
                            [
                                89.809341,
                                2.756323
                            ],
                            [
                                89.628258,
                                2.794767
                            ],
                            [
                                89.590721,
                                2.614019
                            ]
                        ]
                    ],
                    'type': 'Polygon'
                }
            }],
            'type': 'FeatureCollection'
        }
        self.search_result = SearchResult.from_geojson(self.geojson_repr)
        # Ensure that each product in a search result has geometry and search intersection as a shapely geometry
        for product in self.search_result:
            product.search_intersection = geometry.shape(product.search_intersection)

    def test_core_serialize_search_results(self):
        """The core api must serialize a search results to geojson format into a file named search_results.geojson"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            path = self.dag.serialize(self.search_result, filename=f.name)
            self.assertEqual(path, f.name)
        with open(path, 'r') as f:
            self.assertDictEqual(json.load(f), self.geojson_repr)
        os.unlink(path)

    def test_core_serialize_search_results_filename_kwarg(self):
        """The core api must serialize a search results to geojson format into specified file"""
        path = self.dag.serialize(self.search_result)
        self.assertEqual(path, 'search_results.geojson')
        with open(path, 'r') as f:
            self.assertDictEqual(json.load(f), self.geojson_repr)
        os.unlink(path)

    def test_core_deserialize_search_results(self):
        """The core api must deserialize a search result from geojson"""
        search_results_geojson_path = os.path.join(TEST_RESOURCES_PATH, 'eodag_search_result.geojson')
        search_result = self.dag.deserialize(search_results_geojson_path)
        self.assertIsInstance(search_result, SearchResult)
        with open(search_results_geojson_path, 'r') as f:
            self.assertDictEqual(json.load(f), self.geojson_repr)
