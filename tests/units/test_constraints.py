import json
import os
import unittest

from eodag.api.constraints import get_constraint_queryables_with_additional_params
from eodag.config import load_default_config
from eodag.plugins.manager import PluginManager
from eodag.utils.exceptions import NotAvailableError
from tests import TEST_RESOURCES_PATH


class TestConstraints(unittest.TestCase):
    def setUp(self) -> None:
        super(TestConstraints, self).setUp()
        providers_config = load_default_config()
        self.plugins_manager = PluginManager(providers_config)

    def test_get_constraint_queryables_with_additional_params(self):
        constraints_path = os.path.join(TEST_RESOURCES_PATH, "constraints.json")
        with open(constraints_path) as f:
            constraints = json.load(f)
        plugins = self.plugins_manager.get_search_plugins("ERA5_SL", "cop_cds")
        plugin = next(plugins)
        queryables = get_constraint_queryables_with_additional_params(
            constraints, {"variable": "f"}, plugin, "ERA5_SL"
        )
        self.assertEqual(4, len(queryables))
        self.assertIn("year", queryables)
        queryable = queryables.get("year")
        self.assertSetEqual({"2000", "2001"}, queryable["enum"])
        self.assertNotIn("variable", queryables)
        # not existing parameter
        with self.assertRaises(NotAvailableError):
            get_constraint_queryables_with_additional_params(
                constraints, {"param": "f"}, plugin, "ERA5_SL"
            )
        # not existing value of parameter
        with self.assertRaises(NotAvailableError):
            get_constraint_queryables_with_additional_params(
                constraints, {"variable": "g"}, plugin, "ERA5_SL"
            )
        # 2 parameters
        queryables = get_constraint_queryables_with_additional_params(
            constraints, {"variable": "c", "year": "2000"}, plugin, "ERA5_SL"
        )
        self.assertEqual(3, len(queryables))
        self.assertNotIn("year", queryables)
        self.assertNotIn("variable", queryables)
        self.assertIn("month", queryables)
        self.assertIn("day", queryables)
        self.assertIn("time", queryables)
        queryable = queryables.get("time")
        self.assertSetEqual({"01:00", "12:00", "18:00", "22:00"}, queryable["enum"])
