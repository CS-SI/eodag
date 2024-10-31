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

from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Dict, List, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    computed_field,
    model_serializer,
)

from eodag.rest.types.eodag_search import EODAGSearch
from eodag.rest.utils.rfc3339 import str_to_interval
from eodag.types import python_field_definition_to_json

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


class QueryablesGetParams(BaseModel):
    """Store GET Queryables query params"""

    collection: Optional[str] = Field(default=None, serialization_alias="productType")
    datetime: Optional[str] = Field(default=None)

    model_config = ConfigDict(extra="allow", frozen=True)

    @model_serializer(mode="wrap")
    def _serialize(self, handler: SerializerFunctionWrapHandler) -> Dict[str, Any]:
        dumped: Dict[str, Any] = handler(self)
        return {EODAGSearch.to_eodag(k): v for k, v in dumped.items()}

    # use [prop-decorator] mypy error code when mypy==1.12 is released
    @computed_field  # type: ignore[misc]
    @property
    def start_datetime(self) -> Optional[str]:
        """Extract start_datetime property from datetime"""
        start = str_to_interval(self.datetime)[0]
        return start.strftime("%Y-%m-%dT%H:%M:%SZ") if start else None

    # use [prop-decorator] mypy error code when mypy==1.12 is released
    @computed_field  # type: ignore[misc]
    @property
    def end_datetime(self) -> Optional[str]:
        """Extract end_datetime property from datetime"""
        end = str_to_interval(self.datetime)[1]
        return end.strftime("%Y-%m-%dT%H:%M:%SZ") if end else None


class StacQueryableProperty(BaseModel):
    """A class representing a queryable property.

    :param description: The description of the queryables property
    :param ref: (optional) A reference link to the schema of the property.
    :param type: (optional) possible types of the property
    """

    description: str
    ref: Optional[str] = Field(default=None, serialization_alias="$ref")
    type: Optional[Union[str, List[str]]] = None
    enum: Optional[List[Any]] = None
    value: Optional[Any] = None
    min: Optional[Union[int, List[Union[int, None]]]] = None
    max: Optional[Union[int, List[Union[int, None]]]] = None
    oneOf: Optional[List[Any]] = None
    items: Optional[Any] = None

    @classmethod
    def from_python_field_definition(
        cls, id: str, python_field_definition: Annotated[Any, FieldInfo]
    ) -> StacQueryableProperty:
        """Build Model from python_field_definition"""
        def_dict = python_field_definition_to_json(python_field_definition)

        if not def_dict.get("description", None):
            def_dict["description"] = def_dict.get("title", None) or id

        return cls(**def_dict)

    @model_serializer(mode="wrap")
    def remove_none(
        self,
        handler: SerializerFunctionWrapHandler,
        _: SerializationInfo,
    ):
        """Remove none value property fields during serialization"""
        props: Dict[str, Any] = handler(self)
        return {k: v for k, v in props.items() if v is not None}


class StacQueryables(BaseModel):
    """A class representing queryable properties for the STAC API.

    :param json_schema: The URL of the JSON schema.
    :param q_id: (optional) The identifier of the queryables.
    :param q_type: The type of the object.
    :param title: The title of the queryables.
    :param description: The description of the queryables
    :param properties: A dictionary of queryable properties.
    :param additional_properties: Whether additional properties are allowed.
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
    default_properties: ClassVar[Dict[str, StacQueryableProperty]] = {
        "collection": StacQueryableProperty(
            description="Collection",
            ref="https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json#/collection",
        )
    }
    possible_properties: ClassVar[Dict[str, StacQueryableProperty]] = {
        "geometry": StacQueryableProperty(
            description="Geometry",
            ref="https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json#/geometry",
        ),
        "datetime": StacQueryableProperty(
            description="Datetime - use parameters year, month, day, time instead if available",
            ref="https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/datetime.json#/properties/datetime",
        ),
        "bbox": StacQueryableProperty(
            description="BBox",
            type="array",
            oneOf=[{"minItems": 4, "maxItems": 4}, {"minItems": 6, "maxItems": 6}],
            items={"type": "number"},
        ),
    }
    properties: Dict[str, Any] = Field()
    required: Optional[List[str]] = Field(None)
    additional_properties: bool = Field(
        default=True, serialization_alias="additionalProperties"
    )

    def __contains__(self, name: str) -> bool:
        return name in self.properties
