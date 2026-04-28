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
from typing import Literal

from pydantic import AliasChoices, ValidationError, create_model

from eodag.types import queryables


class TestQueryables(unittest.TestCase):
    def setUp(self):
        super(TestQueryables, self).setUp()
        self.model = create_model(
            "Queryables",
            ecmwf_date=(
                Literal[
                    "2020-10-06",
                    "2021-05-18",
                    "2021-10-12",
                    "2023-06-27",
                    "2024-11-12/2026-01-12",
                ],
                ...,
            ),
            __base__=queryables.Queryables,
        )

    def test_search_ecmwf_date(self):
        """search used with "ecmwf_date" argument must not raise errors if the argument is correct"""
        # match with single value
        self.model.model_validate(
            {
                "collection": "dummy_collection",
                "ecmwf_date": "2020-10-06",
            }
        )
        # match with date interval
        self.model.model_validate(
            {
                "collection": "dummy_collection",
                "ecmwf_date": "2025-01-10",
            }
        )
        # match with date interval
        self.model.model_validate(
            {
                "collection": "dummy_collection",
                "ecmwf_date": "2025-01-05/2025-01-10",
            }
        )

    def test_search_ecmwf_date_with_errors(self):
        """search used with "ecmwf_date" argument must raise errors if the argument is incorrect"""
        # not a string
        with self.assertRaises(ValidationError) as context:
            self.model.model_validate(
                {"collection": "dummy_collection", "ecmwf_date": ["foo"]}
            )
        self.assertIn(
            "date must be a string formatted as single date ('yyyy-mm-dd') or range ('yyyy-mm-dd/yyyy-mm-dd')",
            str(context.exception),
        )
        # empty string
        with self.assertRaises(ValidationError) as context:
            self.model.model_validate(
                {"collection": "dummy_collection", "ecmwf_date": ""}
            )
        self.assertIn(
            "date must be a string formatted as single date ('yyyy-mm-dd') or range ('yyyy-mm-dd/yyyy-mm-dd')",
            str(context.exception),
        )
        # wrong format
        with self.assertRaises(ValidationError) as context:
            self.model.model_validate(
                {"collection": "dummy_collection", "ecmwf_date": "2025-31-12"}
            )
        self.assertIn(
            "date must be a string formatted as single date ('yyyy-mm-dd') or range ('yyyy-mm-dd/yyyy-mm-dd')",
            str(context.exception),
        )
        # invalid date
        with self.assertRaises(ValidationError) as context:
            self.model.model_validate(
                {"collection": "dummy_collection", "ecmwf_date": "2025-02-29"}
            )
        self.assertIn(
            "date must follow 'yyyy-mm-dd' format",
            str(context.exception),
        )
        # end date before start date
        with self.assertRaises(ValidationError) as context:
            self.model.model_validate(
                {
                    "collection": "dummy_collection",
                    "ecmwf_date": "2025-01-10/2025-01-05",
                }
            )
        self.assertIn(
            "date range end must be after start",
            str(context.exception),
        )
        # date not allowed by constraints
        with self.assertRaises(ValidationError) as context:
            self.model.model_validate(
                {"collection": "dummy_collection", "ecmwf_date": "2020-10-07"}
            )
        self.assertIn(
            "date not allowed",
            str(context.exception),
        )
        with self.assertRaises(ValidationError) as context:
            self.model.model_validate(
                {
                    "collection": "dummy_collection",
                    "ecmwf_date": "2020-10-06/2020-10-10",
                }
            )
        self.assertIn(
            "date not allowed",
            str(context.exception),
        )
        with self.assertRaises(ValidationError) as context:
            self.model.model_validate(
                {
                    "collection": "dummy_collection",
                    "ecmwf_date": "2024-11-10/2024-11-12",
                }
            )
        self.assertIn(
            "date not allowed",
            str(context.exception),
        )

    def test_ecmwf_extension_dual_aliases(self):
        """EcmwfItemProperties fields must expose both stac-prefixed and unprefixed aliases."""
        from eodag.types.stac_extensions import EcmwfItemProperties

        field = EcmwfItemProperties.model_fields["ecmwf_data_format"]
        # alias and serialization_alias use the stac-prefixed form
        self.assertEqual(field.alias, "ecmwf:data_format")
        self.assertEqual(field.serialization_alias, "ecmwf:data_format")
        # validation_alias accepts both prefixed and unprefixed forms
        self.assertIsInstance(field.validation_alias, AliasChoices)
        self.assertEqual(
            field.validation_alias.choices, ["ecmwf:data_format", "data_format"]
        )
