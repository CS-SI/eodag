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
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union, cast

from pydantic import BaseModel, ConfigDict, Field, conint, conlist, field_validator
from shapely import wkt
from shapely.errors import GEOSException
from shapely.geometry import Polygon, shape
from shapely.geometry.base import GEOMETRY_TYPES, BaseGeometry

from eodag.types.bbox import BBox
from eodag.utils import DEFAULT_ITEMS_PER_PAGE, DEFAULT_PAGE

NumType = Union[float, int]
GeomArgs = Union[List[NumType], Tuple[NumType], Dict[str, NumType], str, BaseGeometry]

PositiveInt = conint(gt=0)
SortByList = conlist(Tuple[str, str], min_length=1)


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
    sortBy: Optional[SortByList] = Field(None)  # type: ignore

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

    @field_validator("sortBy", mode="before")
    @classmethod
    def check_sort_by_params(
        cls, sort_by_params: Optional[SortByList]  # type: ignore
    ) -> Optional[SortByList]:  # type: ignore
        """Check if the sortBy argument is correct

        :param sort_by_params: The sortBy argument
        :type sort_by_params: str
        :returns: The sortBy argument with sorting order parsed (whitespace(s) are
                  removed and only the 3 first letters in uppercase are kept)
        :rtype: str
        """
        if sort_by_params is not None:
            assert isinstance(
                sort_by_params, list
            ), f"Sort argument must be a list of tuple(s), got a '{type(sort_by_params)}' instead"
            sort_order_pattern = r"^(ASC|DES)[a-zA-Z]*$"
            for i, sort_by_param in enumerate(sort_by_params):
                assert isinstance(
                    sort_by_param, tuple
                ), f"Sort argument must be a list of tuple(s), got a list of '{type(sort_by_param)}' instead"
                sort_param = sort_by_param[0]
                sort_order = sort_by_param[1]
                sort_order = sort_order.strip().upper()
                assert re.match(sort_order_pattern, sort_order) is not None, (
                    "Sorting order must be set to 'ASC' (ASCENDING) or 'DESC' (DESCENDING), "
                    f"got '{sort_order}' with '{sort_param}' instead"
                )
                sort_by_params[i] = (sort_param, sort_order[:3])
            return sort_by_params
        return None
