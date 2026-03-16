# -*- coding: utf-8 -*-
# Copyright 2022, CS GROUP - France, https://www.csgroup.eu/
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

import logging
from typing import Any, Optional

from eodag.types.stac_extensions import EcmwfItemProperties
from eodag.utils.dates import parse_date, parse_year_month_day

logger = logging.getLogger("eodag.search.build_search_result")

ECMWF_PREFIX = "ecmwf:"

ALLOWED_KEYWORDS = set(
    [k.replace("ecmwf_", "") for k in EcmwfItemProperties.model_fields.keys()]
)

END = "end_datetime"

START = "start_datetime"


def ecmwf_mtd() -> dict[str, Any]:
    """
    Make metadata mapping dict from a list of defined ECMWF Keywords

    We automatically add the #to_geojson convert to prevent modification of entries by eval() in the metadata mapping.

    keyword:
        - keyword
        - $."keyword"#to_geojson

    :return: metadata mapping dict
    """
    return {k: [k, f'{{$."{k}"#to_geojson}}'] for k in ALLOWED_KEYWORDS}


def update_properties_from_element(
    prop: dict[str, Any], element: dict[str, Any], values: list[str]
) -> None:
    """updates a property dict with the given values based on the information from the element dict
    e.g. the type is set based on the type of the element
    """
    # multichoice elements are transformed into array
    if element["type"] in ("StringListWidget", "StringListArrayWidget"):
        prop["type"] = "array"
        if values:
            prop["items"] = {"type": "string", "enum": sorted(values)}

    # single choice elements are transformed into string
    elif element["type"] in (
        "StringChoiceWidget",
        "DateRangeWidget",
        "FreeformInputWidget",
    ):
        prop["type"] = "string"
        if values:
            prop["enum"] = sorted(values)

    # a bbox element
    elif element["type"] in ["GeographicExtentWidget", "GeographicExtentMapWidget"]:
        prop.update(
            {
                "type": "array",
                "minItems": 4,
                "additionalItems": False,
                "items": [
                    {
                        "type": "number",
                        "maximum": 90,
                        "minimum": -90,
                        "description": "North border of the bounding box",
                    },
                    {
                        "type": "number",
                        "maximum": 180,
                        "minimum": -180,
                        "description": "West border of the bounding box",
                    },
                    {
                        "type": "number",
                        "maximum": 90,
                        "minimum": -90,
                        "description": "South border of the bounding box",
                    },
                    {
                        "type": "number",
                        "maximum": 180,
                        "minimum": -180,
                        "description": "East border of the bounding box",
                    },
                ],
            }
        )

    # DateRangeWidget is a calendar date picker
    if element["type"] == "DateRangeWidget":
        prop["description"] = "date formatted like yyyy-mm-dd/yyyy-mm-dd"

    # a single geographic location
    if element["type"] == "GeographicLocationWidget":
        prop.update(
            {
                "type": "object",
                "description": "Longitude and latitude of a single location",
                "properties": {
                    "longitude": {
                        "type": "number",
                        "maximum": 180,
                        "minimum": -180,
                    },
                    "latitude": {
                        "type": "number",
                        "maximum": 90,
                        "minimum": -90,
                    },
                },
            }
        )

    if description := element.get("help"):
        prop["description"] = description


def ecmwf_format(v: str, alias: bool = True) -> str:
    """Add ECMWF prefix to value v if v is a ECMWF keyword.

    :param v: parameter to format
    :param alias: whether to format for alias (with ':') or for query param (False, with '_')
    :return: formatted parameter

    >>> ecmwf_format('dataset', alias=False)
    'ecmwf_dataset'
    >>> ecmwf_format('variable')
    'ecmwf:variable'
    >>> ecmwf_format('unknown_param')
    'unknown_param'
    """
    separator = ":" if alias else "_"
    return f"{ECMWF_PREFIX[:-1]}{separator}{v}" if v in ALLOWED_KEYWORDS else v


def ecmwf_temporal_to_eodag(
    params: dict[str, Any]
) -> tuple[Optional[str], Optional[str]]:
    """
    Converts ECMWF temporal parameters to EODAG temporal parameters.

    ECMWF temporal parameters:
        - **year** or **hyear**: Union[str, list[str]] — Year(s) as a string or list of strings.
        - **month** or **hmonth**: Union[str, list[str]] — Month(s) as a string or list of strings.
        - **day** or **hday**: Union[str, list[str]] — Day(s) as a string or list of strings.
        - **time**: str — A string representing the time in the format `HHMM` (e.g., `0200`, `0800`, `1400`).
        - **date**: str — A string in one of the formats:
            - `YYYY-MM-DD`
            - `YYYY-MM-DD/YYYY-MM-DD`
            - `YYYY-MM-DD/to/YYYY-MM-DD`

    :param params: Dictionary containing ECMWF temporal parameters.
    :return: A tuple with:
        - **start**: A string in the format `YYYY-MM-DDTHH:MM:SSZ`.
        - **end**: A string in the format `YYYY-MM-DDTHH:MM:SSZ`.
    """
    start = end = None

    if date := params.get("date"):
        if isinstance(date, list):
            date = "/".join(date)
        start, end = parse_date(date, params.get("time"))

    elif year := (params.get("year") or params.get("hyear")):
        month = params.get("month") or params.get("hmonth")
        day = params.get("day") or params.get("hday")
        time = params.get("time")

        start, end = parse_year_month_day(year, month, day, time)

    if start and end:
        return start.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        return None, None


__all__ = [
    "ecmwf_mtd",
    "update_properties_from_element",
    "ecmwf_format",
    "ecmwf_temporal_to_eodag",
    "ECMWF_PREFIX",
    "ALLOWED_KEYWORDS",
    "END",
    "START",
]
