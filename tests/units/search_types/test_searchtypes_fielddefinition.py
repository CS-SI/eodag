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

from pydantic import AliasChoices
from pydantic_core import PydanticUndefined
from typing_extensions import get_args, get_origin

from eodag.types import json_field_definition_to_python


class TestFieldDefinition(unittest.TestCase):
    def test_json_field_definition_to_python(self):
        """Python field definition reflects the provided configuration"""

        # not required
        python_field_def = json_field_definition_to_python(
            json_field_definition={
                "title": "Model level",
                "type": "array",
                "description": "Model level 1 is the top of the atmosphere. Model level 60 is the Earth's surface.",
            },
            default_value=None,
            required=False,
            validation_alias=AliasChoices("ecmwf:model_level", "model_level"),
            serialization_alias="ecmwf:model_level",
        )
        args = get_args(python_field_def)
        self.assertEqual(args[0], list)
        self.assertEqual(args[1].title, "Model level")
        self.assertIsNone(args[1].get_default())
        self.assertEqual(args[1].is_required(), False)
        self.assertEqual(
            args[1].validation_alias,
            AliasChoices("ecmwf:model_level", "model_level"),
        )
        self.assertEqual(args[1].serialization_alias, "ecmwf:model_level")

        # same validation and serialization alias
        python_field_def = json_field_definition_to_python(
            json_field_definition={
                "title": "Lorem",
                "type": "array",
                "description": "Lorem ipsum dolor sit amet.",
            },
            default_value=None,
            required=False,
            validation_alias="lorem",
            serialization_alias="lorem",
        )
        args = get_args(python_field_def)
        self.assertEqual(args[0], list)
        self.assertEqual(args[1].title, "Lorem")
        self.assertIsNone(args[1].get_default())
        self.assertEqual(args[1].is_required(), False)
        self.assertEqual(args[1].validation_alias, "lorem")
        self.assertEqual(args[1].serialization_alias, "lorem")

        # python type is string
        python_field_def = json_field_definition_to_python(
            json_field_definition={
                "title": "Date",
                "type": "string",
                "enum": ["2003-01-01/2024-12-31"],
                "description": "date formatted like yyyy-mm-dd/yyyy-mm-dd",
            },
            default_value=None,
            required=True,
            validation_alias=AliasChoices("ecmwf:date", "date"),
            serialization_alias="ecmwf:date",
        )
        args = get_args(python_field_def)
        self.assertEqual(args[0], Literal["2003-01-01/2024-12-31"])
        self.assertEqual(args[1].title, "Date")
        # required and no default value provided
        self.assertEqual(args[1].get_default(), PydanticUndefined)
        self.assertEqual(args[1].is_required(), True)
        self.assertEqual(args[1].validation_alias, AliasChoices("ecmwf:date", "date"))
        self.assertEqual(args[1].serialization_alias, "ecmwf:date")

        # python type is dict
        python_field_def = json_field_definition_to_python(
            json_field_definition={
                "title": "Location",
                "type": "object",
                "properties": {
                    "longitude": {"type": "number", "maximum": 180, "minimum": -180},
                    "latitude": {"type": "number", "maximum": 90, "minimum": -90},
                },
            },
            default_value=None,
            required=True,
            validation_alias=AliasChoices("ecmwf:location", "location"),
            serialization_alias="ecmwf:location",
        )
        args = get_args(python_field_def)
        # cannot use isinstance with TypedDict
        self.assertEqual(args[0].__name__, "dictionary")
        self.assertEqual(args[1].title, "Location")
        self.assertIsInstance
        # required and no default value provided
        self.assertEqual(args[1].get_default(), PydanticUndefined)
        self.assertEqual(args[1].is_required(), True)
        self.assertEqual(
            args[1].validation_alias,
            AliasChoices("ecmwf:location", "location"),
        )
        self.assertEqual(args[1].serialization_alias, "ecmwf:location")

        # python type is list, items is a list
        python_field_def = json_field_definition_to_python(
            json_field_definition={
                "title": "Sub-region extraction",
                "type": "array",
                "minItems": 4,
                "additionalItems": False,
                "items": [
                    {"type": "number", "maximum": 180, "minimum": -180},
                    {"type": "number", "maximum": 90, "minimum": -90},
                    {"type": "number", "maximum": 180, "minimum": -180},
                    {"type": "number", "maximum": 90, "minimum": -90},
                ],
            },
            default_value=[42.0, 10.0, 40.0, 12.0],
            required=False,
            validation_alias=AliasChoices("ecmwf:area", "area"),
            serialization_alias="ecmwf:area",
        )
        args = get_args(python_field_def)
        self.assertEqual(get_origin(args[0]), tuple)
        self.assertEqual(args[1].title, "Sub-region extraction")
        self.assertEqual(args[1].get_default(), [42.0, 10.0, 40.0, 12.0])
        self.assertEqual(args[1].is_required(), False)
        self.assertEqual(args[1].validation_alias, AliasChoices("ecmwf:area", "area"))
        self.assertEqual(args[1].serialization_alias, "ecmwf:area")

        # python type is list, items is const
        python_field_def = json_field_definition_to_python(
            json_field_definition={
                "title": "Time",
                "type": "array",
                "items": {"const": "00:00", "type": "string"},
                "description": "Model base time as HH:MM (UTC)",
            },
            default_value="00:00",
            required=True,
            validation_alias=AliasChoices("ecmwf:time", "time"),
            serialization_alias="ecmwf:time",
        )
        args = get_args(python_field_def)
        self.assertEqual(args[0], list[Literal["00:00"]])
        self.assertEqual(args[1].title, "Time")
        self.assertEqual(args[1].get_default(), "00:00")
        # not required if the default value is provided
        self.assertEqual(args[1].is_required(), False)
        self.assertEqual(args[1].validation_alias, AliasChoices("ecmwf:time", "time"))
        self.assertEqual(args[1].serialization_alias, "ecmwf:time")

        # python type is list, items is an enum
        python_field_def = json_field_definition_to_python(
            json_field_definition={
                "title": "Variable",
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["10m_u_component_of_wind", "10m_v_component_of_wind"],
                },
            },
            default_value=["10m_u_component_of_wind"],
            required=True,
            validation_alias=AliasChoices("ecmwf:variable", "variable"),
            serialization_alias="ecmwf:variable",
        )
        args = get_args(python_field_def)
        self.assertEqual(
            args[0],
            list[Literal["10m_u_component_of_wind", "10m_v_component_of_wind"]],
        )
        self.assertEqual(args[1].title, "Variable")
        self.assertEqual(args[1].get_default(), ["10m_u_component_of_wind"])
        # not required if the default value is provided
        self.assertEqual(args[1].is_required(), False)
        self.assertEqual(
            args[1].validation_alias,
            AliasChoices("ecmwf:variable", "variable"),
        )
        self.assertEqual(args[1].serialization_alias, "ecmwf:variable")

        # enum
        python_field_def = json_field_definition_to_python(
            json_field_definition={
                "title": "Sky type",
                "type": "string",
                "enum": ["clear"],
            },
            default_value="clear",
            required=True,
            validation_alias=AliasChoices("ecmwf:sky_type", "sky_type"),
            serialization_alias="ecmwf:sky_type",
        )
        args = get_args(python_field_def)
        self.assertEqual(args[0], Literal["clear"])
        self.assertEqual(args[1].title, "Sky type")
        self.assertEqual(args[1].get_default(), "clear")
        # not required if the default value is provided
        self.assertEqual(args[1].is_required(), False)
        self.assertEqual(
            args[1].validation_alias,
            AliasChoices("ecmwf:sky_type", "sky_type"),
        )
        self.assertEqual(args[1].serialization_alias, "ecmwf:sky_type")

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
