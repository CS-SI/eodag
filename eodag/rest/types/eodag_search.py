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

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union, cast

from pydantic import (
    AliasChoices,
    AliasPath,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel
from pydantic_core import InitErrorDetails, PydanticCustomError
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

from eodag.rest.utils import flatten_list, is_dict_str_any, list_to_str_list
from eodag.rest.utils.cql_evaluate import EodagEvaluator
from eodag.utils import DEFAULT_ITEMS_PER_PAGE

if TYPE_CHECKING:
    try:
        from typing import Self
    except ImportError:
        from _typeshed import Self

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
    id: Optional[List[str]] = Field(
        None, alias="ids"
    )  # TODO: remove when updating queryables
    geom: Optional[Geometry] = Field(None, alias="geometry")
    start: Optional[str] = Field(None, alias="start_datetime")
    end: Optional[str] = Field(None, alias="end_datetime")
    startTimeFromAscendingNode: Optional[str] = Field(
        None,
        alias="start_datetime",
        validation_alias=AliasChoices("start_datetime", "datetime"),
    )
    completionTimeFromAscendingNode: Optional[str] = Field(None, alias="end_datetime")
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
    sortBy: Optional[List[Tuple[str, str]]] = Field(None, alias="sortby")
    raise_errors: bool = False

    _to_eodag_map: Dict[str, str]

    @model_validator(mode="after")
    def set_raise_errors(self) -> Self:
        """Set raise_errors to True if provider is set"""
        if self.provider:
            self.raise_errors = True
        return self

    @model_validator(mode="after")
    def remove_timeFromAscendingNode(self) -> Self:  # pylint: disable=invalid-name
        """TimeFromAscendingNode are just used for translation and not for search"""
        self.startTimeFromAscendingNode = None  # pylint: disable=invalid-name
        self.completionTimeFromAscendingNode = None  # pylint: disable=invalid-name
        return self

    @model_validator(mode="after")
    def parse_extra_fields(self) -> Self:
        """process unknown and oseo EODAG custom extensions fields"""
        # Transform EODAG custom extensions OSEO and UNK.
        if not self.__pydantic_extra__:
            return self

        keys_to_update: Dict[str, str] = {}
        for key in self.__pydantic_extra__.keys():
            if key.startswith("unk:"):
                keys_to_update[key] = key[len("unk:") :]
            elif key.startswith("oseo:"):
                keys_to_update[key] = key[len("oseo:") :]

        for old_key, new_key in keys_to_update.items():
            self.__pydantic_extra__[to_camel(new_key)] = self.__pydantic_extra__.pop(
                old_key
            )

        return self

    @model_validator(mode="before")
    @classmethod
    def remove_keys(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Remove 'datetime', 'crunch', 'intersects', and 'bbox' keys"""
        for key in ["datetime", "crunch", "intersects", "bbox", "filter_lang"]:
            values.pop(key, None)
        return values

    @model_validator(mode="before")
    @classmethod
    def parse_collections(
        cls, values: Dict[str, Any], info: ValidationInfo
    ) -> Dict[str, Any]:
        """convert collections to productType"""

        if collections := values.pop("collections", None):
            if len(collections) > 1:
                raise ValueError("Only one collection is supported per search")
            values["productType"] = collections[0]
        else:
            if not getattr(info, "context", None) or not info.context.get(  # type: ignore
                "isCatalog"
            ):
                raise ValueError("A collection is required")

        return values

    @model_validator(mode="before")
    @classmethod
    def parse_query(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert a STAC query parameter filter with the "eq" operator to a dict.
        """

        def add_error(error_message: str, input: Any) -> None:
            errors.append(
                InitErrorDetails(
                    type=PydanticCustomError("invalid_query", error_message),  # type: ignore
                    loc=("query",),
                    input=input,
                )
            )

        query = values.pop("query", None)
        if not query:
            return values

        query_props: Dict[str, Any] = {}
        errors: List[InitErrorDetails] = []
        for property_name, conditions in cast(Dict[str, Any], query).items():
            # Remove the prefix "properties." if present
            prop = property_name.replace("properties.", "", 1)

            # Check if exactly one operator is specified per property
            if not is_dict_str_any(conditions) or len(conditions) != 1:  # type: ignore
                add_error(
                    "Exactly 1 operator must be specified per property",
                    query[property_name],
                )
                continue

            # Retrieve the operator and its value
            operator, value = next(iter(cast(Dict[str, Any], conditions).items()))

            # Validate the operator
            if operator not in ("eq", "lte", "in") or (
                operator == "lte" and prop != "eo:cloud_cover"
            ):
                add_error(
                    f'operator "{operator}" is not supported for property "{prop}"',
                    query[property_name],
                )
                continue
            if operator == "in" and not isinstance(value, list):
                add_error(
                    f'operator "{operator}" requires a value of type list',
                    query[property_name],
                )
                continue

            query_props[prop] = value

        if errors:
            raise ValidationError.from_exception_data(
                title=cls.__name__, line_errors=errors
            )

        return {**values, **query_props}

    @model_validator(mode="before")
    @classmethod
    def parse_cql(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process cql2 filter
        """

        def add_error(error_message: str) -> None:
            errors.append(
                InitErrorDetails(
                    type=PydanticCustomError("invalid_filter", error_message),  # type: ignore
                    loc=("filter",),
                )
            )

        filter_ = values.pop("filter", None)
        if not filter_:
            return values

        errors: List[InitErrorDetails] = []
        try:
            parsing_result = EodagEvaluator().evaluate(parse_json(filter_))  # type: ignore
        except (ValueError, NotImplementedError) as e:
            add_error(str(e))
            raise ValidationError.from_exception_data(
                title=cls.__name__, line_errors=errors
            ) from e

        if not is_dict_str_any(parsing_result):
            add_error("The parsed filter is not a proper dictionary")
            raise ValidationError.from_exception_data(
                title=cls.__name__, line_errors=errors
            )

        cql_args: Dict[str, Any] = cast(Dict[str, Any], parsing_result)

        invalid_keys = {
            "collections": 'Use "collection" instead of "collections"',
            "ids": 'Use "id" instead of "ids"',
        }
        for k, m in invalid_keys.items():
            if k in cql_args:
                add_error(m)

        if errors:
            raise ValidationError.from_exception_data(
                title=cls.__name__, line_errors=errors
            )

        # convert collection to EODAG collections
        if col := cql_args.pop("collection", None):
            cql_args["collections"] = col if isinstance(col, list) else [col]

        # convert id to EODAG ids
        if id := cql_args.pop("id", None):
            cql_args["ids"] = id if isinstance(id, list) else [id]

        return {**values, **cql_args}

    @field_validator("instrument", mode="before")
    @classmethod
    def join_instruments(cls, v: Union[str, List[str]]) -> str:
        """convert instruments to instrument"""
        if isinstance(v, list):
            return ",".join(v)
        return v

    @field_validator("sortBy", mode="before")
    @classmethod
    def parse_sortby(
        cls,
        sortby_post_params: List[Dict[str, str]],
    ) -> List[Tuple[str, str]]:
        """
        Convert STAC POST sortby to EODAG sortby
        """
        special_fields = {
            "start": "startTimeFromAscendingNode",
            "end": "completionTimeFromAscendingNode",
        }
        return [
            (
                special_fields.get(
                    to_camel(cls.to_eodag(param["field"])),
                    to_camel(cls.to_eodag(param["field"])),
                ),
                param["direction"],
            )
            for param in sortby_post_params
        ]

    @field_validator("start", "end")
    @classmethod
    def cleanup_dates(cls, v: str) -> str:
        """proper format dates"""
        if v.endswith("+00:00"):
            return v.replace("+00:00", "") + "Z"
        return v

    @classmethod
    def _create_to_eodag_map(cls) -> None:
        """Create mapping to convert fields from STAC to EODAG"""
        cls._to_eodag_map = {}
        for name, field_info in cls.model_fields.items():
            if field_info.validation_alias:
                if isinstance(field_info.validation_alias, (AliasChoices, AliasPath)):
                    for a in list_to_str_list(
                        flatten_list(field_info.validation_alias.convert_to_aliases())
                    ):
                        cls._to_eodag_map[a] = name
                else:
                    cls._to_eodag_map[field_info.validation_alias] = name
            elif field_info.alias:
                cls._to_eodag_map[field_info.alias] = name

    @classmethod
    def to_eodag(cls, value: str) -> str:
        """Convert a STAC parameter to its matching EODAG name"""
        if not isinstance(cls._to_eodag_map, dict) or not cls._to_eodag_map:
            cls._create_to_eodag_map()
        return cls._to_eodag_map.get(value, value)

    @classmethod
    def to_stac(cls, field_name: str) -> str:
        """Get the alias of a field in a Pydantic model"""
        field = cls.model_fields.get(field_name)
        if field is not None and field.alias is not None:
            return field.alias
        return field_name
