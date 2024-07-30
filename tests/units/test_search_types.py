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

from pydantic import ValidationError

from eodag.types import search_args
from eodag.utils.exceptions import ValidationError as EodagValidationError


class TestStacSearch(unittest.TestCase):
    def test_search_sort_by_arg(self):
        """search used with "sort_by" argument must not raise errors if the argument is correct"""
        # "sort_by" argument must be a list of tuples of two elements and the second element must be "ASC" or "DESC"
        search_args.SearchArgs.model_validate(
            {
                "productType": "dummy_product_type",
                "sort_by": [("eodagSortParam", "ASC")],
            }
        )
        search_args.SearchArgs.model_validate(
            {
                "productType": "dummy_product_type",
                "sort_by": [("eodagSortParam", "DESC")],
            }
        )

    def test_search_sort_by_arg_with_errors(self):
        """search used with "sort_by" argument must raise errors if the argument is incorrect"""
        # raise a Pydantic error with an empty list
        with self.assertRaises(ValidationError) as context:
            search_args.SearchArgs.model_validate(
                {"productType": "dummy_product_type", "sort_by": []}
            )
        self.assertIn(
            "List should have at least 1 item after validation, not 0",
            str(context.exception),
        )
        # raise a Pydantic error with syntax errors
        with self.assertRaises(ValidationError) as context:
            search_args.SearchArgs.model_validate(
                {"productType": "dummy_product_type", "sort_by": "eodagSortParam ASC"}
            )
        self.assertIn(
            "Sort argument must be a list of tuple(s), got a '<class 'str'>' instead",
            str(context.exception),
        )
        with self.assertRaises(ValidationError) as context:
            search_args.SearchArgs.model_validate(
                {"productType": "dummy_product_type", "sort_by": ["eodagSortParam ASC"]}
            )
        self.assertIn(
            "Sort argument must be a list of tuple(s), got a list of '<class 'str'>' instead",
            str(context.exception),
        )
        # raise a Pydantic error with a wrong sorting order
        with self.assertRaises(ValidationError) as context:
            search_args.SearchArgs.model_validate(
                {
                    "productType": "dummy_product_type",
                    "sort_by": [("eodagSortParam", " wrong_order ")],
                }
            )
        self.assertIn(
            "Sorting order must be set to 'ASC' (ASCENDING) or 'DESC' (DESCENDING), "
            "got 'WRONG_ORDER' with 'eodagSortParam' instead",
            str(context.exception),
        )
        # raise an EODAG error with a sorting order called with different values for a same sorting parameter
        with self.assertRaises(EodagValidationError) as e:
            search_args.SearchArgs.model_validate(
                {
                    "productType": "dummy_product_type",
                    "sort_by": [("eodagSortParam", "ASC"), ("eodagSortParam", "DESC")],
                }
            )
        self.assertIn(
            "'eodagSortParam' parameter is called several times to sort results with different sorting "
            "orders. Please set it to only one ('ASC' (ASCENDING) or 'DESC' (DESCENDING))",
            str(e.exception.message),
        )
