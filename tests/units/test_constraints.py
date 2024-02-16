# -*- coding: utf-8 -*-
# Copyright 2024, CS GROUP - France, https://www.csgroup.eu/
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
import unittest

from eodag.config import load_default_config
from eodag.plugins.manager import PluginManager
from eodag.utils.constraints import get_constraint_queryables_with_additional_params
from eodag.utils.exceptions import ValidationError
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

        # filter on one parameter
        queryables = get_constraint_queryables_with_additional_params(
            constraints, {"variable": "f"}, plugin, "ERA5_SL"
        )
        self.assertEqual(6, len(queryables))
        self.assertIn("year", queryables)
        queryable = queryables.get("year")
        self.assertSetEqual({"2000", "2001"}, queryable["enum"])
        self.assertIn("variable", queryables)

        # not existing parameter
        queryables = get_constraint_queryables_with_additional_params(
            constraints, {"param": "f"}, plugin, "ERA5_SL"
        )
        self.assertIn("not_available", queryables)
        self.assertEqual("param", queryables["not_available"]["enum"].pop())

        # not existing value of parameter
        with self.assertRaises(ValidationError):
            get_constraint_queryables_with_additional_params(
                constraints, {"variable": "g"}, plugin, "ERA5_SL"
            )

        # with params/defaults
        queryables = get_constraint_queryables_with_additional_params(
            constraints,
            {"variable": "c", "type": "B", "year": "2000"},
            plugin,
            "ERA5_SL",
        )
        self.assertEqual(7, len(queryables))
        self.assertIn("year", queryables)
        self.assertIn("variable", queryables)
        self.assertIn("month", queryables)
        self.assertIn("day", queryables)
        self.assertIn("time", queryables)
        self.assertIn("type", queryables)
        queryable = queryables.get("time")
        self.assertSetEqual({"01:00", "12:00", "18:00", "22:00"}, queryable["enum"])
        queryable = queryables.get("type")
        self.assertSetEqual({"C", "B"}, queryable["enum"])
        queryable = queryables.get("year")
        self.assertSetEqual({"2000", "2001"}, queryable["enum"])
