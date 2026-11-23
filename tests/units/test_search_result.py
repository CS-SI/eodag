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
from unittest import mock

import geojson
from lxml import html
from pystac import ItemCollection
from shapely.geometry.collection import GeometryCollection

from eodag.utils.exceptions import RequestError
from tests.context import EOProduct, SearchResult


class TestSearchResult(unittest.TestCase):
    def setUp(self):
        super(TestSearchResult, self).setUp()
        self.search_result = SearchResult([])

    def test_fetch_next_page_retries_without_advancing(self):
        """Failed page requests can be retried with the same token."""
        gateway = mock.Mock()
        plugin = mock.Mock()
        gateway._prepare_search.side_effect = lambda **params: ([plugin], params)
        first = SearchResult(
            [EOProduct("provider", {"id": "first", "geometry": "POINT (0 0)"})],
            search_params={"limit": 1},
            next_page_token="token-2",
            next_page_token_key="token",
            raise_errors=True,
        )
        second = SearchResult(
            [EOProduct("provider", {"id": "second", "geometry": "POINT (0 0)"})],
            search_params={"limit": 1},
            next_page_token="token-3",
            next_page_token_key="token",
        )
        third = SearchResult(
            [EOProduct("provider", {"id": "third", "geometry": "POINT (0 0)"})],
            search_params={"limit": 1},
        )
        first._dag = second._dag = gateway
        gateway._do_search.side_effect = [
            RequestError("temporary"),
            second,
            RequestError("temporary"),
            third,
        ]

        with self.assertRaises(RequestError):
            first.fetch_next_page()
        self.assertEqual(first.search_params, {"limit": 1})
        self.assertEqual(first.next_page_token, "token-2")
        self.assertIs(first.fetch_next_page(), second)
        self.assertEqual(
            gateway._do_search.call_args_list[0], gateway._do_search.call_args_list[1]
        )
        self.assertTrue(second.raise_errors)
        with self.assertRaises(RequestError):
            second.fetch_next_page()
        self.assertIs(second.fetch_next_page(), third)
        self.assertEqual(
            gateway._do_search.call_args_list[2], gateway._do_search.call_args_list[3]
        )
        self.assertEqual(
            gateway._do_search.call_args.kwargs["next_page_token"], "token-3"
        )
        self.assertTrue(gateway._do_search.call_args.kwargs["raise_errors"])
        self.assertIsNone(third.fetch_next_page())

    def test_fetch_next_page_empty_or_repeated(self):
        """Empty or repeated pages stop pagination."""
        gateway = mock.Mock()
        gateway._prepare_search.return_value = ([mock.Mock()], {})
        first = SearchResult(
            [EOProduct("provider", {"id": "first", "geometry": "POINT (0 0)"})],
            next_page_token="token",
        )
        first._dag = gateway
        gateway._do_search.return_value = SearchResult([])
        self.assertIsNone(first.fetch_next_page())
        gateway._do_search.return_value = SearchResult(first.data)
        with self.assertLogs("eodag.search_result", level="WARNING"):
            self.assertIsNone(first.fetch_next_page())

    def test_next_page_preserves_update_behavior(self):
        """Page iteration respects both update modes."""
        for update in (False, True):
            with self.subTest(update=update):
                gateway = mock.Mock()
                gateway._prepare_search.side_effect = lambda **params: (
                    [mock.Mock()],
                    params,
                )
                first = SearchResult(
                    [EOProduct("provider", {"id": "first", "geometry": "POINT (0 0)"})],
                    search_params={"limit": 1},
                    next_page_token="token",
                    raise_errors=True,
                )
                second = SearchResult(
                    [
                        EOProduct(
                            "provider", {"id": "second", "geometry": "POINT (0 0)"}
                        )
                    ],
                    search_params={"limit": 1},
                    next_page_token="token-3",
                )
                third = SearchResult(
                    [EOProduct("provider", {"id": "third", "geometry": "POINT (0 0)"})]
                )
                first._dag = second._dag = gateway
                gateway._do_search.side_effect = [second, third]
                self.assertEqual(list(first.next_page(update=update)), [second, third])
                self.assertEqual(len(first), 3 if update else 1)
                self.assertEqual(first.next_page_token, None if update else "token")

    def test_search_result_init(self):
        """SearchResult.init must preserve search parameters independently of products"""
        # product with federation:backends
        product = EOProduct(
            provider=None,
            properties={
                "geometry": "POINT (0 0)",
                "federation:backends": ["backend-1"],
            },
        )

        search_result = SearchResult(
            [product],
            number_matched=42,
            errors=[("provider", Exception("boom"))],
            search_params={"start_datetime": "2025-01-01T00:00:00Z"},
            next_page_token="token",
            next_page_token_key="pageToken",
            raise_errors=True,
        )

        self.assertEqual(search_result.number_matched, 42)
        self.assertEqual(len(search_result.errors), 1)
        self.assertEqual(search_result.errors[0][0], "provider")
        self.assertIsInstance(search_result.errors[0][1], Exception)
        self.assertEqual(
            search_result.search_params,
            {
                "start_datetime": "2025-01-01T00:00:00Z",
            },
        )
        self.assertEqual(search_result.next_page_token, "token")
        self.assertEqual(search_result.next_page_token_key, "pageToken")
        self.assertTrue(search_result.raise_errors)

        # product without federation:backends
        product = EOProduct(
            provider=None,
            properties={
                "geometry": "POINT (0 0)",
                "instruments": ["i1"],
            },
        )

        search_result = SearchResult(
            [product],
            number_matched=42,
            errors=[],
            search_params={"page": 2},
            next_page_token="token",
            next_page_token_key="pageToken",
            raise_errors=False,
        )

        self.assertEqual(search_result.number_matched, 42)
        self.assertEqual(len(search_result.errors), 0)
        self.assertEqual(search_result.search_params, {"page": 2})
        self.assertEqual(search_result.next_page_token, "token")
        self.assertEqual(search_result.next_page_token_key, "pageToken")
        self.assertFalse(search_result.raise_errors)

    def test_search_result_filter_online(self):
        """SearchResult.filter_online must only keep online results"""
        self.search_result2 = SearchResult(
            [
                EOProduct(
                    provider=None,
                    properties={"geometry": "POINT (0 0)", "order:status": "succeeded"},
                ),
                EOProduct(
                    provider=None,
                    properties={"geometry": "POINT (0 0)", "order:status": "orderable"},
                ),
            ]
        )
        filtered_products = self.search_result2.filter_online()
        origin_size = len(self.search_result2)
        filtered_size = len(filtered_products)
        self.assertFalse(origin_size == filtered_size)
        for product in filtered_products:
            assert product.properties["order:status"] == "succeeded"

    def test_search_result_geo_interface(self):
        """SearchResult must provide a FeatureCollection geo-interface"""
        geo_interface = geojson.loads(geojson.dumps(self.search_result))
        self.assertEqual(geo_interface["type"], "FeatureCollection")
        self.assertEqual(geo_interface["features"], [])

    def test_search_result_as_dict(self):
        geojson_object = self.search_result.as_dict()
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

    def test_search_result_as_pystac_object(self):
        pystac_object = self.search_result.as_pystac_object()
        self.assertIsInstance(pystac_object, ItemCollection)

    def test_search_result_is_list_like(self):
        """SearchResult must provide a list interface"""
        self.assertIsInstance(self.search_result, UserList)

    def test_search_result_from_feature_collection(self):
        """SearchResult instances must be build-able from feature collection geojson"""
        same_search_result = SearchResult.from_dict(
            geojson.loads(geojson.dumps(self.search_result))
        )
        self.assertEqual(len(same_search_result), len(self.search_result))

    def test_search_result_from_pystac(self):
        """SearchResult instances must be build-able from feature collection geojson"""
        same_search_result = SearchResult.from_pystac(
            ItemCollection.from_dict(self.search_result.as_dict())
        )
        self.assertEqual(len(same_search_result), len(self.search_result))

    def test_search_result_repr_html(self):
        """SearchResult html repr must be correctly formatted"""
        sr_repr = html.fromstring(self.search_result._repr_html_())
        self.assertIn("SearchResult", sr_repr.xpath("//thead/tr/td")[0].text)

    def test_search_result_errors(self):
        """SearchResult instances must store search errors"""
        self.assertEqual(self.search_result.errors, [])
        self.search_result.errors.append(["foo", Exception("1st exception")])
        self.search_result.errors.append(["bar", Exception("2nd exception")])
        self.assertEqual(len(self.search_result.errors), 2)
        self.assertEqual(SearchResult([]).errors, [])
