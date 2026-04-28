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
from unittest import mock

from eodag import EODataAccessGateway
from tests.units.core.base import TestCoreBase
from tests.utils import TEST_RESOURCES_PATH


class TestCoreStrictMode(TestCoreBase):
    def setUp(self):
        super().setUp()
        # Ensure a clean environment for each test
        self.mock_os_environ = mock.patch.dict(os.environ, {}, clear=True)
        self.mock_os_environ.start()

        # This file removes TEST_PRODUCT_2 from the main config, in order to test strict and permissive behavior
        os.environ["EODAG_COLLECTIONS_CFG_FILE"] = os.path.join(
            TEST_RESOURCES_PATH, "file_collections_modes.yml"
        )
        os.environ["EODAG_PROVIDERS_CFG_FILE"] = os.path.join(
            TEST_RESOURCES_PATH, "file_providers_override.yml"
        )

    def tearDown(self):
        self.mock_os_environ.stop()
        super().tearDown()

    def test_list_collections_strict_mode(self):
        """list_collections must only return collections from the main config in strict mode"""
        try:
            os.environ["EODAG_STRICT_COLLECTIONS"] = "true"
            dag = EODataAccessGateway()

            # In strict mode, TEST_PRODUCT_2 should not be listed
            collections = dag.list_collections(fetch_providers=False)
            ids = [col.id for col in collections]
            self.assertNotIn("TEST_PRODUCT_2", ids)

        finally:
            os.environ.pop("EODAG_STRICT_COLLECTIONS", None)

    def test_list_collections_permissive_mode(self):
        """list_collections must include provider-only collections in permissive mode"""
        if "EODAG_STRICT_COLLECTIONS" in os.environ:
            del os.environ["EODAG_STRICT_COLLECTIONS"]

        dag = EODataAccessGateway()

        # In permissive mode, TEST_PRODUCT_2 should be listed
        collections = dag.list_collections(fetch_providers=False)
        ids = [col.id for col in collections]
        self.assertIn("TEST_PRODUCT_2", ids)
