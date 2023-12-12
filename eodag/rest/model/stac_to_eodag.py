# -*- coding: utf-8 -*-
# Copyright 2018, CS GROUP - France, https://www.csgroup.eu/
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
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator
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

from eodag.rest.cql_evaluate import EodagEvaluator
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


class STACtoEODAGModel(BaseModel):
    """Model used to convert a STAC formated request to an EODAG formated one"""

    productType: Optional[str] = Field(None, alias="collections")
    provider: Optional[str] = Field(None)
    ids: Optional[List[str]] = Field(None)
    geom: Optional[Geometry]
    start: Optional[str] = Field(None, alias="start_datetime")
    end: Optional[str] = Field(None, alias="end_datetime")
    publicationDate: Optional[str] = Field(None, alias="published")
    creationDate: Optional[str] = Field(None, alias="created")
    modificationDate: Optional[str] = Field(None, alias="updated")
    platformSerialIdentifier: Optional[str] = Field(None, alias="platform")
    instrument: Optional[str] = Field(None, alias="instruments")
    platform: Optional[str] = Field(None, alias="constellation")
    resolution: Optional[float] = Field(None, alias="gsd")
    cloudCover: Optional[float] = Field(None, alias="eo:cloud_cover")
    snowCover: Optional[float] = Field(None, alias="eo:snow_cover")
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
    items_per_page: Optional[int] = Field(DEFAULT_ITEMS_PER_PAGE, alias="limit")

    class Config:
        """Model config"""

        extra = "allow"
        populate_by_name = True
        arbitrary_types_allowed = True

    @field_validator("start", "end")
    @classmethod
    def cleanup_dates(cls, v: str) -> str:
        """proper format dates"""
        if v.endswith("+00:00"):
            return v.replace("+00:00", "") + "Z"
        return v

    @field_validator("instrument", mode="before")
    @classmethod
    def join_instruments(cls, v: Union[str, List[str]]) -> str:
        """convert instruments to instrument"""
        if isinstance(v, list):
            return ",".join(v)
        return v

    @model_validator(mode="before")
    @classmethod
    def remove_custom_extensions(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """process unknown and oseo EODAG custom extensions fields"""
        # Transform EODAG custom extensions OSEO and UNK.
        keys_to_update = {}
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
    def convert_query_to_dict(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert a STAC query parameter filter with the "eq" operator to a dict.
        """
        query = values.pop("query", None)
        if query is None:
            return values

        if not isinstance(query, dict):
            raise SyntaxError("Invalid query syntax")

        query_props = {}
        for property_name, conditions in query.items():
            # Remove the "properties." prefix if present
            prop = property_name.removeprefix("properties.")

            # Check if exactly one operator is specified per property
            if len(conditions) != 1:
                raise ValueError("Exactly 1 operator must be specified per property")

            # Retrieve the operator and its value
            operator, value = next(iter(conditions.items()))

            # Validate the operator
            if operator == "lte" and prop != "eo:cloud_cover":
                raise ValueError('"lte" operator is only supported for eo:cloud_cover')

            if operator not in ("eq", "lte"):
                raise ValueError(
                    'Only the "eq" and "lte" operators are supported'
                    ', with "lte" only for eo:cloud_cover'
                )

            # Add the property name and value to the result dictionary
            query_props[prop] = value

        return {**values, **query_props}

    @model_validator(mode="before")
    @classmethod
    def convert_collections_to_product_type(
        cls, values: Dict[str, Any], info: ValidationInfo
    ) -> Dict[str, Any]:
        """convert collections and collection to productType"""
        collections = values.pop("collections", None)
        collection = values.pop("collection", None)

        if not isinstance(collections, list):
            collections = [collections]
        if not isinstance(collection, list):
            collection = [collection]

        combined_collections = [c for c in collections if c] + [
            c for c in collection if c and c not in collections
        ]

        if len(combined_collections) > 1:
            raise ValueError("Only one collection is supported per search")

        if combined_collections:
            values["productType"] = combined_collections[0]
        elif info.context and not info.context.get("isCatalog"):
            raise ValueError("A collection is required")

        return values

    @model_validator(mode="before")
    @classmethod
    def assemble_geom(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert intersects and bbox to geom.

        geom is pulled from geometry.
        """
        values.pop("intersects", None)
        values.pop("bbox", None)
        values["geom"] = values.pop("geometry", None)
        return values

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
        cql_args: Dict[str, Any] = EodagEvaluator().evaluate(parse_json(filter_))
        return {**values, **cql_args}

    @model_validator(mode="before")
    @classmethod
    def remove_datetime(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Remove datetime replaced by start_date and end_date"""
        values.pop("datetime", None)
        return values

    @classmethod
    def snake_to_camel(cls, snake_str: str) -> str:
        """Convert snake_case to camelCase"""
        # Split the string by underscore and capitalize each component except the first one
        components = snake_str.split("_")
        return components[0] + "".join(x.title() for x in components[1:])
