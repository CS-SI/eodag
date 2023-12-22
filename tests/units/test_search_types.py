# -*- coding: utf-8 -*-
# Copyright 2024, CS GROUP - France, https://www.csgroup.eu/
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
from unittest import mock

from pydantic_core import ValidationError

from eodag.types import search_args


class TestStacSearch(unittest.TestCase):
    def test_search_sort_by_arg(self):
        """search used with "sortBy" argument must not raise errors if the argument is correct"""
        # "sortBy" argument must be a list of tuples of two elements and the second element must be "ASC" or "DESC"
        search_args.SearchArgs.model_validate(
            {"productType": "dummy_product_type", "sortBy": [("eodagSortParam", "ASC")]}
        )
        search_args.SearchArgs.model_validate(
            {"productType": "dummy_product_type", "sortBy": [("eodagSortParam", "DESC")]}
        )

    def test_search_sort_by_arg_with_errors(self):
        """search used with "sortBy" argument must raise errors if the argument is incorrect"""
        # raise an error with an empty list
        with self.assertRaises(ValidationError) as context:
            search_args.SearchArgs.model_validate(
                {"productType": "dummy_product_type", "sortBy": []}
            )
        self.assertIn(
            "List should have at least 1 item after validation, not 0",
            str(context.exception),
        )
        # raise an error with syntax errors
        with self.assertRaises(ValidationError) as context:
            search_args.SearchArgs.model_validate(
                {"productType": "dummy_product_type", "sortBy": "eodagSortParam ASC"}
            )
        self.assertIn(
            "Sort argument must be a list of tuple(s), got a '<class 'str'>' instead",
            str(context.exception),
        )
        with self.assertRaises(ValidationError) as context:
            search_args.SearchArgs.model_validate(
                {"productType": "dummy_product_type", "sortBy": ["eodagSortParam ASC"]}
            )
        self.assertIn(
            "Sort argument must be a list of tuple(s), got a list of '<class 'str'>' instead",
            str(context.exception),
        )
        # raise an error with a wrong sorting order
        with self.assertRaises(ValidationError) as context:
            search_args.SearchArgs.model_validate(
                {"productType": "dummy_product_type", "sortBy": [("eodagSortParam", " wrong_order ")]}
            )
        self.assertIn(
            "Sorting order must be set to 'ASC' (ASCENDING) or 'DESC' (DESCENDING), got 'WRONG_ORDER' with 'eodagSortParam' instead",
            str(context.exception),
        )
