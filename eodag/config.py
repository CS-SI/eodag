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
from __future__ import annotations

import logging
import os
import tempfile
from inspect import isclass
from typing import (
    Any,
    Dict,
    ItemsView,
    Iterator,
    List,
    Literal,
    Optional,
    Tuple,
    TypedDict,
    Union,
    ValuesView,
    get_type_hints,
)

import orjson
import requests
import yaml
import yaml.constructor
import yaml.parser
from annotated_types import Gt
from jsonpath_ng import JSONPath
from pkg_resources import resource_filename
from requests.auth import AuthBase
from typing_extensions import Doc

from eodag.utils import (
    HTTP_REQ_TIMEOUT,
    USER_AGENT,
    Annotated,
    cached_yaml_load,
    cached_yaml_load_all,
    cast_scalar_value,
    deepcopy,
    dict_items_recursive_apply,
    merge_mappings,
    slugify,
    string_to_jsonpath,
    update_nested_dict,
    uri_to_path,
)
from eodag.utils.exceptions import ValidationError

logger = logging.getLogger("eodag.config")

EXT_PRODUCT_TYPES_CONF_URI = (
    "https://cs-si.github.io/eodag/eodag/resources/ext_product_types.json"
)


class SimpleYamlProxyConfig:
    """A simple configuration class acting as a proxy to an underlying dict object
    as returned by yaml.load"""

    def __init__(self, conf_file_path: str) -> None:
        try:
            self.source: Dict[str, Any] = cached_yaml_load(conf_file_path)
        except yaml.parser.ParserError as e:
            print("Unable to load user configuration file")
            raise e

    def __getitem__(self, item: Any) -> Any:
        return self.source[item]

    def __contains__(self, item: Any) -> Any:
        return item in self.source

    def __iter__(self) -> Iterator[str]:
        return iter(self.source)

    def items(self) -> ItemsView[str, Any]:
        """Iterate over keys and values of source"""
        return self.source.items()

    def values(self) -> ValuesView[Any]:
        """Iterate over values of source"""
        return self.source.values()

    def update(self, other: "SimpleYamlProxyConfig") -> None:
        """Update a :class:`~eodag.config.SimpleYamlProxyConfig`"""
        if not isinstance(other, self.__class__):
            raise ValueError("'{}' must be of type {}".format(other, self.__class__))
        self.source.update(other.source)


class ProviderConfig(yaml.YAMLObject):
    """Representation of eodag configuration.

    :param name: The name of the provider
    :type name: str
    :param priority: (optional) The priority of the provider while searching a product.
                     Lower value means lower priority. (Default: 0)
    :type priority: int
    :param api: (optional) The configuration of a plugin of type Api
    :type api: :class:`~eodag.config.PluginConfig`
    :param search: (optional) The configuration of a plugin of type Search
    :type search: :class:`~eodag.config.PluginConfig`
    :param products: (optional) The products types supported by the provider
    :type products: dict
    :param download: (optional) The configuration of a plugin of type Download
    :type download: :class:`~eodag.config.PluginConfig`
    :param auth: (optional) The configuration of a plugin of type Authentication
    :type auth: :class:`~eodag.config.PluginConfig`
    :param kwargs: Additional configuration variables for this provider
    :type kwargs: Any
    """

    name: str
    priority: int = 0  # Set default priority to 0
    api: PluginConfig
    search: PluginConfig
    products: Dict[str, Any]
    download: PluginConfig
    auth: PluginConfig
    product_types_fetched: bool  # set in core.update_product_types_list

    yaml_loader = yaml.Loader
    yaml_dumper = yaml.SafeDumper
    yaml_tag = "!provider"

    @classmethod
    def from_yaml(cls, loader: yaml.Loader, node: Any) -> ProviderConfig:
        """Build a :class:`~eodag.config.ProviderConfig` from Yaml"""
        cls.validate(tuple(node_key.value for node_key, _ in node.value))
        for node_key, node_value in node.value:
            if node_key.value == "name":
                node_value.value = slugify(node_value.value).replace("-", "_")
                break
        return loader.construct_yaml_object(node, cls)

    @classmethod
    def from_mapping(cls, mapping: Dict[str, Any]) -> ProviderConfig:
        """Build a :class:`~eodag.config.ProviderConfig` from a mapping"""
        cls.validate(mapping)
        for key in ("api", "search", "download", "auth"):
            if key in mapping:
                mapping[key] = PluginConfig.from_mapping(mapping[key])
        c = cls()
        c.__dict__.update(mapping)
        return c

    @staticmethod
    def validate(config_keys: Union[Tuple[str, ...], Dict[str, Any]]) -> None:
        """Validate a :class:`~eodag.config.ProviderConfig`

        :param config_keys: The configurations keys to validate
        :type config_keys: dict
        """
        if "name" not in config_keys:
            raise ValidationError("Provider config must have name key")
        if not any(k in config_keys for k in ("api", "search", "download", "auth")):
            raise ValidationError("A provider must implement at least one plugin")
        if "api" in config_keys and any(
            k in config_keys for k in ("search", "download", "auth")
        ):
            raise ValidationError(
                "A provider implementing an Api plugin must not implement any other "
                "type of plugin"
            )

    def update(self, mapping: Optional[Dict[str, Any]]) -> None:
        """Update the configuration parameters with values from `mapping`

        :param mapping: The mapping from which to override configuration parameters
        :type mapping: dict
        """
        if mapping is None:
            mapping = {}
        merge_mappings(
            self.__dict__,
            {
                key: value
                for key, value in mapping.items()
                if key not in ("name", "api", "search", "download", "auth")
                and value is not None
            },
        )
        for key in ("api", "search", "download", "auth"):
            current_value: Optional[Dict[str, Any]] = getattr(self, key, None)
            mapping_value = mapping.get(key, {})
            if current_value is not None:
                current_value.update(mapping_value)
            elif mapping_value:
                setattr(self, key, PluginConfig.from_mapping(mapping_value))


class PluginConfig(yaml.YAMLObject):
    """Representation of a plugin config

    :param name: The name of the plugin class to use to instantiate the plugin object
    :type name: str
    :param metadata_mapping: (optional) The mapping between eodag metadata and
                                  the plugin specific metadata
    :type metadata_mapping: dict
    :param free_params: (optional) Additional configuration parameters
    :type free_params: dict
    """

    class Pagination(TypedDict):
        """Search pagination configuration"""

        max_items_per_page: int
        total_items_nb_key_path: Union[str, JSONPath]
        next_page_url_key_path: Union[str, JSONPath]
        next_page_query_obj_key_path: Union[str, JSONPath]
        next_page_merge_key_path: Union[str, JSONPath]
        next_page_url_tpl: str
        next_page_query_obj: str
        count_endpoint: str
        start_page: int

    class Sort(TypedDict):
        """Configuration for sort during search"""

        sort_by_default: List[Tuple[str, str]]
        sort_by_tpl: str
        sort_param_mapping: Dict[str, str]
        sort_order_mapping: Dict[Literal["ascending", "descending"], str]
        max_sort_params: Annotated[int, Gt(0)]

    class OrderOnResponse(TypedDict):
        """Configuration for order on-response during download"""

        metadata_mapping: Dict[str, Union[str, List[str]]]

    class OrderStatusSuccess(TypedDict):
        """
        Configuration to identify order status success during download

        Order status response matching the following parameters are considered success
        At least one is required
        """

        status: Annotated[str, Doc("Variable in the order status response json body")]
        message: Annotated[str, Doc("Variable in the order status response json body")]
        http_code: Annotated[int, Doc("HTTP code of the order status response")]

    class OrderStatusOrdered(TypedDict):
        """
        Configuration to identify order status ordered during download
        """

        http_code: Annotated[int, Doc("HTTP code of the order status response")]

    class OrderStatusRequest(TypedDict):
        """
        Order status request configuration
        """

        method: Annotated[str, Doc("Request HTTP method")]
        headers: Annotated[Dict[str, Any], Doc("Request hearders")]

    class OrderStatusOnSuccess(TypedDict):
        """Configuration for order status on-success during download"""

        need_search: Annotated[bool, Doc("If a new search is needed on success")]
        result_type: str
        results_entry: str
        metadata_mapping: Dict[str, Union[str, List[str]]]

    class OrderStatus(TypedDict):
        """Configuration for order status during download"""

        request: PluginConfig.OrderStatusRequest
        metadata_mapping: Annotated[
            Dict[str, Union[str, List[str]]],
            Doc("Metadata-mapping used to parse order status response"),
        ]
        success: PluginConfig.OrderStatusSuccess
        error: Annotated[
            Dict[str, Any],
            Doc("Part of the order status response that tells there is an error"),
        ]
        ordered: PluginConfig.OrderStatusOrdered
        on_success: PluginConfig.OrderStatusOnSuccess

    name: str
    type: str

    # search & api ---------------------------------------------------------------------
    priority: int  # copied from ProviderConfig in PluginManager.get_search_plugins()
    products: Dict[
        str, Any
    ]  # copied from ProviderConfig in PluginManager.get_search_plugins()
    product_type_config: Dict[str, Any]  # set in core._prepare_search
    auth: Union[AuthBase, Dict[str, str]]  # set in core._do_search
    api_endpoint: str
    need_auth: bool
    result_type: str
    results_entry: str
    pagination: PluginConfig.Pagination
    sort: PluginConfig.Sort
    query_params_key: str
    discover_metadata: Dict[str, str]
    discover_product_types: Dict[str, Any]
    discover_queryables: Dict[str, Any]
    metadata_mapping: Dict[str, Union[str, List[str]]]
    free_params: Dict[Any, Any]
    free_text_search_operations: Dict[str, Any]  # ODataV4Search
    metadata_pre_mapping: Dict[str, Any]  # ODataV4Search
    data_request_url: str  # DataRequestSearch
    status_url: str  # DataRequestSearch
    result_url: str  # DataRequestSearch
    search_definition: Dict[str, Any]  # CSWSearch
    merge_responses: bool  # PostJsonSearch for aws_eos
    collection: bool  # PostJsonSearch for aws_eos
    max_connections: int  # StaticStacSearch
    timeout: float  # StaticStacSearch
    s3_bucket: str  # CreodiasS3Search
    end_date_excluded: bool  # BuildSearchResult
    ssl_verify: bool

    # download -------------------------------------------------------------------------
    base_uri: str
    outputs_prefix: str
    extract: bool
    outputs_extension: str
    order_enabled: bool  # HTTPDownload
    order_method: str  # HTTPDownload
    order_headers: Dict[str, str]  # HTTPDownload
    order_on_response: PluginConfig.OrderOnResponse
    order_status: PluginConfig.OrderStatus
    bucket_path_level: int  # S3RestDownload
    requester_pays: bool  # AwsDownload
    flatten_top_dirs: bool

    # auth -----------------------------------------------------------------------------
    credentials: Dict[str, str]
    auth_uri: str
    auth_base_uri: str
    auth_error_code: int
    headers: Dict[str, str]
    token_provision: str  # KeycloakOIDCPasswordAuth
    client_id: str  # KeycloakOIDCPasswordAuth
    client_secret: str  # KeycloakOIDCPasswordAuth
    realm: str  # KeycloakOIDCPasswordAuth
    user_consent_needed: str  # OIDCAuthorizationCodeFlowAuth
    authentication_uri_source: str  # OIDCAuthorizationCodeFlowAuth
    redirect_uri: str  # OIDCAuthorizationCodeFlowAuth
    authorization_uri: str  # OIDCAuthorizationCodeFlowAuth
    login_form_xpath: str  # OIDCAuthorizationCodeFlowAuth
    user_consent_form_xpath: str  # OIDCAuthorizationCodeFlowAuth
    user_consent_form_data: Dict[str, str]  # OIDCAuthorizationCodeFlowAuth
    token_exchange_post_data_method: str  # OIDCAuthorizationCodeFlowAuth
    token_uri: str  # OIDCAuthorizationCodeFlowAuth
    token_key: str  # OIDCAuthorizationCodeFlowAuth
    signed_url_key: str  # SASAuth
    refresh_uri: str  # TokenAuth
    refresh_token_key: str  # TokenAuth

    yaml_loader = yaml.Loader
    yaml_dumper = yaml.SafeDumper
    yaml_tag = "!plugin"

    @classmethod
    def from_yaml(cls, loader: yaml.Loader, node: Any) -> PluginConfig:
        """Build a :class:`~eodag.config.PluginConfig` from Yaml"""
        cls.validate(tuple(node_key.value for node_key, _ in node.value))
        return loader.construct_yaml_object(node, cls)

    @classmethod
    def from_mapping(cls, mapping: Dict[str, Any]) -> PluginConfig:
        """Build a :class:`~eodag.config.PluginConfig` from a mapping"""
        c = cls()
        c.__dict__.update(mapping)
        return c

    @staticmethod
    def validate(config_keys: Tuple[Any, ...]) -> None:
        """Validate a :class:`~eodag.config.PluginConfig`"""
        if "type" not in config_keys:
            raise ValidationError(
                "A Plugin config must specify the Plugin it configures"
            )

    def update(self, mapping: Optional[Dict[Any, Any]]) -> None:
        """Update the configuration parameters with values from `mapping`

        :param mapping: The mapping from which to override configuration parameters
        :type mapping: dict
        """
        if mapping is None:
            mapping = {}
        merge_mappings(
            self.__dict__, {k: v for k, v in mapping.items() if v is not None}
        )


def load_default_config() -> Dict[str, ProviderConfig]:
    """Load the providers configuration into a dictionnary.

    Load from eodag `resources/providers.yml` or `EODAG_PROVIDERS_CFG_FILE` environment
    variable if exists.

    :returns: The default provider's configuration
    :rtype: dict
    """
    eodag_providers_cfg_file = os.getenv(
        "EODAG_PROVIDERS_CFG_FILE"
    ) or resource_filename("eodag", "resources/providers.yml")
    return load_config(eodag_providers_cfg_file)


def load_config(config_path: str) -> Dict[str, ProviderConfig]:
    """Load the providers configuration into a dictionnary from a given file

    :param config_path: The path to the provider config file
    :type config_path: str
    :returns: The default provider's configuration
    :rtype: dict
    """
    logger.debug(f"Loading configuration from {config_path}")
    config: Dict[str, ProviderConfig] = {}
    try:
        # Providers configs are stored in this file as separated yaml documents
        # Load all of it
        providers_configs: List[ProviderConfig] = cached_yaml_load_all(config_path)
    except yaml.parser.ParserError as e:
        logger.error("Unable to load configuration")
        raise e
    stac_provider_config = load_stac_provider_config()
    for provider_config in providers_configs:
        # for provider_config in copy.deepcopy(providers_configs):
        provider_config_init(provider_config, stac_provider_config)
        config[provider_config.name] = provider_config
    return config


def provider_config_init(
    provider_config: ProviderConfig,
    stac_search_default_conf: Optional[Dict[str, Any]] = None,
) -> None:
    """Applies some default values to provider config

    :param provider_config: An eodag provider configuration
    :type provider_config: :class:`~eodag.config.ProviderConfig`
    :param stac_search_default_conf: default conf to overwrite with provider_config if STAC
    :type stac_search_default_conf: dict
    """
    # For the provider, set the default outputs_prefix of its download plugin
    # as tempdir in a portable way
    for param_name in ("download", "api"):
        if param_name in vars(provider_config):
            param_value = getattr(provider_config, param_name)
            if not getattr(param_value, "outputs_prefix", None):
                param_value.outputs_prefix = tempfile.gettempdir()
            if not getattr(param_value, "delete_archive", None):
                param_value.delete_archive = True

    try:
        if (
            stac_search_default_conf is not None
            and provider_config.search
            and provider_config.search.type
            in [
                "StacSearch",
                "StaticStacSearch",
            ]
        ):
            # search config set to stac defaults overriden with provider config
            per_provider_stac_provider_config = deepcopy(stac_search_default_conf)
            provider_config.search.__dict__ = update_nested_dict(
                per_provider_stac_provider_config["search"],
                provider_config.search.__dict__,
                allow_empty_values=True,
            )
    except AttributeError:
        pass


def override_config_from_file(config: Dict[str, Any], file_path: str) -> None:
    """Override a configuration with the values in a file

    :param config: An eodag providers configuration dictionary
    :type config: dict
    :param file_path: The path to the file from where the new values will be read
    :type file_path: str
    """
    logger.info("Loading user configuration from: %s", os.path.abspath(file_path))
    with open(os.path.abspath(os.path.realpath(file_path)), "r") as fh:
        try:
            config_in_file = yaml.safe_load(fh)
            if config_in_file is None:
                return
        except yaml.parser.ParserError as e:
            logger.error("Unable to load user configuration file")
            raise e
    override_config_from_mapping(config, config_in_file)


def override_config_from_env(config: Dict[str, Any]) -> None:
    """Override a configuration with environment variables values

    :param config: An eodag providers configuration dictionary
    :type config: dict
    """

    def build_mapping_from_env(
        env_var: str, env_value: str, mapping: Dict[str, Any]
    ) -> None:
        """Recursively build a dictionary from an environment variable.

        The environment variable must respect the pattern: KEY1__KEY2__[...]__KEYN.
        It will be transformed to::

            {
                "key1": {
                    "key2": {
                        {...}
                    }
                }
            }

        :param env_var: The environment variable to be transformed into a dictionary
        :type env_var: str
        :param env_value: The value from environment variable
        :type env_value: str
        :param mapping: The mapping in which the value will be created
        :type mapping: dict
        """
        parts = env_var.split("__")
        iter_parts = iter(parts)
        env_type = get_type_hints(PluginConfig).get(next(iter_parts, ""), str)
        child_env_type = (
            get_type_hints(env_type).get(next(iter_parts, ""), None)
            if isclass(env_type)
            else None
        )
        if len(parts) == 2 and child_env_type:
            # for nested config (pagination, ...)
            # try converting env_value type from type hints
            try:
                env_value = cast_scalar_value(env_value, child_env_type)
            except TypeError:
                logger.warning(
                    f"Could not convert {parts} value {env_value} to {child_env_type}"
                )
            mapping.setdefault(parts[0], {})
            mapping[parts[0]][parts[1]] = env_value
        elif len(parts) == 1:
            # try converting env_value type from type hints
            try:
                env_value = cast_scalar_value(env_value, env_type)
            except TypeError:
                logger.warning(
                    f"Could not convert {parts[0]} value {env_value} to {env_type}"
                )
            mapping[parts[0]] = env_value
        else:
            new_map = mapping.setdefault(parts[0], {})
            build_mapping_from_env("__".join(parts[1:]), env_value, new_map)

    mapping_from_env: Dict[str, Any] = {}
    for env_var in os.environ:
        if env_var.startswith("EODAG__"):
            build_mapping_from_env(
                env_var[len("EODAG__") :].lower(),  # noqa
                os.environ[env_var],
                mapping_from_env,
            )

    override_config_from_mapping(config, mapping_from_env)


def override_config_from_mapping(
    config: Dict[str, Any], mapping: Dict[str, Any]
) -> None:
    """Override a configuration with the values in a mapping

    :param config: An eodag providers configuration dictionary
    :type config: dict
    :param mapping: The mapping containing the values to be overriden
    :type mapping: dict
    """
    for provider, new_conf in mapping.items():
        old_conf: Optional[Dict[str, Any]] = config.get(provider)
        if old_conf is not None:
            old_conf.update(new_conf)
        else:
            logger.info(
                "%s: unknown provider found in user conf, trying to use provided configuration",
                provider,
            )
            try:
                new_conf["name"] = new_conf.get("name", provider)
                config[provider] = ProviderConfig.from_mapping(new_conf)
            except Exception:
                logger.warning(
                    "%s skipped: could not be loaded from user configuration", provider
                )

                import traceback as tb

                logger.debug(tb.format_exc())


def merge_configs(config: Dict[str, Any], other_config: Dict[str, Any]) -> None:
    """Override a configuration with the values of another configuration

    :param config: An eodag providers configuration dictionary
    :type config: dict
    :param other_config: An eodag providers configuration dictionary
    :type other_config: dict
    """
    # configs union with other_config values as default
    other_config = dict(config, **other_config)

    for provider, new_conf in other_config.items():
        old_conf = config.get(provider, None)

        if old_conf:
            # update non-objects values
            new_conf = dict(old_conf.__dict__, **new_conf.__dict__)

            for conf_k, conf_v in new_conf.items():
                old_conf_v = getattr(old_conf, conf_k, None)

                if isinstance(conf_v, PluginConfig) and isinstance(
                    old_conf_v, PluginConfig
                ):
                    old_conf_v.update(conf_v.__dict__)
                    new_conf[conf_k] = old_conf_v
                elif isinstance(old_conf_v, PluginConfig):
                    new_conf[conf_k] = old_conf_v

                setattr(config[provider], conf_k, new_conf[conf_k])
        else:
            config[provider] = new_conf


def load_yml_config(yml_path: str) -> Dict[Any, Any]:
    """Load a conf dictionnary from given yml absolute path

    :returns: The yml configuration file
    :rtype: dict
    """
    config = SimpleYamlProxyConfig(yml_path)
    return dict_items_recursive_apply(config.source, string_to_jsonpath)


def load_stac_config() -> Dict[str, Any]:
    """Load the stac configuration into a dictionnary

    :returns: The stac configuration
    :rtype: dict
    """
    return load_yml_config(
        resource_filename("eodag", os.path.join("resources/", "stac.yml"))
    )


def load_stac_api_config() -> Dict[str, Any]:
    """Load the stac API configuration into a dictionnary

    :returns: The stac API configuration
    :rtype: dict
    """
    return load_yml_config(
        resource_filename("eodag", os.path.join("resources/", "stac_api.yml"))
    )


def load_stac_provider_config() -> Dict[str, Any]:
    """Load the stac provider configuration into a dictionnary

    :returns: The stac provider configuration
    :rtype: dict
    """
    return SimpleYamlProxyConfig(
        resource_filename("eodag", os.path.join("resources/", "stac_provider.yml"))
    ).source


def get_ext_product_types_conf(
    conf_uri: str = EXT_PRODUCT_TYPES_CONF_URI,
) -> Dict[str, Any]:
    """Read external product types conf

    :param conf_uri: URI to local or remote configuration file
    :type conf_uri: str
    :returns: The external product types configuration
    :rtype: dict
    """
    logger.info("Fetching external product types from %s", conf_uri)
    if conf_uri.lower().startswith("http"):
        # read from remote
        try:
            response = requests.get(
                conf_uri, headers=USER_AGENT, timeout=HTTP_REQ_TIMEOUT
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.debug(e)
            logger.warning(
                "Could not read remote external product types conf from %s", conf_uri
            )
            return {}
    elif conf_uri.lower().startswith("file"):
        conf_uri = uri_to_path(conf_uri)

    # read from local
    try:
        with open(conf_uri, "rb") as f:
            return orjson.loads(f.read())
    except (orjson.JSONDecodeError, FileNotFoundError) as e:
        logger.debug(e)
        logger.warning(
            "Could not read local external product types conf from %s", conf_uri
        )
        return {}
