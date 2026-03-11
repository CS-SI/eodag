# -*- coding: utf-8 -*-
# Copyright 2026, CS GROUP - France, https://www.csgroup.eu/
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

"""Custom SQLite functions for collections storage."""

from __future__ import annotations

import datetime
import json
import logging
from typing import TYPE_CHECKING, Optional

from shapely import wkt
from shapely.errors import ShapelyError

from eodag.utils import get_geometry_from_various
from eodag.utils.dates import rfc3339_str_to_datetime

if TYPE_CHECKING:
    from sqlite3 import Connection


logger = logging.getLogger("eodag.databases.sqlite_functions")


def check_collection_geom_intersection(coll_json: str, geom_wkt: str) -> bool:
    """Extract geometry from a collection's JSON content and check if it intersects the input geometry.

    :param coll_json: Collection JSON as string
    :param geom_wkt: The input geometry as WKT string
    :returns: True if there is an intersection, otherwise False

    :raises: :class:`~shapely.errors.ShapelyError`
    """
    try:
        coll_dict = json.loads(coll_json)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False

    coll_geom = coll_dict["extent"]["spatial"]["bbox"][0]
    coll_geom_obj = get_geometry_from_various(geometry=coll_geom)

    geom_obj = wkt.loads(geom_wkt)

    if coll_geom_obj is None or geom_obj is None:
        return False

    try:
        geom_intersection = coll_geom_obj.intersection(geom_obj)
    except ShapelyError:
        logger.warning(
            "Unable to intersect the requested extent: %s with the collection geometry: %s",
            geom_obj,
            coll_geom_obj,
        )
        return False

    if geom_intersection.is_empty:
        return False

    return True


def check_collection_interval_intersection(
    coll_json: str, start_date_str: Optional[str], end_date_str: Optional[str]
) -> bool:
    """Extract interval from a collection's JSON content and check if it intersects the input interval.

    :param coll_json: Collection JSON as string
    :param start_date_str: The input start date as string
    :param end_date_str: The input end date as string
    :returns: Start datetime string or None
    """
    try:
        coll_dict = json.loads(coll_json)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False

    min_aware = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
    max_aware = datetime.datetime.max.replace(tzinfo=datetime.timezone.utc)

    coll_start_str = coll_dict["extent"]["temporal"]["interval"][0][0]
    if coll_start_str and isinstance(coll_start_str, str):
        coll_start = rfc3339_str_to_datetime(coll_start_str)
    else:
        coll_start = coll_start_str or min_aware
    coll_end_str = coll_dict["extent"]["temporal"]["interval"][0][1]
    if coll_end_str and isinstance(coll_end_str, str):
        coll_end = rfc3339_str_to_datetime(coll_end_str)
    else:
        coll_end = coll_end_str or max_aware

    max_start = max(
        rfc3339_str_to_datetime(start_date_str) if start_date_str else min_aware,
        coll_start,
    )
    min_end = min(
        rfc3339_str_to_datetime(end_date_str) if end_date_str else max_aware,
        coll_end,
    )
    if not (max_start <= min_end):
        return False
    return True


def register_sqlite_functions(con: Connection) -> None:
    """Register custom SQLite functions.

    :param con: SQLite connection object
    """
    con.create_function(
        "check_collection_geom_intersection", 2, check_collection_geom_intersection
    )
    con.create_function(
        "check_collection_interval_intersection",
        3,
        check_collection_interval_intersection,
    )
