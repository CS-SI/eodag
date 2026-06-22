# -*- coding: utf-8 -*-
# Copyright 2026, CS GROUP - France, https://www.csgroup.eu/
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

import subprocess
import sys
import unittest


class TestEodagInit(unittest.TestCase):
    """Test that the eodag package properly exposes its modules"""

    def test_eodag_config_module_accessible_in_fresh_interpreter(self):
        """Test that eodag.config module is accessible in a fresh Python process"""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import eodag; print(eodag.config.EXT_COLLECTIONS_CONF_URI)",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"Command failed with stderr: {result.stderr}",
        )
        self.assertTrue(result.stdout.strip().startswith("https://"))

    def test_eodag_config_ext_collections_conf_uri_accessible(self):
        """Test that eodag.config.EXT_COLLECTIONS_CONF_URI is accessible"""
        import eodag

        # This is the use case from the GitHub Actions workflow
        uri = eodag.config.EXT_COLLECTIONS_CONF_URI
        self.assertIsNotNone(uri)
        self.assertIsInstance(uri, str)
        self.assertTrue(uri.startswith("https://"))

    def test_eodag_lazy_imports_still_work(self):
        """Test that existing lazy imports still work"""
        import eodag

        # Test all existing lazy imports
        self.assertTrue(hasattr(eodag, "EODataAccessGateway"))
        self.assertTrue(hasattr(eodag, "EOProduct"))
        self.assertTrue(hasattr(eodag, "SearchResult"))
        self.assertTrue(hasattr(eodag, "setup_logging"))

        # These should be callable/usable
        self.assertIsNotNone(eodag.EODataAccessGateway)
        self.assertIsNotNone(eodag.EOProduct)
        self.assertIsNotNone(eodag.SearchResult)
        self.assertIsNotNone(eodag.setup_logging)
