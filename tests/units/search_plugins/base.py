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
from pathlib import Path

from eodag.api.provider import ProvidersDict
from eodag.config import load_default_config
from eodag.plugins.manager import PluginManager
from eodag.utils import get_geometry_from_various
from tests.utils import TEST_RESOURCES_PATH


class BaseSearchPluginTest(unittest.TestCase):
    def setUp(self):
        super(BaseSearchPluginTest, self).setUp()
        providers = ProvidersDict.from_configs(load_default_config())
        self.plugins_manager = PluginManager(providers)
        self.collection = "S2_MSI_L1C"
        geom = [137.772897, 13.134202, 153.749135, 23.885986]
        geometry = get_geometry_from_various([], geometry=geom)
        self.search_criteria_s2_msi_l1c = {
            "collection": self.collection,
            "start_datetime": "2020-08-08",
            "end_datetime": "2020-08-16",
            "geometry": geometry,
        }
        self.provider_resp_dir = Path(TEST_RESOURCES_PATH) / "provider_responses"

    def get_search_plugin(self, collection=None, provider=None):
        return next(
            self.plugins_manager.get_search_plugins(
                collection=collection, provider=provider
            )
        )

    def get_auth_plugin(self, search_plugin):
        return self.plugins_manager.get_auth_plugin(search_plugin)


__all__ = ["BaseSearchPluginTest"]
