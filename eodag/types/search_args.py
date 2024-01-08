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
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union, cast

from pydantic import BaseModel, ConfigDict, Field, conint, field_validator
from shapely import wkt
from shapely.errors import GEOSException
from shapely.geometry import Polygon, shape
from shapely.geometry.base import GEOMETRY_TYPES, BaseGeometry

from eodag.types.bbox import BBox
from eodag.utils import DEFAULT_ITEMS_PER_PAGE, DEFAULT_PAGE

NumType = Union[float, int]
GeomArgs = Union[List[NumType], Tuple[NumType], Dict[str, NumType], str, BaseGeometry]

PositiveInt = conint(gt=0)


class SearchArgs(BaseModel):
    """Represents an EODAG search"""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    provider: Optional[str] = Field(None)
    productType: str = Field()
    id: Optional[str] = Field(None)
    start: Optional[str] = Field(None)
    end: Optional[str] = Field(None)
    geom: Optional[BaseGeometry] = Field(None)
    locations: Optional[Dict[str, str]] = Field(None)
    page: Optional[int] = Field(DEFAULT_PAGE, gt=0)  # type: ignore
    items_per_page: Optional[PositiveInt] = Field(DEFAULT_ITEMS_PER_PAGE)  # type: ignore

    @field_validator("start", "end", mode="before")
    @classmethod
    def check_date_format(cls, v: str) -> str:
        """Validate dates"""
        try:
            datetime.fromisoformat(v)
        except ValueError as e:
            raise ValueError("start_date and end must follow ISO8601 format") from e
        return v

    @field_validator("geom", mode="before")
    @classmethod
    def check_geom(cls, v: GeomArgs) -> BaseGeometry:
        """Validate geom"""
        # GeoJSON geometry
        if isinstance(v, dict) and v.get("type") in GEOMETRY_TYPES:
            return cast(BaseGeometry, shape(v))

        # Bounding Box
        if isinstance(v, (list, tuple, dict)):
            return BBox(v).to_polygon()

        if isinstance(v, str):
            # WKT geometry
            try:
                return cast(Polygon, wkt.loads(v))
            except GEOSException as e:
                raise ValueError(f"Invalid geometry WKT string: {v}") from e

        if isinstance(v, BaseGeometry):
            return v

        raise TypeError(f"Invalid geometry type: {type(v)}")
