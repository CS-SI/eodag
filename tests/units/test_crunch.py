# -*- coding: utf-8 -*-
# Copyright 2026, CS GROUP - France, http://www.c-s.fr
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
from typing import Any
from unittest import mock

import dateutil
import shapely
from shapely import Polygon, geometry
from shapely.errors import ShapelyError

from eodag.api.product import EOProduct
from eodag.api.search_result import SearchResult
from eodag.crunch import (
    FilterDate,
    FilterLatestByName,
    FilterLatestIntersect,
    FilterOverlap,
    FilterProperty,
)
from eodag.plugins.crunch import Crunch
from eodag.utils import DEFAULT_SHAPELY_GEOMETRY
from eodag.utils.exceptions import ValidationError


class TestPluginCrunch(unittest.TestCase):

    __product_id: int = 0

    def __fake_search_result(
        self, products_properties: list[dict[str, Any]]
    ) -> SearchResult:
        """Mock search result"""
        search_results = []
        for product_properties in products_properties:
            TestPluginCrunch.__product_id += 1
            properties = {
                "id": "fake_{}".format(TestPluginCrunch.__product_id),
                "geometry": DEFAULT_SHAPELY_GEOMETRY,
            }
            for key in product_properties:
                properties[key] = product_properties[key]

            search_results.append(
                EOProduct(
                    provider="fake_provider",
                    properties=properties,
                    collection="fake_collection",
                )
            )

        return SearchResult(search_results)

    def test_crunch_base(self):
        """Crunch base test"""
        crunch = Crunch({})
        products: list[EOProduct] = []
        try:
            crunch.proceed(products)
            self.fail("Abstract class Crunch must not be instantiable")
        except NotImplementedError:
            pass
        except Exception as error:
            self.fail(
                "Unexpected error when try to instanciate abstract class Crunch: {error}".format(
                    error=error
                )
            )

    def test_crunch_filterdate(self):
        """Crunch FilterDate test"""
        # No products to filter
        search_results: SearchResult = self.__fake_search_result([])
        filtered_result = search_results.crunch(
            FilterDate(dict(start="2025-01-15", end="2025-01-15"))
        )
        self.assertEqual(len(filtered_result), 0)

        # Some products to filter
        search_results = self.__fake_search_result(
            [
                {"start_datetime": "2025-01-16", "end_datetime": "2025-01-16"},
                {"start_datetime": "2025-01-16", "end_datetime": "2025-01-17"},
                {"start_datetime": "2025-01-17", "end_datetime": "2025-01-17"},
                {"start_datetime": "2025-01-17", "end_datetime": "2025-01-18"},
                {"start_datetime": "2025-01-17", "end_datetime": "2025-01-19"},
            ]
        )
        self.assertEqual(len(search_results), 5)

        # Full filter

        filtered_result = search_results.crunch(
            FilterDate(dict(start="2025-01-15", end="2025-01-15"))
        )
        self.assertEqual(len(filtered_result), 0)

        filtered_result = search_results.crunch(
            FilterDate(dict(start="2025-01-16 00:00:00", end="2025-01-16 23:59:59"))
        )
        self.assertEqual(len(filtered_result), 1)

        filtered_result = search_results.crunch(
            FilterDate(dict(start="2025-01-16", end="2025-01-16"))
        )
        self.assertEqual(len(filtered_result), 1)

        filtered_result = search_results.crunch(
            FilterDate(dict(start="2025-01-16", end="2025-01-17"))
        )

        self.assertEqual(len(filtered_result), 3)

        filtered_result = search_results.crunch(
            FilterDate(dict(start="2025-01-16", end="2025-01-18"))
        )
        self.assertEqual(len(filtered_result), 4)

        # Partial filter

        filtered_result = search_results.crunch(FilterDate(dict(start="2025-01-17")))
        self.assertEqual(len(filtered_result), 3)

        filtered_result = search_results.crunch(FilterDate(dict(end="2025-01-18")))
        self.assertEqual(len(filtered_result), 4)

        # No filters
        filtered_result = search_results.crunch(FilterDate())
        self.assertEqual(len(filtered_result), 5)

        # Wrong filter (invalid date order)
        filtered_result = search_results.crunch(
            FilterDate(dict(start="2025-01-17", end="2025-01-16"))
        )
        self.assertEqual(len(filtered_result), 0)

        # Invalid filter
        try:
            filtered_result = search_results.crunch(
                FilterDate(dict(start="invalid_date", end="2025-01-18"))
            )
            self.fail("Must not let pass invalid date format")
        except dateutil.parser._parser.ParserError:
            pass

        try:
            filtered_result = search_results.crunch(
                FilterDate(dict(start="2025-01-16", end="wrong_date"))
            )
            self.fail("Must not let pass invalid date format")
        except dateutil.parser._parser.ParserError:
            pass

        # Uncomplete products
        search_results = self.__fake_search_result(
            [
                {"start_datetime": None, "end_datetime": "2025-01-16"},
                {"start_datetime": "2025-01-16", "end_datetime": "2025-01-17"},
                {"start_datetime": "2025-01-17", "end_datetime": None},
                {"start_datetime": "2025-01-17", "end_datetime": "2025-01-18"},
                {"start_datetime": None, "end_datetime": None},
            ]
        )

        filtered_result = search_results.crunch(
            FilterDate(dict(start="2025-01-15", end="2025-01-15"))
        )
        self.assertEqual(len(filtered_result), 1)

        filtered_result = search_results.crunch(FilterDate(dict(start="2025-01-17")))
        self.assertEqual(len(filtered_result), 4)

        filtered_result = search_results.crunch(FilterDate(dict(end="2025-01-18")))
        self.assertEqual(len(filtered_result), 5)

    def test_crunch_filterdate_sort(self):
        """Crunch FilterDate.sort_product_by_start_date test"""

        # sort_product_by_start_date
        products = self.__fake_search_result(
            [
                {"start_datetime": "2025-01-18", "end_datetime": "2025-01-18"},
                {"start_datetime": "2025-01-16", "end_datetime": "2025-01-16"},
                {"start_datetime": "2025-01-17", "end_datetime": "2025-01-17"},
            ]
        )
        products.sort(key=FilterDate.sort_product_by_start_date)
        self.assertEqual(products[0].properties["start_datetime"], "2025-01-16")
        self.assertEqual(products[1].properties["start_datetime"], "2025-01-17")
        self.assertEqual(products[2].properties["start_datetime"], "2025-01-18")

        products.sort(key=FilterDate.sort_product_by_start_date, reverse=True)
        self.assertEqual(products[0].properties["start_datetime"], "2025-01-18")
        self.assertEqual(products[1].properties["start_datetime"], "2025-01-17")
        self.assertEqual(products[2].properties["start_datetime"], "2025-01-16")

        products = self.__fake_search_result(
            [
                {"start_datetime": "2025-01-18", "end_datetime": "2025-01-18"},
                {"start_datetime": None, "end_datetime": "2025-01-16"},
                {"start_datetime": "2025-01-17", "end_datetime": "2025-01-17"},
            ]
        )
        products.sort(key=FilterDate.sort_product_by_start_date, reverse=False)
        self.assertEqual(products[0].properties.get("start_datetime", None), None)
        self.assertEqual(
            products[1].properties.get("start_datetime", None), "2025-01-17"
        )
        self.assertEqual(
            products[2].properties.get("start_datetime", None), "2025-01-18"
        )

    def test_crunch_latest_intersect(self):
        """Crunch FilterLatestIntersect test"""

        # No products to filter
        search_results: SearchResult = self.__fake_search_result([])
        filtered_result = search_results.crunch(FilterLatestIntersect())
        self.assertEqual(len(filtered_result), 0)

        # Some product filter
        search_results = self.__fake_search_result(
            [
                {"geometry": geometry.box(10, 20, 15, 30)},
                {"geometry": geometry.box(10, 30, 15, 40)},
                {"geometry": geometry.box(15, 20, 20, 30)},
                {"geometry": geometry.box(15, 30, 20, 40)},
            ]
        )

        # No filter
        filtered_result = search_results.crunch(FilterLatestIntersect())
        self.assertEqual(len(filtered_result), 4)

        # invalid filter geometry, ignore filter
        filtered_result = search_results.crunch(
            FilterLatestIntersect(), geometry="hell_wrong_geometry"
        )
        self.assertEqual(len(filtered_result), 4)

        # Mismatch filter

        filtered_result = search_results.crunch(
            FilterLatestIntersect(), geometry=geometry.box(0, 0, 0, 0)
        )
        self.assertEqual(len(filtered_result), 0)

        filtered_result = search_results.crunch(
            FilterLatestIntersect(),
            geometry={"lonmin": 0, "latmin": 0, "lonmax": 0, "latmax": 0},
        )
        self.assertEqual(len(filtered_result), 0)

        filtered_result = search_results.crunch(
            FilterLatestIntersect(),
            geometry=Polygon(((0, 0), (0, 1), (1, 1), (1, 0), (0, 0))),
        )
        self.assertEqual(len(filtered_result), 0)

    def test_crunch_latest_intersect_sort(self):
        """Crunch FilterLatestIntersect.sort_product_by_start_date test"""

        # sort_product_by_start_date
        products = self.__fake_search_result(
            [
                {"start_datetime": "2025-01-18", "end_datetime": "2025-01-18"},
                {"start_datetime": "2025-01-16", "end_datetime": "2025-01-16"},
                {"start_datetime": "2025-01-17", "end_datetime": "2025-01-17"},
            ]
        )
        products.sort(key=FilterLatestIntersect.sort_product_by_start_date)
        self.assertEqual(products[0].properties["start_datetime"], "2025-01-16")
        self.assertEqual(products[1].properties["start_datetime"], "2025-01-17")
        self.assertEqual(products[2].properties["start_datetime"], "2025-01-18")

        products.sort(
            key=FilterLatestIntersect.sort_product_by_start_date, reverse=True
        )
        self.assertEqual(products[0].properties["start_datetime"], "2025-01-18")
        self.assertEqual(products[1].properties["start_datetime"], "2025-01-17")
        self.assertEqual(products[2].properties["start_datetime"], "2025-01-16")

        products = self.__fake_search_result(
            [
                {"start_datetime": "2025-01-18", "end_datetime": "2025-01-18"},
                {"start_datetime": None, "end_datetime": "2025-01-16"},
                {"start_datetime": "2025-01-17", "end_datetime": "2025-01-17"},
            ]
        )
        products.sort(
            key=FilterLatestIntersect.sort_product_by_start_date, reverse=False
        )
        self.assertEqual(products[0].properties.get("start_datetime", None), None)
        self.assertEqual(
            products[1].properties.get("start_datetime", None), "2025-01-17"
        )
        self.assertEqual(
            products[2].properties.get("start_datetime", None), "2025-01-18"
        )

    def test_crunch_lastestbyname(self):
        """Crunch FilterLatestByName test"""

        # Missing parameter
        search_results: SearchResult = self.__fake_search_result([])
        try:
            _ = search_results.crunch(FilterLatestByName())
            self.fail('FilterLatestByName require parameter "name_pattern"')
        except ValidationError:
            pass

        # Invalid pattern
        try:
            _ = search_results.crunch(
                FilterLatestByName({"name_pattern": "hell_pattern!"})
            )
            self.fail('FilterLatestByName require valid parameter "name_pattern"')
        except ValidationError:
            pass

        # No products
        filter_products = search_results.crunch(
            FilterLatestByName({"name_pattern": "(?P<tileid>\\d{6})"})
        )
        self.assertEqual(len(filter_products), 0)

        # Some products to filter
        search_results = self.__fake_search_result(
            [
                {"start_datetime": "2025-01-18", "title": "000001"},
                {"start_datetime": "2025-01-18", "title": "000002"},
                {"start_datetime": "2025-01-19", "title": "000003"},
                {"start_datetime": "2025-01-19", "title": "000004"},
                {"start_datetime": "2025-01-20", "title": "000005"},
            ]
        )
        filter_products = search_results.crunch(
            FilterLatestByName({"name_pattern": "(?P<tileid>\\d{6})"})
        )
        self.assertEqual(len(filter_products), 5)

        # Some products to filter with mixed title
        search_results = self.__fake_search_result(
            [
                {"start_datetime": "2025-01-18", "title": "malformed"},
                {"start_datetime": "2025-01-18", "title": "000002"},
                {"start_datetime": "2025-01-19", "title": "malformed"},
                {"start_datetime": "2025-01-19", "title": "000004"},
                {"start_datetime": "2025-01-20", "title": "malformed"},
            ]
        )
        filter_products = search_results.crunch(
            FilterLatestByName({"name_pattern": "(?P<tileid>\\d{6})"})
        )
        self.assertEqual(len(filter_products), 2)

        # Some products to filter with mixed title, repeated formatted title
        search_results = self.__fake_search_result(
            [
                {"start_datetime": "2025-01-18", "title": "malformed"},
                {"start_datetime": "2025-01-18", "title": "000002"},
                {"start_datetime": "2025-01-19", "title": "malformed"},
                {"start_datetime": "2025-01-19", "title": "000002"},
                {"start_datetime": "2025-01-20", "title": "malformed"},
            ]
        )
        filter_products = search_results.crunch(
            FilterLatestByName({"name_pattern": "(?P<tileid>\\d{6})"})
        )
        self.assertEqual(len(filter_products), 1)

    def test_crunch_overlap(self):
        """Crunch FilterOverlap test"""

        # No products, no configuration
        search_results: SearchResult = self.__fake_search_result([])
        filtered_result = search_results.crunch(FilterOverlap())
        self.assertEqual(len(filtered_result), 0)

        filtered_result = search_results.crunch(
            FilterOverlap(), geometry=geometry.box(0, 0, 0, 0)
        )
        self.assertEqual(len(filtered_result), 0)

        # Invalid configuration
        search_results = self.__fake_search_result(
            [
                {"geometry": geometry.box(10, 20, 15, 30)},
                {"geometry": geometry.box(10, 30, 15, 40)},
                {"geometry": geometry.box(15, 20, 20, 30)},
                {"geometry": geometry.box(15, 30, 20, 40)},
            ]
        )
        filtered_result = search_results.crunch(
            FilterOverlap(
                {
                    "minimum_overlap": -1,  # min: 0
                    "contains": False,
                    "intersects": False,
                    "within": False,
                }
            ),
            geometry=geometry.box(0, 0, 0, 0),
        )
        self.assertEqual(len(filtered_result), 0)

        filtered_result = search_results.crunch(
            FilterOverlap(
                {
                    "minimum_overlap": "hell_minimum!",
                    "contains": False,
                    "intersects": False,
                    "within": False,
                }
            ),
            geometry=geometry.box(0, 0, 0, 0),
        )
        self.assertEqual(len(filtered_result), 0)

        # Parameters exclusion (contains, intersects, within)
        filtered_result = search_results.crunch(
            FilterOverlap(
                {
                    "minimum_overlap": 100,
                    "contains": True,
                    "intersects": True,
                    "within": False,
                }
            ),
            geometry=geometry.box(0, 0, 0, 0),
        )
        self.assertEqual(len(filtered_result), 4)

        filtered_result = search_results.crunch(
            FilterOverlap(
                {
                    "minimum_overlap": 100,
                    "contains": True,
                    "intersects": False,
                    "within": True,
                }
            ),
            geometry=geometry.box(0, 0, 0, 0),
        )
        self.assertEqual(len(filtered_result), 4)

        filtered_result = search_results.crunch(
            FilterOverlap(
                {
                    "minimum_overlap": 100,
                    "contains": False,
                    "intersects": True,
                    "within": True,
                }
            ),
            geometry=geometry.box(0, 0, 0, 0),
        )
        self.assertEqual(len(filtered_result), 4)

        # Intersect
        filtered_result = search_results.crunch(
            FilterOverlap(
                {
                    "minimum_overlap": 95,
                    "contains": False,
                    "intersects": True,
                    "within": False,
                }
            ),
            geometry=geometry.box(12, 25, 13, 35),
        )
        self.assertEqual(len(filtered_result), 2)

        # Contains
        filtered_result = search_results.crunch(
            FilterOverlap(
                {
                    "minimum_overlap": 100,
                    "contains": True,
                    "intersects": False,
                    "within": False,
                }
            ),
            geometry=geometry.box(12, 25, 13, 35),
        )
        self.assertEqual(len(filtered_result), 0)

        # Contains
        filtered_result = search_results.crunch(
            FilterOverlap(
                {
                    "minimum_overlap": 100,
                    "contains": True,
                    "intersects": False,
                    "within": False,
                }
            ),
            geometry=geometry.box(12, 21, 13, 29),
        )
        self.assertEqual(len(filtered_result), 1)

        # Within
        filtered_result = search_results.crunch(
            FilterOverlap(
                {
                    "minimum_overlap": 100,
                    "contains": False,
                    "intersects": False,
                    "within": True,
                }
            ),
            geometry=geometry.box(9, 19, 16, 31),
        )
        self.assertEqual(len(filtered_result), 1)

        # Search geom area = 0
        geom = Polygon(((10, 20), (15, 30), (15, 20), (10, 30), (10, 20)))
        self.assertFalse(geom.is_valid)
        search_results = self.__fake_search_result(
            [
                {"geometry": geometry.box(10, 20, 15, 30)},
                {"geometry": geometry.box(10, 30, 15, 40)},
                {"geometry": geometry.box(15, 20, 20, 30)},
                {"geometry": geometry.box(15, 30, 20, 40)},
            ]
        )
        filtered_result = search_results.crunch(
            FilterOverlap(
                {
                    "minimum_overlap": 50,
                    "contains": False,
                    "intersects": True,
                    "within": False,
                }
            ),
            geometry=geometry.box(10, 30, 10, 30),
        )
        self.assertEqual(len(filtered_result), 0)

        # Product invalid geometry (butterfly shape) recoverable
        geom = Polygon(((10, 20), (15, 30), (15, 20), (10, 30), (10, 20)))
        self.assertFalse(geom.is_valid)
        search_results = self.__fake_search_result([{"geometry": geom}])
        filter = FilterOverlap(
            {
                "minimum_overlap": 50,
                "contains": False,
                "intersects": True,
                "within": False,
            }
        )

        # Disable search intersection to test invalid geom
        for index in range(0, len(search_results)):
            search_results[index].search_intersection = None

        filtered_result = search_results.crunch(
            filter, geometry=geometry.box(10, 30, 20, 40)
        )
        self.assertEqual(len(filtered_result), 1)

        # Force fail search_geom intersection
        def shapely_intersect_forced_exception(a, b, grid_size=None, **kwargs):
            print("Mocked: no shapely.intersection allowed")
            raise ShapelyError("No intersection allowed")

        with mock.patch.object(
            shapely, "intersection", new=shapely_intersect_forced_exception
        ):
            filtered_result = search_results.crunch(
                filter, geometry=geometry.box(10, 30, 20, 40)
            )
            self.assertEqual(len(filtered_result), 0)

    def test_crunch_property(self):
        """Crunch FilterProperty test"""

        # No configuration
        search_results = self.__fake_search_result(
            [
                {"myproperty": 1},
                {"myproperty": 2},
                {"myproperty": 3},
                {"myproperty": 4},
                {"myproperty": 5},
            ]
        )
        filtered_result = search_results.crunch(FilterProperty({}))
        self.assertEqual(len(filtered_result), 5)

        # Partial configuration
        filtered_result = search_results.crunch(FilterProperty({"myproperty": 3}))
        self.assertEqual(len(filtered_result), 1)

        filtered_result = search_results.crunch(FilterProperty({"myproperty": 6}))
        self.assertEqual(len(filtered_result), 0)

        # Wrong configuration
        filtered_result = search_results.crunch(
            FilterProperty({"myproperty": 6, "operator": "hell"})
        )
        self.assertEqual(len(filtered_result), 5)

        # Full configuration
        for test in [
            {"value": 2, "operator": "lt", "expect_results": 1},
            {"value": 2, "operator": "le", "expect_results": 2},
            {"value": 2, "operator": "eq", "expect_results": 1},
            {"value": 2, "operator": "ne", "expect_results": 4},
            {"value": 2, "operator": "ge", "expect_results": 4},
            {"value": 2, "operator": "gt", "expect_results": 3},
            {"value": 4, "operator": "lt", "expect_results": 3},
            {"value": 4, "operator": "le", "expect_results": 4},
            {"value": 4, "operator": "eq", "expect_results": 1},
            {"value": 4, "operator": "ne", "expect_results": 4},
            {"value": 4, "operator": "ge", "expect_results": 2},
            {"value": 4, "operator": "gt", "expect_results": 1},
        ]:
            filtered_result = search_results.crunch(
                FilterProperty(
                    {"myproperty": test["value"], "operator": test["operator"]}
                )
            )
            self.assertEqual(len(filtered_result), test["expect_results"])

        # Multitypes data
        search_results = self.__fake_search_result(
            [
                {"myproperty": 1},
                {"myproperty": "2"},
                {"myproperty": bool},
                {"myproperty": None},
                {"myproperty": 5},
            ]
        )
        filtered_result = search_results.crunch(FilterProperty({"myproperty": 3}))
        self.assertEqual(len(filtered_result), 0)

        filtered_result = search_results.crunch(FilterProperty({"myproperty": 2}))
        self.assertEqual(len(filtered_result), 0)

        filtered_result = search_results.crunch(FilterProperty({"myproperty": "2"}))
        self.assertEqual(len(filtered_result), 1)

        filtered_result = search_results.crunch(FilterProperty({"myproperty": None}))
        self.assertEqual(len(filtered_result), 1)

        # Mismatch filter value type makes no filter wihtout error
        filtered_result = search_results.crunch(FilterProperty({"myproperty": True}))
        self.assertEqual(len(filtered_result), 1)

        # Multitypes data with operator set
        for value in [42, "myvalue", True]:
            for test in [
                {"operator": "lt", "expect_match": False},  # Lower (False)
                {"operator": "le", "expect_match": True},  # Lower(False) + Equal(True)
                {"operator": "eq", "expect_match": True},  # Equal(True)
                {"operator": "ne", "expect_match": False},  # Non Equal(False)
                {
                    "operator": "ge",
                    "expect_match": True,
                },  # Greater(False) + Equal(True)
                {"operator": "gt", "expect_match": False},  # Greater(False)
            ]:
                search_results = self.__fake_search_result([{"myproperty": value}])
                filtered_result = search_results.crunch(
                    FilterProperty({"myproperty": value, "operator": test["operator"]})
                )
                self.assertEqual(len(filtered_result) == 1, test["expect_match"])
