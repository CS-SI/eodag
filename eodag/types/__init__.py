# -*- coding: utf-8 -*-
# Copyright 2023, CS GROUP - France, https://www.csgroup.eu/
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
"""EODAG types"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union, get_args, get_origin

from pydantic import Field
from typing_extensions import Annotated

# Types mapping from JSON Schema and OpenAPI 3.1.0 specifications to Python
# See https://spec.openapis.org/oas/v3.1.0#data-types
JSON_TYPES_MAPPING: Dict[str, type] = {
    "boolean": bool,
    "integer": int,
    "number": float,
    "string": str,
    "array": list,
    "null": type(None),
}


def json_type_to_python(json_type: Union[str, List[str]]) -> type:
    """Get python type from json type https://spec.openapis.org/oas/v3.1.0#data-types

    >>> json_type_to_python("number")
    <class 'float'>
    >>> json_type_to_python(["string", "null"])
    typing.Optional[str]

    :param json_type: the json type
    :returns: the python type
    """
    if isinstance(json_type, list) and len(json_type) > 1:
        return Union[tuple(JSON_TYPES_MAPPING.get(jt, Any) for jt in json_type)]  # type: ignore
    elif isinstance(json_type, str):
        return JSON_TYPES_MAPPING.get(json_type, Any)
    else:
        return Any


def python_type_to_json(python_type: type) -> Optional[Union[str, List[str]]]:
    """Get json type from python https://spec.openapis.org/oas/v3.1.0#data-types

    >>> python_type_to_json(int)
    'integer'
    >>> python_type_to_json(Union[float, str])
    ['number', 'string']

    :param python_type: the python type
    :returns: the json type
    """
    if get_origin(python_type) == Union:
        json_type = list()
        for single_python_type in get_args(python_type):
            if single_python_type in JSON_TYPES_MAPPING.values():
                # JSON_TYPES_MAPPING key from given value
                single_json_type = list(JSON_TYPES_MAPPING.keys())[
                    list(JSON_TYPES_MAPPING.values()).index(single_python_type)
                ]
                json_type.append(single_json_type)
        return json_type
    elif python_type in JSON_TYPES_MAPPING.values():
        # JSON_TYPES_MAPPING key from given value
        return list(JSON_TYPES_MAPPING.keys())[
            list(JSON_TYPES_MAPPING.values()).index(python_type)
        ]
    else:
        return None


def json_field_definition_to_python(json_field_definition: Dict[str, Any]) -> Annotated:
    """Get python field definition from json object

    >>> json_field_definition_to_python(
    ...     {
    ...         'type': 'boolean',
    ...         'title': 'Foo parameter'
    ...     }
    ... )
    typing.Annotated[bool, FieldInfo(annotation=NoneType, required=False, title='Foo parameter')]

    :param python_type: the python type
    :returns: the json type
    """
    python_type = json_type_to_python(json_field_definition.get("type", None))

    field_type_kwargs = dict(
        title=json_field_definition.get("title", None),
        description=json_field_definition.get("description", None),
        pattern=json_field_definition.get("pattern", None),
    )

    if "enum" in json_field_definition and isinstance(
        json_field_definition["enum"], list
    ):
        python_type = Literal[tuple(json_field_definition["enum"])]  # type: ignore

    if "$ref" in json_field_definition:
        field_type_kwargs["json_schema_extra"] = {"$ref": json_field_definition["$ref"]}

    return Annotated[python_type, Field(None, **field_type_kwargs)]
