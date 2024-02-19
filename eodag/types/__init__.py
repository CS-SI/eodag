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

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import Field
from pydantic.fields import FieldInfo

from eodag.utils import Annotated, copy_deepcopy, get_args, get_origin
from eodag.utils.exceptions import ValidationError

# Types mapping from JSON Schema and OpenAPI 3.1.0 specifications to Python
# See https://spec.openapis.org/oas/v3.1.0#data-types
JSON_TYPES_MAPPING: Dict[str, type] = {
    "boolean": bool,
    "integer": int,
    "number": float,
    "string": str,
    "array": list,
    "object": dict,
    "null": type(None),
}


def json_type_to_python(json_type: Union[str, List[str]]) -> type:
    """Get python type from json type https://spec.openapis.org/oas/v3.1.0#data-types

    >>> json_type_to_python("number")
    <class 'float'>

    :param json_type: the json type
    :returns: the python type
    """
    if isinstance(json_type, list) and len(json_type) > 1:
        return Union[tuple(JSON_TYPES_MAPPING.get(jt, type(None)) for jt in json_type)]  # type: ignore
    elif isinstance(json_type, str):
        return JSON_TYPES_MAPPING.get(json_type, type(None))
    else:
        return type(None)


def python_type_to_json(python_type: type) -> Optional[Union[str, List[str]]]:
    """Get json type from python https://spec.openapis.org/oas/v3.1.0#data-types

    >>> python_type_to_json(int)
    'integer'
    >>> python_type_to_json(Union[float, str])
    ['number', 'string']

    :param python_type: the python type
    :returns: the json type
    """
    if get_origin(python_type) is Union:
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


def json_field_definition_to_python(
    json_field_definition: Dict[str, Any],
    default_value: Optional[Any] = None,
    required: Optional[bool] = False,
) -> Annotated[Any, FieldInfo]:
    """Get python field definition from json object

    >>> result = json_field_definition_to_python(
    ...     {
    ...         'type': 'boolean',
    ...         'title': 'Foo parameter'
    ...     }
    ... )
    >>> str(result).replace('_extensions', '') # python3.8 compatibility
    "typing.Annotated[bool, FieldInfo(annotation=NoneType, required=False, title='Foo parameter')]"

    :param json_field_definition: the json field definition
    :param default_value: default value of the field
    :param required: if the field is required
    :returns: the python field definition
    """
    python_type = json_type_to_python(json_field_definition.get("type", None))

    field_type_kwargs = dict(
        title=json_field_definition.get("title", None),
        description=json_field_definition.get("description", None),
        pattern=json_field_definition.get("pattern", None),
    )

    if "enum" in json_field_definition and (
        isinstance(json_field_definition["enum"], (list, set))
    ):
        python_type = Literal[tuple(sorted(json_field_definition["enum"]))]  # type: ignore

    if "$ref" in json_field_definition:
        field_type_kwargs["json_schema_extra"] = {"$ref": json_field_definition["$ref"]}

    if not required or default_value:
        return Annotated[python_type, Field(default=default_value, **field_type_kwargs)]
    else:
        return Annotated[python_type, Field(..., **field_type_kwargs)]


def python_field_definition_to_json(
    python_field_definition: Annotated[Any, FieldInfo]
) -> Dict[str, Any]:
    """Get json field definition from python `typing.Annotated`

    >>> from pydantic import Field
    >>> from eodag.utils import Annotated
    >>> python_field_definition_to_json(
    ...     Annotated[
    ...         Optional[str],
    ...         Field(None, description='Foo bar', json_schema_extra={'$ref': '/path/to/schema'})
    ...     ]
    ... )
    {'type': ['string', 'null'], 'description': 'Foo bar', '$ref': '/path/to/schema'}

    :param python_field_annotated: the python field annotated type
    :returns: the json field definition
    """
    if get_origin(python_field_definition) is not Annotated:
        raise ValidationError(
            "%s must be an instance of Annotated" % python_field_definition
        )

    json_field_definition = dict()

    python_field_args = get_args(python_field_definition)

    # enum & type
    if get_origin(python_field_args[0]) is Literal:
        enum_args = get_args(python_field_args[0])
        json_field_definition["type"] = python_type_to_json(type(enum_args[0]))
        json_field_definition["enum"] = list(enum_args)
    # type
    else:
        field_type = python_type_to_json(python_field_args[0])
        if field_type is not None:
            json_field_definition["type"] = python_type_to_json(python_field_args[0])

    if len(python_field_args) < 2:
        return json_field_definition

    # other definition args
    title = getattr(python_field_args[1], "title", None)
    if title is not None:
        json_field_definition["title"] = title

    description = getattr(python_field_args[1], "description", None)
    if description is not None:
        json_field_definition["description"] = description

    pattern = getattr(python_field_args[1], "pattern", None)
    if pattern is not None:
        json_field_definition["pattern"] = description

    if (
        python_field_args[1].json_schema_extra is not None
        and "$ref" in python_field_args[1].json_schema_extra
    ):
        json_field_definition["$ref"] = python_field_args[1].json_schema_extra["$ref"]

    default = python_field_args[1].get_default()
    if default:
        json_field_definition["value"] = default

    return json_field_definition


def model_fields_to_annotated(
    model_fields: Dict[str, FieldInfo]
) -> Dict[str, Annotated[Any, FieldInfo]]:
    """Convert BaseModel.model_fields from FieldInfo to Annotated

    >>> from pydantic import create_model
    >>> some_model = create_model("some_model", foo=(str, None))
    >>> fields_definitions = model_fields_to_annotated(some_model.model_fields)
    >>> str(fields_definitions).replace('_extensions', '') # python3.8 compatibility
    "{'foo': typing.Annotated[str, FieldInfo(annotation=NoneType, required=False)]}"

    :param model_fields: BaseModel.model_fields to convert
    :returns: Annotated tuple usable as create_model argument
    """
    annotated_model_fields = dict()
    for param, field_info in model_fields.items():
        field_type = field_info.annotation or type(None)
        new_field_info = copy_deepcopy(field_info)
        new_field_info.annotation = None
        annotated_model_fields[param] = Annotated[field_type, new_field_info]
    return annotated_model_fields
