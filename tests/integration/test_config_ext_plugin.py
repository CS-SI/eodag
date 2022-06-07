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
import unittest
from tempfile import TemporaryDirectory

import pkg_resources

from tests import TEST_RESOURCES_PATH
from tests.context import EODataAccessGateway
from tests.utils import mock


class TestExternalPluginConfig(unittest.TestCase):
    def setUp(self):
        super(TestExternalPluginConfig, self).setUp()
        # Mock home and eodag conf directory to tmp dir
        self.tmp_home_dir = TemporaryDirectory()
        self.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, return_value=self.tmp_home_dir.name
        )
        self.expanduser_mock.start()

        self.dag = EODataAccessGateway()

    def tearDown(self):
        super(TestExternalPluginConfig, self).tearDown()

        self.dag.providers_config.pop("fakeplugin_provider", None)

        # remove entry point manually, see https://github.com/pypa/setuptools/issues/1759
        distpath = pkg_resources.working_set.by_key.pop("eodag-fakeplugin").location
        pkg_resources.working_set.entry_keys.pop(distpath)
        pkg_resources.working_set.entries.remove(distpath)

        # stop Mock and remove tmp config dir
        self.expanduser_mock.stop()
        self.tmp_home_dir.cleanup()

    def test_update_providers_from_ext_plugin(self):
        """Load fake external plugin and check if it updates providers config"""

        default_providers_count = len(self.dag.providers_config)

        fakeplugin_location = os.path.join(TEST_RESOURCES_PATH, "fake_ext_plugin")

        # Create the fake entry point definition
        ep = pkg_resources.EntryPoint.parse(
            "FakePluginAPI = eodag_fakeplugin:FakePluginAPI"
        )
        # Create a fake distribution to insert into the global working_set
        d = pkg_resources.Distribution(
            location=fakeplugin_location,
            project_name="eodag_fakeplugin",
            version="0.1",
        )
        ep.dist = d
        # Add the mapping to the fake EntryPoint
        d._ep_map = {"eodag.plugins.api": {"FakePluginAPI": ep}}
        # Add the fake distribution to the global working_set
        pkg_resources.working_set.add(d, fakeplugin_location)

        # New EODataAccessGateway instance, check if new conf has been loaded
        self.dag = EODataAccessGateway()
        self.assertEqual(len(self.dag.providers_config), default_providers_count + 1)
