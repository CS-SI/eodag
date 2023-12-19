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
from typing import Any, Dict, List, Optional, Union, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from pygeofilter.parsers.cql2_json import parse as parse_json
from shapely.geometry import (
    GeometryCollection,
    LinearRing,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)

from eodag.rest.utils import is_dict_str_any, is_list_str
from eodag.rest.utils.cql_evaluate import EodagEvaluator
from eodag.utils import DEFAULT_ITEMS_PER_PAGE

Geometry = Union[
    Dict[str, Any],
    Point,
    MultiPoint,
    LineString,
    MultiLineString,
    Polygon,
    MultiPolygon,
    LinearRing,
    GeometryCollection,
]


class EODAGSearch(BaseModel):
    """Model used to convert a STAC formated request to an EODAG formated one"""

    model_config = ConfigDict(
        extra="allow", populate_by_name=True, arbitrary_types_allowed=True
    )

    productType: Optional[str] = Field(None, alias="collections", validate_default=True)
    provider: Optional[str] = Field(None)
    ids: Optional[List[str]] = Field(None)
    id: Optional[List[str]] = Field(None, alias="ids")
    geom: Optional[Geometry] = Field(None, alias="geometry")
    start: Optional[str] = Field(None, alias="start_datetime")
    end: Optional[str] = Field(None, alias="end_datetime")
    publicationDate: Optional[str] = Field(None, alias="published")
    creationDate: Optional[str] = Field(None, alias="created")
    modificationDate: Optional[str] = Field(None, alias="updated")
    platformSerialIdentifier: Optional[str] = Field(None, alias="platform")
    instrument: Optional[str] = Field(None, alias="instruments")
    platform: Optional[str] = Field(None, alias="constellation")
    resolution: Optional[int] = Field(None, alias="gsd")
    cloudCover: Optional[int] = Field(None, alias="eo:cloud_cover")
    snowCover: Optional[int] = Field(None, alias="eo:snow_cover")
    processingLevel: Optional[str] = Field(None, alias="processing:level")
    orbitDirection: Optional[str] = Field(None, alias="sat:orbit_state")
    relativeOrbitNumber: Optional[int] = Field(None, alias="sat:relative_orbit")
    orbitNumber: Optional[int] = Field(None, alias="sat:absolute_orbit")
    # TODO: colision in property name. Need to handle "sar:product_type"
    sensorMode: Optional[str] = Field(None, alias="sar:instrument_mode")
    polarizationChannels: Optional[List[str]] = Field(None, alias="sar:polarizations")
    dopplerFrequency: Optional[str] = Field(None, alias="sar:frequency_band")
    doi: Optional[str] = Field(None, alias="sci:doi")
    productVersion: Optional[str] = Field(None, alias="version")
    illuminationElevationAngle: Optional[float] = Field(
        None, alias="view:sun_elevation"
    )
    illuminationAzimuthAngle: Optional[float] = Field(None, alias="view:sun_azimuth")
    page: Optional[int] = Field(1)
    items_per_page: int = Field(DEFAULT_ITEMS_PER_PAGE, alias="limit")

    @model_validator(mode="before")
    @classmethod
    def remove_custom_extensions(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """process unknown and oseo EODAG custom extensions fields"""
        # Transform EODAG custom extensions OSEO and UNK.
        keys_to_update: Dict[str, str] = {}
        for key in values.keys():
            if key.startswith("unk:"):
                keys_to_update[key] = key[len("unk:") :]
            elif key.startswith("oseo:"):
                keys_to_update[key] = key[len("oseo:") :]

        for old_key, new_key in keys_to_update.items():
            values[cls.snake_to_camel(new_key)] = values.pop(old_key)

        return values

    @model_validator(mode="before")
    @classmethod
    def remove_keys(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Remove 'datetime', 'crunch', 'intersects', and 'bbox' keys"""
        for key in ["datetime", "crunch", "intersects", "bbox"]:
            values.pop(key, None)
        return values

    @model_validator(mode="before")
    @classmethod
    def convert_collections_to_product_type(
        cls, values: Dict[str, Any]
    ) -> Dict[str, Any]:
        """convert collections and collection to productType"""
        collections = values.pop("collections", [])
        collection = values.pop("collection", [])

        if collection and isinstance(collection, str):
            collection = [collection]
        elif collection and not is_list_str(collection):  # type: ignore
            raise ValueError("Collection must be a string or a list of strings")

        if collections and not is_list_str(collections):  # type: ignore
            raise ValueError("Collections must a list of strings")

        combined_collections = cast(
            List[str],
            [c for c in collections if c]  # type: ignore
            + [c for c in collection if c and c not in collections],  # type: ignore
        )

        if len(combined_collections) > 1:
            raise ValueError("Only one collection is supported per search")

        if combined_collections:
            values["productType"] = combined_collections[0]

        return values

    @model_validator(mode="before")
    @classmethod
    def convert_query_to_dict(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert a STAC query parameter filter with the "eq" operator to a dict.
        """
        query = values.pop("query", None)
        if query is None:
            return values

        if not is_dict_str_any(query):
            raise ValueError("Invalid query syntax")

        query_props: Dict[str, Any] = {}
        for property_name, conditions in cast(Dict[str, Any], query).items():
            # Remove the "properties." prefix if present
            prop = property_name.removeprefix("properties.")

            # Check if exactly one operator is specified per property
            if not is_dict_str_any(conditions) or len(conditions) != 1:  # type: ignore
                raise ValueError(
                    "Query filter: exactly 1 operator must be specified per property"
                )

            # Retrieve the operator and its value
            operator, value = next(iter(cast(Dict[str, Any], conditions).items()))

            # Validate the operator
            if operator == "lte" and prop != "eo:cloud_cover":
                raise ValueError(
                    'Query filter: "lte" operator is only supported for eo:cloud_cover'
                )

            if operator not in ("eq", "lte"):
                raise ValueError(
                    'Query filter: only the "eq" and "lte" operators are supported'
                    ', with "lte" only for eo:cloud_cover'
                )

            # Add the property name and value to the result dictionary
            query_props[prop] = value

        return {**values, **query_props}

    @model_validator(mode="before")
    @classmethod
    def parse_cql(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process cql2 filter
        """
        values.pop("filter_lang", None)
        filter_ = values.pop("filter", None)
        if not filter_:
            return values
        parsing_result = EodagEvaluator().evaluate(parse_json(filter_))  # type: ignore
        if not is_dict_str_any(parsing_result):
            raise ValueError(
                "Error in parsing filter: the result is not a proper dictionary"
            )
        cql_args: Dict[str, Any] = cast(Dict[str, Any], parsing_result)
        return {**values, **cql_args}

    @field_validator("instrument", mode="before")
    @classmethod
    def join_instruments(cls, v: Union[str, List[str]]) -> str:
        """convert instruments to instrument"""
        if isinstance(v, list):
            return ",".join(v)
        return v

    @field_validator("productType")
    @classmethod
    def verify_producttype_is_present(
        cls, v: Optional[str], info: ValidationInfo
    ) -> Optional[str]:
        """Verify productType is present when required"""
        if not v and (
            not info
            or not getattr(info, "context", None)
            or not info.context.get("isCatalog")  # type: ignore
        ):
            raise ValueError("A collection is required")

        return v

    @field_validator("start", "end")
    @classmethod
    def cleanup_dates(cls, v: str) -> str:
        """proper format dates"""
        if v.endswith("+00:00"):
            return v.replace("+00:00", "") + "Z"
        return v

    @classmethod
    def snake_to_camel(cls, snake_str: str) -> str:
        """Convert snake_case to camelCase"""
        # Split the string by underscore and capitalize each component except the first one
        components = snake_str.split("_")
        return components[0] + "".join(x.title() for x in components[1:])

    @classmethod
    def to_eodag(cls, value: str) -> str:
        """Convert a STAC parameter to its matching EODAG name"""
        alias_map = {
            field_info.alias: name
            for name, field_info in cls.model_fields.items()
            if field_info.alias
        }
        return alias_map.get(value, value)

    @classmethod
    def to_stac(cls, field_name: str) -> str:
        """Get the alias of a field in a Pydantic model"""
        field = cls.model_fields.get(field_name)
        if field is not None and field.alias is not None:
            return field.alias
        return field_name
