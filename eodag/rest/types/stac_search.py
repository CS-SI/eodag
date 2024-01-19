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
"""Model describing a STAC search POST request"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Tuple, Union, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    StringConstraints,
    conlist,
    field_validator,
    model_validator,
)
from shapely.geometry import (
    GeometryCollection,
    LinearRing,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
    shape,
)
from shapely.geometry.base import GEOMETRY_TYPES, BaseGeometry
from typing_extensions import Annotated

from eodag.rest.utils.rfc3339 import rfc3339_str_to_datetime, str_to_interval

if TYPE_CHECKING:
    try:
        from typing import Self
    except ImportError:
        from _typeshed import Self

NumType = Union[float, int]

BBox = Union[
    conlist(NumType, min_length=4, max_length=4),
    conlist(NumType, min_length=6, max_length=6),
    Tuple[NumType, NumType, NumType, NumType],
    Tuple[NumType, NumType, NumType, NumType, NumType, NumType],
]

Geometry = Union[
    Point,
    MultiPoint,
    LineString,
    MultiLineString,
    Polygon,
    MultiPolygon,
    LinearRing,
    GeometryCollection,
]


Direction = Annotated[Literal["asc", "desc"], StringConstraints(min_length=1)]


class Sortby(BaseModel):
    """
    A class representing a parameter with which we want to sort results and its sorting order in a
    POST search

    :param field: The name of the parameter with which we want to sort results
    :type field: str
    :param direction: The sorting order of the parameter
    :type direction: str
    """

    __pydantic_config__ = ConfigDict(extra="forbid")

    field: Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
    direction: Direction


class SearchPostRequest(BaseModel):
    """
    class which describes the body of a search request

    Overrides the validation for datetime and spatial filter from the base request model.
    """

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    provider: Optional[str] = None
    collections: Optional[List[str]] = None
    ids: Optional[List[str]] = None
    bbox: Optional[BBox] = None
    intersects: Optional[Geometry] = None
    datetime: Optional[str] = None
    limit: Optional[PositiveInt] = Field(  # type: ignore
        None, description="Maximum number of items per page."
    )
    page: Optional[PositiveInt] = Field(  # type: ignore
        None, description="Page number, must be a positive integer."
    )
    query: Optional[Dict[str, Any]] = None
    filter: Optional[Dict[str, Any]] = None
    filter_lang: Optional[str] = Field(
        None,
        alias="filter-lang",
        description="The language used for filtering.",
        validate_default=True,
    )
    sortby: Optional[List[Sortby]] = None
    crunch: Optional[str] = None

    @model_validator(mode="after")
    def check_filter_lang(self) -> Self:
        """Verify filter-lang has correct value"""
        if not self.filter_lang and self.filter:
            self.filter_lang = "cql2-json"
        if self.filter_lang and not self.filter:
            raise ValueError("filter-lang is set but filter is missing")
        if self.filter_lang != "cql2-json" and self.filter:
            raise ValueError('Only filter language "cql2-json" is accepted')
        return self

    @model_validator(mode="after")
    def only_one_spatial(self) -> Self:
        """Check bbox and intersects are not both supplied."""
        if self.bbox and self.intersects:
            raise ValueError("intersects and bbox parameters are mutually exclusive")
        return self

    @property
    def start_date(self) -> Optional[str]:
        """Extract the start date from the datetime string."""
        return self.get_dates(pos="start")

    @property
    def end_date(self) -> Optional[str]:
        """Extract the end date from the datetime string."""
        return self.get_dates(pos="end")

    @field_validator("ids", "collections", mode="before")
    @classmethod
    def str_to_str_list(cls, v: Union[str, List[str]]) -> List[str]:
        """Convert ids and collections strings to list of strings"""
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    @field_validator("intersects", mode="before")
    @classmethod
    def validate_intersects(cls, v: Union[Dict[str, Any], Geometry]) -> Geometry:
        """Verify format of intersects"""
        if isinstance(v, BaseGeometry):
            return v

        if isinstance(v, dict) and v.get("type") in GEOMETRY_TYPES:  # type: ignore
            return shape(v)

        raise ValueError("Not a valid geometry")

    @field_validator("bbox", mode="before")
    @classmethod
    def str_bbox_to_list(cls, v: Union[str, BBox]) -> BBox:
        """convert bbox str to list of NumType"""
        if isinstance(v, str):
            return [float(b.strip()) for b in v.split(",")]
        return v

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v: BBox) -> BBox:
        """Check order of supplied bbox coordinates."""
        # Validate order
        if len(v) == 4:
            xmin, ymin, xmax, ymax = v
        else:
            xmin, ymin, min_elev, xmax, ymax, max_elev = v
            if max_elev < min_elev:
                raise ValueError(
                    "Maximum elevation must greater than minimum elevation"
                )

        if xmax < xmin:
            raise ValueError("Maximum longitude must be greater than minimum longitude")

        if ymax < ymin:
            raise ValueError("Maximum longitude must be greater than minimum longitude")

        # Validate against WGS84
        if xmin < -180 or ymin < -90 or xmax > 180 or ymax > 90:
            raise ValueError("Bounding box must be within (-180, -90, 180, 90)")

        return v

    @field_validator("datetime")
    @classmethod
    def validate_datetime(cls, v: str) -> str:
        """Validate datetime."""
        if "/" in v:
            values = v.split("/")
        else:
            # Single date is interpreted as end date
            values = ["..", v]

        dates: List[str] = []
        for value in values:
            if value == ".." or value == "":
                dates.append("..")
                continue

            # throws ValueError if invalid RFC 3339 string
            dates.append(rfc3339_str_to_datetime(value).isoformat())

        if dates[0] == ".." and dates[1] == "..":
            raise ValueError(
                "Invalid datetime range, both ends of range may not be open"
            )

        if ".." not in dates and dates[0] > dates[1]:
            raise ValueError(
                "Invalid datetime range, must match format (begin_date, end_date)"
            )

        return v

    @property
    def spatial_filter(self) -> Optional[Geometry]:
        """Return a geojson-pydantic object representing the spatial filter for the search
        request.

        Check for both because the ``bbox`` and ``intersects`` parameters are
        mutually exclusive.
        """
        if self.bbox:
            return cast(
                Polygon,
                Polygon(
                    (
                        (self.bbox[0], self.bbox[1]),
                        (self.bbox[0], self.bbox[3]),
                        (self.bbox[2], self.bbox[3]),
                        (self.bbox[2], self.bbox[1]),
                    )
                ),
            )
        if self.intersects:
            return self.intersects
        return None

    def get_dates(self, pos: Literal["start", "end"]) -> Optional[str]:
        """extract start or end dates from datetime"""
        if not self.datetime:
            return None

        if "/" not in self.datetime:
            return rfc3339_str_to_datetime(self.datetime).isoformat()

        interval = str_to_interval(self.datetime)
        if not interval:
            return None

        start, end = interval

        if pos == "end":
            return end.isoformat() if end else None
        else:
            return start.isoformat() if start else None


def sortby2list(
    v: Optional[str],
) -> Optional[List[Sortby]]:
    """
    Convert sortby filter parameter GET syntax to POST syntax
    """
    if not v:
        return None
    sortby: List[Sortby] = []
    for sortby_param in v.split(","):
        sortby_param = sortby_param.strip()
        direction: Direction = "desc" if sortby_param.startswith("-") else "asc"
        field = sortby_param.lstrip("+-")
        sortby.append(Sortby(field=field, direction=direction))
    return sortby
