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

import json
import unittest

import geojson

from tests import mock
from tests.context import (
    DEFAULT_ITEMS_PER_PAGE,
    SearchResult,
    ValidationError,
    eodag_http_server,
    get_date,
)


class RequestTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tested_product_type = "S2_MSI_L1C"

    def setUp(self):
        self.app = eodag_http_server.app.test_client()

    def test_route(self):
        response = self.app.get("/", follow_redirects=True)
        self.assertEqual(200, response.status_code)

        self._request_valid(self.tested_product_type)

    @mock.patch(
        "eodag.rest.utils.eodag_api.search",
        autospec=True,
        return_value=(
            SearchResult.from_geojson(
                {
                    "features": [
                        {
                            "properties": {
                                "snowCover": None,
                                "resolution": None,
                                "completionTimeFromAscendingNode": "2018-02-16T00:12:14"
                                ".035Z",
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
                                "startTimeFromAscendingNode": "2018-02-15T23:53:22"
                                ".871Z",
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
            ),
            1,
        ),
    )
    def _request_valid(self, url, _):
        response = self.app.get(url, follow_redirects=True)
        self.assertEqual(200, response.status_code)
        # Assert response format is GeoJSON
        return geojson.loads(response.data.decode("utf-8"))

    def _request_not_valid(self, url):
        response = self.app.get(url, follow_redirects=True)
        response_content = json.loads(response.data.decode("utf-8"))

        self.assertEqual(400, response.status_code)
        self.assertIn("description", response_content)
        self.assertIn("invalid", response_content["description"])

    def _request_not_found(self, url):
        response = self.app.get(url, follow_redirects=True)
        response_content = json.loads(response.data.decode("utf-8"))

        self.assertEqual(404, response.status_code)
        self.assertIn("error", response_content)
        self.assertIn("not found", response_content["error"])

    def test_request_params(self):
        self._request_not_valid(
            "search?collections={}&bbox=1".format(self.tested_product_type)
        )
        self._request_not_valid(
            "search?collections={}&bbox=0,43,1".format(self.tested_product_type)
        )
        self._request_not_valid(
            "search?collections={}&bbox=0,,1".format(self.tested_product_type)
        )
        self._request_not_valid(
            "search?collections={}&bbox=a,43,1,44".format(self.tested_product_type)
        )

        self._request_valid("search?collections={}".format(self.tested_product_type))
        self._request_valid(
            "search?collections={}&bbox=0,43,1,44".format(self.tested_product_type)
        )

    def test_not_found(self):
        """A request to eodag server with a not supported product type must return a 404 HTTP error code"""  # noqa
        self._request_not_found("search?collections=ZZZ&bbox=0,43,1,44")

    def test_filter(self):
        result1 = self._request_valid(
            "search?collections={}&bbox=0,43,1,44".format(self.tested_product_type)
        )
        result2 = self._request_valid(
            "search?collections={}&bbox=0,43,1,44&filter=latestIntersect".format(
                self.tested_product_type
            )
        )
        self.assertGreaterEqual(len(result1.features), len(result2.features))

    def test_get_date(self):
        """Date validation function must correctly validate dates"""
        get_date("2018-01-01")
        get_date("2018-01-01T")
        get_date("2018-01-01T00:00")
        get_date("2018-01-01T00:00:00")
        get_date("2018-01-01T00:00:00Z")
        get_date("20180101")

        self.assertRaises(ValidationError, get_date, "foo")
        self.assertRaises(ValidationError, get_date, "foo2018-01-01")

        self.assertIsNone(get_date(None))

    def test_date_search(self):
        result1 = self._request_valid(
            "search?collections={}&bbox=0,43,1,44".format(self.tested_product_type)
        )
        result2 = self._request_valid(
            "search?collections={}&bbox=0,43,1,44&datetime=2018-01-20/2018-01-25".format(
                self.tested_product_type
            )
        )
        self.assertGreaterEqual(len(result1.features), len(result2.features))

    def test_date_search_from_items(self):
        result1 = self._request_valid(
            "collections/{}/items?bbox=0,43,1,44".format(self.tested_product_type)
        )
        result2 = self._request_valid(
            "collections/{}/items?bbox=0,43,1,44&datetime=2018-01-20/2018-01-25".format(
                self.tested_product_type
            )
        )
        self.assertGreaterEqual(len(result1.features), len(result2.features))

    def test_date_search_from_catalog_items(self):
        result1 = self._request_valid(
            "{}/year/2018/month/01/items?bbox=0,43,1,44".format(
                self.tested_product_type
            )
        )
        result2 = self._request_valid(
            "{}/year/2018/month/01/items?bbox=0,43,1,44&datetime=2018-01-20/2018-01-25".format(
                self.tested_product_type
            )
        )
        self.assertGreaterEqual(len(result1.features), len(result2.features))

    def test_catalog_browse(self):
        result = self._request_valid(
            "{}/year/2018/month/01/day".format(self.tested_product_type)
        )
        self.assertListEqual(
            [str(i) for i in range(1, 32)],
            [it["title"] for it in result.get("links", []) if it["rel"] == "child"],
        )

    def test_cloud_cover_search(self):
        result1 = self._request_valid(
            "search?collections={}&bbox=0,43,1,44".format(self.tested_product_type)
        )
        result2 = self._request_valid(
            "search?collections={}&bbox=0,43,1,44&cloudCover=10".format(
                self.tested_product_type
            )
        )
        self.assertGreaterEqual(len(result1.features), len(result2.features))

    def test_search_response_contains_pagination_info(self):
        """Responses to valid search requests must return a geojson with pagination info in properties"""  # noqa
        response = self._request_valid(
            "search?collections={}".format(self.tested_product_type)
        )
        self.assertIn("numberMatched", response)
        self.assertIn("numberReturned", response)
        self.assertIn("context", response)
        self.assertEqual(1, response["context"]["page"])
        self.assertEqual(DEFAULT_ITEMS_PER_PAGE, response["context"]["limit"])
        self.assertIn("matched", response["context"])
        self.assertIn("returned", response["context"])

    @mock.patch(
        "eodag.rest.utils.eodag_api.guess_product_type", autospec=True, return_value=[]
    )
    @mock.patch(
        "eodag.rest.utils.eodag_api.list_product_types",
        autospec=True,
        return_value=[{"ID": "S2_MSI_L1C"}, {"ID": "S2_MSI_L2A"}],
    )
    def test_list_product_types_ok(self, list_pt, guess_pt):
        """A simple request for product types with(out) a provider must succeed"""
        for url in ("/collections",):
            r = self.app.get(url)
            self.assertTrue(guess_pt.called)
            self.assertTrue(list_pt.called)
            self.assertEqual(200, r.status_code)
            self.assertListEqual(
                ["S2_MSI_L1C", "S2_MSI_L2A"],
                [
                    it["title"]
                    for it in json.loads(r.data.decode("utf-8")).get("links", [])
                    if it["rel"] == "child"
                ],
            )

        guess_pt.return_value = ["S2_MSI_L1C"]
        url = "/collections?instrument=MSI"
        r = self.app.get(url)
        self.assertTrue(guess_pt.called)
        self.assertTrue(list_pt.called)
        self.assertEqual(200, r.status_code)
        self.assertListEqual(
            ["S2_MSI_L1C"],
            [
                it["title"]
                for it in json.loads(r.data.decode("utf-8")).get("links", [])
                if it["rel"] == "child"
            ],
        )

    @mock.patch(
        "eodag.rest.utils.eodag_api.list_product_types",
        autospec=True,
        return_value=[{"ID": "S2_MSI_L1C"}, {"ID": "S2_MSI_L2A"}],
    )
    def test_list_product_types_nok(self, list_pt):
        """A request for product types with a not supported filter must return all product types"""  # noqa
        url = "/collections?platform=gibberish"
        r = self.app.get(url)
        self.assertTrue(list_pt.called)
        self.assertEqual(200, r.status_code)
        self.assertListEqual(
            ["S2_MSI_L1C", "S2_MSI_L2A"],
            [
                it["title"]
                for it in json.loads(r.data.decode("utf-8")).get("links", [])
                if it["rel"] == "child"
            ],
        )

    def test_conformance(self):
        self._request_valid("conformance")

    def test_service_desc(self):
        self._request_valid("service-desc")

    def test_service_doc(self):
        response = self.app.get("service-doc", follow_redirects=True)
        self.assertEqual(200, response.status_code)
