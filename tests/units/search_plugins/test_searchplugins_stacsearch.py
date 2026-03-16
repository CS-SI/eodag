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
from typing import Literal, Union, get_origin
from unittest import mock

from shapely.geometry.base import BaseGeometry
from typing_extensions import get_args

from eodag.plugins.search import PreparedSearch, QueryStringSearch
from eodag.utils.exceptions import MisconfiguredError
from tests.units.search_plugins.base import BaseSearchPluginTest


class TestSearchPluginStacSearch(BaseSearchPluginTest):
    @mock.patch(
        "eodag.plugins.search.qssearch.stacsearch.StacSearch._request", autospec=True
    )
    def test_plugins_search_stacsearch_mapping_earthsearch(self, mock__request):
        """The metadata mapping for earth_search should return well formatted results"""  # noqa

        geojson_geometry = self.search_criteria_s2_msi_l1c["geometry"].__geo_interface__

        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.side_effect = [
            {
                "features": [
                    {
                        "id": "foo",
                        "geometry": geojson_geometry,
                        "properties": {
                            "s2:product_uri": "S2B_MSIL1C_20201009T012345_N0209_R008_T31TCJ_20201009T123456.SAFE",
                        },
                    },
                    {
                        "id": "bar",
                        "geometry": geojson_geometry,
                        "properties": {
                            "s2:product_uri": "S2B_MSIL1C_20200910T012345_N0209_R008_T31TCJ_20200910T123456.SAFE",
                        },
                    },
                    {
                        "id": "bar",
                        "geometry": geojson_geometry,
                        "properties": {
                            "s2:product_uri": "S2B_MSIL1C_20201010T012345_N0209_R008_T31TCJ_20201010T123456.SAFE",
                        },
                    },
                ],
            },
        ]

        search_plugin = self.get_search_plugin(self.collection, "earth_search")

        products = search_plugin.query(
            prep=PreparedSearch(page=1, limit=2),
            **self.search_criteria_s2_msi_l1c,
        )
        self.assertEqual(
            products[0].properties["eodag:product_path"],
            "products/2020/10/9/S2B_MSIL1C_20201009T012345_N0209_R008_T31TCJ_20201009T123456",
        )
        self.assertEqual(
            products[1].properties["eodag:product_path"],
            "products/2020/9/10/S2B_MSIL1C_20200910T012345_N0209_R008_T31TCJ_20200910T123456",
        )
        self.assertEqual(
            products[2].properties["eodag:product_path"],
            "products/2020/10/10/S2B_MSIL1C_20201010T012345_N0209_R008_T31TCJ_20201010T123456",
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.stacsearch.StacSearch._request", autospec=True
    )
    def test_plugins_search_stacsearch_default_geometry(self, mock__request):
        """The metadata mapping for a stac provider should return a default geometry"""

        geojson_geometry = self.search_criteria_s2_msi_l1c["geometry"].__geo_interface__

        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.side_effect = [
            {
                "features": [
                    {
                        "id": "foo",
                        "geometry": geojson_geometry,
                    },
                    {
                        "id": "bar",
                        "geometry": None,
                    },
                ],
            },
        ]

        search_plugin = self.get_search_plugin(self.collection, "earth_search")

        products = search_plugin.query(
            prep=PreparedSearch(
                page=1,
                limit=3,
            )
        )
        self.assertEqual(
            products.data[0].geometry, self.search_criteria_s2_msi_l1c["geometry"]
        )
        self.assertEqual(products[1].geometry.bounds, (-180.0, -90.0, 180.0, 90.0))

    @mock.patch(
        "eodag.plugins.search.qssearch.geodessearch.GeodesSearch._request",
        autospec=True,
    )
    @mock.patch(
        "eodag.api.product.drivers.base.DatasetDriver.guess_asset_key_and_roles",
        autospec=True,
    )
    @mock.patch.dict(QueryStringSearch.extract_properties, {"json": mock.MagicMock()})
    def test_plugins_search_stacsearch_normalize_asset_key_from_href(
        self, mock_guess_asset_key_and_roles, mock_geodes_search_request
    ):
        """normalize_results must guess asset key from href if asset_key_from_href is set to True"""

        mock_properties_from_json = QueryStringSearch.extract_properties["json"]
        mock_properties_from_json.return_value = {
            "geometry": "POINT (0 0)",
            "assets": {
                "foo": {
                    "href": "https://example.com/foo",
                    "roles": ["bar"],
                },
            },
        }
        mock_guess_asset_key_and_roles.return_value = ("normalized_key", ["some_role"])

        # guess asset key from href
        search_plugin = self.get_search_plugin(self.collection, "earth_search")
        self.assertFalse(hasattr(search_plugin.config, "asset_key_from_href"))
        products = search_plugin.normalize_results([{}])
        mock_guess_asset_key_and_roles.assert_called_once_with(
            products[0].driver, "https://example.com/foo", products[0]
        )
        self.assertEqual(len(products[0].assets), 1)
        self.assertEqual(products[0].assets["foo"]["roles"], ["some_role"])

        mock_guess_asset_key_and_roles.reset_mock()
        # guess asset key from origin key
        search_plugin = self.get_search_plugin(self.collection, "geodes")
        self.assertEqual(search_plugin.config.asset_key_from_href, False)
        products = search_plugin.normalize_results([{}])
        mock_guess_asset_key_and_roles.assert_called_once_with(
            products[0].driver, "foo", products[0]
        )
        self.assertEqual(len(products[0].assets), 1)
        self.assertEqual(products[0].assets["foo"]["roles"], ["some_role"])
        # title is also set using normlized key
        self.assertEqual(products[0].assets["foo"]["title"], "normalized_key")

        mock_guess_asset_key_and_roles.reset_mock()
        # no-extension href: driver returns (None, None), original key and roles are kept
        mock_guess_asset_key_and_roles.return_value = (None, None)
        mock_properties_from_json.return_value = {
            "geometry": "POINT (0 0)",
            "assets": {
                "some-asset": {
                    "href": "https://example.com/foo",
                    "roles": ["bar"],
                },
            },
        }
        search_plugin = self.get_search_plugin(self.collection, "earth_search")
        products = search_plugin.normalize_results([{}])
        self.assertEqual(len(products[0].assets), 1)
        self.assertIn("some-asset", products[0].assets)
        self.assertEqual(products[0].assets["some-asset"]["roles"], ["bar"])
        self.assertEqual(products[0].assets["some-asset"]["title"], "some-asset")

        mock_guess_asset_key_and_roles.reset_mock()
        # no-extension href with existing title: original title is preserved
        mock_guess_asset_key_and_roles.return_value = (None, None)
        mock_properties_from_json.return_value = {
            "geometry": "POINT (0 0)",
            "assets": {
                "some-asset": {
                    "href": "https://example.com/foo",
                    "roles": ["bar"],
                    "title": "My custom title",
                },
            },
        }
        search_plugin = self.get_search_plugin(self.collection, "earth_search")
        products = search_plugin.normalize_results([{}])
        self.assertEqual(len(products[0].assets), 1)
        self.assertIn("some-asset", products[0].assets)
        self.assertEqual(products[0].assets["some-asset"]["title"], "My custom title")

    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.requests.post", autospec=True
    )
    def test_plugins_search_stacsearch_opened_time_intervals(self, mock_requests_post):
        """Opened time intervals must be handled by StacSearch plugin"""
        mock_requests_post.return_value = mock.Mock()
        mock_requests_post.return_value.json.side_effect = [
            {
                "features": [
                    {
                        "id": "foo",
                        "geometry": None,
                    },
                ],
            },
        ] * 4
        search_plugin = self.get_search_plugin(self.collection, "earth_search")

        search_plugin.query(
            start_datetime="2020-01-01",
            end_datetime="2020-01-02",
        )
        self.assertEqual(
            mock_requests_post.call_args.kwargs["json"]["datetime"],
            "2020-01-01T00:00:00.000Z/2020-01-02T00:00:00.000Z",
        )

        search_plugin.query(start_datetime="2020-01-01")
        self.assertEqual(
            mock_requests_post.call_args.kwargs["json"]["datetime"],
            "2020-01-01T00:00:00.000Z/..",
        )

        search_plugin.query(end_datetime="2020-01-02")
        self.assertEqual(
            mock_requests_post.call_args.kwargs["json"]["datetime"],
            "../2020-01-02T00:00:00.000Z",
        )

        search_plugin.query()
        self.assertNotIn("datetime", mock_requests_post.call_args.kwargs["json"])

    @mock.patch(
        "eodag.plugins.search.qssearch.stacsearch.StacSearch._request", autospec=True
    )
    def test_plugins_search_stacsearch_distinct_collection_mtd_mapping(
        self, mock__request
    ):
        """The metadata mapping for a stac provider should not mix specific collections metadata-mapping"""
        mock__request.return_value = mock.Mock()
        result = {
            "features": [
                {
                    "id": "foo",
                    "geometry": None,
                },
            ],
        }
        mock__request.return_value.json.side_effect = [result, result]
        search_plugin = self.get_search_plugin(self.collection, "earth_search")

        # update metadata_mapping only for S2_MSI_L1C
        search_plugin.config.products["S2_MSI_L1C"]["metadata_mapping"]["bar"] = (
            None,
            "baz",
        )
        products = search_plugin.query(
            collection="S2_MSI_L1C",
            auth=None,
        )
        self.assertIn("bar", products.data[0].properties)
        self.assertEqual(products.data[0].properties["bar"], "baz")

        # search with another collection
        self.assertNotIn(
            "metadata_mapping", search_plugin.config.products["S1_SAR_GRD"]
        )
        products = search_plugin.query(
            collection="S1_SAR_GRD",
            auth=None,
        )
        self.assertNotIn("bar", products.data[0].properties)

    @mock.patch(
        "eodag.plugins.search.qssearch.stacsearch.StacSearch._request", autospec=True
    )
    def test_plugins_search_stacsearch_distinct_collection_mtd_mapping_earth_search(
        self, mock__request
    ):
        """The metadata mapping for a earth_search should correctly build tileIdentifier"""
        mock__request.return_value = mock.Mock()
        result = {
            "features": [
                {
                    "id": "foo",
                    "geometry": None,
                    "properties": {
                        "mgrs:utm_zone": "31",
                        "mgrs:latitude_band": "T",
                        "mgrs:grid_square": "CJ",
                    },
                },
            ],
        }
        collection = "S2_MSI_L1C"
        mock__request.return_value.json.side_effect = [result]
        search_plugin = self.get_search_plugin(collection, "earth_search")

        products = search_plugin.query(
            collection=collection,
            auth=None,
        )
        self.assertIn("grid:code", products.data[0].properties)
        self.assertEqual(
            products.data[0].properties["grid:code"],
            "MGRS-31TCJ",
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.QueryStringSearch._request",
        autospec=True,
    )
    def test_plugins_search_stacsearch_discover_queryables(self, mock_request):
        provider_queryables = {
            "type": "object",
            "title": "Querable",
            "properties": {
                "dataset_id": {
                    "title": "dataset_id",
                    "type": "string",
                    "oneOf": [
                        {
                            "const": "EO:ESA:DAT:COP-DEM",
                            "title": "EO:ESA:DAT:COP-DEM",
                            "group": None,
                        }
                    ],
                },
                "bbox": {
                    "title": "Bbox",
                    "type": "array",
                    "minItems": 4,
                    "maxItems": 4,
                    "items": [
                        {"type": "number", "maximum": 180, "minimum": -180},
                        {"type": "number", "maximum": 90, "minimum": -90},
                        {"type": "number", "maximum": 180, "minimum": -180},
                        {"type": "number", "maximum": 90, "minimum": -90},
                    ],
                },
                "productIdentifier": {
                    "title": "Product Identifier",
                    "type": "string",
                    "pattern": "^[a-zA-Z0-9]+$",
                },
                "collection": {
                    "title": "Collection",
                    "type": "string",
                    "oneOf": [
                        {"const": "DGE_30", "title": "DGE_30", "group": None},
                        {"const": "DGE_90", "title": "DGE_90", "group": None},
                        {"const": "DTE_30", "title": "DTE_30", "group": None},
                        {"const": "DTE_90", "title": "DTE_90", "group": None},
                    ],
                },
                "startdate": {
                    "title": "Start Date",
                    "type": "string",
                    "format": "date-time",
                    "minimum": "",
                    "maximum": "",
                    "default": "",
                },
                "enddate": {
                    "title": "End Date",
                    "type": "string",
                    "format": "date-time",
                    "minimum": "",
                    "maximum": "",
                    "default": "",
                },
            },
            "required": ["dataset_id"],
        }
        mock_request.return_value = mock.Mock()
        mock_request.return_value.json.side_effect = [provider_queryables]
        plugin = self.get_search_plugin(provider="wekeo_main")
        queryables = plugin.discover_queryables(
            collection="COP_DEM_GLO90_DGED", provider="wekeo_main"
        )
        self.assertIn("collection", queryables)
        self.assertIn("geom", queryables)
        self.assertIn("start", queryables)
        self.assertIn("end", queryables)

    @mock.patch(
        "eodag.plugins.search.qssearch.stacsearch.StacSearch._request", autospec=True
    )
    def test_plugins_search_stacsearch_unparsed_query_parameters(self, mock__request):
        """search_param_unparsed should pass query params as-is to the provider"""
        result = {"features": []}
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.side_effect = [result]
        search_plugin = self.get_search_plugin(provider="earth_search")
        search_plugin.query(query={"foo": "bar", "baz": "qux"})

        self.assertTrue(mock__request.called)
        called_args, _ = mock__request.call_args
        prepared_search = called_args[1]
        self.assertEqual(
            prepared_search.query_params["query"], {"foo": "bar", "baz": "qux"}
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.QueryStringSearch._request",
        autospec=True,
    )
    def test_plugins_search_dedl_discover_queryables(self, mock_request):
        """
        Test the discovery and parsing of queryables from the DEDL provider.

        This test verifies that:
        - The "ecmwf:time" field is correctly interpreted as an annotated list with a
        single literal value "00:00".
        - The "start" field is interpreted as an annotated union of datetime and date types.
        - The "geom" field is interpreted as an annotated union that includes a string,
        a dictionary with string keys and float values, and subclasses of BaseGeometry.

        The test mocks the _request method of the plugin to simulate a response with
        predefined queryables, then verifies the correctness of the resulting type annotations.
        """
        provider_queryables = {
            "$schema": "https://json-schema.org/draft/2019-09/schema",
            "type": "object",
            "title": "Queryables for EODAG STAC API",
            "description": "Queryable names for the EODAG STAC API Item Search filter. ",
            "properties": {
                "ecmwf:variable": {
                    "default": "10m_u_component_of_wind",
                    "items": {
                        "enum": [
                            "10m_u_component_of_wind",
                            "10m_v_component_of_wind",
                            "2m_dewpoint_temperature",
                            "2m_temperature",
                        ],
                        "type": "string",
                    },
                    "title": "variable",
                    "type": "array",
                },
                "ecmwf:pressure_level": {
                    "items": {},
                    "title": "pressure_level",
                    "type": "array",
                },
                "ecmwf:time": {
                    "default": "00:00",
                    "description": "Model base time as HH:MM (UTC)",
                    "items": {"const": "00:00", "type": "string"},
                    "title": "time",
                    "type": "array",
                },
                "start_datetime": {
                    "anyOf": [
                        {"format": "date-time", "type": "string"},
                        {"format": "date", "type": "string"},
                    ],
                    "default": "2015-01-01T00:00:00Z",
                    "title": "start_datetime",
                },
                "end_datetime": {
                    "anyOf": [
                        {"format": "date-time", "type": "string"},
                        {"format": "date", "type": "string"},
                    ],
                    "default": "2015-01-01T00:00:00Z",
                    "title": "end_datetime",
                },
                "geometry": {
                    "description": "Geometry",
                    "ref": "https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json#/geometry",
                },
                "bbox": {
                    "description": "BBox",
                    "type": "array",
                    "oneOf": [
                        {"minItems": 4, "maxItems": 4},
                        {"minItems": 6, "maxItems": 6},
                    ],
                    "items": {"type": "number"},
                },
            },
            "required": [
                "ecmwf:variable",
                "ecmwf:time",
                "start_datetime",
                "geometry",
                "bbox",
            ],
            "additionalProperties": False,
        }
        mock_request.return_value = mock.Mock()
        mock_request.return_value.json.side_effect = [provider_queryables]
        plugin = self.get_search_plugin(provider="dedl")
        queryables_dedl = plugin.discover_queryables(
            collection="CAMS_GAC_FORECAST", provider="dedl"
        )

        # Check that "ecmwf:time" has type Annotated[list[Literal['00:00']], ...]
        self.assertIn("ecmwf_time", queryables_dedl)
        annotated_type = queryables_dedl["ecmwf_time"]
        args = get_args(annotated_type)
        base_type = args[0]
        self.assertEqual(get_origin(base_type), list)
        literal_args = get_args(base_type)
        self.assertEqual(literal_args, (Literal["00:00"],))

        # Check that "start" has type Annotated[str, ...]
        self.assertIn("start", queryables_dedl)
        annotated_type = queryables_dedl["start"]
        args = get_args(annotated_type)
        self.assertEqual(args[0], str)

        # Check that "geom" has type Annotated[Union[str, dict[str, float], BaseGeometry], ...]
        self.assertIn("geom", queryables_dedl)
        annotated_type = queryables_dedl["geom"]
        args = get_args(annotated_type)
        base_type = args[0]
        self.assertEqual(get_origin(base_type), Union)
        union_args = get_args(base_type)
        self.assertIn(str, union_args)
        self.assertTrue(any(get_origin(arg) is dict for arg in union_args))
        self.assertTrue(
            any(
                issubclass(arg, BaseGeometry)
                for arg in union_args
                if isinstance(arg, type)
            )
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_stacsearch_discover_queryables_merge(self, mock_request):
        """discover_queryables must merge provider and eodag queryable types, aliases, and attributes"""
        from pydantic import AliasChoices

        provider_queryables = {
            "type": "object",
            "properties": {
                # no constrained type: eodag's str type expected
                "start_datetime": {
                    "title": "Start datetime",
                    "type": "string",
                    "format": "date-time",
                    "description": "provider start description",
                },
                # simple object: should get eodag's Union type (no Literal constraint)
                "geometry": {
                    "title": "Geometry",
                    "description": "provider geometry description",
                },
                # not in eodag queryables: kept as-is from provider
                "some_provider_param": {
                    "title": "Some param",
                    "type": "integer",
                    "description": "provider-only param",
                },
            },
        }
        mock_request.return_value = mock.Mock()
        mock_request.return_value.json.side_effect = [provider_queryables]
        plugin = self.get_search_plugin(provider="dedl")
        queryables = plugin.discover_queryables(
            collection="CAMS_GAC_FORECAST", provider="dedl"
        )

        # 1. "start" should be present (mapped from "start_datetime" via alias)
        self.assertIn("start", queryables)
        start_args = get_args(queryables["start"])
        start_type, start_fi = start_args[0], start_args[1]
        # type should be eodag's str (no Literal from provider)
        self.assertEqual(start_type, str)
        # alias from eodag should be preserved (AliasChoices with "start_datetime")
        self.assertIsInstance(start_fi.alias, AliasChoices)
        self.assertIn("start_datetime", start_fi.alias.choices)
        # non-empty attributes from provider
        self.assertEqual(start_fi.description, "provider start description")
        self.assertEqual(start_fi.title, "Start datetime")

        # 2. "geom" should be present (mapped from "geometry" via alias)
        self.assertIn("geom", queryables)
        geom_args = get_args(queryables["geom"])
        geom_type, geom_fi = geom_args[0], geom_args[1]
        # type should be eodag's Union (provider has no constraints)
        self.assertEqual(get_origin(geom_type), Union)
        # alias from eodag should be preserved
        self.assertIsInstance(geom_fi.alias, AliasChoices)
        self.assertIn("geometry", geom_fi.alias.choices)
        # non-empty attributes from provider
        self.assertEqual(geom_fi.description, "provider geometry description")
        self.assertEqual(geom_fi.title, "Geometry")

        # 3. "end" should be present (added from "datetime" split)
        #    "datetime" isn't in provider_queryables, so "end" won't be auto-added
        self.assertNotIn("end", queryables)
        self.assertNotIn("datetime", queryables)

        # 4. check "some_provider_param" is kept as-is
        self.assertIn("some_provider_param", queryables)
        sp_args = get_args(queryables["some_provider_param"])
        sp_type, sp_fi = sp_args[0], sp_args[1]
        self.assertEqual(sp_type, int)
        # non-empty attributes from provider
        self.assertEqual(sp_fi.description, "provider-only param")
        self.assertEqual(sp_fi.title, "Some param")

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    def test_plugins_search_stacsearch_discover_queryables_datetime_split(
        self, mock_request
    ):
        """discover_queryables must split provider 'datetime' into 'start' and 'end'"""
        from pydantic import AliasChoices

        provider_queryables = {
            "type": "object",
            "properties": {
                "datetime": {
                    "title": "Datetime",
                    "type": "string",
                    "format": "date-time",
                },
                "some_param": {
                    "title": "Some param",
                    "type": "string",
                },
            },
        }
        mock_request.return_value = mock.Mock()
        mock_request.return_value.json.side_effect = [provider_queryables]
        plugin = self.get_search_plugin(provider="dedl")
        queryables = plugin.discover_queryables(
            collection="CAMS_GAC_FORECAST", provider="dedl"
        )

        # "datetime" itself must not appear in queryables
        self.assertNotIn("datetime", queryables)

        # "start" and "end" must be added from eodag definitions
        self.assertIn("start", queryables)
        self.assertIn("end", queryables)

        # check "start" has the expected eodag alias
        start_args = get_args(queryables["start"])
        start_fi = start_args[1]
        self.assertIsInstance(start_fi.alias, AliasChoices)
        self.assertIn("start_datetime", start_fi.alias.choices)

        # check "end" has the expected eodag alias
        end_args = get_args(queryables["end"])
        end_fi = end_args[1]
        self.assertEqual(end_fi.alias, "end_datetime")

        # provider-only param still present
        self.assertIn("some_param", queryables)

    def test_plugins_search_stacsearch_missing_results_entry_misconfigured(self):
        """StacSearch must raise MisconfiguredError when results_entry is missing
        for a subclass not referenced in STAC_SEARCH_PLUGINS"""
        from eodag.config import PluginConfig
        from eodag.plugins.search.qssearch import StacSearch

        class _UnregisteredStacSearch(StacSearch):
            pass

        config = PluginConfig()
        # do not set results_entry on purpose
        with self.assertRaises(MisconfiguredError) as ctx:
            _UnregisteredStacSearch("some_provider", config)
        self.assertIn("results_entry", str(ctx.exception))
        self.assertIn("_UnregisteredStacSearch", str(ctx.exception))
        self.assertIn("STAC_SEARCH_PLUGINS", str(ctx.exception))

    def test_plugins_search_stacsearch_missing_results_entry_reraises_for_known_plugin(
        self,
    ):
        """StacSearch must re-raise AttributeError when results_entry is missing
        for a subclass referenced in STAC_SEARCH_PLUGINS"""
        from eodag.config import PluginConfig
        from eodag.plugins.search import GeodesSearch

        config = PluginConfig()
        # GeodesSearch is in STAC_SEARCH_PLUGINS so AttributeError must be re-raised
        with self.assertRaises(AttributeError):
            GeodesSearch("geodes", config)
