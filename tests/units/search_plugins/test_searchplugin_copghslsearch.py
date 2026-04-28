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
from tempfile import TemporaryDirectory
from typing import Literal
from unittest import mock

from typing_extensions import get_args

from eodag.plugins.search import PreparedSearch
from eodag.plugins.search.cop_ghsl import (
    _convert_bbox_to_lonlat_EPSG3035,
    _convert_bbox_to_lonlat_mollweide,
    _get_available_values_from_constraints,
    _replace_datetimes,
)
from eodag.utils import USER_AGENT, deepcopy, get_geometry_from_various
from eodag.utils.exceptions import ValidationError
from tests.units.search_plugins.base import BaseSearchPluginTest
from tests.units.search_plugins.mock_response import MockResponse


class TestSearchPluginCopGhslSearch(BaseSearchPluginTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Mock home and eodag conf directory to tmp dir
        cls.tmp_home_dir = TemporaryDirectory()
        cls.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, return_value=cls.tmp_home_dir.name
        )
        cls.expanduser_mock.start()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        # stop Mock and remove tmp config dir
        cls.expanduser_mock.stop()
        cls.tmp_home_dir.cleanup()

    def setUp(self):
        super(TestSearchPluginCopGhslSearch, self).setUp()
        self.constraints = [
            {
                "year": ["2000", "2005", "2010"],
                "proj:code": ["EPSG:54009"],
                "tile_size": ["10m"],
            },
            {
                "year": ["2000", "2005", "2010"],
                "proj:code": ["EPSG:4326"],
                "tile_size": ["3ss"],
            },
        ]

    def test_plugins_search_cop_ghsl_convert_bbox(self):
        """test if bboxes given in letres are converted correctly to degrees"""
        # Mollweide coordinate system (ESRI:54009)
        bbox_mollweide = ["-6 041 000", "7 000 000", "-5 041 000", "6 000 000"]
        bbox_degrees = _convert_bbox_to_lonlat_mollweide(bbox_mollweide)
        expected_bbox = [-95.57, 61.3, -67.36, 51.21]
        for i, num in enumerate(bbox_degrees):
            self.assertEqual(expected_bbox[i], round(num, 2))
        # Mollweide point outside of map
        bbox_mollweide = ["-6 041 000", "9 000 000", "-5 041 000", "8 000 000"]
        bbox_degrees = _convert_bbox_to_lonlat_mollweide(bbox_mollweide)
        expected_bbox = [-180, 89.09, -108.89, 72.77]
        for i, num in enumerate(bbox_degrees):
            self.assertEqual(expected_bbox[i], round(num, 2))

        # ETRS89/LAEA Europe coordinate system (EPSG:3035)
        bbox_3035 = ["1,944,000", "1,042,000", "2,044,000", "942,000"]
        bbox_degrees = _convert_bbox_to_lonlat_EPSG3035(bbox_3035)
        expected_bbox = [-14.34, 28.99, -13.11, 28.39]
        for i, num in enumerate(bbox_degrees):
            self.assertEqual(expected_bbox[i], round(num, 2))
        bbox_3035 = ["4,744,000", "1,542,000", "4,844,000", "1,442,000"]
        bbox_degrees = _convert_bbox_to_lonlat_EPSG3035(bbox_3035)
        expected_bbox = [14.7, 36.83, 15.74, 35.86]
        for i, num in enumerate(bbox_degrees):
            self.assertEqual(expected_bbox[i], round(num, 2))

    def test_plugins_search_cop_ghsl_get_available_values_from_constraints(self):
        """test if get_available_values_from_contraints returns the available values for
        the given filters based on the given constraints and throws an error if no values are available"""
        # invalid parameter in filter
        with self.assertRaises(ValidationError):
            _get_available_values_from_constraints(
                self.constraints, {"bla": "1", "year": "2000"}, "PT1"
            )
        # invalid value for parameter
        with self.assertRaises(ValidationError):
            _get_available_values_from_constraints(
                self.constraints,
                {"proj:code": "EPSG:54009", "year": "2020", "tile_size": "10m"},
                "PT1",
            )
        # invalid combination
        with self.assertRaises(ValidationError):
            _get_available_values_from_constraints(
                self.constraints,
                {"proj:code": "EPSG:54009", "year": "2000", "tile_size": "3ss"},
                "PT1",
            )
        # timespan without valid value for year
        with self.assertRaises(ValidationError):
            _get_available_values_from_constraints(
                self.constraints,
                {
                    "proj:code": "EPSG:54009",
                    "year": ["2011", "2012"],
                    "tile_size": "10m",
                },
                "PT1",
            )

        # valid request for one year
        available_values = _get_available_values_from_constraints(
            self.constraints,
            {"proj:code": "EPSG:54009", "year": "2000", "tile_size": "10m"},
            "PT1",
        )
        expected_available = {
            "year": ["2000", "2005", "2010"],
            "proj:code": ["EPSG:54009"],
            "tile_size": ["10m"],
        }
        self.assertDictEqual(expected_available, available_values)
        # valid request for a time span
        available_values = _get_available_values_from_constraints(
            self.constraints,
            {
                "proj:code": "EPSG:54009",
                "year": ["1999", "2000", "2001"],
                "tile_size": "10m",
            },
            "PT1",
        )
        expected_available = {
            "year": ["2000"],
            "proj:code": ["EPSG:54009"],
            "tile_size": ["10m"],
        }
        self.assertDictEqual(expected_available, available_values)

    def test_plugins_search_cop_ghsl_replace_datetimes(self):
        """test replacement of datetime parameters in the request by year/month
        months should only be calculated if start year and end year are the same
        """
        # no year given, timespan for several years
        params = {
            "start_datetime": "2020-01-01T00:00:00Z",
            "end_datetime": "2023-01-01T00:00:00Z",
        }
        _replace_datetimes(params)
        self.assertIn("year", params)
        self.assertListEqual(["2020", "2021", "2022", "2023"], params["year"])
        # different date format
        params = {"start_datetime": "2020-01-01", "end_datetime": "2023-01-01"}
        _replace_datetimes(params)
        self.assertIn("year", params)
        self.assertListEqual(["2020", "2021", "2022", "2023"], params["year"])
        # datetimes and year given -> keep year
        params = {
            "start_datetime": "2020-01-01T00:00:00Z",
            "end_datetime": "2023-01-01T00:00:00Z",
            "year": "2019",
        }
        _replace_datetimes(params)
        self.assertIn("year", params)
        self.assertEqual("2019", params["year"])

        # one year -> include months
        params = {
            "start_datetime": "2020-08-01T00:00:00Z",
            "end_datetime": "2020-11-01T00:00:00Z",
        }
        _replace_datetimes(params)
        self.assertIn("year", params)
        self.assertListEqual(["2020"], params["year"])
        self.assertIn("month", params)
        self.assertListEqual(["08", "09", "10", "11"], params["month"])

    @mock.patch("eodag.plugins.search.cop_ghsl.CopGhslSearch._fetch_constraints")
    def test_plugins_search_cop_ghsl_check_input_parameters_valid(
        self, mock_fetch_constraints
    ):
        """test if the input parameters are correctly validated"""
        mock_fetch_constraints.return_value = {"constraints": self.constraints}
        plugin = next(self.plugins_manager.get_search_plugins(provider="cop_ghsl"))
        # missing parameter
        input_params = {"year": "2020", "proj:code": "EPSG:54009"}
        with self.assertRaises(ValidationError):
            plugin._check_input_parameters_valid("PT1", input_params)

        # valid input with one year
        input_params = {"year": "2000", "proj:code": "EPSG:54009", "tile_size": "10m"}
        plugin._check_input_parameters_valid(
            "PT1", input_params
        )  # nothing should be raised
        # valid input several years
        input_params = {
            "year": ["1999", "2000", "2001"],
            "proj:code": "EPSG:54009",
            "tile_size": "10m",
        }
        plugin._check_input_parameters_valid("PT1", input_params)
        expected_params = {
            "year": ["2000"],
            "proj:code": "EPSG:54009",
            "tile_size": "10m",
        }
        # year in input params should be updated
        self.assertDictEqual(expected_params, input_params)

        # valid input with grouped_by param
        constraints = [
            {
                "year": ["2000", "2005", "2010"],
                "month": ["01", "02", "03"],
                "proj:code": ["EPSG:54009"],
                "tile_size": ["10m"],
            },
            {
                "year": ["2000", "2005", "2010"],
                "month": ["01", "02", "03"],
                "proj:code": ["EPSG:4326"],
                "tile_size": ["3ss"],
            },
        ]
        mock_fetch_constraints.return_value = {"constraints": constraints}
        input_params = {
            "year": "2000",
            "month": ["02", "03", "04"],
            "proj:code": "EPSG:54009",
            "tile_size": "10m",
            "grouped_by": "month",
        }
        plugin._check_input_parameters_valid("PT1", input_params)
        expected_params = {
            "year": "2000",
            "month": ["02", "03"],
            "proj:code": "EPSG:54009",
            "tile_size": "10m",
        }
        self.assertDictEqual(expected_params, input_params)
        # valid input with grouped_by param, grouping param not given
        input_params = {
            "year": "2000",
            "proj:code": "EPSG:54009",
            "tile_size": "10m",
            "grouped_by": "month",
        }
        plugin._check_input_parameters_valid("PT1", input_params)
        expected_params = {
            "year": "2000",
            "month": ["01", "02", "03"],
            "proj:code": "EPSG:54009",
            "tile_size": "10m",
        }
        self.assertDictEqual(expected_params, input_params)

    @mock.patch("eodag.plugins.search.cop_ghsl.CopGhslSearch._fetch_constraints")
    @mock.patch("eodag.plugins.search.cop_ghsl.requests.get")
    def test_plugins_search_cop_ghsl_get_tiles_for_filters(
        self, mock_requests_get, mock_fetch_constraints
    ):
        mock_fetch_constraints.return_value = {"constraints": self.constraints}
        provider_tiles = {
            "grid": [
                {
                    "tileID": "R3_C3",
                    "BBox": ["-160.008", "69.100", "-150.008", "59.100"],
                },
                {
                    "tileID": "R3_C4",
                    "BBox": ["-150.008", "69.100", "-140.008", "59.100"],
                },
                {
                    "tileID": "R3_C5",
                    "BBox": ["-140.008", "69.100", "-130.008", "59.100"],
                },
                {
                    "tileID": "R3_C6",
                    "BBox": ["-130.008", "69.100", "-120.008", "59.100"],
                },
            ],
            "unit": "lat/lon",
        }
        mock_requests_get.return_value = MockResponse(
            json_data=provider_tiles, status_code=200
        )
        collection = "GHS_BUILT_S"
        plugin = next(
            self.plugins_manager.get_search_plugins(
                collection=collection, provider="cop_ghsl"
            )
        )
        product_type_config = deepcopy(plugin.config.products.get(collection, {}))
        input_params = {
            "year": ["2000", "2005"],
            "proj:code": "EPSG:4326",
            "tile_size": "3ss",
            "collection": collection,
        }
        tiles, unit = plugin._get_tiles_for_filters(product_type_config, input_params)
        self.assertEqual("lat/lon", unit)
        self.assertEqual(2, len(tiles))
        self.assertIn("2000", tiles)
        self.assertIn("2005", tiles)
        self.assertEqual(mock_requests_get.call_count, 2)
        ssl_verify = getattr(plugin.config, "ssl_verify", True)
        mock_requests_get.assert_has_calls(
            [
                mock.call(
                    "https://human-settlement.emergency.copernicus.eu/data/tilesDLD/tilesDLD_BUILT_2000_3ss_4326.json",
                    verify=ssl_verify,
                    timeout=5,
                    headers=USER_AGENT,
                ),
                mock.call(
                    "https://human-settlement.emergency.copernicus.eu/data/tilesDLD/tilesDLD_BUILT_2005_3ss_4326.json",
                    verify=ssl_verify,
                    timeout=5,
                    headers=USER_AGENT,
                ),
            ]
        )

    @mock.patch("eodag.plugins.search.cop_ghsl.CopGhslSearch._fetch_constraints")
    @mock.patch("eodag.plugins.search.cop_ghsl.requests.get")
    def test_plugins_search_cop_ghsl_get_tile_from_product_id(
        self, mock_requests_get, mock_fetch_constraints
    ):
        """test fetching a tile for a product id"""
        mock_fetch_constraints.return_value = {"constraints": self.constraints}
        provider_tiles = {
            "grid": [
                {
                    "tileID": "R3_C3",
                    "BBox": ["-160.008", "69.100", "-150.008", "59.100"],
                },
                {
                    "tileID": "R3_C4",
                    "BBox": ["-150.008", "69.100", "-140.008", "59.100"],
                },
                {
                    "tileID": "R3_C5",
                    "BBox": ["-140.008", "69.100", "-130.008", "59.100"],
                },
                {
                    "tileID": "R3_C6",
                    "BBox": ["-130.008", "69.100", "-120.008", "59.100"],
                },
            ],
            "unit": "lat/lon",
        }
        mock_requests_get.return_value = MockResponse(
            json_data=provider_tiles, status_code=200
        )
        collection = "GHS_BUILT_S"
        plugin = next(
            self.plugins_manager.get_search_plugins(
                collection=collection, provider="cop_ghsl"
            )
        )
        params = {
            "collection": collection,
            "id": "GHS_BUILT_S__4326_3ss_2000_NRES__R3_C4",
        }
        tile, unit = plugin._get_tile_from_product_id(params)
        self.assertEqual("lat/lon", unit)
        self.assertEqual(1, len(tile))
        self.assertEqual(1, len(tile["2000"]))
        self.assertEqual("R3_C4", tile["2000"][0]["tileID"])

    def test_plugins_search_cop_ghsl_create_products_from_tiles(self):
        """test the creation of products based on tiles returned by the provider"""
        tiles = {
            "2000": [
                {
                    "tileID": "R3_C3",
                    "BBox": ["-160.008", "69.100", "-150.008", "59.100"],
                },
                {
                    "tileID": "R3_C4",
                    "BBox": ["-150.008", "69.100", "-140.008", "59.100"],
                },
                {
                    "tileID": "R3_C5",
                    "BBox": ["-140.008", "69.100", "-130.008", "59.100"],
                },
                {
                    "tileID": "R3_C6",
                    "BBox": ["-130.008", "69.100", "-120.008", "59.100"],
                },
            ],
            "2005": [
                {
                    "tileID": "R3_C3",
                    "BBox": ["-160.008", "69.100", "-150.008", "59.100"],
                },
                {
                    "tileID": "R3_C4",
                    "BBox": ["-150.008", "69.100", "-140.008", "59.100"],
                },
                {
                    "tileID": "R3_C5",
                    "BBox": ["-140.008", "69.100", "-130.008", "59.100"],
                },
                {
                    "tileID": "R3_C6",
                    "BBox": ["-130.008", "69.100", "-120.008", "59.100"],
                },
            ],
        }
        collection = "GHS_BUILT_S"
        plugin = next(
            self.plugins_manager.get_search_plugins(
                collection=collection, provider="cop_ghsl"
            )
        )
        product_type_config = deepcopy(plugin.config.products.get(collection, {}))
        params = product_type_config
        params["year"] = ["2000", "2005"]
        params["proj:code"] = "EPSG:4326"
        params["tile_size"] = "3ss"
        params["classification"] = "TOTAL"
        params["per_page"] = 5
        params["page"] = 1
        products, count = plugin._create_products_from_tiles(
            tiles, "lat/lon", collection, params, "classification", need_count=True
        )
        self.assertEqual(8, count)
        self.assertEqual(5, len(products))
        properties = products[0].properties
        self.assertEqual("2000-01-01T00:00:00Z", properties["start_datetime"])
        self.assertEqual("2000-12-31T23:59:59Z", properties["end_datetime"])
        self.assertEqual("2000", properties["year"])
        self.assertEqual("EPSG:4326", properties["proj:code"])
        self.assertEqual(
            "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_BUILT_S_GLOBE_R2023A/"
            "GHS_BUILT_S_E2000_GLOBE_R2023A_4326_3ss/V1-0/tiles/GHS_BUILT_S_E2000_GLOBE_R2023A_4326_3ss_V1_0_R3_C3.zip",
            products[0].assets["download_link"]["href"],
        )
        geometry = get_geometry_from_various(
            geometry=["-160.008", "69.100", "-150.008", "59.100"]
        )
        self.assertEqual(geometry, products[0].geometry)

    def test_plugins_search_cop_ghsl_create_products_without_tiles(self):
        """test if products are created correctly for product types without tiles"""

        prep = PreparedSearch(limit=5)
        # product type with one file
        collection = "GHS_FUA"
        plugin = next(
            self.plugins_manager.get_search_plugins(
                collection=collection, provider="cop_ghsl"
            )
        )
        plugin.config.collection_config = {
            "collection": collection,
            "extent": {
                "temporal": {
                    "interval": [["2015-01-01T00:00:00Z", "2015-12-31T00:00:00Z"]]
                }
            },
        }
        products, count = plugin._create_products_without_tiles(collection, prep, {})
        self.assertEqual(1, count)
        self.assertEqual(1, len(products))
        properties = products[0].properties
        self.assertEqual("2015-01-01T00:00:00Z", properties["start_datetime"])
        self.assertEqual("2015-12-31T00:00:00Z", properties["end_datetime"])

        if "download_link" in products[0].assets:
            self.assertEqual(
                "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL//GHS_FUA_UCDB2015_GLOBE_R2019A"
                "/V1-0/GHS_FUA_UCDB2015_GLOBE_R2019A_54009_1K_V1_0.zip",
                products[0].assets["download_link"].get("href"),
            )
        # product type with several files
        collection = "GHS_UCDB_REGION"
        plugin = next(
            self.plugins_manager.get_search_plugins(
                collection=collection, provider="cop_ghsl"
            )
        )
        plugin.config.collection_config = {
            "collection": collection,
            "extent": {
                "temporal": {
                    "interval": [["1975-01-01T00:00:00Z", "2030-12-31T00:00:00Z"]]
                }
            },
        }
        # with filter for region
        products, count = plugin._create_products_without_tiles(
            collection, prep, {"region": "EUROPE", "grouped_by": "region"}
        )
        self.assertEqual(1, count)
        self.assertEqual(1, len(products))
        properties = products[0].properties
        self.assertEqual("1975-01-01T00:00:00Z", properties["start_datetime"])
        self.assertEqual("2030-12-31T00:00:00Z", properties["end_datetime"])
        self.assertEqual("EUROPE", properties["region"])
        if "download_link" in products[0].assets:
            self.assertEqual(
                "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_UCDB_GLOBE_R2024A/"
                + "GHS_UCDB_REGION_GLOBE_R2024A"
                "/GHS_UCDB_REGION_EUROPE_R2024A/V1-1/GHS_UCDB_REGION_EUROPE_R2024A_V1_1.zip",
                products[0].assets["download_link"].get("href"),
            )

        # product type with several files and assets
        collection = "GHS_ENACT_POP"
        plugin = next(
            self.plugins_manager.get_search_plugins(
                collection=collection, provider="cop_ghsl"
            )
        )
        filters = {
            "grouped_by": "month",
            "month": "02",
            "tile_size": "30ss",
            "proj:code": "EPSG:4326",
        }
        product_type_mapping = deepcopy(plugin.config.products.get(collection, {}))
        filters.update(product_type_mapping)
        products, count = plugin._create_products_without_tiles(
            collection, prep, filters
        )
        self.assertEqual(1, count)
        self.assertEqual(1, len(products))
        properties = products[0].properties
        self.assertEqual("2011-02-01T00:00:00Z", properties["start_datetime"])
        self.assertEqual("2011-02-28T23:59:59Z", properties["end_datetime"])
        self.assertEqual("2011", properties["year"])
        self.assertEqual("02", properties["month"])
        assets = products[0].assets
        self.assertEqual(3, len(assets))
        self.assertIn("day", assets)
        self.assertEqual(
            "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/ENACT/ENACT_POP_2011_EU28_R2020A"
            "/ENACT_POP_D022011_EU28_R2020A_4326_30ss/V1-0/ENACT_POP_D022011_EU28_R2020A_4326_30ss_V1_0.zip",
            assets["day"]["href"],
        )
        self.assertIn("night", assets)

    @mock.patch("eodag.plugins.search.cop_ghsl.CopGhslSearch._fetch_constraints")
    def test_plugins_search_cop_ghsl_discover_queryables(self, mock_fetch_constraints):
        """test that the correct queryables are returned"""
        mock_fetch_constraints.return_value = {"constraints": self.constraints}
        plugin = next(
            self.plugins_manager.get_search_plugins(
                collection="GHS_BUILT_S", provider="cop_ghsl"
            )
        )
        kwargs = {"collection": "GHS_BUILT_S"}
        collection_config = plugin.config.products.get("GHS_BUILT_S", {})
        kwargs.update(collection_config)
        if "metadata_mapping" in kwargs:
            kwargs.pop("metadata_mapping")
        if "assets_mapping" in kwargs:
            kwargs.pop("assets_mapping")
        queryables = plugin.discover_queryables(**kwargs)
        self.assertEqual(6, len(queryables))
        expected_queryables = [
            "year",
            "tile_size",
            "proj:code",
            "start",
            "end",
            "geom",
        ]
        for qu in expected_queryables:
            self.assertIn(qu, queryables)
        tile_size_queryable = queryables["tile_size"]
        self.assertIn(Literal["10m", "3ss"], get_args(tile_size_queryable))

        # test filtering queryables
        kwargs["proj:code"] = "EPSG:54009"
        queryables = plugin.discover_queryables(**kwargs)
        tile_size_queryable = queryables["tile_size"]
        self.assertIn(Literal["10m"], get_args(tile_size_queryable))
        # with array
        kwargs["proj:code"] = ["EPSG:54009"]
        queryables = plugin.discover_queryables(**kwargs)
        tile_size_queryable = queryables["tile_size"]
        self.assertIn(Literal["10m"], get_args(tile_size_queryable))

        # product type without geometry filter
        constraints = deepcopy(self.constraints)
        for constraint in constraints:
            constraint["year"] = ["2011"]
            constraint["month"] = ["01", "02"]
        mock_fetch_constraints.return_value = {"constraints": constraints}
        kwargs = {"collection": "GHS_ENACT_POP"}
        collection_config = plugin.config.products.get("GHS_ENACT_POP", {})
        kwargs.update(collection_config)
        if "metadata_mapping" in kwargs:
            kwargs.pop("metadata_mapping")
        if "assets_mapping" in kwargs:
            kwargs.pop("assets_mapping")
        queryables = plugin.discover_queryables(**kwargs)
        self.assertEqual(6, len(queryables))
        expected_queryables = [
            "year",
            "tile_size",
            "proj:code",
            "month",
            "start",
            "end",
        ]
        for qu in expected_queryables:
            self.assertIn(qu, queryables)
