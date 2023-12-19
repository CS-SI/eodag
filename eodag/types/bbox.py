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
from typing import Any, Dict, List, Tuple, Union

from pydantic import BaseModel, validator
from shapely.geometry.polygon import Polygon

NumType = Union[float, int]
BBoxArgs = Union[
    List[NumType], Tuple[NumType, NumType, NumType, NumType], Dict[str, NumType]
]


class BBox(BaseModel):
    """
    A class used to represent a Bounding Box.
    """

    lonmin: NumType
    latmin: NumType
    lonmax: NumType
    latmax: NumType

    def __init__(__pydantic_self__, bboxArgs: BBoxArgs) -> None:  # type: ignore
        """
        Constructs all the necessary attributes for the BBox object.

        :param bboxArgs: Four float values representing lonmin, latmin, lonmax, latmax respectively
            or a dictionary containing key-value pairs of attribute names and values.
        """
        if isinstance(bboxArgs, (list, tuple)) and len(bboxArgs) == 4:
            values = {
                "lonmin": bboxArgs[0],
                "latmin": bboxArgs[1],
                "lonmax": bboxArgs[2],
                "latmax": bboxArgs[3],
            }

        elif isinstance(bboxArgs, dict) and len(bboxArgs) == 4:
            values = bboxArgs
        else:
            raise ValueError(
                "Expected a dictionary, list or tuple with 4 values for lonmin, latmin, lonmax, latmax"
            )
        super().__init__(**values)

    @validator("lonmin", "lonmax")
    @classmethod
    def validate_longitude(cls, v: NumType) -> NumType:
        """
        Validates the longitude values.

        :param v: The longitude value to be validated.
        :return: The validated longitude value.
        """
        if not -180 <= v <= 180:
            raise ValueError("Longitude values must be between -180 and 180")
        return v

    @validator("latmin", "latmax")
    @classmethod
    def validate_latitude(cls, v: NumType) -> NumType:
        """
        Validates the latitude values.

        :param v: The latitude value to be validated.
        :return: The validated latitude value.
        """
        if not -90 <= v <= 90:
            raise ValueError("Latitude values must be between -90 and 90")
        return v

    @validator("lonmax")
    @classmethod
    def validate_lonmax(cls, v: NumType, values: Dict[str, Any]) -> NumType:
        """
        Validates that lonmax is greater than lonmin.

        :param v: The lonmax value to be validated.
        :param values: A dictionary containing the current attribute values.
        :return: The validated lonmax value.
        """
        if "lonmin" in values and v < values["lonmin"]:
            raise ValueError("lonmax must be greater than lonmin")
        return v

    @validator("latmax")
    @classmethod
    def validate_latmax(cls, v: NumType, values: Dict[str, Any]) -> NumType:
        """
        Validates that latmax is greater than latmin.

        :param v: The latmax value to be validated.
        :param values: A dictionary containing the current attribute values.
        :return: The validated latmax value.
        """
        if "latmin" in values and v < values["latmin"]:
            raise ValueError("latmax must be greater than latmin")
        return v

    def to_polygon(self) -> Polygon:
        """
        Converts the bounding box to a polygon.

        :return: The Polygon object representing the bounding box.
        """
        return Polygon(
            (
                (self.lonmin, self.latmin),
                (self.lonmin, self.latmax),
                (self.lonmax, self.latmax),
                (self.lonmax, self.latmin),
            )
        )
