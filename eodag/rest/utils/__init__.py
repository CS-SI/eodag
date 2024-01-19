# -*- coding: utf-8 -*-
# Copyright 2023, CS Systemes d'Information, https://www.csgroup.eu/
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

import glob
import logging
import os
from io import BufferedReader
from shutil import make_archive, rmtree
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    NamedTuple,
    Optional,
)
from urllib.parse import unquote_plus, urlencode

import orjson
from fastapi import Request
from pydantic import ValidationError as pydanticValidationError

from eodag.plugins.crunch.filter_latest_intersect import FilterLatestIntersect
from eodag.plugins.crunch.filter_latest_tpl_name import FilterLatestByName
from eodag.plugins.crunch.filter_overlap import FilterOverlap
from eodag.utils import StreamResponse
from eodag.utils.exceptions import ValidationError

if TYPE_CHECKING:
    from eodag.rest.types.stac_search import SearchPostRequest


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
    """Verify whether the variable is of type dict[str, Any]"""
    if isinstance(var, Dict):
        return all(isinstance(k, str) for k in var.keys())  # type: ignore
    return False


def is_list_str(var: Any) -> bool:
    """Verify whether the variable is of type list[str]"""
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


def flatten_list(nested_list: List[Any]) -> List[Any]:
    """Flatten a nested list structure into a single list."""
    if not isinstance(nested_list, list):
        return [nested_list]
    else:
        flattened: List[Any] = []
        for element in nested_list:
            flattened.extend(flatten_list(element))
        return flattened


def list_to_str_list(input_list: List[Any]) -> List[str]:
    """Attempt to convert a list of any type to a list of strings."""
    try:
        # Try to convert each element to a string
        return [str(element) for element in input_list]
    except Exception as e:
        # Raise an exception if any element cannot be converted
        raise TypeError(f"Failed to convert to List[str]: {e}") from e


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


def read_file_chunks_and_delete(
    opened_file: BufferedReader, chunk_size: int = 64 * 1024
) -> Iterator[bytes]:
    """Yield file chunks and delete file when finished."""
    while True:
        data = opened_file.read(chunk_size)
        if not data:
            opened_file.close()
            os.remove(opened_file.name)
            logger.debug("%s deleted after streaming complete", opened_file.name)
            break
        yield data
    yield data


def file_to_stream(
    file_path: str,
) -> StreamResponse:
    """Break a file into chunck and return it as a byte stream"""
    if os.path.isdir(file_path):
        # do not zip if dir contains only one file
        all_filenames = [
            f
            for f in glob.glob(os.path.join(file_path, "**", "*"), recursive=True)
            if os.path.isfile(f)
        ]
        if len(all_filenames) == 1:
            filepath_to_stream = all_filenames[0]
        else:
            filepath_to_stream = f"{file_path}.zip"
            logger.debug(
                "Building archive for downloaded product path %s",
                filepath_to_stream,
            )
            make_archive(file_path, "zip", file_path)
            rmtree(file_path)
    else:
        filepath_to_stream = file_path

    filename = os.path.basename(filepath_to_stream)
    return StreamResponse(
        content=read_file_chunks_and_delete(open(filepath_to_stream, "rb")),
        headers={
            "content-disposition": f"attachment; filename={filename}",
        },
    )
