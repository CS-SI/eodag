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
from inspect import isclass
from typing import (
    TYPE_CHECKING,
    Any,
    Iterator,
    Mapping,
    Optional,
    Union,
    get_type_hints,
)

import yaml

from eodag.api.collection import Collection
from eodag.api.product.metadata_mapping import (
    NOT_AVAILABLE,
    mtd_cfg_as_conversion_and_querypath,
)
from eodag.config import PluginConfig, credentials_in_auth, load_stac_provider_config
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
from eodag.utils.free_text_search import compile_free_text_query
from eodag.utils.repr import html_table

if TYPE_CHECKING:
    from eodag.api.core import EODataAccessGateway
    from typing_extensions import Self

logger = logging.getLogger("eodag.provider")

AUTH_TOPIC_KEYS = ("auth", "search_auth", "download_auth")
PLUGINS_TOPICS_KEYS = ("api", "search", "download") + AUTH_TOPIC_KEYS


class ProviderConfig(yaml.YAMLObject):
    """EODAG configuration for a provider.

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
    priority: int = 0
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
        # Create a deep copy to avoid modifying the input dict or its nested structures
        mapping_copy = deepcopy(mapping)
        for key in PLUGINS_TOPICS_KEYS:
            if _mapping := mapping_copy.get(key):
                mapping_copy[key] = PluginConfig.from_mapping(_mapping)
        c = cls()
        c.__dict__.update(mapping_copy)
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

    def with_name(self, new_name: str) -> Self:
        """Create a copy of this ProviderConfig with a different name.

        :param new_name: The new name for the provider config.
        :return: A new ProviderConfig instance with the updated name.
        """
        config_dict = self.__dict__.copy()
        config_dict["name"] = new_name

        for key in PLUGINS_TOPICS_KEYS:
            if key in config_dict and isinstance(config_dict[key], PluginConfig):
                config_dict[key] = config_dict[key].__dict__

        return self.__class__.from_mapping(config_dict)

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


class Provider:
    """
    Represents a data provider with its configuration and utility methods.

    :param config: Provider configuration as ProviderConfig instance or dict
    :param collections_fetched: Flag indicating whether collections have been fetched

    Example
    -------

    >>> from eodag.api.provider import Provider
    >>> config = {
    ...     'name': 'example_provider',
    ...     'description': 'Example provider for testing',
    ...     'search': {'type': 'StacSearch'},
    ...     'products': {'S2_MSI_L1C': {'_collection': 'S2_MSI_L1C'}}
    ... }
    >>> provider = Provider(config)
    >>> provider.name
    'example_provider'
    >>> 'S2_MSI_L1C' in provider.product_types
    True
    >>> provider.priority  # Default priority
    0
    """

    _name: str
    _config: ProviderConfig
    collections_fetched: bool

    def __init__(self, config: ProviderConfig | dict[str, Any]):
        """Initialize provider with configuration."""
        if isinstance(config, dict):
            self._config = ProviderConfig.from_mapping(config)
        elif isinstance(config, ProviderConfig):
            self._config = config
        else:
            msg = f"Unsupported config type: {type(config)}. Expected ProviderConfig or dict."
            raise ValidationError(msg)

        self._name = self._config.name
        self.collections_fetched = False

    def __str__(self) -> str:
        """Return the provider's name as string."""
        return self.name

    def __repr__(self) -> str:
        """Return a string representation of the Provider."""
        return f"Provider('{self.name}')"

    def __eq__(self, other: object):
        """Compare providers by name or with a string."""
        if isinstance(other, Provider):
            return self.name == other.name

        elif isinstance(other, str):
            return self.name == other

        return False

    def __hash__(self):
        """Hash based on provider name, for use in sets/dicts."""
        return hash(self.name)

    def _repr_html_(self, show_name: bool = True) -> str:
        """HTML representation for Jupyter/IPython display."""
        group_display = f" ({self.group})" if self.group else ""
        header_html = (
            f"""
        <h4 class="provider-title">{self.name}{group_display}</h4>
        """
            if show_name
            else ""
        )

        summaries = {
            "Description": self.config.description or "",
            "URL": self.config.url or "",
            "Priority": self.priority,
        }

        html = f"""
        <br />
        <div>
            {header_html}
            <br />
            {html_table(summaries)}
            <br />
            <br />
            {html_table(list(self.product_types.keys()))}
        </div>
        """

        return html

    @property
    def config(self) -> ProviderConfig:
        """
        Provider configuration (read-only assignment).

        To update configuration safely, use provider.update_from_config()
        which handles metadata mapping and other provider-specific logic.

        Note: Direct config modification (config.update(), config.name = ...)
        bypasses important provider validation.
        """
        return self._config

    @property
    def name(self) -> str:
        """The name of the provider."""
        return self._name

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
    def unparsable_properties(self) -> set[str]:
        """Return set of unparsable properties for generic product types, if any."""
        if not self.fetchable or self.search_config is None:
            return set()

        props = getattr(
            getattr(self.search_config, "discover_product_types", None),
            "generic_product_type_unparsable_properties",
            {},
        )
        return set(props.keys()) if isinstance(props, dict) else set()

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

        In strict mode, removes collections not in "dag.collections_config".
        In permissive mode, adds empty collection to config for missing types.

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
        :raises ValidationError: If the config attempts to change the provider name.
        """
        # Prevent name changes to maintain provider identity
        source = config if isinstance(config, dict) else config.__dict__
        if (new_name := source.get("name")) and new_name != self._name:
            raise ValidationError(
                f"Cannot change provider name from '{self._name}' to '{new_name}'. "
                "Provider names are immutable after creation."
            )

        # check if metadata mapping is already built for that provider
        # this happens when the provider search plugin has already been used
        search_key = "search" if "search" in self.config else "api"
        new_conf_search = source.get(search_key, {}) or {}

        if "metadata_mapping" in new_conf_search and self._mm_already_built():
            mtd_cfg_as_conversion_and_querypath(
                deepcopy(new_conf_search["metadata_mapping"]),
                new_conf_search["metadata_mapping"],
            )

        self.config.update(config)


class ProvidersDict(UserDict[str, Provider]):
    """
    A dictionary-like collection of Provider objects, keyed by provider name.

    :param providers: Initial providers to populate the dictionary.
    """

    def __contains__(self, item: object) -> bool:
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
            # Wrap each provider in a collapsible details element
            rows += (
                f"<tr><td style='text-align: left;'>"
                f"<details>"
                f"<summary style='cursor: pointer; font-weight: bold;'>{provider.name}</summary>"
                f"{provider._repr_html_(show_name=False)}"
                f"</details>"
                f"</td></tr>"
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

    def filter(self, q: Optional[str] = None) -> Iterator[Provider]:
        """
        Yield providers whose name, group, description or URL matches the free-text query.

        Supports logical operators with parenthesis (``AND``/``OR``/``NOT``), quoted phrases (``"exact phrase"``),
        ``*`` and ``?`` wildcards.

        If no query is provided, returns all providers in the collection.

        :param q: Free-text parameter to filter providers. If None, yields all providers.
        :return: Iterator of matching Provider objects.

        Example
        -------

        >>> from eodag.api.provider import ProvidersDict, Provider
        >>> providers = ProvidersDict()
        >>> providers['test1'] = Provider({
        ...     'name': 'test1',
        ...     'description': 'Satellite data',
        ...     'search': {'type': 'StacSearch'}
        ... })
        >>> providers['test2'] = Provider({
        ...     'name': 'test2',
        ...     'description': 'Weather data',
        ...     'search': {'type': 'StacSearch'}
        ... })
        >>> # Filter by description content
        >>> list(p.name for p in providers.filter('Satellite'))
        ['test1']
        >>> # Filter with logical operators
        >>> providers['test3'] = Provider({
        ...     'name': 'test3',
        ...     'description': 'Satellite weather data',
        ...     'search': {'type': 'StacSearch'}
        ... })
        >>> list(p.name for p in providers.filter('Satellite AND weather'))
        ['test3']
        >>> # Get all providers when no filter
        >>> len(list(providers.filter()))
        3
        """
        if not q:
            yield from self.data.values()
            return

        free_text_query = compile_free_text_query(q)
        searchable_attributes = {"name", "group", "description", "url"}

        for p in self.data.values():
            searchables = {
                k: v for k, v in p.config.__dict__.items() if k in searchable_attributes
            }
            if free_text_query(searchables):
                yield p

    def filter_by_name_or_group(
        self, name_or_group: Optional[str] = None
    ) -> Iterator[Provider]:
        """
        Yield providers whose name or group matches the given name_or_group.

        If name_or_group is None, yields all providers.

        :param name_or_group: The provider name or group to filter by. If None, yields all providers.
        :return: Iterator of matching Provider objects.

        Example
        -------

        >>> from eodag.api.provider import ProvidersDict, Provider
        >>> providers = ProvidersDict()
        >>> providers['sentinel'] = Provider({'name': 'sentinel', 'group': 'esa', 'search': {'type': 'StacSearch'}})
        >>> providers['landsat'] = Provider({'name': 'landsat', 'group': 'usgs', 'search': {'type': 'StacSearch'}})
        >>> providers['modis'] = Provider({'name': 'modis', 'group': 'nasa', 'search': {'type': 'StacSearch'}})
        >>>
        >>> # Filter by exact provider name
        >>> list(p.name for p in providers.filter_by_name_or_group('sentinel'))
        ['sentinel']
        >>>
        >>> # Filter by group (case-insensitive)
        >>> list(p.name for p in providers.filter_by_name_or_group('ESA'))
        ['sentinel']
        >>>
        >>> # Get all providers when no filter
        >>> len(list(providers.filter_by_name_or_group()))
        3
        """
        if name_or_group is None:
            yield from self.data.values()
            return

        name_or_group_lower = name_or_group.lower()
        for provider in self.data.values():
            if provider.name.lower() == name_or_group_lower or (
                provider.group and provider.group.lower() == name_or_group_lower
            ):
                yield provider

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
        configs: Mapping[str, ProviderConfig | dict[str, Any]],
    ) -> Mapping[str, ProviderConfig | dict[str, Any]]:
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
        configs: Mapping[str, ProviderConfig | dict[str, Any]],
    ) -> None:
        """
        Update providers from a dictionary of configurations.

        :param configs: A dictionary mapping provider names to configurations.
        """
        configs = self._get_whitelisted_configs(configs)
        for name, conf in configs.items():
            if isinstance(conf, dict) and conf.get("name") != name:
                if "name" in conf:
                    logger.debug(
                        "%s: config name '%s' overridden by dict key",
                        name,
                        conf["name"],
                    )
                conf = {**conf, "name": name}
            elif isinstance(conf, ProviderConfig) and conf.name != name:
                raise ValidationError(
                    f"ProviderConfig name '{conf.name}' must match dict key '{name}'"
                )

            try:
                if name in self.data:
                    self.data[name].update_from_config(conf)
                    logger.debug("%s: configuration updated", name)
                else:
                    logger.info("%s: loading provider from configuration", name)
                    self.data[name] = Provider(conf)

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
    def from_configs(
        cls, configs: Mapping[str, ProviderConfig | dict[str, Any]]
    ) -> Self:
        """
        Build a ProvidersDict from a configuration mapping.

        :param configs: A dictionary mapping provider names to configuration dicts or ProviderConfig instances.
        :return: An instance of ProvidersDict populated with the given configurations.
        """
        providers = cls()
        providers.update_from_configs(configs)
        return providers
