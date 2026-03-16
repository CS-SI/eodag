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
import json
import unittest
import zipfile

from eodag.api.provider import ProvidersDict
from eodag.config import load_default_config
from eodag.plugins.manager import PluginManager


class BaseDownloadPluginTest(unittest.TestCase):

    plugins_manager: PluginManager

    @classmethod
    def setUpClass(cls):
        super(BaseDownloadPluginTest, cls).setUpClass()
        providers = ProvidersDict.from_configs(load_default_config())
        cls.plugins_manager = PluginManager(providers)

    @classmethod
    def tearDownClass(cls):
        super(BaseDownloadPluginTest, cls).tearDownClass()

    def setUp(self):
        super(BaseDownloadPluginTest, self).setUp()

    def tearDown(self):
        super(BaseDownloadPluginTest, self).tearDown()

    def create_zip_file(self, local_path: str, prepath: str = ""):

        files: dict[str, str] = {
            "file1.txt": "this is a text content",
            "config.json": json.dumps(
                {
                    "type": "Download",
                    "extract": True,
                    "archive_depth": 1,
                    "output_extension": ".json",
                    "max_workers": 4,
                    "ssl_verify": True,
                }
            ),
            "404.html": "<!doctype html><body><h1>404 Not found</h1><hr /></body></html>",
        }
        with zipfile.ZipFile(local_path, "w") as zip:
            for filename in files:
                zip.writestr(
                    "{}{}".format(prepath, filename),
                    files[filename],
                    zipfile.ZIP_DEFLATED,
                )


__all__ = ["BaseDownloadPluginTest"]
