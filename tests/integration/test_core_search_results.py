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

import json
import os
import shutil
import tempfile

from shapely import geometry

from tests import TEST_RESOURCES_PATH, EODagTestCase
from tests.context import EODataAccessGateway, EOProduct, SearchResult
from tests.utils import mock


class TestCoreSearchResults(EODagTestCase):
    def setUp(self):
        super(TestCoreSearchResults, self).setUp()
        # Mock home and eodag conf directory to tmp dir
        self.tmp_home_dir = tempfile.mkdtemp()
        self.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, return_value=self.tmp_home_dir
        )
        self.expanduser_mock.start()
        self.dag = EODataAccessGateway()
        self.maxDiff = None
        self.geojson_repr = {
            "features": [
                {
                    "properties": {
                        "snowCover": None,
                        "resolution": None,
                        "completionTimeFromAscendingNode": "2018-02-16T00:12:14.035Z",
                        "keyword": {},
                        "productType": "OCN",
                        "downloadLink": (
                            "https://peps.cnes.fr/resto/collections/S1/"
                            "578f1768-e66e-5b86-9363-b19f8931cc7b/download"
                        ),
                        "eodag_provider": "peps",
                        "eodag_product_type": "S1_SAR_OCN",
                        "platformSerialIdentifier": "S1A",
                        "cloudCover": 0,
                        "title": "S1A_WV_OCN__2SSV_20180215T235323_"
                        "20180216T001213_020624_023501_0FD3",
                        "orbitNumber": 20624,
                        "instrument": "SAR-C SAR",
                        "abstract": None,
                        "eodag_search_intersection": {
                            "coordinates": [
                                [
                                    [89.590721, 2.614019],
                                    [89.771805, 2.575546],
                                    [89.809341, 2.756323],
                                    [89.628258, 2.794767],
                                    [89.590721, 2.614019],
                                ]
                            ],
                            "type": "Polygon",
                        },
                        "organisationName": None,
                        "startTimeFromAscendingNode": "2018-02-15T23:53:22.871Z",
                        "platform": None,
                        "sensorType": None,
                        "processingLevel": None,
                        "orbitType": None,
                        "topicCategory": None,
                        "orbitDirection": None,
                        "parentIdentifier": None,
                        "sensorMode": None,
                        "quicklook": None,
                    },
                    "id": "578f1768-e66e-5b86-9363-b19f8931cc7b",
                    "type": "Feature",
                    "geometry": {
                        "coordinates": [
                            [
                                [89.590721, 2.614019],
                                [89.771805, 2.575546],
                                [89.809341, 2.756323],
                                [89.628258, 2.794767],
                                [89.590721, 2.614019],
                            ]
                        ],
                        "type": "Polygon",
                    },
                }
            ],
            "type": "FeatureCollection",
        }
        self.search_result = SearchResult.from_geojson(self.geojson_repr)
        # Ensure that each product in a search result has geometry and search
        # intersection as a shapely geometry
        for product in self.search_result:
            product.search_intersection = geometry.shape(product.search_intersection)

    def tearDown(self):
        super(TestCoreSearchResults, self).tearDown()
        # stop Mock and remove tmp config dir
        self.expanduser_mock.stop()
        try:
            shutil.rmtree(self.tmp_home_dir)
        except OSError:
            pass

    def test_core_serialize_search_results(self):
        """The core api must serialize a search results to geojson"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            # Serialization when the destination file is specified => goes to the
            # specified file
            path = self.dag.serialize(self.search_result, filename=f.name)
            self.assertEqual(path, f.name)
        with open(path, "r") as f:
            self.make_assertions(f)
        os.unlink(path)
        # Serialization when the destination is not specified => goes to
        # 'search_results.geojson' in the cur dir
        tmpdirname = tempfile.mkdtemp()
        current_dir = os.getcwd()
        os.chdir(tmpdirname)
        self.assertEqual(
            self.dag.serialize(self.search_result), "search_results.geojson"
        )
        os.chdir(current_dir)
        shutil.rmtree(tmpdirname)

    def test_core_deserialize_search_results(self):
        """The core api must deserialize a search result from geojson"""
        search_results_geojson_path = os.path.join(
            TEST_RESOURCES_PATH, "eodag_search_result.geojson"
        )
        search_result = self.dag.deserialize(search_results_geojson_path)
        self.assertIsInstance(search_result, SearchResult)
        with open(search_results_geojson_path, "r") as f:
            self.make_assertions(f)

    def make_assertions(self, f):
        d = json.load(f)
        self.assertEqual(d["type"], self.geojson_repr["type"])
        self.assertEqual(len(d["features"]), len(self.geojson_repr["features"]))
        feature = d["features"][0]
        self.assertEqual(feature["id"], self.geojson_repr["features"][0]["id"])
        self.assertEqual(feature["type"], self.geojson_repr["features"][0]["type"])
        self.assertDictEqual(
            feature["geometry"], self.geojson_repr["features"][0]["geometry"]
        )
        for key, value in self.geojson_repr["features"][0]["properties"].items():
            if key not in ("geometry", "id"):
                if isinstance(value, dict):
                    self.assertDictEqual(value, feature["properties"][key])
                elif isinstance(value, list):
                    self.assertListEqual(value, feature["properties"][key])
                else:
                    self.assertEqual(value, feature["properties"][key])
            else:
                self.assertEqual(value, feature[key])

    @staticmethod
    def _minimal_eoproduct_geojson_repr(eo_id, geom_coords, geom_type="Polygon"):
        return {
            "properties": {
                "eodag_provider": "peps",
                "eodag_product_type": "S1_SAR_OCN",
                "eodag_search_intersection": {
                    "coordinates": geom_coords,
                    "type": geom_type,
                },
            },
            "id": eo_id,
            "geometry": {"coordinates": geom_coords, "type": geom_type},
        }

    def test_group_by_extent(self):
        geom_coords_1 = [[[89, 2], [90, 2], [90, 3], [89, 3], [89, 2]]]
        geom_coords_2 = [[[90, 3], [91, 3], [91, 4], [90, 4], [90, 3]]]
        geom_coords_3 = [[[92, 4], [92, 4], [92, 5], [91, 5], [91, 4]]]

        eo_geom1 = EOProduct.from_geojson(
            self._minimal_eoproduct_geojson_repr("1", geom_coords_1)
        )
        eo_geom2 = EOProduct.from_geojson(
            self._minimal_eoproduct_geojson_repr("2", geom_coords_2)
        )
        eo_geom3 = EOProduct.from_geojson(
            self._minimal_eoproduct_geojson_repr("3", geom_coords_3)
        )
        first_search = SearchResult([eo_geom1])
        second_search = SearchResult([eo_geom1, eo_geom2])
        third_search = SearchResult([eo_geom1, eo_geom2, eo_geom3])

        grouped_searches = EODataAccessGateway.group_by_extent(
            [first_search, second_search, third_search]
        )

        # The returned value is a List[SearchResult]
        self.assertIsInstance(grouped_searches, list)
        self.assertTrue(all(isinstance(sr, SearchResult) for sr in grouped_searches))
        # We expect three groups because we have given products that have
        # three different geometry bounds.
        self.assertEqual(len(grouped_searches), 3)
        # Given how the search results were constructed the resulting groups
        # must have these 3 different lengths.
        ss_len = [len(sr) for sr in grouped_searches]
        self.assertIn(1, ss_len)
        self.assertIn(2, ss_len)
        self.assertIn(3, ss_len)

    def test_empty_search_result_return_empty_list(self):
        products_paths = self.dag.download_all(None)
        self.assertFalse(products_paths)

    def test_download_all_callback(self):
        product = self._dummy_downloadable_product()
        search_result = SearchResult([product])

        def downloaded_callback_func(product):
            self.assertTrue(product in search_result)
            downloaded_callback_func.times_called += 1

        downloaded_callback_func.times_called = 0

        try:
            self.assertEqual(downloaded_callback_func.times_called, 0)
            products_paths = self.dag.download_all(
                search_result, downloaded_callback=downloaded_callback_func
            )
            self.assertEqual(downloaded_callback_func.times_called, len(search_result))
        finally:
            for product_path in products_paths:
                self._clean_product(product_path)
