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
from importlib.resources import files as res_files
from inspect import isclass
from typing import Any, ItemsView, Iterator, Optional, ValuesView, get_type_hints

import orjson
import requests
import yaml
import yaml.parser

from eodag.api.plugin import PluginConfig
from eodag.api.product.metadata_mapping import mtd_cfg_as_conversion_and_querypath
from eodag.api.provider import (
    Provider,
    ProviderConfig,
    ProvidersDict,
    provider_config_init,
)
from eodag.utils import (
    HTTP_REQ_TIMEOUT,
    USER_AGENT,
    cached_yaml_load,
    cached_yaml_load_all,
    cast_scalar_value,
    deepcopy,
    dict_items_recursive_apply,
    string_to_jsonpath,
    uri_to_path,
)

logger = logging.getLogger("eodag.config")

EXT_COLLECTIONS_CONF_URI = (
    "https://cs-si.github.io/eodag/eodag/resources/ext_collections.json"
)
AUTH_TOPIC_KEYS = ("auth", "search_auth", "download_auth")
PLUGINS_TOPICS_KEYS = ("api", "search", "download") + AUTH_TOPIC_KEYS


class SimpleYamlProxyConfig:
    """A simple configuration class acting as a proxy to an underlying dict object
    as returned by yaml.load"""

    def __init__(self, conf_file_path: str) -> None:
        try:
            self.source: dict[str, Any] = cached_yaml_load(conf_file_path)
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


def load_default_config() -> ProvidersDict:
    """Load the providers configuration into a dictionary.

    Load from eodag `resources/providers.yml` or `EODAG_PROVIDERS_CFG_FILE` environment
    variable if exists.

    :returns: The default provider's configuration
    """
    eodag_providers_cfg_file = os.getenv("EODAG_PROVIDERS_CFG_FILE") or str(
        res_files("eodag") / "resources" / "providers.yml"
    )

    return load_config(eodag_providers_cfg_file)


def load_config(config_path: str) -> ProvidersDict:
    """Load the providers configuration into a dictionary from a given file

    If EODAG_PROVIDERS_WHITELIST is set, only load listed providers.

    :param config_path: The path to the provider config file
    :returns: The default provider's configuration
    """
    logger.debug("Loading configuration from %s", config_path)
    providers = ProvidersDict(providers=None)

    try:
        # Providers configs are stored in this file as separated yaml documents
        # Load all of it
        providers_configs: list[ProviderConfig] = cached_yaml_load_all(config_path)
    except yaml.parser.ParserError as e:
        logger.error("Unable to load configuration")
        raise e

    stac_provider_config = load_stac_provider_config()

    whitelist_env = os.getenv("EODAG_PROVIDERS_WHITELIST")
    whitelist = None
    if whitelist_env:
        whitelist = {provider for provider in whitelist_env.split(",")}
        logger.info("Using providers whitelist: %s", ", ".join(whitelist))

    for provider_config in providers_configs:
        provider_whitelisted = provider_config.name in whitelist if whitelist else True
        if provider_config is None or not provider_whitelisted:
            continue

        provider_config_init(provider_config, stac_provider_config)
        providers.add(Provider(provider_config.name, provider_config))

    return providers


def override_config_from_file(
    config: dict[str, ProviderConfig], file_path: str
) -> None:
    """Override a configuration with the values in a file

    :param config: An eodag providers configuration dictionary
    :param file_path: The path to the file from where the new values will be read
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


def override_config_from_env(config: dict[str, ProviderConfig]) -> None:
    """Override a configuration with environment variables values

    :param config: An eodag providers configuration dictionary
    """

    def build_mapping_from_env(
        env_var: str, env_value: str, mapping: dict[str, Any]
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
        :param env_value: The value from environment variable
        :param mapping: The mapping in which the value will be created
        """
        parts = env_var.split("__")
        iter_parts = iter(parts)
        env_type = get_type_hints(PluginConfig).get(next(iter_parts, ""), str)
        child_env_type = (
            get_type_hints(env_type).get(next(iter_parts, ""))
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

    mapping_from_env: dict[str, Any] = {}
    for env_var in os.environ:
        if env_var.startswith("EODAG__"):
            build_mapping_from_env(
                env_var[len("EODAG__") :].lower(),  # noqa
                os.environ[env_var],
                mapping_from_env,
            )

    override_config_from_mapping(config, mapping_from_env)


def override_config_from_mapping(
    config: dict[str, ProviderConfig], mapping: dict[str, Any]
) -> None:
    """Override a configuration with the values in a mapping.

    If the environment variable ``EODAG_PROVIDERS_WHITELIST`` is set (as a comma-separated list of provider names),
    only the listed providers will be used from the mapping. All other providers in the mapping will be ignored.

    :param config: An eodag providers configuration dictionary
    :param mapping: The mapping containing the values to be overriden
    """
    whitelist_env = os.getenv("EODAG_PROVIDERS_WHITELIST")
    whitelist = None
    if whitelist_env:
        whitelist = {provider for provider in whitelist_env.split(",")}

    for provider, new_conf in mapping.items():
        # check if metada-mapping as already been built as jsonpath in providers_config
        # or provider not in whitelist
        if not isinstance(new_conf, dict) or (whitelist and provider not in whitelist):
            continue
        new_conf_search = new_conf.get("search", {}) or {}
        new_conf_api = new_conf.get("api", {}) or {}
        if provider in config and "metadata_mapping" in {
            **new_conf_search,
            **new_conf_api,
        }:
            search_plugin_key = (
                "search" if "metadata_mapping" in new_conf_search else "api"
            )
            # get some already configured value
            configured_metadata_mapping = getattr(
                config[provider], search_plugin_key
            ).metadata_mapping
            some_configured_value = next(iter(configured_metadata_mapping.values()))
            # check if the configured value has already been built as jsonpath
            if (
                isinstance(some_configured_value, list)
                and isinstance(some_configured_value[1], tuple)
                or isinstance(some_configured_value, tuple)
            ):
                # also build as jsonpath the incoming conf
                mtd_cfg_as_conversion_and_querypath(
                    deepcopy(mapping[provider][search_plugin_key]["metadata_mapping"]),
                    mapping[provider][search_plugin_key]["metadata_mapping"],
                )

        # try overriding conf
        old_conf: Optional[ProviderConfig] = config.get(provider)
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


def merge_configs(config: dict[str, Any], other_config: dict[str, Any]) -> None:
    """Override a configuration with the values of another configuration

    :param config: An eodag providers configuration dictionary
    :param other_config: An eodag providers configuration dictionary
    """
    # configs union with other_config values as default
    other_config = dict(config, **other_config)

    for provider, new_conf in other_config.items():
        old_conf = config.get(provider)

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


def load_yml_config(yml_path: str) -> dict[Any, Any]:
    """Load a conf dictionary from given yml absolute path

    :returns: The yml configuration file
    """
    config = SimpleYamlProxyConfig(yml_path)
    return dict_items_recursive_apply(config.source, string_to_jsonpath)


def load_stac_config() -> dict[str, Any]:
    """Load the stac configuration into a dictionary

    :returns: The stac configuration
    """
    return load_yml_config(str(res_files("eodag") / "resources" / "stac.yml"))


def load_stac_api_config() -> dict[str, Any]:
    """Load the stac API configuration into a dictionary

    :returns: The stac API configuration
    """
    return load_yml_config(str(res_files("eodag") / "resources" / "stac_api.yml"))


def load_stac_provider_config() -> dict[str, Any]:
    """Load the stac provider configuration into a dictionary

    :returns: The stac provider configuration
    """
    return SimpleYamlProxyConfig(
        str(res_files("eodag") / "resources" / "stac_provider.yml")
    ).source


def get_ext_collections_conf(
    conf_uri: str = EXT_COLLECTIONS_CONF_URI,
) -> dict[str, Any]:
    """Read external collections conf

    :param conf_uri: URI to local or remote configuration file
    :returns: The external collections configuration
    """
    logger.info("Fetching external collections from %s", conf_uri)
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
                "Could not read remote external collections conf from %s", conf_uri
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
            "Could not read local external collections conf from %s", conf_uri
        )
        return {}
