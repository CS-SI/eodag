import json
import os
import unittest
from unittest import mock

from eodag.api.queryables import (
    BaseQueryableProperty,
    QueryableProperty,
    Queryables,
    format_provider_queryables,
    format_queryable,
    get_provider_product_type_queryables,
    get_provider_queryables,
    get_queryables_from_constraints,
    get_queryables_from_metadata_mapping,
    rename_to_stac_standard,
)
from eodag.config import load_default_config
from eodag.plugins.manager import PluginManager
from eodag.utils import MockResponse
from eodag.utils.exceptions import NotAvailableError
from tests import TEST_RESOURCES_PATH


class TestQueryables(unittest.TestCase):
    def setUp(self) -> None:
        super(TestQueryables, self).setUp()
        providers_config = load_default_config()
        self.plugins_manager = PluginManager(providers_config)

    def test_rename_to_stac_standard(self):
        self.assertEqual("sat:orbit_state", rename_to_stac_standard("orbitDirection"))
        self.assertEqual("oseo:wavelengths", rename_to_stac_standard("wavelengths"))

    def test_format_queryable(self):
        queryable = format_queryable("sensorMode")
        self.assertTrue(isinstance(queryable, BaseQueryableProperty))
        self.assertFalse(isinstance(queryable, QueryableProperty))
        self.assertEqual("Instrument Mode", queryable.description)
        queryable = format_queryable("sensorMode", False, {"ref": "https:a.b.c"})
        self.assertTrue(isinstance(queryable, QueryableProperty))
        self.assertEqual("https:a.b.c", queryable.ref)
        queryable = format_queryable("year", attributes={"values": ["2000", "2010"]})
        self.assertTrue(isinstance(queryable, BaseQueryableProperty))
        self.assertFalse(isinstance(queryable, QueryableProperty))
        self.assertListEqual(["2000", "2010"], queryable.values)

    def test_format_provider_queryables(self):
        provider_queryables = {
            "year": {"type": ["str"], "enum": ["2000", "2010"], "ref": "https:a.b.c"},
            "variable": {"type": "str", "enum": ["wind", "rain"]},
        }
        queryables = format_provider_queryables(provider_queryables)
        self.assertEqual(2, len(queryables))
        queryable1 = queryables["year"]
        self.assertTrue(isinstance(queryable1, BaseQueryableProperty))
        self.assertFalse(isinstance(queryable1, QueryableProperty))
        self.assertEqual("Year", queryable1.description)
        self.assertListEqual(["str"], queryable1.type)
        self.assertListEqual(["2000", "2010"], queryable1.values)
        queryable2 = queryables["variable"]
        self.assertTrue(isinstance(queryable2, BaseQueryableProperty))
        self.assertFalse(isinstance(queryable2, QueryableProperty))
        self.assertEqual("Variable", queryable2.description)
        self.assertListEqual(["str"], queryable2.type)
        self.assertListEqual(["wind", "rain"], queryable2.values)
        queryables = format_provider_queryables(provider_queryables, False)
        self.assertEqual(2, len(queryables))
        queryable1 = queryables["year"]
        self.assertTrue(isinstance(queryable1, QueryableProperty))
        self.assertEqual("https:a.b.c", queryable1.ref)

    def test_get_queryables_from_metadata_mapping(self):
        plugins = self.plugins_manager.get_search_plugins("S1_SAR_GRD", "peps")
        plugin = next(plugins)
        default_queryables = Queryables().get_base_properties()
        queryables = get_queryables_from_metadata_mapping(
            plugin, "S1_SAR_GRD", default_queryables
        )
        self.assertEqual(19, len(queryables))
        self.assertIn("id", queryables)
        self.assertIn("bbox", queryables)
        self.assertIn("instrument", queryables)
        queryable = queryables.get("instrument")
        self.assertTrue(isinstance(queryable, BaseQueryableProperty))
        self.assertFalse(isinstance(queryable, QueryableProperty))
        self.assertEqual("Instruments", queryable.description)
        default_queryables = Queryables().properties
        queryables = get_queryables_from_metadata_mapping(
            plugin, "S1_SAR_GRD", default_queryables, False
        )
        self.assertEqual(19, len(queryables))
        queryable = queryables.get("id")
        self.assertTrue(isinstance(queryable, QueryableProperty))
        self.assertEqual("ID", queryable.description)
        self.assertEqual(
            "https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json#/id",
            queryable.ref,
        )

    @mock.patch("eodag.api.queryables.requests.get", autospec=True)
    def test_get_provider_queryables(self, mock_requests_get):
        queryables_path = os.path.join(TEST_RESOURCES_PATH, "stac/queryables.json")
        with open(queryables_path) as f:
            provider_queryables = json.load(f)
        mock_requests_get.return_value = MockResponse(
            provider_queryables, status_code=200
        )
        plugins = self.plugins_manager.get_search_plugins(provider="planetary_computer")
        plugin = next(plugins)
        queryables = get_provider_queryables(plugin, "planetary_computer", True)
        self.assertIn("id", queryables)
        self.assertIn("platform", queryables)
        queryable = queryables.get("platform")
        self.assertEqual("Platform", queryable.description)
        self.assertListEqual(["SENTINEL-1A", "SENTINEL-1B"], queryable.values)

    @mock.patch("eodag.api.queryables.requests.get", autospec=True)
    def test_get_provider_product_type_queryables(self, mock_requests_get):
        queryables_path = os.path.join(TEST_RESOURCES_PATH, "stac/queryables.json")
        with open(queryables_path) as f:
            provider_queryables = json.load(f)
        mock_requests_get.return_value = MockResponse(
            provider_queryables, status_code=200
        )
        plugins = self.plugins_manager.get_search_plugins(
            "S1_SAR_GRD", "planetary_computer"
        )
        plugin = next(plugins)
        queryables = get_provider_product_type_queryables(
            plugin, "planetary_computer", "S1_SAR_GRD", True
        )
        self.assertIn("processingLevel", queryables)
        self.assertIn("platform", queryables)
        queryable = queryables.get("platform")
        self.assertEqual("Platform", queryable.description)
        self.assertListEqual(["SENTINEL-1A", "SENTINEL-1B"], queryable.values)

    @mock.patch("eodag.api.queryables.requests.get", autospec=True)
    def test_get_queryables_from_constraints(self, mock_requests_get):
        plugins = self.plugins_manager.get_search_plugins("ERA5_SL", "cop_cds")
        plugin = next(plugins)
        constraints_path = os.path.join(TEST_RESOURCES_PATH, "constraints.json")
        with open(constraints_path) as f:
            constraints = json.load(f)
        mock_requests_get.return_value = MockResponse(constraints, status_code=200)
        # without additional parameters
        queryables = get_queryables_from_constraints(plugin, "ERA5_SL")
        self.assertEqual(7, len(queryables))
        self.assertIn("year", queryables)
        self.assertIn("variable", queryables)
        queryable = queryables.get("variable")
        self.assertEqual("Variable", queryable.description)
        self.assertListEqual(["a", "b", "c", "e", "f"], queryable.values)
        # with one parameter
        queryables = get_queryables_from_constraints(plugin, "ERA5_SL", variable="f")
        self.assertEqual(4, len(queryables))
        self.assertIn("year", queryables)
        queryable = queryables.get("year")
        self.assertListEqual(["2000", "2001"], queryable.values)
        self.assertNotIn("variable", queryables)
        # not existing parameter
        with self.assertRaises(NotAvailableError):
            get_queryables_from_constraints(plugin, "ERA5_SL", parameter="f")
        # not existing value of parameter
        with self.assertRaises(NotAvailableError):
            get_queryables_from_constraints(plugin, "ERA5_SL", variable="g")
        # 2 parameters
        queryables = get_queryables_from_constraints(
            plugin, "ERA5_SL", variable="c", year="2000"
        )
        self.assertEqual(3, len(queryables))
        self.assertNotIn("year", queryables)
        self.assertNotIn("variable", queryables)
        self.assertIn("month", queryables)
        self.assertIn("day", queryables)
        self.assertIn("time", queryables)
        queryable = queryables.get("time")
        self.assertListEqual(["01:00", "12:00", "18:00", "22:00"], queryable.values)
        self.assertEqual("Time", queryable.description)
