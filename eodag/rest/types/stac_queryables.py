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
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from eodag.types import python_field_definition_to_json
from eodag.utils import Annotated

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


class StacQueryableProperty(BaseModel):
    """A class representing a queryable property.

    :param description: The description of the queryables property
    :type description: str
    :param ref: (optional) A reference link to the schema of the property.
    :type ref: str
    :param type: (optional) possible types of the property
    :type type: list[str]
    """

    description: str
    ref: Optional[str] = Field(default=None, serialization_alias="$ref")
    type: Optional[Union[str, List[str]]] = None
    enum: Optional[List[Any]] = None
    value: Optional[Any] = None

    @classmethod
    def from_python_field_definition(
        cls, id: str, python_field_definition: Annotated[Any, FieldInfo]
    ) -> StacQueryableProperty:
        """Build Model from python_field_definition"""
        def_dict = python_field_definition_to_json(python_field_definition)

        if not def_dict.get("description", None):
            def_dict["description"] = def_dict.get("title", None) or id

        return cls(**def_dict)


class StacQueryables(BaseModel):
    """A class representing queryable properties for the STAC API.

    :param json_schema: The URL of the JSON schema.
    :type json_schema: str
    :param q_id: (optional) The identifier of the queryables.
    :type q_id: str
    :param q_type: The type of the object.
    :type q_type: str
    :param title: The title of the queryables.
    :type title: str
    :param description: The description of the queryables
    :type description: str
    :param properties: A dictionary of queryable properties.
    :type properties: dict
    :param additional_properties: Whether additional properties are allowed.
    :type additional_properties: bool
    """

    json_schema: str = Field(
        default="https://json-schema.org/draft/2019-09/schema",
        serialization_alias="$schema",
    )
    q_id: Optional[str] = Field(default=None, serialization_alias="$id")
    q_type: str = Field(default="object", serialization_alias="type")
    title: str = Field(default="Queryables for EODAG STAC API")
    description: str = Field(
        default="Queryable names for the EODAG STAC API Item Search filter."
    )
    properties: Dict[str, StacQueryableProperty] = Field(
        default={
            "ids": StacQueryableProperty(
                description="ID",
                ref="https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json#/id",
            ),
            "collections": StacQueryableProperty(
                description="Collection",
                ref="https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json#/collection",
            ),
            "geometry": StacQueryableProperty(
                description="Geometry",
                ref="https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json#/geometry",
            ),
            "datetime": StacQueryableProperty(
                description="Datetime - use parameters year, month, day, time instead if available",
                ref="https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/datetime.json#/properties/datetime",
            ),
        }
    )
    additional_properties: bool = Field(
        default=True, serialization_alias="additionalProperties"
    )

    def get_properties(self) -> Dict[str, StacQueryableProperty]:
        """Get the queryable properties.

        :returns: A dictionary containing queryable properties.
        :rtype: typing.Dict[str, StacQueryableProperty]
        """
        properties = {}
        for key, property in self.properties.items():
            property = StacQueryableProperty(
                description=property.description, type=property.type
            )
            properties[key] = property
        return properties

    def __contains__(self, name: str) -> bool:
        return name in self.properties

    def __setitem__(self, name: str, qprop: StacQueryableProperty) -> None:
        # only keep "datetime" queryable for dates
        if name not in ("start_datetime", "end_datetime"):
            self.properties[name] = qprop
