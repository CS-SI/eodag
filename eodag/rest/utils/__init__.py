# -*- coding: utf-8 -*-
# Copyright 2018, CS Systemes d'Information, https://www.csgroup.eu/
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
"""EODAG REST utils"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List, NamedTuple, Optional
from urllib.parse import unquote_plus, urlencode

import orjson
from fastapi import Request

from eodag.plugins.crunch.filter_latest_intersect import FilterLatestIntersect
from eodag.plugins.crunch.filter_latest_tpl_name import FilterLatestByName
from eodag.plugins.crunch.filter_overlap import FilterOverlap

if TYPE_CHECKING:
    from eodag.rest.types.stac_search import SearchPostRequest

from pydantic import ValidationError as pydanticValidationError

from eodag.utils.exceptions import ValidationError

logger = logging.getLogger("eodag.rest.utils")


class Cruncher(NamedTuple):
    """Type hinted Cruncher namedTuple"""

    clazz: Callable[..., Any]
    config_params: List[str]


crunchers = {
    "latestIntersect": Cruncher(FilterLatestIntersect, []),
    "latestByName": Cruncher(FilterLatestByName, ["name_pattern"]),
    "overlap": Cruncher(FilterOverlap, ["minimum_overlap"]),
}


def format_pydantic_error(e: pydanticValidationError) -> str:
    """Format Pydantic ValidationError

    :param e: A Pydantic ValidationError object
    :tyype e: pydanticValidationError
    """
    error_header = f"Invalid request, {e.error_count()} error(s): "
    error_messages = [err["msg"] for err in e.errors()]
    return error_header + "; ".join(set(error_messages))


def is_dict_str_any(var: Any) -> bool:
    """Verify whether the variable is of type Dict[str, Any]"""
    if isinstance(var, Dict):
        return all(isinstance(k, str) for k in var.keys())  # type: ignore
    return False


def is_list_str(var: Any) -> bool:
    """Verify whether the variable is of type Dict[str, Any]"""
    if isinstance(var, List):
        return all(isinstance(e, str) for e in var)  # type: ignore
    return False


def str2list(v: Optional[str]) -> Optional[List[str]]:
    """Convert string to list base on , delimiter."""
    if v:
        return v.split(",")
    return None


def str2json(k: str, v: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """decoding a URL parameter and then parsing it as JSON."""
    if not v:
        return None
    try:
        return orjson.loads(unquote_plus(v))
    except orjson.JSONDecodeError as e:
        raise ValidationError(f"{k}: Incorrect JSON object") from e


def get_next_link(
    request: Request,
    search_request: SearchPostRequest,
    total_results: int,
    items_per_page: int,
) -> Optional[Dict[str, Any]]:
    """Generate next link URL and body"""
    body = search_request.model_dump(exclude_none=True)

    params = dict(request.query_params)

    page = int(body.get("page", 0) or params.get("page", 0)) or 1

    if items_per_page * page >= total_results:
        return None

    url: str
    if request.method == "POST":
        body["page"] = page + 1
        url = str(request.url)
    else:
        params["page"] = str(page + 1)
        url = f"{request.state.url}?{urlencode(params)}"

    next: Dict[str, Any] = {
        "rel": "next",
        "href": url,
        "title": "Next page",
        "method": request.method,
        "type": "application/geo+json",
    }
    if request.method == "POST":
        next["body"] = body
    return next
