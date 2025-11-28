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
import importlib
import os
import shutil
import sys
import unittest
from tempfile import TemporaryDirectory

from pytest import MonkeyPatch

from tests import TEST_RESOURCES_PATH
from tests.context import EODataAccessGateway
from tests.utils import mock


class TestExternalPluginConfig(unittest.TestCase):
    def setUp(self):
        super(TestExternalPluginConfig, self).setUp()

        # clean sys path
        self._saved_sys_path = sys.path[:]
        sys.path[:] = [p for p in sys.path if "fake_ext_plugin" not in p]
        importlib.invalidate_caches()

        # Mock home and eodag conf directory to tmp dir
        self.tmp_home_dir = TemporaryDirectory()
        self.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, return_value=self.tmp_home_dir.name
        )
        self.expanduser_mock.start()

        self.dag = EODataAccessGateway()

    def tearDown(self):
        super(TestExternalPluginConfig, self).tearDown()

        self.dag._providers.pop("fakeplugin_provider", None)

        # stop Mock and remove tmp config dir
        self.expanduser_mock.stop()
        self.tmp_home_dir.cleanup()
        # reset sys.path
        sys.path[:] = self._saved_sys_path
        importlib.invalidate_caches()

    def test_update_providers_from_ext_plugin(self):
        """Load fake external plugin and check if it updates providers config"""

        default_providers_count = len(self.dag._providers)

        src = os.path.join(TEST_RESOURCES_PATH, "fake_ext_plugin")
        fakeplugin_location = os.path.join(self.tmp_home_dir.name, "fake_ext_plugin")
        shutil.copytree(src, fakeplugin_location)
        shutil.move(
            os.path.join(fakeplugin_location, "eodag_fakeplugin.egg-info_"),
            os.path.join(fakeplugin_location, "eodag_fakeplugin.egg-info"),
        )

        with MonkeyPatch.context() as monkeypatch:
            monkeypatch.syspath_prepend(fakeplugin_location)

            # New EODataAccessGateway instance, check if new conf has been loaded
            self.dag = EODataAccessGateway()
            self.assertEqual(len(self.dag._providers), default_providers_count + 1)
