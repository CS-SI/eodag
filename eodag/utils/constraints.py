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
from typing import Any, Dict, List, Set, Union

import requests

from eodag.api.product.metadata_mapping import get_provider_queryable_key
from eodag.plugins.apis.base import Api
from eodag.plugins.search.base import Search
from eodag.utils import HTTP_REQ_TIMEOUT, USER_AGENT
from eodag.utils.exceptions import TimeOutError, ValidationError

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
    params = copy.deepcopy(input_params)
    constraint_matches = {}
    defaults = params.pop("defaults", {})
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
            if provider_key:
                eodag_provider_key_mapping[provider_key] = param
                params_available[param] = True
                if value in constraint[provider_key]:
                    params_matched[param] = True
                values_available[param].update(constraint[provider_key])
        # match with default values of params
        for default_param, default_value in defaults.items():
            provider_key = get_provider_queryable_key(
                default_param,
                constraint,
                metadata_mapping,
            )
            if provider_key:
                eodag_provider_key_mapping[provider_key] = default_param
                params_matched[default_param] = False
                if default_value in constraint[provider_key]:
                    params_matched[default_param] = True
        constraint_matches[i] = params_matched

    # check if all parameters are available in the constraints
    for param, available in params_available.items():
        if not available:
            raise ValidationError(f"parameter {param} is not queryable")

    # add values of constraints matching params
    queryables: Dict[str, Dict[str, Set[Any]]] = {}
    for num, matches in constraint_matches.items():
        if False not in matches.values():
            for key in constraints[num]:
                if key in queryables:
                    queryables[key]["enum"].update(constraints[num][key])
                else:
                    queryables[key] = {}
                    queryables[key]["enum"] = set(constraints[num][key])

    # check if constraints matching params have been found
    if len(queryables) == 0:
        if len(params) > 1:
            raise ValidationError(
                f"combination of values {str(params)} is not possible"
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
    try:
        headers = USER_AGENT
        logger.debug("fetching constraints from %s", constraints_url)
        if hasattr(plugin, "auth"):
            res = requests.get(
                constraints_url,
                headers=headers,
                auth=plugin.auth,
                timeout=HTTP_REQ_TIMEOUT,
            )
        else:
            res = requests.get(
                constraints_url, headers=headers, timeout=HTTP_REQ_TIMEOUT
            )
        res.raise_for_status()
    except requests.exceptions.Timeout as exc:
        raise TimeOutError(exc, timeout=HTTP_REQ_TIMEOUT) from exc
    except requests.exceptions.HTTPError as err:
        logger.error(
            "constraints could not be fetched from %s, error: %s",
            constraints_url,
            str(err),
        )
        return []
    else:
        constraints_data = res.json()
        config = plugin.config.__dict__
        if (
            "constraints_entry" in config
            and config["constraints_entry"]
            and config["constraints_entry"] in constraints_data
        ):
            constraints = constraints_data[config["constraints_entry"]]
        else:
            constraints = constraints_data
        return constraints
