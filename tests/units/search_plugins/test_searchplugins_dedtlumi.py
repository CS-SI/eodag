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
from eodag.utils.exceptions import ValidationError
from tests.units.search_plugins.base import BaseSearchPluginTest


class TestSearchPluginDedtLumi(BaseSearchPluginTest):
    def setUp(self):
        super(TestSearchPluginDedtLumi, self).setUp()
        self.provider = "dedt_lumi"
        self.search_plugin = self.get_search_plugin(provider=self.provider)
        self.collection = "DT_CLIMATE_ADAPTATION"

    def test_plugins_apis_dedt_lumi_query_feature(self):
        """Test the proper handling of geom into ecmwf:feature"""

        # Search using geometry
        _expected_feature = {
            "shape": [[43.0, 1.0], [44.0, 1.0], [44.0, 2.0], [43.0, 2.0], [43.0, 1.0]],
            "type": "polygon",
        }
        results = self.search_plugin.query(
            collection=self.collection,
            start="2021-01-01",
            geometry={"lonmin": 1, "latmin": 43, "lonmax": 2, "latmax": 44},
        )
        eoproduct = results.data[0]

        self.assertDictEqual(_expected_feature, eoproduct.properties["ecmwf:feature"])

        # Unsupported multi-polygon
        with self.assertRaises(ValidationError):
            self.search_plugin.query(
                collection=self.collection,
                start="2021-01-01",
                geometry="""MULTIPOLYGON (
                    ((1.23 43.42, 1.23 43.76, 1.68 43.76, 1.68 43.42, 1.23 43.42)),
                    ((2.23 43.42, 2.23 43.76, 3.68 43.76, 3.68 43.42, 2.23 43.42))
                )""",
            )
