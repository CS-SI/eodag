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

import os

import yaml

from eodag import EODataAccessGateway
from eodag.api.provider import ProviderConfig
from eodag.utils import cached_yaml_load_all
from tests.units.core.base import TestCoreBase
from tests.utils import TEST_RESOURCES_PATH


class TestCoreConfWithEnvVar(TestCoreBase):
    def tearDown(self):
        """Teardown run after every test"""
        if hasattr(self, "dag"):
            del self.dag

    def test_core_object_prioritize_locations_file_in_envvar(self):
        """The core object must use the locations file pointed by the EODAG_LOCS_CFG_FILE env var"""
        try:
            os.environ["EODAG_LOCS_CFG_FILE"] = os.path.join(
                TEST_RESOURCES_PATH, "file_locations_override.yml"
            )
            self.dag = EODataAccessGateway()
            self.assertEqual(
                self.dag.locations_config,
                [dict(attr="dummyattr", name="dummyname", path="dummypath.shp")],
            )
        finally:
            os.environ.pop("EODAG_LOCS_CFG_FILE", None)

    def test_core_object_prioritize_config_file_in_envvar(self):
        """The core object must use the config file pointed by the EODAG_CFG_FILE env var"""
        try:
            os.environ["EODAG_CFG_FILE"] = os.path.join(
                TEST_RESOURCES_PATH, "file_config_override.yml"
            )
            self.dag = EODataAccessGateway()
            # usgs priority is set to 5 in the test config overrides
            self.assertEqual(self.dag.get_preferred_provider(), ("usgs", 5))
            # cop_dataspace outputs prefix is set to /data
            self.assertEqual(
                self.dag._providers["cop_dataspace"].config.download.output_dir, "/data"
            )
        finally:
            os.environ.pop("EODAG_CFG_FILE", None)

    def test_core_object_prioritize_providers_file_in_envvar(self):
        """The core object must use the providers conf file pointed by the EODAG_PROVIDERS_CFG_FILE env var"""
        try:
            os.environ["EODAG_PROVIDERS_CFG_FILE"] = os.path.join(
                TEST_RESOURCES_PATH, "file_providers_override.yml"
            )
            self.dag = EODataAccessGateway()
            # only foo_provider in conf
            self.assertEqual(self.dag.providers.names, ["foo_provider"])
            self.assertEqual(
                self.dag._providers["foo_provider"].search_config.api_endpoint,
                "https://foo.bar/search",
            )
        finally:
            os.environ.pop("EODAG_PROVIDERS_CFG_FILE", None)

    def test_core_collections_config_envvar(self):
        """collections should be loaded from file defined in env var"""
        # setup providers config
        config_path = os.path.join(TEST_RESOURCES_PATH, "file_providers_override.yml")
        providers_config: list[ProviderConfig] = cached_yaml_load_all(config_path)
        providers_config[0].products["TEST_PRODUCT_1"] = {"_collection": "TP1"}
        providers_config[0].products["TEST_PRODUCT_2"] = {"_collection": "TP2"}
        with open(
            os.path.join(self.tmp_home_dir.name, "file_providers_override2.yml"), "w"
        ) as f:
            f.write(yaml.dump(providers_config[0]))
        # set env variables
        os.environ["EODAG_PROVIDERS_CFG_FILE"] = os.path.join(
            self.tmp_home_dir.name, "file_providers_override2.yml"
        )
        os.environ["EODAG_COLLECTIONS_CFG_FILE"] = os.path.join(
            TEST_RESOURCES_PATH, "file_collections_override.yml"
        )

        # check collections
        try:
            self.dag = EODataAccessGateway()
            col = self.dag.list_collections(fetch_providers=False)
            self.assertEqual(2, len(col))
            self.assertEqual("TEST_PRODUCT_1", col[0].id)
            self.assertEqual("TEST_PRODUCT_2", col[1].id)
        finally:
            # remove env variables
            os.environ.pop("EODAG_PROVIDERS_CFG_FILE", None)
            os.environ.pop("EODAG_COLLECTIONS_CFG_FILE", None)
