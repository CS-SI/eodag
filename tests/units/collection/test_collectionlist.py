# -*- coding: utf-8 -*-
# Copyright 2025, CS GROUP - France, https://www.csgroup.eu/
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
from collections import UserList

from lxml import html

from eodag.api.collection import Collection, CollectionsList


class TestCollectionsList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures for the class."""
        super().setUpClass()
        cls.collections_list = CollectionsList([Collection(id="foo")])

    def test_search_result_is_list_like(self):
        """CollectionsList must provide a list interface"""
        self.assertIsInstance(self.collections_list, UserList)

    def test_search_result_repr_html(self):
        """CollectionsList html repr must be correctly formatted"""
        sr_repr = html.fromstring(self.collections_list._repr_html_())
        self.assertIn("CollectionsList", sr_repr.xpath("//details/summary")[0].text)
