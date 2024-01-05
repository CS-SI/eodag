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

import re
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

from eodag.api.product.metadata_mapping import OSEO_METADATA_MAPPING
from eodag.config import load_stac_config
from eodag.types import python_field_definition_to_json
from eodag.utils import Annotated

CAMEL_TO_SPACE_TITLED = re.compile(r"[:_-]|(?<=[a-z])(?=[A-Z])")


def rename_to_stac_standard(key: str) -> str:
    """Fetch the queryable properties for a collection.

    :param key: The camelCase key name obtained from a collection's metadata mapping.
    :type key: str
    :returns: The STAC-standardized property name if it exists, else the default camelCase queryable name
    :rtype: str
    """
    # Load the stac config properties for renaming the properties
    # to their STAC standard
    stac_config = load_stac_config()
    stac_config_properties: Dict[str, Any] = stac_config["item"]["properties"]

    for stac_property, value in stac_config_properties.items():
        if isinstance(value, list):
            value = value[0]
        if str(value).endswith(key):
            return stac_property

    if key in OSEO_METADATA_MAPPING:
        return "oseo:" + key

    return key


class BaseQueryableProperty(BaseModel):
    """A class representing a queryable property.

    :param description: The description of the queryables property
    :type description: str
    :param type: (optional) possible types of the property
    :type type: list[str]
    """

    description: str
    type: Optional[list] = None

    def update_properties(self, new_properties: dict):
        """updates the properties with the given new properties keeping already existing value"""
        if "type" in new_properties and not self.type:
            self.type = new_properties["type"]


class QueryableProperty(BaseQueryableProperty):
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

    def update_properties(self, new_properties: dict):
        """updates the properties with the given new properties keeping already existing value"""
        if "type" in new_properties and not self.type:
            self.type = new_properties["type"]
        if "ref" in new_properties and not self.ref:
            self.ref = new_properties["ref"]

    @classmethod
    def from_python_field_definition(
        cls, id: str, python_field_definition: Tuple[Annotated, Any]
    ) -> QueryableProperty:
        """Build Model from python_field_definition"""
        def_dict = python_field_definition_to_json(python_field_definition)

        if not def_dict.get("description", None):
            def_dict["description"] = def_dict.get("title", None) or id

        return cls(**def_dict)


class Queryables(BaseModel):
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
    properties: Dict[str, QueryableProperty] = Field(
        default={
            "id": QueryableProperty(
                description="ID",
                ref="https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json#/id",
            ),
            "collection": QueryableProperty(
                description="Collection",
                ref="https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json#/collection",
            ),
            "geometry": QueryableProperty(
                description="Geometry",
                ref="https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json#/geometry",
            ),
            "bbox": QueryableProperty(
                description="Bbox",
                ref="https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json#/bbox",
            ),
            "datetime": QueryableProperty(
                description="Datetime",
                ref="https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/datetime.json#/properties/datetime",
            ),
        }
    )
    additional_properties: bool = Field(
        default=True, serialization_alias="additionalProperties"
    )

    def get_base_properties(self) -> Dict[str, BaseQueryableProperty]:
        """Get the queryable properties.

        :returns: A dictionary containing queryable properties.
        :rtype: typing.Dict[str, QueryableProperty]
        """
        base_properties = {}
        for key, property in self.properties.items():
            base_property = BaseQueryableProperty(
                description=property.description, type=property.type
            )
            base_properties[key] = base_property
        return base_properties

    def __contains__(self, name: str) -> bool:
        return name in self.properties

    def __setitem__(self, name: str, qprop: QueryableProperty) -> None:
        # only keep "datetime" queryable for dates
        if "name" not in ("start_datetime", "end_datetime"):
            self.properties[name] = qprop


def format_queryable(queryable_key: str, base=True) -> BaseQueryableProperty:
    """
    creates a queryable property from a property key
    :param queryable_key: key of the property for which the queryable property shall be created
    :type queryable_key: str
    :param base: if a base queryable object or an extended queryable object should be created
    :type base: bool
    :returns: queryable property for the given key
    :rtype: QueryableProperty
    """
    if queryable_key not in ["start", "end", "geom", "locations", "id"]:
        stac_key = rename_to_stac_standard(queryable_key)
    else:
        stac_key = queryable_key
    titled_name = re.sub(CAMEL_TO_SPACE_TITLED, " ", stac_key.split(":")[-1]).title()
    if base:
        return BaseQueryableProperty(description=titled_name)
    return QueryableProperty(description=titled_name)


def format_provider_queryables(
    provider_queryables: dict, queryables: dict, base: bool = True
) -> Dict[str, Any]:
    """
    formats the provider queryables and adds them to the existing queryables
    :param provider_queryables: queryables fetched from the provider
    :type provider_queryables: dict
    :param queryables: default queryables to which provider queryables will be added
    :type queryables: dict
    :param base: if a base queryable object or an extended queryable object should be created
    :type base: bool
    :returns queryable_properties: A dict containing the formatted queryable properties
                                       including queryables fetched from the provider.
    :rtype dict
    """
    for queryable, data in provider_queryables.items():
        titled_name = re.sub(
            CAMEL_TO_SPACE_TITLED, " ", queryable.split(":")[-1]
        ).title()
        attributes = {"description": titled_name}
        if queryable in queryables:
            queryable_prop = queryables[queryable]
        else:
            if base:
                queryable_prop = BaseQueryableProperty(description=titled_name)
            else:
                queryable_prop = QueryableProperty(description=titled_name)
        if "type" in data:
            if isinstance(data["type"], list):
                attributes["type"] = data["type"]
            else:
                attributes["type"] = [data["type"]]
        if "ref" in data and not base:
            attributes["ref"] = data["ref"]
        queryable_prop.update_properties(attributes)
        queryables[queryable] = queryable_prop
    return queryables
