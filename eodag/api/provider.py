# -*- coding: utf-8 -*-
# Copyright 2025, CS GROUP - France, https://www.csgroup.eu/
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
import traceback
from collections import UserDict
from dataclasses import dataclass, field
from inspect import isclass
from typing import TYPE_CHECKING, Any, Iterator, Optional, Union, get_type_hints

import yaml

from eodag.api.collection import Collection
from eodag.api.plugin import PluginConfig, credentials_in_auth
from eodag.api.product.metadata_mapping import (
    NOT_AVAILABLE,
    mtd_cfg_as_conversion_and_querypath,
)
from eodag.config import load_stac_provider_config
from eodag.utils import (
    GENERIC_COLLECTION,
    STAC_SEARCH_PLUGINS,
    cast_scalar_value,
    deepcopy,
    merge_mappings,
    slugify,
    update_nested_dict,
)
from eodag.utils.exceptions import (
    UnsupportedProductType,
    UnsupportedProvider,
    ValidationError,
)
from eodag.utils.repr import dict_to_html_table

if TYPE_CHECKING:
    from eodag.api.core import EODataAccessGateway
    from typing_extensions import Self

logger = logging.getLogger("eodag.provider")

AUTH_TOPIC_KEYS = ("auth", "search_auth", "download_auth")
PLUGINS_TOPICS_KEYS = ("api", "search", "download") + AUTH_TOPIC_KEYS


class ProviderConfig(yaml.YAMLObject):
    """Representation of eodag configuration.

    :param name: The name of the provider
    :param priority: (optional) The priority of the provider while searching a product.
                     Lower value means lower priority. (Default: 0)
    :param roles: The roles of the provider (e.g. "host", "producer", "licensor", "processor")
    :param description: (optional) A short description of the provider
    :param url: URL to the webpage representing the provider
    :param api: (optional) The configuration of a plugin of type Api
    :param search: (optional) The configuration of a plugin of type Search
    :param products: (optional) The products types supported by the provider
    :param download: (optional) The configuration of a plugin of type Download
    :param auth: (optional) The configuration of a plugin of type Authentication
    :param search_auth: (optional) The configuration of a plugin of type Authentication for search
    :param download_auth: (optional) The configuration of a plugin of type Authentication for download
    :param kwargs: Additional configuration variables for this provider
    """

    name: str
    group: str
    priority: int = 0  # Set default priority to 0
    roles: list[str]
    description: str
    url: str
    api: PluginConfig
    search: PluginConfig
    products: dict[str, Any]
    download: PluginConfig
    auth: PluginConfig
    search_auth: PluginConfig
    download_auth: PluginConfig

    yaml_loader = yaml.Loader
    yaml_dumper = yaml.SafeDumper
    yaml_tag = "!provider"

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Apply defaults when building from yaml."""
        self.__dict__.update(state)
        self._apply_defaults()

    def __or__(self, other: Self | dict[str, Any]) -> Self:
        """Merge ProviderConfig with another ProviderConfig or a dict using | operator"""
        new_conf = deepcopy(self)
        new_conf.update(other)
        return new_conf

    def __ior__(self, other: Self | dict[str, Any]) -> Self:
        """In-place merge of ProviderConfig with another ProviderConfig or a dict using |= operator"""
        self.update(other)
        return self

    def __contains__(self, key):
        """Check if a key is in the ProviderConfig."""
        return key in self.__dict__

    @classmethod
    def from_yaml(cls, loader: yaml.Loader, node: Any) -> Iterator[Self]:
        """Build a :class:`~eodag.config.ProviderConfig` from Yaml"""
        cls.validate(tuple(node_key.value for node_key, _ in node.value))
        for node_key, node_value in node.value:
            if node_key.value == "name":
                node_value.value = slugify(node_value.value).replace("-", "_")
                break
        return loader.construct_yaml_object(node, cls)

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> Self:
        """Build a :class:`~eodag.config.ProviderConfig` from a mapping"""
        cls.validate(mapping)
        for key in PLUGINS_TOPICS_KEYS:
            if _mapping := mapping.get(key):
                mapping[key] = PluginConfig.from_mapping(_mapping)
        c = cls()
        c.__dict__.update(mapping)
        c._apply_defaults()
        return c

    @staticmethod
    def validate(config_keys: Union[tuple[str, ...], dict[str, Any]]) -> None:
        """Validate a :class:`~eodag.config.ProviderConfig`

        :param config_keys: The configurations keys to validate
        """
        if "name" not in config_keys:
            raise ValidationError("Provider config must have name key")
        if not any(k in config_keys for k in PLUGINS_TOPICS_KEYS):
            raise ValidationError("A provider must implement at least one plugin")
        non_api_keys = [k for k in PLUGINS_TOPICS_KEYS if k != "api"]
        if "api" in config_keys and any(k in config_keys for k in non_api_keys):
            raise ValidationError(
                "A provider implementing an Api plugin must not implement any other "
                "type of plugin"
            )

    def update(self, config: Self | dict[str, Any]) -> None:
        """Update the configuration parameters with values from `mapping`

        :param config: The config from which to override configuration parameters
        """
        source = config if isinstance(config, dict) else config.__dict__

        merge_mappings(
            self.__dict__,
            {
                key: value
                for key, value in source.items()
                if key not in PLUGINS_TOPICS_KEYS and value is not None
            },
        )
        for key in PLUGINS_TOPICS_KEYS:
            current_value: Optional[PluginConfig] = getattr(self, key, None)
            config_value = source.get(key, {})
            if current_value is not None:
                current_value |= config_value
            elif isinstance(config_value, PluginConfig):
                setattr(self, key, config_value)
            elif config_value:
                try:
                    setattr(self, key, PluginConfig.from_mapping(config_value))
                except ValidationError as e:
                    logger.warning(
                        (
                            "Could not add %s Plugin config to %s configuration: %s. "
                            "Try updating existing %s Plugin configs instead."
                        ),
                        key,
                        self.name,
                        str(e),
                        ", ".join([k for k in PLUGINS_TOPICS_KEYS if hasattr(self, k)]),
                    )
        self._apply_defaults()

    def _apply_defaults(self: Self) -> None:
        """Applies some default values to provider config."""
        stac_search_default_conf = load_stac_provider_config()

        # For the provider, set the default output_dir of its download plugin
        # as tempdir in a portable way
        for download_topic_key in ("download", "api"):
            if download_topic_key in vars(self):
                download_conf = getattr(self, download_topic_key)
                if not getattr(download_conf, "output_dir", None):
                    download_conf.output_dir = tempfile.gettempdir()
                if not getattr(download_conf, "delete_archive", None):
                    download_conf.delete_archive = True

        try:
            if (
                stac_search_default_conf is not None
                and self.search
                and self.search.type in STAC_SEARCH_PLUGINS
            ):
                # search config set to stac defaults overriden with provider config
                per_provider_stac_provider_config = deepcopy(stac_search_default_conf)
                self.search.__dict__ = update_nested_dict(
                    per_provider_stac_provider_config["search"],
                    self.search.__dict__,
                    allow_empty_values=True,
                )
        except AttributeError:
            pass


@dataclass
class Provider:
    """
    Represents a data provider with its configuration and utility methods.

    :param name: Name of the provider.
    :param collections_fetched: Flag indicating whether product types have been fetched.
    """

    _config: ProviderConfig
    name: Optional[str] = field(default=None)
    collections_fetched: bool = False  # set in core.update_collections_list

    def __post_init__(self):
        """Post-initialization to set the provider name if not provided."""
        if isinstance(self._config, dict):
            self._config.setdefault("name", self.name)
            self._config = ProviderConfig.from_mapping(self._config)

        elif not isinstance(self._config, ProviderConfig):
            msg = (
                f"Unsupported config type: {type(self._config)}. "
                "Expected ProviderConfig or dict."
            )
            raise ValidationError(msg)

        self.name = self.name or self._config.name

        if self.name is None:
            raise ValidationError(
                "Provider name could not be determined from the config."
            )

    def __str__(self) -> str:
        """Return the provider's name as string."""
        return self.name

    def __repr__(self) -> str:
        """Return a string representation of the Provider."""
        return f"Provider('{self.name}')"

    def __eq__(self, other: str | Self):
        """Compare providers by name or with a string."""
        if isinstance(other, Provider):
            return self.name == other.name

        elif isinstance(other, str):
            return self.name == other

        return False

    def __hash__(self):
        """Hash based on provider name, for use in sets/dicts."""
        return hash(self.name)

    def _repr_html_(self) -> str:
        """HTML representation for Jupyter/IPython display."""
        thead = f"""<thead><tr><td style='text-align: left; color: grey;'>
            Provider: <span style='color: black'>{self.name}</span>
            </td></tr></thead>
        """
        # Show some key info, but not all config
        summary = {
            "name": self.name,
            "group": self.group,
            "priority": self.priority,
            "products": list(self.products.keys()) if self.products else [],
        }

        return (
            f"<table>{thead}"
            f"<tr><td style='text-align: left;'>"
            f"{dict_to_html_table(summary, depth=1)}"
            f"</td></tr></table>"
        )

    @property
    def config(self) -> ProviderConfig:
        """Get the provider's configuration."""
        return self._config

    @config.setter
    def config(self, value: ProviderConfig) -> None:
        """Set the provider's configuration."""
        self._config = value

    @property
    def product_types(self) -> dict[str, Any]:
        """Return the product types dictionary for this provider."""
        return getattr(self.config, "products", {})

    @property
    def priority(self) -> int:
        """Return the provider's priority (default: 0)."""
        return self.config.priority

    @property
    def group(self) -> Optional[str]:
        """Return the provider's group, if any."""
        return getattr(self.config, "group", None)

    @property
    def search_config(self) -> Optional[PluginConfig]:
        """Return the search plugin config, if any."""
        return getattr(self.config, "search", None) or getattr(self.config, "api", None)

    @property
    def fetchable(self) -> bool:
        """Return True if the provider can fetch product types."""
        return bool(
            getattr(self.search_config, "discover_product_types", {}).get("fetch_url")
        )

    @property
    def unparsable_properties(self) -> Optional[set[str]]:
        """Return set of unparsable properties for generic product types, if any."""
        if self.fetchable:
            return getattr(
                self.search_config.discover_product_types,
                "generic_product_type_unparsable_properties",
                {},
            ).keys()

        return None

    @property
    def api_config(self) -> Optional[PluginConfig]:
        """Return the api plugin config, if any."""
        return getattr(self.config, "api", None)

    @property
    def download_config(self) -> Optional[PluginConfig]:
        """Return the download plugin config, if any."""
        return getattr(self.config, "download", None)

    def _get_auth_confs_with_credentials(self) -> list[PluginConfig]:
        """
        Collect all auth configs from the provider that have credentials.

        :return: List of auth plugin configs with credentials.
        """
        return [
            getattr(self.config, auth_key)
            for auth_key in AUTH_TOPIC_KEYS
            if hasattr(self.config, auth_key)
            and credentials_in_auth(getattr(self.config, auth_key))
        ]

    def _copy_matching_credentials(
        self,
        auth_confs_with_creds: list[PluginConfig],
    ) -> None:
        """
        Copy credentials from matching auth configs to the target auth config.

        :param auth_confs_with_creds: Auth configs with credentials.
        """
        for key in AUTH_TOPIC_KEYS:
            provider_auth_config = getattr(self.config, key, None)
            if provider_auth_config and not credentials_in_auth(provider_auth_config):
                for conf_with_creds in auth_confs_with_creds:
                    if conf_with_creds.matches_target_auth(provider_auth_config):
                        getattr(
                            self.config, key
                        ).credentials = conf_with_creds.credentials

    def delete_product_type(self, name: str) -> None:
        """Remove a product type from this provider.

        :param name: The product type name.

        :raises UnsupportedProductType: If the product type is not found.
        """
        try:
            del self.product_types[name]
        except KeyError:
            msg = f"Product type '{name}' not found in provider '{self.name}'."
            raise UnsupportedProductType(msg)

    def sync_product_types(
        self,
        dag: EODataAccessGateway,
        strict_mode: bool,
    ) -> None:
        """
        Synchronize product types for a provider based on strict or permissive mode.

        In strict mode, removes product types not in "dag.collections_config".
        In permissive mode, adds empty product type configs for missing types.

        :param dag: The gateway instance to use to list existing collections and to create new collection instances.
        :param strict_mode: If True, remove unknown product types; if False, add empty configs for them.
        """
        products_to_remove: list[str] = []
        products_to_add: list[str] = []

        for product_id in self.product_types:
            if product_id == GENERIC_COLLECTION:
                continue

            if product_id not in dag.collections_config:
                if strict_mode:
                    products_to_remove.append(product_id)
                    continue

                empty_product = Collection(
                    dag=dag, id=product_id, title=product_id, description=NOT_AVAILABLE
                )
                dag.collections_config[
                    product_id
                ] = empty_product  # will update available_product_types
                products_to_add.append(product_id)

        if products_to_add:
            logger.debug(
                "Product types permissive mode, %s added (provider %s)",
                ", ".join(products_to_add),
                self,
            )

        if products_to_remove:
            logger.debug(
                "Product types strict mode, ignoring %s (provider %s)",
                ", ".join(products_to_remove),
                self,
            )
            for id in products_to_remove:
                self.delete_product_type(id)

    def _mm_already_built(self) -> bool:
        """Check if metadata mapping is already built (converted to querypaths/conversion)."""
        mm = getattr(self.search_config, "metadata_mapping", None)
        if not mm:
            return False

        try:
            first = next(iter(mm.values()))
        except StopIteration:
            return False

        # Consider it built if it's a tuple, or a list with second element as tuple
        if isinstance(first, tuple):
            return True
        if isinstance(first, list) and len(first) > 1 and isinstance(first[1], tuple):
            return True

        return False

    def update_from_config(self, config: ProviderConfig | dict[str, Any]) -> None:
        """Update the provider's configuration from a given config.

        :param config: The new configuration to update from.
        """
        # check if metadata mapping is already built for that provider
        # this happens when the provider search plugin has already been used
        source = config if isinstance(config, dict) else config.__dict__
        search_key = "search" if "search" in self.config else "api"
        new_conf_search = source.get(search_key, {}) or {}

        if "metadata_mapping" in new_conf_search and self._mm_already_built():
            mtd_cfg_as_conversion_and_querypath(
                deepcopy(new_conf_search["metadata_mapping"]),
                new_conf_search["metadata_mapping"],
            )

        self.config |= config


class ProvidersDict(UserDict[str, Provider]):
    """
    A dictionary-like collection of Provider objects, keyed by provider name.

    :param providers: Initial providers to populate the dictionary.
    """

    def __contains__(self, item: str | Provider) -> bool:
        """
        Check if a provider is in the dictionary by name or Provider instance.

        :param item: Provider name or Provider instance to check.
        :return: True if the provider is in the dictionary, False otherwise.
        """
        if isinstance(item, Provider):
            return item.name in self.data
        return item in self.data

    def __setitem__(self, key: str, value: Provider) -> None:
        """
        Add a Provider to the dictionary.

        :param key: The name of the provider.
        :param value: The Provider instance to add.
        :raises ValueError: If the provider key already exists.
        """
        if key in self.data:
            msg = f"Provider '{key}' already exists."
            raise ValueError(msg)
        super().__setitem__(key, value)

    def __delitem__(self, key: str) -> None:
        """
        Delete a provider by name.

        :param key: The name of the provider to delete.
        :raises UnsupportedProvider: If the provider key is not found.
        """
        if key not in self.data:
            msg = f"Provider '{key}' not found."
            raise UnsupportedProvider(msg)
        super().__delitem__(key)

    def __or__(self, other: Self) -> Self:
        """
        Merge two ProvidersDict using the | operator.

        :param other: Another ProvidersDict to merge.
        :return: A new ProvidersDict containing merged providers.
        """
        new_providers = deepcopy(self.data)
        new_providers.update_from_configs(other.configs)
        return new_providers

    def __ior__(self, other: Self) -> Self:
        """
        In-place merge of two ProvidersDict using the |= operator.

        :param other: Another ProvidersDict to merge.
        :return: The updated ProvidersDict (self).
        """
        self.update_from_configs(deepcopy(other.configs))
        return self

    def __repr__(self) -> str:
        """
        String representation of ProvidersDict.

        :return: String listing provider names.
        """
        return f"ProvidersDict({list(self.data.keys())})"

    def _repr_html_(self) -> str:
        """
        HTML representation for Jupyter/IPython display.

        :return: HTML string representation of the ProvidersDict.
        """
        thead = f"""<thead><tr><td style='text-align: left; color: grey;'>
                ProvidersDict ({len(self.data)})
                </td></tr></thead>"""
        rows = ""

        for provider in self.data.values():
            rows += (
                f"<tr><td style='text-align: left;'>{provider._repr_html_()}</td></tr>"
            )

        return f"<table>{thead}{rows}</table>"

    @property
    def names(self) -> list[str]:
        """
        List of provider names.

        :return: List of provider names.
        """
        return [provider.name for provider in self.data.values()]

    @property
    def configs(self) -> dict[str, ProviderConfig]:
        """
        Dictionary of provider configs keyed by provider name.

        :return: Dictionary mapping provider name to ProviderConfig.
        """
        return {provider.name: provider.config for provider in self.data.values()}

    @property
    def priorities(self) -> dict[str, int]:
        """
        Dictionary of provider priorities keyed by provider name.

        :return: Dictionary mapping provider name to priority integer.
        """
        return {
            provider.name: provider.config.priority for provider in self.data.values()
        }

    def get_config(self, provider: str) -> Optional[ProviderConfig]:
        """
        Get a ProviderConfig by provider name.

        If the provider is not found by name, attempts to get by group.

        :param provider: The provider name or group.
        :return: The ProviderConfig if found, otherwise None.
        """
        prov = self.get(provider)
        return prov.config if prov else None

    def get_products(self, provider: str | Provider) -> Optional[dict[str, Any]]:
        """
        Get the products dictionary for a provider by name or Provider instance.

        :param provider: Provider name or Provider instance.
        :return: The dictionary of product types or None if provider not found.
        """
        if isinstance(provider, Provider):
            name = provider.name
        else:
            name = provider

        provider_obj = self.data.get(name)
        return provider_obj.products if provider_obj else None

    def filter_by_name(self, name: Optional[str] = None) -> Self:
        """
        Return a ProvidersDict filtered by provider name or group.

        :param name: The name or group to filter by.
        :return: The filtered ProvidersDict.
        """
        if not name:
            return self

        return ProvidersDict(
            {n: p for n, p in self.data.items() if name in [p.name, p.group]}
        )

    def delete_product_type(self, provider: str, product_type: str) -> None:
        """
        Delete a product type from a provider.

        :param provider: The provider's name.
        :param product_ID: The product type to delete.
        :raises UnsupportedProvider: If the provider or product is not found.
        """
        if provider_obj := self.get(provider):
            if product_type in provider_obj.product_types:
                provider_obj.delete_product_type(product_type)
            else:
                msg = f"Product type '{product_type}' not found for provider '{provider}'."
                raise UnsupportedProductType(msg)
        else:
            msg = f"Provider '{provider}' not found."
            raise UnsupportedProvider(msg)

    def _share_credentials(self) -> None:
        """
        Share credentials between plugins with matching criteria
        across all providers in this dictionary.
        """
        auth_confs_with_creds: list[PluginConfig] = []
        for provider in self.values():
            auth_confs_with_creds.extend(provider._get_auth_confs_with_credentials())

        if not auth_confs_with_creds:
            return

        for provider in self.values():
            provider._copy_matching_credentials(auth_confs_with_creds)

    @staticmethod
    def _get_whitelisted_configs(
        configs: dict[str, ProviderConfig | dict[str, Any]],
    ) -> dict[str, ProviderConfig | dict[str, Any]]:
        """
        Filter configs according to the EODAG_PROVIDERS_WHITELIST environment variable, if set.

        :param configs: The dictionary of provider configurations.
        :return: Filtered configurations.
        """
        whitelist = set(os.getenv("EODAG_PROVIDERS_WHITELIST", "").split(","))
        if not whitelist or whitelist == {""}:
            return configs
        return {name: conf for name, conf in configs.items() if name in whitelist}

    def update_from_configs(
        self,
        configs: dict[str, ProviderConfig | dict[str, Any]],
    ) -> None:
        """
        Update providers from a dictionary of configurations.

        :param configs: A dictionary mapping provider names to configurations.
        """
        configs = self._get_whitelisted_configs(configs)
        for name, conf in configs.items():
            try:
                if name in self.data:
                    self.data[name].update_from_config(conf)
                    logger.debug("%s: configuration updated", name)
                else:
                    logger.info("%s: loading provider from configuration", name)
                    self.data[name] = Provider(conf, name)

                self.data[name].collections_fetched = False

            except Exception:
                operation = "updating" if name in self.data else "creating"
                logger.warning("%s: skipped %s due to invalid config", name, operation)
                logger.debug("Traceback:\n%s", traceback.format_exc())

        self._share_credentials()

    def update_from_config_file(self, file_path: str) -> None:
        """
        Override provider configurations with values loaded from a YAML file.

        :param file_path: The path to the configuration file.
        :raises yaml.parser.ParserError: If the YAML file cannot be parsed.
        """
        logger.info("Loading user configuration from: %s", os.path.abspath(file_path))
        with open(os.path.abspath(os.path.realpath(file_path)), "r") as fh:
            try:
                config_in_file = yaml.safe_load(fh)
                if config_in_file is None:
                    return
            except yaml.parser.ParserError as e:
                logger.error("Unable to load configuration file %s", file_path)
                raise e

        self.update_from_configs(config_in_file)

    def update_from_env(self) -> None:
        """
        Override provider configurations with environment variables values.

        Environment variables must start with 'EODAG__' and follow a nested key
        pattern separated by double underscores '__'.
        """

        def build_mapping_from_env(
            env_var: str, env_value: str, mapping: dict[str, Any]
        ) -> None:
            """
            Recursively build a dictionary from an environment variable.

            The environment variable must respect the pattern: KEY1__KEY2__[...]__KEYN.
            It will be transformed into a nested dictionary.

            :param env_var: The environment variable key (nested keys separated by '__').
            :param env_value: The value from environment variable.
            :param mapping: The dictionary where the nested mapping is built.
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
                try:
                    env_value = cast_scalar_value(env_value, child_env_type)
                except TypeError:
                    logger.warning(
                        f"Could not convert {parts} value {env_value} to {child_env_type}"
                    )
                mapping.setdefault(parts[0], {})
                mapping[parts[0]][parts[1]] = env_value
            elif len(parts) == 1:
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

        mapping_from_env: dict[str, dict[str, Any]] = {}
        for env_var in os.environ:
            if env_var.startswith("EODAG__"):
                build_mapping_from_env(
                    env_var[len("EODAG__") :].lower(),  # noqa
                    os.environ[env_var],
                    mapping_from_env,
                )

        self.update_from_configs(mapping_from_env)

    @classmethod
    def from_configs(cls, configs: dict[ProviderConfig | dict[str, Any]]) -> Self:
        """
        Build a ProvidersDict from a configuration mapping.

        :param configs: A dictionary mapping provider names to configuration dicts or ProviderConfig instances.
        :return: An instance of ProvidersDict populated with the given configurations.
        """
        configs = cls._get_whitelisted_configs(configs)
        providers = cls()
        providers.update_from_configs(configs)
        return providers
