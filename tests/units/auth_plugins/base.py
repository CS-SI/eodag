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

from eodag.api.provider import ProvidersDict
from eodag.plugins.manager import PluginManager


class BaseAuthPluginTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.plugins_manager = PluginManager(ProvidersDict())
        cls.auth_plugins = {}

    def tearDown(self):
        super().tearDown()
        # remove credentials set during tests
        for provider in self.plugins_manager.providers:
            self.get_auth_plugin(provider).config.__dict__.pop("credentials", None)

    def get_auth_plugin(self, provider):
        if provider in self.auth_plugins:
            return self.auth_plugins[provider]
        auth_plugin = next(self.plugins_manager.get_auth_plugins(provider))
        self.auth_plugins[provider] = auth_plugin
        return auth_plugin


__all__ = ["BaseAuthPluginTest"]
