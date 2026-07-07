# -*- coding: utf-8 -*-
# Copyright 2026, CS GROUP - France, https://www.csgroup.eu/
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

import functools
import os
import warnings
from copy import deepcopy as copy_deepcopy
from typing import Any

import yaml


class LegacyAwareLoader(yaml.CSafeLoader):
    """YAML loader that accepts legacy EODAG tags (!provider, !plugin, !!python/tuple)
    and converts them to safe Python objects. Uses CSafeLoader for performance."""


# Constructor for !provider tag - reuse legacy deserialization logic
# from ProviderConfig and keep deprecation warnings.
def provider_constructor(loader, node):
    if isinstance(node, yaml.MappingNode):
        from eodag.api.provider import ProviderConfig

        warnings.warn(
            "Usage of deprecated YAML tag '!provider' for provider configuration "
            "(Please use plain YAML mappings instead)"
            " -- Deprecated since v4.5.0",
            FutureWarning,
            stacklevel=2,
        )
        return ProviderConfig.from_yaml(loader, node)
    return None


# Constructor for !plugin tag - reuse legacy deserialization logic.
def plugin_constructor(loader, node):
    if isinstance(node, yaml.MappingNode):
        from eodag.config import PluginConfig

        warnings.warn(
            "Usage of deprecated YAML tag '!plugin' for plugin configuration "
            "(Please use plain YAML mappings instead)"
            " -- Deprecated since v4.5.0",
            FutureWarning,
            stacklevel=2,
        )
        return PluginConfig.from_yaml(loader, node)
    return None


# Constructor for !!python/tuple tag - convert to tuple.
def python_tuple_constructor(loader, node):
    if isinstance(node, yaml.SequenceNode):
        return tuple(loader.construct_sequence(node))
    elif isinstance(node, yaml.ScalarNode):
        return (loader.construct_scalar(node),)
    return None


# Register constructors for legacy tags.
LegacyAwareLoader.add_constructor("!provider", provider_constructor)
LegacyAwareLoader.add_constructor("!plugin", plugin_constructor)
LegacyAwareLoader.add_constructor(
    "tag:yaml.org,2002:python/tuple", python_tuple_constructor
)


@functools.lru_cache()
def _mutable_cached_yaml_load(config_path: str) -> Any:
    with open(
        os.path.abspath(os.path.realpath(config_path)), mode="r", encoding="utf-8"
    ) as fh:
        return yaml.load(fh, Loader=LegacyAwareLoader)


def cached_yaml_load(config_path: str) -> dict[str, Any]:
    """Cached :func:`yaml.load`

    :param config_path: path to the yaml configuration file
    :returns: loaded yaml configuration
    """
    return copy_deepcopy(_mutable_cached_yaml_load(config_path))


@functools.lru_cache()
def _mutable_cached_yaml_load_all(config_path: str) -> list[Any]:
    with open(config_path, "r") as fh:
        return list(yaml.load_all(fh, Loader=LegacyAwareLoader))


def cached_yaml_load_all(config_path: str) -> list[Any]:
    """Cached :func:`yaml.load_all`

    Load all configurations stored in the configuration file as separated yaml documents

    :param config_path: path to the yaml configuration file
    :returns: list of configurations
    """
    return copy_deepcopy(_mutable_cached_yaml_load_all(config_path))


__all__ = [
    "LegacyAwareLoader",
    "cached_yaml_load",
    "cached_yaml_load_all",
]
