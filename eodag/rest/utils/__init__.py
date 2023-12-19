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

import ast
import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List, NamedTuple, Optional, Tuple
from urllib.parse import unquote_plus, urlencode

import orjson
from fastapi import Request

from eodag.api.search_result import SearchResult
from eodag.plugins.crunch.filter_latest_intersect import FilterLatestIntersect
from eodag.plugins.crunch.filter_latest_tpl_name import FilterLatestByName
from eodag.plugins.crunch.filter_overlap import FilterOverlap

if TYPE_CHECKING:
    from eodag.rest.types.stac_search import SearchPostRequest

from pydantic import ValidationError as pydanticValidationError

from eodag.utils import string_to_jsonpath
from eodag.utils.exceptions import MisconfiguredError, ValidationError

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


STAC_QUERY_PATTERN = "query.*.*"


def format_pydantic_error(e: pydanticValidationError) -> str:
    """Format Pydantic ValidationError

    :param e: A Pydantic ValidationError object
    :tyype e: pydanticValidationError
    """
    error_header = f"Invalid request, {e.error_count()} error(s): "
    error_messages = [err["msg"] for err in e.errors()]
    return error_header + "; ".join(set(error_messages))


def filter_products(
    products: SearchResult, arguments: Dict[str, Any], **kwargs: Any
) -> SearchResult:
    """Apply an eodag cruncher to filter products"""
    filter_name = arguments.get("filter")
    if filter_name:
        cruncher = crunchers.get(filter_name)
        if not cruncher:
            raise ValidationError("unknown filter name")

        cruncher_config: Dict[str, Any] = dict()
        for config_param in cruncher.config_params:
            config_param_value = arguments.get(config_param)
            if not config_param_value:
                raise ValidationError(
                    f'filter additional parameters required: {", ".join(cruncher.config_params)}'
                )
            cruncher_config[config_param] = config_param_value

        try:
            products = products.crunch(cruncher.clazz(cruncher_config), **kwargs)
        except MisconfiguredError as e:
            raise ValidationError(str(e))

    return products


def get_metadata_query_paths(metadata_mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Get dict of query paths and their names from metadata_mapping

    :param metadata_mapping: STAC metadata mapping (see 'resources/stac_provider.yml')
    :type metadata_mapping: dict
    :returns: Mapping of query paths with their corresponding names
    :rtype: dict
    """
    metadata_query_paths: Dict[str, Any] = {}
    for metadata_name, metadata_spec in metadata_mapping.items():
        # When metadata_spec have a length of 1 the query path is not specified
        if len(metadata_spec) == 2:
            metadata_query_template = metadata_spec[0]
            try:
                # We create the dict corresponding to the metadata query of the metadata
                metadata_query_dict = ast.literal_eval(
                    metadata_query_template.format(**{metadata_name: None})
                )
                # We check if our query path pattern matches one or more of the dict path
                matches = [
                    (str(match.full_path))
                    for match in string_to_jsonpath(
                        STAC_QUERY_PATTERN, force=True
                    ).find(metadata_query_dict)
                ]
                if matches:
                    metadata_query_path = matches[0]
                    metadata_query_paths[metadata_query_path] = metadata_name
            except KeyError:
                pass
    return metadata_query_paths


def get_arguments_query_paths(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Get dict of query paths and their values from arguments

    Build a mapping of the query paths present in the arguments
    with their values. All matching paths of our STAC_QUERY_PATTERN
    ('query.*.*') are used.

    :param arguments: Request args
    :type arguments: dict
    :returns: Mapping of query paths with their corresponding values
    :rtype: dict
    """
    return dict(
        (str(match.full_path), match.value)
        for match in string_to_jsonpath(STAC_QUERY_PATTERN, force=True).find(arguments)
    )


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
    except orjson.JSONDecodeError:
        raise ValidationError(f"{k}: Incorrect JSON object")


def get_next_link(
    request: Request, search_request: SearchPostRequest
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Generate next link URL and body"""
    if request.method == "POST":
        body = search_request.model_dump(exclude_none=True)
        body["page"] = int(body.get("page", 1)) + 1
        return (str(request.url), body)

    params = dict(request.query_params)
    params["page"] = str(int(params.get("page", 1)) + 1)
    return (f"{request.state.url}?{urlencode(params)}", None)
