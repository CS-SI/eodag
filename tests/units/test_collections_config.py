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
import unittest
from pathlib import Path

import yaml


class TestCollectionsConfig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestCollectionsConfig, cls).setUpClass()
        collections_path = (
            Path(__file__).parents[2] / "eodag" / "resources" / "collections.yml"
        )
        with open(collections_path, encoding="utf-8") as fh:
            cls.collections = yaml.safe_load(fh)

    def test_collection_processing_levels_use_stac_short_names(self):
        """Default collection processing levels must use STAC short names"""
        long_processing_levels = {
            collection_id: collection["processing:level"]
            for collection_id, collection in self.collections.items()
            if isinstance(collection, dict)
            and isinstance(collection.get("processing:level"), str)
            and collection["processing:level"].lower().startswith("level")
        }

        self.assertEqual(long_processing_levels, {})

    def test_collection_processing_levels_are_not_number_only(self):
        """Default collection processing levels must not be number-only values"""
        number_only_processing_levels = {
            collection_id: collection["processing:level"]
            for collection_id, collection in self.collections.items()
            if isinstance(collection, dict)
            and isinstance(collection.get("processing:level"), str)
            and collection["processing:level"].strip().isdigit()
        }

        self.assertEqual(number_only_processing_levels, {})
