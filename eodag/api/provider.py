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
import logging
import os
import tempfile
from collections import UserDict
from dataclasses import dataclass
from inspect import isclass
from typing import Any, Optional, Self, Union, get_type_hints

import yaml

from eodag.api.plugin import PluginConfig, credentials_in_auth
from eodag.api.product.metadata_mapping import (
    NOT_AVAILABLE,
    mtd_cfg_as_conversion_and_querypath,
)
from eodag.utils import (
    GENERIC_PRODUCT_TYPE,
    STAC_SEARCH_PLUGINS,
    cast_scalar_value,
    deepcopy,
    merge_mappings,
    slugify,
    update_nested_dict,
)
from eodag.utils.exceptions import ValidationError
from eodag.utils.repr import dict_to_html_table

logger = logging.getLogger("eodag.provider")

AUTH_TOPIC_KEYS = ("auth", "search_auth", "download_auth")
PLUGINS_TOPICS_KEYS = ("api", "search", "download") + AUTH_TOPIC_KEYS


class ProviderConfig(yaml.YAMLObject):
    """Representation of eodag configuration.

    :param name: The name of the provider
    :param priority: (optional) The priority of the provider while searching a product.
                     Lower value means lower priority. (Default: 0)
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
    product_types_fetched: bool  # set in core.update_product_types_list

    yaml_loader = yaml.Loader
    yaml_dumper = yaml.SafeDumper
    yaml_tag = "!provider"

    @classmethod
    def from_yaml(cls, loader: yaml.Loader, node: Any) -> Self:
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
            if key in mapping:
                mapping[key] = PluginConfig.from_mapping(mapping[key])
        c = cls()
        c.__dict__.update(mapping)
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

    def update(self, mapping: Optional[dict[str, Any]]) -> None:
        """Update the configuration parameters with values from `mapping`

        :param mapping: The mapping from which to override configuration parameters
        """
        if mapping is None:
            mapping = {}
        merge_mappings(
            self.__dict__,
            {
                key: value
                for key, value in mapping.items()
                if key not in PLUGINS_TOPICS_KEYS and value is not None
            },
        )
        for key in PLUGINS_TOPICS_KEYS:
            current_value: Optional[PluginConfig] = getattr(self, key, None)
            mapping_value = mapping.get(key, {})
            if current_value is not None:
                current_value.update(mapping_value)
            elif mapping_value:
                try:
                    setattr(self, key, PluginConfig.from_mapping(mapping_value))
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


def provider_config_init(
    provider_config: ProviderConfig,
    stac_search_default_conf: Optional[dict[str, Any]] = None,
) -> None:
    """Applies some default values to provider config

    :param provider_config: An eodag provider configuration
    :param stac_search_default_conf: default conf to overwrite with provider_config if STAC
    """
    # For the provider, set the default output_dir of its download plugin
    # as tempdir in a portable way
    for download_topic_key in ("download", "api"):
        if download_topic_key in vars(provider_config):
            download_conf = getattr(provider_config, download_topic_key)
            if not getattr(download_conf, "output_dir", None):
                download_conf.output_dir = tempfile.gettempdir()
            if not getattr(download_conf, "delete_archive", None):
                download_conf.delete_archive = True

    try:
        if (
            stac_search_default_conf is not None
            and provider_config.search
            and provider_config.search.type in STAC_SEARCH_PLUGINS
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


@dataclass
class Provider:
    """
    Represents a data provider with its configuration and utility methods.
    """

    name: str
    _config: ProviderConfig

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
        self.config = value

    @property
    def products(self) -> dict[str, Any]:
        """Return the products dictionary for this provider."""
        return self.config.products

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
        if self.search_config is None:
            return False

        if not hasattr(self.search_config, "discover_product_types"):
            return False

        if not hasattr(self.search_config.discover_product_types, "fetch_url"):
            return False

        return True

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

    def product(self, product_type: str) -> Optional[Any]:
        """Return a product type if available from this provider.

        Args:
            product_type (str): The product type name.

        Returns:
            Optional[Any]: The product type config or None if not found.
        """
        return self.products.get(product_type)

    def delete_product(self, product_type: str) -> None:
        """Remove a product type from this provider.

        Args:
            product_type (str): The product type name.

        Raises:
            KeyError: If the product type is not found.
        """
        if self.product(product_type):
            del self.products[product_type]
        else:
            raise KeyError(
                f"Product type '{product_type}' not found in provider '{self.name}'."
            )

    def _get_auth_confs_with_credentials(self) -> list[PluginConfig]:
        """
        Collect all auth configs from the provider that have credentials.

        Returns:
            list[PluginConfig]: List of auth plugin configs with credentials.
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

        Args:
            auth_confs_with_creds (list[PluginConfig]): Auth configs with credentials.
        """
        for key in AUTH_TOPIC_KEYS:
            provider_auth_config = getattr(self.config, key, None)
            if provider_auth_config and not credentials_in_auth(provider_auth_config):
                for conf_with_creds in auth_confs_with_creds:
                    if conf_with_creds.matches_target_auth(provider_auth_config):
                        getattr(
                            self.config, key
                        ).credentials = conf_with_creds.credentials

    def sync_product_types(
        self,
        available_product_types: set[str],
        strict_mode: bool,
    ) -> None:
        """
        Synchronize product types for a provider based on strict or permissive mode.

        In strict mode, removes product types not in available_product_types.
        In permissive mode, adds empty product type configs for missing types.

        :param provider: The provider name whose product types should be synchronized.
        :param available_product_types: The set of available product type IDs.
        :param strict_mode: If True, remove unknown product types; if False, add empty configs for them.
        :returns: None
        """
        products_to_remove: list[str] = []
        products_to_add: list[str] = []

        for product_id in self.products:
            if product_id == GENERIC_PRODUCT_TYPE:
                continue

            if product_id not in available_product_types:
                if strict_mode:
                    products_to_remove.append(product_id)
                    continue

                empty_product = {
                    "title": product_id,
                    "abstract": NOT_AVAILABLE,
                }
                self.product_types_config.source[
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
                self.delete_product(id)


@dataclass
class ProvidersDict(UserDict[str, Provider]):
    """
    A dictionary-like collection of Provider objects, keyed by provider name.

    Args:
        providers (list[Provider] | dict[str, PluginConfig] | None): Initial providers.
    """

    def __init__(
        self,
        providers: list[Provider] | dict[str, PluginConfig] | None,
    ):
        """
        Initialize the ProvidersDict.

        Args:
            providers (list[Provider] | dict[str, PluginConfig] | None): Initial providers.
        """

        super().__init__()

        if providers is None:
            self.data = {}

        elif isinstance(providers, dict):
            self.data = {name: Provider(name, conf) for name, conf in providers.items()}
        else:
            self.data = {
                p.name
                if isinstance(p, Provider)
                else p: p
                if isinstance(p, Provider)
                else Provider(p, {})
                for p in providers
            }

    def __contains__(self, item: str | Provider) -> bool:
        """Check if a provider is in the dictionary by name or Provider instance."""
        if isinstance(item, Provider):
            return item.name in self.data

        return item in self.data

    def __getitem__(self, key: str) -> Provider:
        """Get a Provider by name."""
        return self.data[key]

    def __repr__(self) -> str:
        """String representation of ProvidersDict."""
        return f"ProvidersDict({list(self.data.keys())})"

    def _repr_html_(self) -> str:
        """HTML representation for Jupyter/IPython display."""
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
        """List of provider names."""
        return [provider.name for provider in self.data.values()]

    @property
    def configs(self) -> dict[str, ProviderConfig]:
        """Dictionary of provider configs keyed by provider name."""
        return {provider.name: provider.config for provider in self.data.values()}

    @property
    def priorities(self) -> dict[str, int]:
        """Dictionary of provider priorities keyed by provider name."""
        return {
            provider.name: provider.config.priority for provider in self.data.values()
        }

    def get(self, provider: str) -> Optional[Provider]:
        """Get a Provider by name, or by group if not found by name."""
        # Try by name first
        result = self.data.get(provider)
        if result is not None:
            return result

        # Try by group attribute
        for prov in self.data.values():
            if getattr(prov, "group", None) == provider:
                return prov

        return None

    def get_config(self, provider: str) -> Optional[ProviderConfig]:
        """Get a ProviderConfig by provider name, or by group if not found by name."""
        prov = self.get(provider)
        return prov.config if prov else None

    def set_config(self, provider: str, cfg: ProviderConfig) -> None:
        """
        Update the ProviderConfig for a given provider name in place.

        Args:
            name (str): The name of the provider to update.
            cfg (ProviderConfig): The new ProviderConfig to set.

        Raises:
            KeyError: If the provider is not found.
        """
        if provider in self.data:
            self.data[provider].config = cfg
        else:
            raise KeyError(f"Provider '{provider}' not found.")

    def get_products(self, provider: str | Provider) -> Optional[dict[str, Any]]:
        """Get the products dictionary for a provider by name or Provider instance."""
        if isinstance(provider, Provider):
            name = provider.name

        provider = self.data.get(name)
        return provider.products if provider else None

    def add(self, provider: Provider) -> None:
        """Add a Provider to the dictionary.

        Args:
            provider (Provider): The provider to add.

        Raises:
            ValueError: If the provider already exists.
        """
        if provider.name in self.data:
            raise ValueError(f"Provider '{provider.name}' already exists.")

        self.data[provider.name] = provider

    def delete(self, name: str) -> None:
        """Delete a provider by name.

        Args:
            name (str): The name of the provider to delete.

        Raises:
            KeyError: If the provider is not found.
        """
        if name in self.data:
            del self.data[name]
        else:
            raise KeyError(f"Provider '{name}' not found.")

    def filter_by_name(self, name: Optional[str]) -> Self:
        """Return a ProvidersDict filtered by provider name or group.

        Args:
            name (Optional[str]): The name or group to filter by.

        Returns:
            ProvidersDict: The filtered ProvidersDict.
        """
        if not name:
            return self

        filtered_providers = [
            p for p in self.data.values() if p.name in [name, p.group]
        ]

        return ProvidersDict(filtered_providers)

    def filter_by_group(self, name: Optional[str]) -> Self:
        """Return a ProvidersDict filtered by group name.

        Args:
            name (Optional[str]): The group name to filter by.

        Returns:
            ProvidersDict: The filtered ProvidersDict.
        """
        if not name:
            return self

        filtered_providers = [p for p in self.data.values() if p.name == p.group]

        return ProvidersDict(filtered_providers)

    def delete_product(self, provider: str, product_ID: str) -> None:
        """Delete a product from a provider.

        Args:
            provider (str): The provider's name.
            product_ID (str): The product type to delete.

        Raises:
            KeyError: If the provider or product is not found.
        """
        if provider_obj := self.get(provider):
            if product_ID in provider_obj.products:
                provider_obj.delete_product(product_ID)
            else:
                raise KeyError(
                    f"Product '{product_ID}' not found for Provider '{provider}'."
                )

        else:
            raise KeyError(f"Provider '{provider}' not found.")

    def share_credentials(self) -> None:
        """
        Share credentials between plugins having the same matching criteria
        across all providers in this list.
        """
        auth_confs_with_creds: list[PluginConfig] = []
        for provider in self.values():
            auth_confs_with_creds.extend(provider._get_auth_confs_with_credentials())

        if not auth_confs_with_creds:
            return

        for provider in self.values():
            provider._copy_matching_credentials(auth_confs_with_creds)

    def merge(self, other: Self) -> None:
        """
        Override the current providers' configuration with the values of another ProvidersDict.

        :param other: Another ProvidersDict instance whose configs will override the current ones.
        """
        for name, other_provider in other.items():
            if name in self:
                current_provider = self[name]
                old_conf = current_provider.config
                new_conf = other_provider.config

                merged_dict = dict(old_conf.__dict__)
                merged_dict.update(new_conf.__dict__)

                for key, value in merged_dict.items():
                    old_val = getattr(old_conf, key, None)
                    if isinstance(value, PluginConfig) and isinstance(
                        old_val, PluginConfig
                    ):
                        old_val.update(value.__dict__)
                        merged_dict[key] = old_val
                    elif isinstance(old_val, PluginConfig):
                        merged_dict[key] = old_val

                    setattr(old_conf, key, merged_dict[key])
            else:
                self.data[name] = other_provider

    def _override_configs_from_mapping(self, mapping: dict[str, Any]) -> None:
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

        for name, conf in mapping.items():
            # check if metada-mapping as already been built as jsonpath in providers_config
            # or provider not in whitelist
            if not isinstance(conf, dict) or (whitelist and name not in whitelist):
                continue

            conf_search = conf.get("search", {}) or {}
            conf_api = conf.get("api", {}) or {}

            if name in self.keys() and "metadata_mapping" in {
                **conf_search,
                **conf_api,
            }:
                search_plugin_key = (
                    "search" if "metadata_mapping" in conf_search else "api"
                )

                # get some already configured value
                configured_metadata_mapping = getattr(
                    self.get_config(name), search_plugin_key
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
                        deepcopy(mapping[name][search_plugin_key]["metadata_mapping"]),
                        mapping[name][search_plugin_key]["metadata_mapping"],
                    )

            # try overriding conf
            old_conf: Optional[ProviderConfig] = self.get_config(name)
            if old_conf is not None:
                old_conf.update(conf)
            else:
                logger.info(
                    "%s: unknown provider found in user conf, trying to use provided configuration",
                    name,
                )
                try:
                    conf["name"] = conf.get("name", name)
                    conf = ProviderConfig.from_mapping(conf)
                    self.set_config(name, conf)
                except Exception:
                    logger.warning(
                        "%s skipped: could not be loaded from user configuration", name
                    )

                    import traceback as tb

                    logger.debug(tb.format_exc())

    def override_configs_from_file(self, file_path: str) -> None:
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

        self._override_configs_from_mapping(config_in_file)

    def override_configs_from_env(self) -> None:
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

        self._override_configs_from_mapping(mapping_from_env)

    def update_config(
        self, conf_update: dict[str, Any], stac_provider_config: dict[str, Any] | None
    ) -> None:
        """Update the configuration from environment variables and user configuration file."""
        self._override_configs_from_mapping(conf_update)
        self.share_credentials()

        for provider in conf_update.keys():
            provider_config_init(
                self.providers.get_config(name=provider), stac_provider_config
            )

        setattr(self.data[provider].config, "product_types_fetched", False)
