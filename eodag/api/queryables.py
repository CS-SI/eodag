import logging
import re
from copy import deepcopy
from typing import Any, Dict, Optional, Union

import requests
from pydantic import BaseModel, Field

from eodag.api.product.metadata_mapping import OSEO_METADATA_MAPPING
from eodag.config import load_stac_config
from eodag.plugins.apis.base import Api
from eodag.plugins.search.base import Search
from eodag.utils import USER_AGENT
from eodag.utils.exceptions import NotAvailableError, RequestError

CAMEL_TO_SPACE_TITLED = re.compile(r"[:_-]|(?<=[a-z])(?=[A-Z])")
logger = logging.getLogger("eodag.queryables")


def rename_to_stac_standard(key: str) -> str:
    """Fetch the queryable properties for a collection.

    :param key: The camelCase key name obtained from a collection's metadata mapping.
    :type key: str
    :returns: The STAC-standardized property name if it exists, else the default camelCase queryable name
    :rtype: str
    """
    # Load the stac config properties for renaming the properties
    # to their STAC standard
    stac_config = load_stac_config()
    stac_config_properties: Dict[str, Any] = stac_config["item"]["properties"]

    for stac_property, value in stac_config_properties.items():
        if isinstance(value, list):
            value = value[0]
        if str(value).endswith(key):
            return stac_property

    if key in OSEO_METADATA_MAPPING:
        return "oseo:" + key

    return key


class BaseQueryableProperty(BaseModel):
    """A class representing a queryable property.

    :param description: The description of the queryables property
    :type description: str
    :param type: (optional) possible types of the property
    :type type: list[str]
    """

    description: str
    type: Optional[list] = None
    values: Optional[list] = None

    def update_properties(self, new_properties: dict):
        """updates the properties with the given new properties keeping already existing value"""
        if "type" in new_properties and not self.type:
            self.type = new_properties["type"]
        if "values" in new_properties and not self.values:
            self.values = new_properties["values"]


class QueryableProperty(BaseQueryableProperty):
    """A class representing a queryable property.

    :param description: The description of the queryables property
    :type description: str
    :param ref: (optional) A reference link to the schema of the property.
    :type ref: str
    :param type: (optional) possible types of the property
    :type type: list[str]
    """

    description: str
    ref: Optional[str] = Field(default=None, serialization_alias="$ref")
    type: Optional[list] = None

    def update_properties(self, new_properties: dict):
        """updates the properties with the given new properties keeping already existing value"""
        super().update_properties(new_properties)
        if "ref" in new_properties and not self.ref:
            self.ref = new_properties["ref"]


class Queryables(BaseModel):
    """A class representing queryable properties for the STAC API.

    :param json_schema: The URL of the JSON schema.
    :type json_schema: str
    :param q_id: (optional) The identifier of the queryables.
    :type q_id: str
    :param q_type: The type of the object.
    :type q_type: str
    :param title: The title of the queryables.
    :type title: str
    :param description: The description of the queryables
    :type description: str
    :param properties: A dictionary of queryable properties.
    :type properties: dict
    :param additional_properties: Whether additional properties are allowed.
    :type additional_properties: bool
    """

    json_schema: str = Field(
        default="https://json-schema.org/draft/2019-09/schema",
        serialization_alias="$schema",
    )
    q_id: Optional[str] = Field(default=None, serialization_alias="$id")
    q_type: str = Field(default="object", serialization_alias="type")
    title: str = Field(default="Queryables for EODAG STAC API")
    description: str = Field(
        default="Queryable names for the EODAG STAC API Item Search filter."
    )
    properties: Dict[str, QueryableProperty] = Field(
        default={
            "id": QueryableProperty(
                description="ID",
                ref="https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json#/id",
            ),
            "collection": QueryableProperty(
                description="Collection",
                ref="https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json#/collection",
            ),
            "geometry": QueryableProperty(
                description="Geometry",
                ref="https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json#/geometry",
            ),
            "bbox": QueryableProperty(
                description="Bbox",
                ref="https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json#/bbox",
            ),
            "datetime": QueryableProperty(
                description="Datetime",
                ref="https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/datetime.json#/properties/datetime",
            ),
        }
    )
    additional_properties: bool = Field(
        default=True, serialization_alias="additionalProperties"
    )

    def get_base_properties(self) -> Dict[str, BaseQueryableProperty]:
        """Get the queryable properties.

        :returns: A dictionary containing queryable properties.
        :rtype: typing.Dict[str, QueryableProperty]
        """
        base_properties = {}
        for key, property in self.properties.items():
            base_property = BaseQueryableProperty(
                description=property.description,
                type=property.type,
                values=property.values,
            )
            base_properties[key] = base_property
        return base_properties

    def __contains__(self, name: str) -> bool:
        return name in self.properties

    def __setitem__(self, name: str, qprop: BaseQueryableProperty) -> None:
        self.properties[name] = qprop


def format_queryable(
    queryable_key: str, base: bool = True, attributes: Dict[str, Any] = None
) -> BaseQueryableProperty:
    """
    creates a queryable property from a property key
    :param queryable_key: key of the property for which the queryable property shall be created
    :type queryable_key: str
    :param base: if a base queryable object or an extended queryable object should be created
    :type base: bool
    :param attributes: attributes of the queryable property
    :type attributes: dict[str,Any]
    :returns: queryable property for the given key
    :rtype: QueryableProperty
    """
    if not attributes:
        attributes = {}
    if queryable_key not in ["start", "end", "geom", "locations", "id"]:
        stac_key = rename_to_stac_standard(queryable_key)
    else:
        stac_key = queryable_key
    titled_name = re.sub(CAMEL_TO_SPACE_TITLED, " ", stac_key.split(":")[-1]).title()
    attributes["description"] = titled_name
    if base:
        return BaseQueryableProperty(**attributes)
    return QueryableProperty(**attributes)


def format_provider_queryables(
    provider_queryables: dict, base: bool = True
) -> Dict[str, Any]:
    """
    formats the provider queryables and adds them to the existing queryables
    :param provider_queryables: queryables fetched from the provider
    :type provider_queryables: dict
    :param base: if a base queryable object or an extended queryable object should be created
    :type base: bool
    :returns queryable_properties: A dict containing the formatted queryable properties
                                       including queryables fetched from the provider.
    :rtype dict
    """
    queryables = {}
    for queryable, data in provider_queryables.items():
        titled_name = re.sub(
            CAMEL_TO_SPACE_TITLED, " ", queryable.split(":")[-1]
        ).title()
        attributes = {"description": titled_name}
        if base:
            queryable_prop = BaseQueryableProperty(description=titled_name)
        else:
            queryable_prop = QueryableProperty(description=titled_name)
        if "type" in data:
            if isinstance(data["type"], list):
                attributes["type"] = data["type"]
            else:
                attributes["type"] = [data["type"]]
        if "ref" in data and not base:
            attributes["ref"] = data["ref"]
        if "enum" in data:
            attributes["values"] = data["enum"]
        queryable_prop.update_properties(attributes)
        queryables[queryable] = queryable_prop
    return queryables


def get_queryables_from_metadata_mapping(
    plugin: Union[Search, Api],
    product_type: str,
    default_queryables: dict,
    base: bool = True,
) -> Dict[str, Any]:
    """
    Create queryables based on the metadata mapping of the given product type
    :param plugin: search plugin from which the metadata information is taken
    :type plugin: Union[Search, Api]
    :param product_type: EODAG product type
    :type product_type: str
    :param base: if base queryable objects or extended queryable objects should be created
    :type base: bool
    :returns queryable_properties: A dict containing the formatted queryable properties
    :rtype dict
    """
    provider_queryables = default_queryables

    metadata_mapping = _get_metadata_mapping(plugin, product_type)

    for key, value in metadata_mapping.items():
        if (
            isinstance(value, list)
            and "TimeFromAscendingNode" not in key
            and key not in provider_queryables
        ):
            queryable = format_queryable(key, base)
            provider_queryables[key] = queryable

    return provider_queryables


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


def _map_to_eodag_keys(
    queryables: Dict[str, Any], plugin: Union[Search, Api], product_type: str = None
) -> Dict[str, Any]:
    metadata_mapping = _get_metadata_mapping(plugin, product_type)
    new_queryables = {}
    for key, values in metadata_mapping.items():
        if isinstance(values, list):
            provider_str = values[0]
            for queryable in queryables:
                pattern = "[^_A-Za-z]" + queryable
                if queryable == provider_str or re.search(pattern, provider_str):
                    new_queryables[key] = queryables.get(queryable)
    return new_queryables


def get_provider_queryables(
    search_plugin: Union[Search, Api],
    provider: str,
    base: bool,
) -> Dict[str, Any]:
    """Fetch the queryables from the given provider.
    If the queryables endpoint is not supported by the provider, an empty dict is returned
    :param search_plugin: search plugin from which the queryables url and authentication can be retrieved
    :type search_plugin: Union[Search, Api]
    :param provider: The provider.
    :type provider: str
    :param base: if base queryable objects or extended queryable objects should be created
    :type base: bool
    :returns queryable_properties: A dict containing the formatted queryable properties
                                   including queryables fetched from the provider.
    :rtype dict
    """

    search_type = search_plugin.config.type
    if search_type == "StacSearch":
        queryables_url = search_plugin.config.api_endpoint.replace(
            "/search", "/queryables"
        )
    else:
        queryables_url = ""
    if not queryables_url:
        logger.info("no url was found for %s provider-specific queryables", provider)
        return {}
    try:
        headers = USER_AGENT
        logger.debug("fetching queryables from %s", queryables_url)
        if hasattr(search_plugin, "auth"):
            res = requests.get(queryables_url, headers=headers, auth=search_plugin.auth)
        else:
            res = requests.get(queryables_url, headers=headers)
        res.raise_for_status()
    except requests.exceptions.HTTPError as err:
        if err.response.status_code == 404:
            logger.info("provider %s does not support queryables", provider)
            return {}
        else:
            raise RequestError(str(err))
    else:
        provider_queryables = res.json()["properties"]
        provider_queryables = _map_to_eodag_keys(provider_queryables, search_plugin)
        return format_provider_queryables(provider_queryables, base)


def get_provider_product_type_queryables(
    search_plugin: Union[Search, Api],
    provider: str,
    product_type: str,
    base: bool,
) -> Dict[str, Any]:
    """Fetch the queryables from the given provider for the given product type
    If the queryables endpoint is not supported by the provider, an empty dict is returned.
    :param search_plugin: search plugin from which the queryables url and authentication can be retrieved
    :type search_plugin: Union[Search, Api]
    :param provider: The provider.
    :type provider: str
    :param product_type: EODAG product type
    :type product_type: str
    :param base: if base queryable objects or extended queryable objects should be created
    :type base: bool
    :returns queryable_properties: A dict containing the formatted queryable properties
                                   including queryables fetched from the provider.
    :rtype dict
    """
    search_type = search_plugin.config.type
    provider_product_type = search_plugin.config.products.get(product_type, {}).get(
        "productType", None
    )
    if not provider_product_type:
        logger.warning(
            "provider product type mapping for product type %s not found",
            product_type,
        )
        provider_product_type = product_type
    if search_type == "StacSearch":
        api_url = search_plugin.config.api_endpoint.replace("/search", "/")
        queryables_url = (
            api_url + "collections/" + provider_product_type + "/queryables"
        )
    else:
        queryables_url = ""

    if not queryables_url:
        logger.info(
            "no url was found for %s on %s provider-specific queryables",
            product_type,
            provider,
        )
        return {}
    try:
        headers = USER_AGENT
        logger.debug("fetching queryables from %s", queryables_url)
        if hasattr(search_plugin, "auth"):
            res = requests.get(queryables_url, headers=headers, auth=search_plugin.auth)
        else:
            res = requests.get(queryables_url, headers=headers)
        res.raise_for_status()
    except requests.exceptions.HTTPError as err:
        if err.response.status_code == 404:
            logger.info("provider %s does not support queryables", provider)
            return {}
        else:
            raise RequestError(str(err))
    else:
        if "properties" in res.json():
            provider_queryables = res.json()["properties"]
            provider_queryables = _map_to_eodag_keys(
                provider_queryables, search_plugin, product_type
            )
            return format_provider_queryables(provider_queryables, base)
        else:
            return {}


def get_queryables_from_constraints(
    plugin: Union[Search, Api], product_type: str, base: bool, **kwargs: dict
) -> Dict[str, Any]:
    """
    creates queryables from the parameters given in the constraints data fetched from the provider
    :param plugin: search plugin containing provider information
    :type plugin: Union[Search, Api]
    :param product_type: EODAG product type
    :type product_type: str
    :param base: if base queryable objects or extended queryable objects should be created
    :type base: bool
    :returns queryable_properties: A dict containing the constraint params formatted as queryable properties
    :rtype dict
    """
    constraints_file_url = getattr(plugin.config, "constraints_file_url", "")
    if not constraints_file_url:
        return {}
    provider_product_type = plugin.config.products.get(product_type, {}).get(
        "productType", None
    )
    if not provider_product_type:
        provider_product_type = plugin.config.products.get(product_type, {}).get(
            "dataset", None
        )
    if not provider_product_type:
        logger.warning(
            "provider product type mapping for product type %s not found",
            product_type,
        )
        provider_product_type = product_type
    if "{" in constraints_file_url:
        constraints_file_url = constraints_file_url.format(
            dataset=provider_product_type
        )
    constraints = _fetch_constraints(constraints_file_url, plugin)
    if not constraints:
        return {}
    constraint_params = {}
    if len(kwargs) == 0:
        # get values from constraints without additional filters
        for constraint in constraints:
            for key in constraint.keys():
                if key in constraint_params:
                    constraint_params[key].update(constraint[key])
                else:
                    constraint_params[key] = set(constraint[key])
    else:
        # get values from constraints with additional filters
        constraint_params = _get_constraint_queryables_with_additional_params(
            constraints, kwargs, plugin, product_type
        )
    queryables = {}
    for key in constraint_params:
        queryables[key] = format_queryable(
            key, base, {"values": sorted(constraint_params[key])}
        )

    return _map_to_eodag_keys(queryables, plugin, product_type)


def _get_constraint_queryables_with_additional_params(
    constraints: list,
    params: Dict[str, Any],
    plugin: Union[Search, Api],
    product_type: str,
):
    constraint_matches = {}
    params_available = {k: False for k in params.keys()}
    # check which constraints match the given parameters
    eodag_provider_key_mapping = {}
    for i, constraint in enumerate(constraints):
        params_matched = {k: False for k in params.keys()}
        for param, value in params.items():
            provider_key = get_provider_queryable_key(
                param, constraint, plugin, product_type
            )
            eodag_provider_key_mapping[provider_key] = param
            if provider_key:
                params_available[param] = True
                if value in constraint[provider_key]:
                    params_matched[param] = True
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
                    queryables[key].update(constraints[num][key])
                elif key not in eodag_provider_key_mapping:
                    queryables[key] = set()

    # check if constraints matching params have been found
    if len(queryables) == 0:
        if len(params) > 1:
            raise NotAvailableError(
                f"combination of values {str(params)} is not possible"
            )
        else:
            raise NotAvailableError(
                f"value {list(params.values())[0]} not available for param {list(params.keys())[0]}"
            )

    return queryables


def _fetch_constraints(constraints_url: str, plugin: Union[Search, Api]) -> list:
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


def get_provider_queryable_key(
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
    :param product_type: product type for which the metadata shuld be used
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


def merge_default_queryables(
    default_queryables: Dict[str, Any], queryables: Dict[str, Any]
):
    """merges the given default queryables with the queryables fetched from the provider
    :param default_queryables: default queryables
    :type default_queryables: dict
    :param queryables: queryables fetched from the provider (queryables endpoint or constraints)
    :type queryables: dict
    """
    to_remove = []
    for queryable in queryables:
        if "TimeFromAscendingNode" in queryable:
            to_remove.append(queryable)
    for queryable_key in to_remove:
        queryables.pop(queryable_key)
    queryables.update(default_queryables)
