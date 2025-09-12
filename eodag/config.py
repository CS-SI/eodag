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
from typing import TYPE_CHECKING

import orjson
import requests
import yaml
import yaml.parser

from eodag.utils import (
    HTTP_REQ_TIMEOUT,
    USER_AGENT,
    cached_yaml_load,
    cached_yaml_load_all,
    dict_items_recursive_apply,
    string_to_jsonpath,
    uri_to_path,
)

if TYPE_CHECKING:
    from typing import Any, ItemsView, Iterator, ValuesView

    from eodag.api.provider import ProviderConfig

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


def load_default_config() -> dict[str, ProviderConfig]:
    """Load the providers configuration into a dictionary.

    Load from eodag `resources/providers.yml` or `EODAG_PROVIDERS_CFG_FILE` environment
    variable if exists.

    :returns: The default provider's configuration
    """
    eodag_providers_cfg_file = os.getenv("EODAG_PROVIDERS_CFG_FILE") or str(
        res_files("eodag") / "resources" / "providers.yml"
    )

    return load_config(eodag_providers_cfg_file)


def load_config(config_path: str) -> dict[str, ProviderConfig]:
    """Load the providers configuration into a dictionary from a given file

    If EODAG_PROVIDERS_WHITELIST is set, only load listed providers.

    :param config_path: The path to the provider config file
    :returns: The default provider's configuration
    """
    logger.debug("Loading configuration from %s", config_path)

    try:
        # Providers configs are stored in this file as separated yaml documents
        # Load all of it
        providers_configs: list[ProviderConfig] = cached_yaml_load_all(config_path)
    except yaml.parser.ParserError as e:
        logger.error("Unable to load configuration")
        raise e

    return {p.name: p for p in providers_configs if p is not None}


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
