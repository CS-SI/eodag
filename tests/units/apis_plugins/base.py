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
from tempfile import TemporaryDirectory
from unittest import mock

from eodag.api.provider import ProvidersDict
from eodag.config import load_default_config
from eodag.plugins.manager import PluginManager


class BaseApisPluginTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(BaseApisPluginTest, cls).setUpClass()
        providers = ProvidersDict.from_configs(load_default_config())
        cls.plugins_manager = PluginManager(providers)
        # Mock home and eodag conf directory to tmp dir
        cls.tmp_home_dir = TemporaryDirectory()
        expanduser_mock_side_effect = (
            lambda *x: x[0]
            .replace("~user", cls.tmp_home_dir.name)
            .replace("~", cls.tmp_home_dir.name)
        )
        cls.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, side_effect=expanduser_mock_side_effect
        )
        cls.expanduser_mock.start()

    @classmethod
    def tearDownClass(cls):
        super(BaseApisPluginTest, cls).tearDownClass()
        # stop Mock and remove tmp config dir
        cls.expanduser_mock.stop()
        cls.tmp_home_dir.cleanup()

    def get_search_plugin(self, collection=None, provider=None):
        return next(
            self.plugins_manager.get_search_plugins(
                collection=collection, provider=provider
            )
        )


__all__ = ["BaseApisPluginTest"]
