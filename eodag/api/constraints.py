import logging
from copy import deepcopy
from typing import Any, Dict, Union

import requests

from eodag.plugins.apis.base import Api
from eodag.plugins.search.base import Search
from eodag.utils import USER_AGENT
from eodag.utils.exceptions import NotAvailableError

logger = logging.getLogger("eodag.constraints")


def get_constraint_queryables_with_additional_params(
    constraints: list,
    params: Dict[str, Any],
    plugin: Union[Search, Api],
    product_type: str,
) -> Dict[str, Dict]:
    """
    gets the queryables from the constraints using the given parameters
    For all queryables only values matching the given parameters based on the constraints will be returned
    :param constraints: list of constraints fetched from the provider
    :type constraints: list
    :param params: conditions the constraints should fulfil
    :type params: dict
    :param plugin: search or api plugin that is used
    :type plugin: Union[Search, Api]
    :param product_type: product type for which the data should be fetched
    :type product_type: str
    :returns: dict containing queryable data
    :rtype: Dict[str, Dict]
    """
    constraint_matches = {}
    params_available = {k: False for k in params.keys()}
    # check which constraints match the given parameters
    eodag_provider_key_mapping = {}
    values_available = {k: set() for k in params.keys()}
    for i, constraint in enumerate(constraints):
        params_matched = {k: False for k in params.keys()}
        for param, value in params.items():
            provider_key = _get_provider_queryable_key(
                param, constraint, plugin, product_type
            )
            eodag_provider_key_mapping[provider_key] = param
            if provider_key:
                params_available[param] = True
                if value in constraint[provider_key]:
                    params_matched[param] = True
                values_available[provider_key].update(constraint[provider_key])
        constraint_matches[i] = params_matched

    # check if all parameters are available in the constraints
    for param, available in params_available.items():
        if not available:
            raise NotAvailableError(f"parameter {param} is not queryable")

    # add values of constraints matching params
    queryables = {}
    for num, matches in constraint_matches.items():
        if False not in matches.values():
            for key in constraints[num]:
                if key in queryables:
                    queryables[key]["enum"].update(constraints[num][key])
                elif key not in eodag_provider_key_mapping:
                    queryables[key] = {}
                    queryables[key]["enum"] = set(constraints[num][key])

    # check if constraints matching params have been found
    if len(queryables) == 0:
        if len(params) > 1:
            raise NotAvailableError(
                f"combination of values {str(params)} is not possible"
            )
        else:
            raise NotAvailableError(
                f"value {list(params.values())[0]} not available for param {list(params.keys())[0]}, "
                f"possible values: {str(values_available[list(params.keys())[0]])}"
            )

    return queryables


def fetch_constraints(constraints_url: str, plugin: Union[Search, Api]) -> list:
    """
    fetches the constraints from a provider
    :param constraints_url: url from which the constraints can be fetched
    :type constraints_url: str
    :param plugin: api or search plugin of the provider
    :type plugin: Union[Search, Api]
    :returns: list of constraints fetched from the provider
    :rtype: list
    """
    try:
        headers = USER_AGENT
        logger.debug("fetching constraints from %s", constraints_url)
        if hasattr(plugin, "auth"):
            res = requests.get(constraints_url, headers=headers, auth=plugin.auth)
        else:
            res = requests.get(constraints_url, headers=headers)
        res.raise_for_status()
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


def _get_provider_queryable_key(
    eodag_key: str,
    provider_queryables: Dict[str, Any],
    plugin: Union[Search, Api],
    product_type: str = None,
) -> str:
    """finds the provider queryable corresponding to the given eodag key based on the metadata mapping
    :param eodag_key: key in eodag
    :type eodag_key: str
    :param provider_queryables: queryables returned from the provider
    :type provider_queryables: dict
    :param plugin: plugin from which the config is taken
    :type plugin: Union[Api, Search]
    :param product_type: product type for which the metadata should be used
    :type product_type: str
    :returns: provider queryable key
    :rtype: str
    """
    metadata_mapping = _get_metadata_mapping(plugin, product_type)
    if eodag_key not in metadata_mapping:
        return ""
    mapping_key = metadata_mapping[eodag_key]
    if isinstance(mapping_key, list):
        for queryable in provider_queryables:
            if queryable in mapping_key[0]:
                return queryable
        return ""
    else:
        return eodag_key


def _get_metadata_mapping(plugin: Union[Search, Api], product_type: str = None):
    metadata_mapping = deepcopy(getattr(plugin.config, "metadata_mapping", {}))

    # product_type-specific metadata-mapping
    if product_type:
        metadata_mapping.update(
            getattr(plugin.config, "products", {})
            .get(product_type, {})
            .get("metadata_mapping", {})
        )
    return metadata_mapping
