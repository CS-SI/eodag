# -*- coding: utf-8 -*-
# Copyright 2024, CS Systemes d'Information, https://www.csgroup.eu/
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
import copy
import logging
import os
from typing import Any, Dict, List, Set, Union

import requests
from requests.auth import AuthBase

from eodag.api.product.metadata_mapping import get_provider_queryable_key
from eodag.plugins.apis.base import Api
from eodag.plugins.search.base import Search
from eodag.utils import deepcopy
from eodag.utils.exceptions import RequestError, ValidationError
from eodag.utils.requests import fetch_json

logger = logging.getLogger("eodag.constraints")


def get_constraint_queryables_with_additional_params(
    constraints: List[Any],
    input_params: Dict[str, Any],
    plugin: Union[Search, Api],
    product_type: str,
) -> Dict[str, Dict[str, Set[Any]]]:
    """
    gets the queryables from the constraints using the given parameters
    For all queryables only values matching the given parameters based on the constraints will be returned
    :param constraints: list of constraints fetched from the provider
    :type constraints: List[Any]
    :param input_params: conditions the constraints should fulfil
    :type input_params: dict
    :param plugin: search or api plugin that is used
    :type plugin: Union[Search, Api]
    :param product_type: product type for which the data should be fetched
    :type product_type: str
    :returns: dict containing queryable data
    :rtype: Dict[str, Dict[str, Set[Any]]]
    """
    defaults = copy.deepcopy(input_params)
    constraint_matches = {}
    params = {k: v for k, v in defaults.items() if v}
    for p in params.keys():
        defaults.pop(p, None)
    params_available = {k: False for k in params.keys()}
    # check which constraints match the given parameters
    eodag_provider_key_mapping = {}
    values_available: Dict[str, Set[Any]] = {k: set() for k in params.keys()}
    metadata_mapping = plugin.config.products.get(product_type, {}).get(
        "metadata_mapping", {}
    )
    if not metadata_mapping:
        metadata_mapping = plugin.config.metadata_mapping
    for i, constraint in enumerate(constraints):
        params_matched = {k: False for k in params.keys()}
        for param, value in params.items():
            provider_key = get_provider_queryable_key(
                param, constraint, metadata_mapping
            )
            if provider_key and provider_key in constraint:
                eodag_provider_key_mapping[provider_key] = param
                params_available[param] = True
                if (
                    isinstance(value, list)
                    and all([v in constraint[provider_key] for v in value])
                    or not isinstance(value, list)
                    and value in constraint[provider_key]
                ):
                    params_matched[param] = True
                elif isinstance(value, str):
                    # for Copernicus providers, values can be multiple and represented with a string
                    # separated by slashes (example: time = "0000/0100/0200")
                    values = value.split("/")
                    params_matched[param] = all(
                        [v in constraint[provider_key] for v in values]
                    )
                values_available[param].update(constraint[provider_key])
        # match with default values of params
        for default_param, default_value in defaults.items():
            provider_key = get_provider_queryable_key(
                default_param,
                constraint,
                metadata_mapping,
            )
            if provider_key and provider_key in constraint:
                eodag_provider_key_mapping[provider_key] = default_param
                params_matched[default_param] = False
                if default_value in constraint[provider_key]:
                    params_matched[default_param] = True
        constraint_matches[i] = params_matched

    # check if all parameters are available in the constraints
    not_available_params = set()
    for param, available in params_available.items():
        if not available:
            not_available_params.add(param)
    if not_available_params:
        return {"not_available": {"enum": not_available_params}}

    # clear constraint_matches if no combination matches
    matching_combinations = [
        False not in v.values() for v in constraint_matches.values()
    ]
    if not any(matching_combinations):
        constraint_matches = {}

    # add values of constraints matching params
    queryables: Dict[str, Dict[str, Set[Any]]] = {}
    for num, matches in constraint_matches.items():
        for key in constraints[num]:
            other_keys_matching = [v for k, v in matches.items() if k != key]
            key_matches_a_constraint = any(
                v.get(key, False) for v in constraint_matches.values()
            )
            if False in other_keys_matching or (
                not key_matches_a_constraint and key in matches
            ):
                continue
            if key in queryables:
                queryables[key]["enum"].update(constraints[num][key])
            else:
                queryables[key] = {}
                queryables[key]["enum"] = set(constraints[num][key])

    other_values = _get_other_possible_values_for_values_with_defaults(
        defaults, params, constraints, metadata_mapping
    )
    for key in queryables:
        if key in other_values:
            queryables[key]["enum"].update(other_values[key])

    # check if constraints matching params have been found
    if len(queryables) == 0:
        if len(params) > 1:
            raise ValidationError(
                f"combination of values {str(params)} is not possible"
            )
        elif len(params) == 1 and len(defaults) > 0:
            raise ValidationError(
                f"value {list(params.values())[0]} not available for param {list(params.keys())[0]} "
                f"with default values {str(defaults)}"
            )

        elif len(params) == 1:
            raise ValidationError(
                f"value {list(params.values())[0]} not available for param {list(params.keys())[0]}, "
                f"possible values: {str(sorted(values_available[list(params.keys())[0]]))}"
            )
        else:
            raise ValidationError(
                f"no constraints matching default params {str(defaults)} found"
            )

    return queryables


def fetch_constraints(
    constraints_url: str, plugin: Union[Search, Api]
) -> List[Dict[Any, Any]]:
    """
    fetches the constraints from a provider
    :param constraints_url: url from which the constraints can be fetched
    :type constraints_url: str
    :param plugin: api or search plugin of the provider
    :type plugin: Union[Search, Api]
    :returns: list of constraints fetched from the provider
    :rtype: List[Dict[Any, Any]]
    """
    auth = (
        plugin.auth
        if hasattr(plugin, "auth") and isinstance(plugin.auth, AuthBase)
        else None
    )
    try:
        constraints_data = fetch_json(constraints_url, auth=auth)
    except RequestError as err:
        logger.error(str(err))
        return []

    config = plugin.config.__dict__
    if (
        "constraints_entry" in config
        and config["constraints_entry"]
        and config["constraints_entry"] in constraints_data
    ):
        constraints = constraints_data[config["constraints_entry"]]
    elif config.get("stop_without_constraints_entry_key", False):
        return []
    else:
        constraints = constraints_data
    return constraints


def _get_other_possible_values_for_values_with_defaults(
    defaults: Dict[str, Any],
    params: Dict[str, Any],
    constraints: List[Dict[Any, Any]],
    metadata_mapping: Dict[str, Union[str, list]],
) -> Dict[str, Set[Any]]:
    possible_values = {}
    for param, default_value in defaults.items():
        fixed_params = deepcopy(params)
        param_values = set()
        for p in defaults:
            if p != param:
                fixed_params[p] = defaults[p]
        for constraint in constraints:
            provider_key = get_provider_queryable_key(
                param, constraint, metadata_mapping
            )
            if not provider_key:
                provider_key = param
            if (
                _matches_constraint(constraint, fixed_params, metadata_mapping)
                and provider_key in constraint
            ):
                param_values.update(constraint[provider_key])
        possible_values[provider_key] = param_values
    return possible_values


def _matches_constraint(
    constraint: Dict[Any, Any],
    params: Dict[str, Any],
    metadata_mapping: Dict[str, Union[str, list]],
) -> bool:
    for p in params:
        provider_key = get_provider_queryable_key(p, constraint, metadata_mapping)
        if provider_key not in constraint:
            continue
        if isinstance(params[p], list):
            for value in params[p]:
                if value not in constraint[provider_key]:
                    return False
        else:
            if params[p] not in constraint[provider_key]:
                return False
    return True
