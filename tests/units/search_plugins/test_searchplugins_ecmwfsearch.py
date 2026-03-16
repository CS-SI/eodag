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
import ast
import json
import os
import unittest
from unittest import mock
from unittest.mock import call

from pydantic_core import PydanticUndefined
from typing_extensions import get_args

from eodag.api.product.metadata_mapping import get_queryable_from_provider
from eodag.api.provider import ProvidersDict
from eodag.config import load_default_config
from eodag.plugins.manager import PluginManager
from eodag.plugins.search import PreparedSearch, ecmwf_temporal_to_eodag
from eodag.utils import USER_AGENT, deepcopy
from eodag.utils.exceptions import ValidationError
from tests.units.search_plugins.mock_response import MockResponse
from tests.utils import TEST_RESOURCES_PATH


class TestSearchPluginECMWFSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSearchPluginECMWFSearch, cls).setUpClass()
        providers = ProvidersDict.from_configs(load_default_config())
        cls.plugins_manager = PluginManager(providers)

    def setUp(self):
        self.provider = "cop_ads"
        self.search_plugin = self.get_search_plugin(provider=self.provider)
        self.query_dates = {
            "start_datetime": "2020-01-01",
            "end_datetime": "2020-01-02",
        }
        self.collection = "CAMS_EAC4"
        self.product_dataset = "cams-global-reanalysis-eac4"
        self.collection_params = {
            "ecmwf:dataset": self.product_dataset,
        }
        self.custom_query_params = {
            "ecmwf:dataset": "cams-global-ghg-reanalysis-egg4",
            "ecmwf:step": 0,
            "ecmwf:variable": "carbon_dioxide",
            "ecmwf:pressure_level": "10",
            "ecmwf:model_level": "1",
            "ecmwf:time": "00:00",
            "ecmwf:data_format": "grib",
        }

    def get_search_plugin(self, collection=None, provider=None):
        return next(
            self.plugins_manager.get_search_plugins(
                collection=collection, provider=provider
            )
        )

    def test_plugins_search_ecmwfsearch_exclude_end_date(self):
        """ECMWFSearch.query must adapt end date in certain cases"""
        # start & stop as dates -> keep end date as it is
        results = self.search_plugin.query(
            collection=self.collection,
            start_datetime="2020-01-01",
            end_datetime="2020-01-02",
        )
        eoproduct = results.data[0]
        self.assertEqual(
            "2020-01-01T00:00:00.000Z",
            eoproduct.properties["start_datetime"],
        )
        self.assertEqual(
            "2020-01-02T00:00:00.000Z",
            eoproduct.properties["end_datetime"],
        )
        # start & stop as datetimes, not midnight -> keep and dates as it is
        results = self.search_plugin.query(
            collection=self.collection,
            start_datetime="2020-01-01T02:00:00Z",
            end_datetime="2020-01-02T03:00:00Z",
        )
        eoproduct = results.data[0]
        self.assertEqual(
            "2020-01-01T02:00:00.000Z",
            eoproduct.properties["start_datetime"],
        )
        self.assertEqual(
            "2020-01-02T03:00:00.000Z",
            eoproduct.properties["end_datetime"],
        )
        # start & stop as datetimes, midnight -> exclude end date
        results = self.search_plugin.query(
            collection=self.collection,
            start_datetime="2020-01-01T00:00:00Z",
            end_datetime="2020-01-02T00:00:00Z",
        )
        eoproduct = results.data[0]
        self.assertEqual(
            "2020-01-01T00:00:00.000Z",
            eoproduct.properties["start_datetime"],
        )
        self.assertEqual(
            "2020-01-01T00:00:00.000Z",
            eoproduct.properties["end_datetime"],
        )
        # start & stop same date -> keep end date
        results = self.search_plugin.query(
            collection=self.collection,
            start_datetime="2020-01-01T00:00:00Z",
            end_datetime="2020-01-01T00:00:00Z",
        )
        eoproduct = results.data[0]
        self.assertEqual(
            "2020-01-01T00:00:00.000Z",
            eoproduct.properties["start_datetime"],
        )
        self.assertEqual(
            "2020-01-01T00:00:00.000Z",
            eoproduct.properties["end_datetime"],
        )

    def test_plugins_search_ecmwfsearch_dates(self):
        """ECMWFSearch.query must use default dates if missing"""

        # given start & stop
        results = self.search_plugin.query(
            collection=self.collection,
            start_datetime="2020-01-01",
            end_datetime="2020-01-02",
        )
        eoproduct = results.data[0]
        self.assertEqual(
            eoproduct.properties["start_datetime"],
            "2020-01-01T00:00:00.000Z",
        )
        self.assertEqual(
            eoproduct.properties["end_datetime"],
            "2020-01-02T00:00:00.000Z",
        )

        # missing start & stop
        results = self.search_plugin.query(
            collection=self.collection,
        )
        eoproduct = results.data[0]
        self.assertNotIn("start_datetime", eoproduct.properties)
        self.assertNotIn("end_datetime", eoproduct.properties)

    def test_plugins_search_ecmwfsearch_with_year_month_day_filter(self):
        """ECMWFSearch.query must use have datetime in response if year, month, day used in filters"""
        self.search_plugin.config.dates_required = True

        results = self.search_plugin.query(
            prep=PreparedSearch(),
            collection="ERA5_SL",
            **{
                "ecmwf:year": "2020",
                "ecmwf:month": ["02"],
                "ecmwf:day": ["20", "21"],
                "ecmwf:time": ["01:00"],
            },
        )
        eoproduct = results.data[0]

        self.assertEqual(
            eoproduct.properties["start_datetime"],
            "2020-02-20T01:00:00.000Z",
        )
        self.assertEqual(
            eoproduct.properties["end_datetime"], "2020-02-21T01:00:00.000Z"
        )
        self.assertEqual(
            eoproduct.properties["ecmwf:year"],
            "2020",
        )
        self.assertEqual(
            eoproduct.properties["ecmwf:month"],
            ["02"],
        )
        self.assertEqual(
            eoproduct.properties["ecmwf:day"],
            ["20", "21"],
        )
        # month with one digit
        results = self.search_plugin.query(
            prep=PreparedSearch(),
            collection="ERA5_SL",
            **{
                "ecmwf:year": "2020",
                "ecmwf:month": ["2"],
                "ecmwf:day": ["20", "21"],
                "ecmwf:time": ["01:00"],
            },
        )
        eoproduct = results.data[0]
        self.assertEqual(
            eoproduct.properties["start_datetime"],
            "2020-02-20T01:00:00.000Z",
        )
        self.assertEqual(
            eoproduct.properties["end_datetime"],
            "2020-02-21T01:00:00.000Z",
        )
        self.assertEqual(
            eoproduct.properties["ecmwf:month"],
            ["2"],
        )
        # qs (used for order request) should contain year/month/day but not date
        self.assertIn("qs", eoproduct.properties)
        self.assertIn("day", eoproduct.properties["qs"])
        self.assertIn("month", eoproduct.properties["qs"])
        self.assertIn("year", eoproduct.properties["qs"])
        self.assertNotIn("date", eoproduct.properties["qs"])

    def test_plugins_search_ecmwfsearch_collection_with_alias(self):
        """alias of collection must be used in search result"""
        self.search_plugin.config.collection_config = {
            "_collection": self.collection,
            "alias": "THE.ALIAS",
        }
        results = self.search_plugin.query(
            collection="THE.ALIAS",
            start_datetime="2020-01-01",
            end_datetime="2020-01-02",
        )
        eoproduct = results.data[0]
        self.assertEqual("THE.ALIAS", eoproduct.collection)

    def test_plugins_search_ecmwfsearch_without_collection(self):
        """
        ECMWFSearch.query must build a EOProduct from input parameters without collection.
        For test only, result cannot be downloaded.
        """
        results = self.search_plugin.query(
            PreparedSearch(count=True),
            **{
                "ecmwf:dataset": self.product_dataset,
                "start_datetime": "2020-01-01",
                "end_datetime": "2020-01-02",
            },
        )
        assert results.number_matched == 1
        eoproduct = results.data[0]

        self.assertEqual(eoproduct.geometry.bounds, (-180.0, -90.0, 180.0, 90.0))
        self.assertEqual(
            eoproduct.properties["start_datetime"], "2020-01-01T00:00:00.000Z"
        )
        self.assertEqual(
            eoproduct.properties["end_datetime"], "2020-01-02T00:00:00.000Z"
        )
        self.assertEqual(eoproduct.properties["title"], eoproduct.properties["id"])
        self.assertTrue(
            eoproduct.properties["title"].startswith(f"{self.product_dataset.upper()}")
        )
        self.assertTrue(
            eoproduct.assets["download_link"].get("order_link").startswith("http")
        )

    def test_plugins_search_ecmwfsearch_with_collection(self):
        """ECMWFSearch.query must build a EOProduct from input parameters with predefined collection"""
        results = self.search_plugin.query(
            **self.query_dates, collection=self.collection, geometry=[1, 2, 3, 4]
        )
        eoproduct = results.data[0]
        assert eoproduct.properties["title"].startswith(self.collection)
        assert eoproduct.geometry.bounds == (1.0, 2.0, 3.0, 4.0)
        # check if collection_params is a subset of eoproduct.properties
        assert self.collection_params.items() <= eoproduct.properties.items()

        # collection default settings can be overwritten using search kwargs
        results = self.search_plugin.query(
            **self.query_dates,
            **{"collection": self.collection, "ecmwf:variable": "temperature"},
        )
        eoproduct = results.data[0]
        assert eoproduct.properties["ecmwf:variable"] == "temperature"

    def test_plugins_search_ecmwfsearch_with_custom_collection(self):
        """ECMWFSearch.query must build a EOProduct from input parameters with custom collection"""
        results = self.search_plugin.query(
            **self.query_dates,
            **self.custom_query_params,
        )
        eoproduct = results.data[0]
        assert eoproduct.properties["title"].startswith(
            self.custom_query_params["ecmwf:dataset"].upper()
        )
        # check if custom_query_params is a subset of eoproduct.properties
        for param in self.custom_query_params:
            try:
                # for numeric values
                assert eoproduct.properties[param] == ast.literal_eval(
                    self.custom_query_params[param]
                )
            except Exception:
                assert eoproduct.properties[param] == self.custom_query_params[param]

    def test_plugins_search_ecmwf_temporal_to_eodag(self):
        """ecmwf_temporal_to_eodag must parse all expected dates formats"""
        self.assertEqual(
            ecmwf_temporal_to_eodag(
                dict(day="15", month="02", year="2022", time="0600")
            ),
            ("2022-02-15T06:00:00Z", "2022-02-15T06:00:00Z"),
        )
        self.assertEqual(
            ecmwf_temporal_to_eodag(dict(hday="15", hmonth="02", hyear="2022")),
            ("2022-02-15T00:00:00Z", "2022-02-15T00:00:00Z"),
        )
        self.assertEqual(
            ecmwf_temporal_to_eodag(dict(date="2022-02-15")),
            ("2022-02-15T00:00:00Z", "2022-02-15T00:00:00Z"),
        )
        self.assertEqual(
            ecmwf_temporal_to_eodag(
                dict(date="2022-02-15T00:00:00Z/2022-02-16T00:00:00Z")
            ),
            ("2022-02-15T00:00:00Z", "2022-02-16T00:00:00Z"),
        )
        self.assertEqual(
            ecmwf_temporal_to_eodag(dict(date="20220215/to/20220216")),
            ("2022-02-15T00:00:00Z", "2022-02-16T00:00:00Z"),
        )
        # List of dates
        self.assertEqual(
            ecmwf_temporal_to_eodag(dict(date=["20220215", "20220216"])),
            ("2022-02-15T00:00:00Z", "2022-02-16T00:00:00Z"),
        )
        self.assertEqual(
            ecmwf_temporal_to_eodag(dict(date=["20220215"])),
            ("2022-02-15T00:00:00Z", "2022-02-15T00:00:00Z"),
        )

    def test_plugins_search_ecmwfsearch_get_available_values_from_contraints(self):
        """ECMWFSearch must return available values from constraints"""
        constraints = [
            {"date": ["2025-01-01/2025-06-01"], "variable": ["a", "b"]},
            {"date": ["2024-01-01/2024-12-01"], "variable": ["a", "b", "c"]},
        ]
        form_keywords = ["date", "variable"]

        # with a date range as a string
        input_keywords = {"date": "2025-01-01/2025-02-01", "variable": "a"}
        available_values = self.search_plugin.available_values_from_constraints(
            constraints, input_keywords, form_keywords
        )
        available_values = {k: sorted(v) for k, v in available_values.items()}
        self.assertIn("variable", available_values)
        self.assertListEqual(["a", "b"], available_values["variable"])
        self.assertIn("date", available_values)

        # with a date range as the first element of a string list
        input_keywords = {"date": ["2025-01-01/2025-02-01"], "variable": "a"}
        available_values = self.search_plugin.available_values_from_constraints(
            constraints, input_keywords, form_keywords
        )
        available_values = {k: sorted(v) for k, v in available_values.items()}
        self.assertIn("variable", available_values)
        self.assertListEqual(["a", "b"], available_values["variable"])
        self.assertIn("date", available_values)

    @mock.patch(
        "eodag.plugins.search.build_search_result.ECMWFSearch._fetch_data",
        autospec=True,
    )
    def test_plugins_search_ecmwfsearch_discover_queryables_ok(self, mock__fetch_data):
        constraints_path = os.path.join(TEST_RESOURCES_PATH, "constraints.json")
        with open(constraints_path) as f:
            constraints = json.load(f)
        constraints[0]["variable"].append("nitrogen_dioxide")
        constraints[0]["type"].append("validated_reanalysis")
        form_path = os.path.join(TEST_RESOURCES_PATH, "form.json")
        with open(form_path) as f:
            form = json.load(f)
        mock__fetch_data.side_effect = [constraints, form]
        collection_config = {
            "extent": {
                "spatial": {"bbox": [[-180.0, -90.0, 180.0, 90.0]]},
                "temporal": {"interval": [["2001-01-01T00:00:00Z", None]]},
            }
        }
        setattr(self.search_plugin.config, "collection_config", collection_config)

        provider_queryables_from_constraints_file = [
            "ecmwf_year",
            "ecmwf_month",
            "ecmwf_day",
            "ecmwf_time",
            "ecmwf_variable",
            "ecmwf_leadtime_hour",
            "ecmwf_type",
            "ecmwf_product_type",
        ]
        default_values = deepcopy(
            getattr(self.search_plugin.config, "products", {}).get(
                "CAMS_EU_AIR_QUALITY_RE", {}
            )
        )
        default_values.pop("metadata_mapping", None)
        # ECMWF-like providers don't have default values anymore: override a default value
        default_values["data_format"] = "grib"
        params = deepcopy(default_values)
        params["collection"] = "CAMS_EU_AIR_QUALITY_RE"
        # set a parameter among the required ones of the form file with a default value in this form but not among the
        # ones of the constraints file to an empty value to check if its associated queryable has no default value
        eodag_formatted_data_format = "ecmwf:data_format"
        provider_data_format = eodag_formatted_data_format.replace("ecmwf:", "")
        self.assertIn(provider_data_format, default_values)
        self.assertIn(provider_data_format, [param["name"] for param in form])
        data_format_in_form = [
            param for param in form if param["name"] == provider_data_format
        ][0]
        self.assertTrue(data_format_in_form.get("required", False))
        self.assertIsNotNone(data_format_in_form.get("details", {}).get("default"))
        for constraint in constraints:
            self.assertNotIn(provider_data_format, constraint)
        params[eodag_formatted_data_format] = ""

        # use a parameter among the ones of the form file but not among the ones of the constraints file
        # and of provider default configuration to check if an error is raised, which is supposed to not happen
        eodag_formatted_download_format = "ecmwf:download_format"
        provider_download_format = eodag_formatted_download_format.replace("ecmwf:", "")
        self.assertNotIn(eodag_formatted_download_format, default_values)
        self.assertIn(provider_download_format, [param["name"] for param in form])
        for constraint in constraints:
            self.assertNotIn(provider_data_format, constraint)
        params[eodag_formatted_download_format] = "foo"
        # create parameters matching the first constraint
        params["variable"] = "nitrogen_dioxide"

        queryables = self.search_plugin.discover_queryables(**params)
        # no error was raised, as expected
        self.assertIsNotNone(queryables)

        mock__fetch_data.assert_has_calls(
            [
                call(
                    mock.ANY,
                    "https://ads.atmosphere.copernicus.eu/api/catalogue/v1/collections/"
                    "cams-europe-air-quality-reanalyses/constraints.json",
                ),
                call(
                    mock.ANY,
                    "https://ads.atmosphere.copernicus.eu/api/catalogue/v1/collections/"
                    "cams-europe-air-quality-reanalyses/form.json",
                ),
            ]
        )

        # queryables from provider constraints file are added (here the ones of CAMS_EU_AIR_QUALITY_RE for cop_ads)
        for provider_queryable in provider_queryables_from_constraints_file:
            provider_queryable = (
                get_queryable_from_provider(
                    provider_queryable,
                    self.search_plugin.get_metadata_mapping("CAMS_EU_AIR_QUALITY_RE"),
                )
                or provider_queryable
            )
            self.assertIn(provider_queryable, queryables)

        # default properties in provider config are added and must be default values of the queryables
        for property, default_value in self.search_plugin.config.products[
            "CAMS_EU_AIR_QUALITY_RE"
        ].items():
            queryable = queryables.get(property)
            # a special case for eodag_formatted_data_format queryable is required
            # as its default value has been overwritten by an empty value
            if queryable is not None and property == eodag_formatted_data_format:
                self.assertEqual(
                    PydanticUndefined, queryable.__metadata__[0].get_default()
                )
                # queryables with empty default values are required
                self.assertTrue(queryable.__metadata__[0].is_required())
            elif queryable is not None:
                self.assertEqual(default_value, queryable.__metadata__[0].get_default())
                # queryables with default values are not required
                self.assertFalse(queryable.__metadata__[0].is_required())

        # required queryable
        queryable = queryables.get("ecmwf:month")
        if queryable is not None:
            self.assertEqual(["01"], queryable.__metadata__[0].get_default())
            self.assertFalse(queryable.__metadata__[0].is_required())

        # check that queryable constraints from the constraints file are in queryable info
        queryable = queryables.get("ecmwf:variable")
        if queryable is not None:
            variable_constraints = constraints[0]["variable"]
            # remove queryable constraints duplicates to make the assertion works
            self.assertSetEqual(
                set(variable_constraints),
                set(get_args(queryable.__origin__.__args__[0])),
            )

        # reset mock
        mock__fetch_data.reset_mock()
        mock__fetch_data.side_effect = [constraints, form]
        # with additional param
        params = deepcopy(default_values)
        params["collection"] = "CAMS_EU_AIR_QUALITY_RE"
        params["ecmwf:variable"] = "a"
        queryables = self.search_plugin.discover_queryables(**params)
        self.assertIsNotNone(queryables)

        # cached values are not used to make the set of unit tests work then the mock is called again
        mock__fetch_data.assert_has_calls(
            [
                call(
                    mock.ANY,
                    "https://ads.atmosphere.copernicus.eu/api/catalogue/v1/collections/"
                    "cams-europe-air-quality-reanalyses/constraints.json",
                ),
                call(
                    mock.ANY,
                    "https://ads.atmosphere.copernicus.eu/api/catalogue/v1/collections/"
                    "cams-europe-air-quality-reanalyses/form.json",
                ),
            ]
        )

        self.assertEqual(12, len(queryables))
        # default properties called in function arguments are added and must be default values of the queryables
        queryable = queryables.get("ecmwf:variable")
        if queryable is not None:
            self.assertEqual("a", queryable.__metadata__[0].get_default())
            self.assertFalse(queryable.__metadata__[0].is_required())

    @mock.patch(
        "eodag.plugins.search.build_search_result.ECMWFSearch._fetch_data",
        autospec=True,
    )
    def test_plugins_search_ecmwfsearch_discover_queryables_ko(self, mock__fetch_data):
        constraints_path = os.path.join(TEST_RESOURCES_PATH, "constraints.json")
        with open(constraints_path) as f:
            constraints = json.load(f)
        form_path = os.path.join(TEST_RESOURCES_PATH, "form.json")
        with open(form_path) as f:
            form = json.load(f)
        mock__fetch_data.side_effect = [constraints, form]

        default_values = deepcopy(
            getattr(self.search_plugin.config, "products", {}).get(
                "CAMS_EU_AIR_QUALITY_RE", {}
            )
        )
        default_values.pop("metadata_mapping", None)
        params = deepcopy(default_values)
        params["collection"] = "CAMS_EU_AIR_QUALITY_RE"

        # use a wrong parameter, e.g. it is not among the ones of the form file, not among
        # the ones of the constraints file and not among the ones of default provider configuration
        wrong_queryable = "foo"
        self.assertNotIn(wrong_queryable, default_values)
        self.assertNotIn(wrong_queryable, [param["name"] for param in form])
        for constraint in constraints:
            self.assertNotIn(wrong_queryable, constraint)
        params[wrong_queryable] = "bar"

        # Test the function, expecting ValidationError to be raised
        with self.assertRaises(ValidationError) as context:
            self.search_plugin.discover_queryables(**params)
        self.assertEqual(
            f"'{wrong_queryable}' is not a queryable parameter for {self.provider}",
            context.exception.message,
        )

    @mock.patch(
        "eodag.plugins.search.build_search_result.ecmwfsearch.ECMWFSearch._fetch_data",
        autospec=True,
        return_value={},
    )
    @mock.patch(
        "eodag.plugins.search.build_search_result.ecmwfsearch.get_geometry_from_ecmwf_location",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.build_search_result.ecmwfsearch.get_geometry_from_ecmwf_feature",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.build_search_result.ecmwfsearch.get_geometry_from_ecmwf_area",
        autospec=True,
    )
    def test_plugins_search_ecmwfsearch_convert_geometry_ok(
        self,
        mock_get_geometry_from_ecmwf_area,
        mock_get_geometry_from_ecmwf_feature,
        mock_get_geometry_from_ecmwf_location,
        mock__fetch_data,
    ):
        """Custom geometry must be converted to Shapely polygon."""
        area = [64.0, 51.0, 52.0, 63.0]
        shape = {
            "shape": [
                [50.0, 50.0],
                [50.0, 60.0],
                [60.0, 60.0],
                [60.0, 50.0],
                [50.0, 50.0],
            ],
            "type": "polygon",
        }
        location = {
            "latitude": 30.0,
            "longitude": 30.0,
        }

        # area
        params = {
            "collection": "CAMS_EU_AIR_QUALITY_RE",
            "area": area,
        }
        queryables = self.search_plugin.discover_queryables(**params)
        self.assertIn("geom", queryables)
        mock_get_geometry_from_ecmwf_area.assert_called_once_with(area)

        # shape
        params = {
            "collection": "CAMS_EU_AIR_QUALITY_RE",
            "feature": shape,
        }
        queryables = self.search_plugin.discover_queryables(**params)
        self.assertIn("geom", queryables)
        mock_get_geometry_from_ecmwf_feature.assert_called_once_with(shape)

        # location
        params = {
            "collection": "CAMS_EU_AIR_QUALITY_RE",
            "location": location,
        }
        queryables = self.search_plugin.discover_queryables(**params)
        self.assertIn("geom", queryables)
        mock_get_geometry_from_ecmwf_location.assert_called_once_with(location)

    @mock.patch(
        "eodag.plugins.search.build_search_result.ECMWFSearch._fetch_data",
        autospec=True,
        return_value={},
    )
    def test_plugins_search_ecmwfsearch_convert_geometry_ko(
        self,
        mock__fetch_data,
    ):
        """
        ``get_geometry_from_ecmwf_*`` must raise an informative exception
        if the given geometry is not well formed.
        """
        # area
        area_values = [
            [1.0, 2.0, 3.0],  # not enough values
            [1.0, 2.0, 3.0, 4.0, 5.0],  # too many values
            [1.0, "lorem", 3.0, 4.0],  # wrong type
        ]
        for area in area_values:
            params = {
                "collection": "CAMS_EU_AIR_QUALITY_RE",
                "area": area,
            }
            with self.assertRaises(ValidationError):
                self.search_plugin.discover_queryables(**params)

        # feature
        feature_values = [
            "foo",  # not a dict
            {"foo": "bar"},  # missing 'type'
            {"type": "points"},  # wrong 'type'
            {"type": "polygon"},  # missing 'shape'
            {"type": "polygon", "shape": "boo"},  # shape is not a list
            {
                "type": "polygon",
                "shape": [1, 2, 3],
            },
        ]
        for feature in feature_values:
            params = {
                "collection": "CAMS_EU_AIR_QUALITY_RE",
                "feature": feature,
            }
            with self.assertRaises(ValidationError):
                self.search_plugin.discover_queryables(**params)

        # location
        location_values = [
            "foo",  # not a dict
            {"lorem": "foo", "ipsum": "boo"},  # missing both fields
            {"latitude": 40, "ipsum": "boo"},  # missing one field
            {"latitude": 40, "longitude": "boo"},  # value is not a number
        ]
        for location in location_values:
            params = {
                "collection": "CAMS_EU_AIR_QUALITY_RE",
                "location": location,
            }
            with self.assertRaises(ValidationError):
                self.search_plugin.discover_queryables(**params)

    @mock.patch("eodag.utils.requests.requests.sessions.Session.get", autospec=True)
    def test_plugins_search_ecmwf_search_wekeo_discover_queryables(
        self, mock_requests_get
    ):
        # One of the providers that has discover_queryables() configured with QueryStringSearch
        search_plugin = self.get_search_plugin(provider="wekeo_ecmwf")
        self.assertEqual("WekeoECMWFSearch", search_plugin.__class__.__name__)
        self.assertEqual(
            "ECMWFSearch",
            search_plugin.discover_queryables.__func__.__qualname__.split(".")[0],
        )

        constraints_path = os.path.join(TEST_RESOURCES_PATH, "constraints.json")
        with open(constraints_path) as f:
            constraints = json.load(f)
        wekeo_ecmwf_constraints = [constraints[0]]

        form_path = os.path.join(TEST_RESOURCES_PATH, "form.json")
        with open(form_path) as f:
            form = json.load(f)
        wekeo_ecmwf_form = form

        mock_requests_get.side_effect = [
            MockResponse(wekeo_ecmwf_constraints, status_code=200),
            MockResponse(wekeo_ecmwf_form, status_code=200),
        ]

        provider_queryables_from_constraints_file = [
            "ecmwf_year",
            "ecmwf_month",
            "ecmwf_day",
            "ecmwf_time",
            "ecmwf_variable",
            "ecmwf_leadtime_hour",
            "ecmwf_type",
            "ecmwf_product_type",
        ]

        queryables = search_plugin._get_collection_queryables(
            collection="ERA5_SL_MONTHLY", alias=None, filters={}
        )
        self.assertIsNotNone(queryables)

        self.assertEqual(len(mock_requests_get.call_args), 2)
        mock_requests_get.assert_any_call(
            mock.ANY,
            "https://cds.climate.copernicus.eu/api/catalogue/v1/collections/"
            "reanalysis-era5-single-levels-monthly-means/constraints.json",
            headers=USER_AGENT,
            auth=None,
            timeout=60,
        )
        mock_requests_get.assert_any_call(
            mock.ANY,
            "https://cds.climate.copernicus.eu/api/catalogue/v1/collections/"
            "reanalysis-era5-single-levels-monthly-means/form.json",
            headers=USER_AGENT,
            auth=None,
            timeout=60,
        )

        # queryables from provider constraints file are added (here the ones of ERA5_SL_MONTHLY for wekeo_ecmwf)
        for provider_queryable in provider_queryables_from_constraints_file:
            provider_queryable = (
                get_queryable_from_provider(
                    provider_queryable,
                    search_plugin.get_metadata_mapping("ERA5_SL_MONTHLY"),
                )
                or provider_queryable
            )
            self.assertIn(provider_queryable, queryables)

        # default properties in provider config are added and must be default values of the queryables
        for property, default_value in search_plugin.config.products[
            "ERA5_SL_MONTHLY"
        ].items():
            queryable = queryables.get(property)
            if queryable is not None:
                self.assertEqual(default_value, queryable.__metadata__[0].get_default())
                # queryables with default values are not required
                self.assertFalse(queryable.__metadata__[0].is_required())

        # queryables without default values are required
        queryable = queryables.get("month")
        if queryable is not None:
            self.assertEqual(PydanticUndefined, queryable.__metadata__[0].get_default())
            self.assertTrue(queryable.__metadata__[0].is_required())

        # check that queryable constraints from the constraints file are in queryable info
        # (here it is a case where all constraints of "variable" queryable can be taken into account)
        queryable = queryables.get("variable")
        if queryable is not None:
            variable_constraints = []
            for constraint in constraints:
                if "variable" in constraint:
                    variable_constraints.extend(constraint["variable"])
            # remove queryable constraints duplicates to make the assertion works
            self.assertSetEqual(
                set(variable_constraints), set(queryable.__origin__.__args__)
            )

        # reset mock
        mock_requests_get.reset_mock()

        # with additional param
        queryables = search_plugin.discover_queryables(
            collection="ERA5_SL_MONTHLY",
            dataset="EO:ECMWF:DAT:REANALYSIS_ERA5_SINGLE_LEVELS_MONTHLY_MEANS",
            **{"ecmwf:variable": "a"},
        )
        self.assertIsNotNone(queryables)

        self.assertEqual(12, len(queryables))
        # default properties called in function arguments are added and must be default values of the queryables
        queryable = queryables.get("ecmwf:variable")
        if queryable is not None:
            self.assertEqual("a", queryable.__metadata__[0].get_default())
            self.assertFalse(queryable.__metadata__[0].is_required())
