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
from inspect import isclass
from textwrap import shorten
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

from eodag.api.product.metadata_mapping import mtd_cfg_as_conversion_and_querypath
from eodag.config import PluginConfig, credentials_in_auth, load_stac_provider_config
from eodag.utils import (
    STAC_SEARCH_PLUGINS,
    cast_scalar_value,
    deepcopy,
    merge_mappings,
    slugify,
    update_nested_dict,
)
from eodag.utils.exceptions import (
    UnsupportedCollection,
    UnsupportedProvider,
    ValidationError,
)
from eodag.utils.free_text_search import compile_free_text_query
from eodag.utils.repr import dict_to_html_table, str_as_href

if TYPE_CHECKING:
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
    :param products: (optional) The collections supported by the provider
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
    products: dict[str, dict[str, Any]]
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
        """Build a :class:`~eodag.api.provider.ProviderConfig` from Yaml"""
        cls.validate(tuple(node_key.value for node_key, _ in node.value))
        for node_key, node_value in node.value:
            if node_key.value == "name":
                node_value.value = slugify(node_value.value).replace("-", "_")
                break
        return loader.construct_yaml_object(node, cls)

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> Self:
        """Build a :class:`~eodag.api.provider.ProviderConfig` from a mapping"""
        cls.validate(mapping)
        # Create a deep copy to avoid modifying the input dict or its nested structures
        mapping_copy = deepcopy(mapping)
        for key in PLUGINS_TOPICS_KEYS:
            if not (_mapping := mapping_copy.get(key)):
                continue

            if not isinstance(_mapping, dict):
                _mapping = _mapping.__dict__

            mapping_copy[key] = PluginConfig.from_mapping(_mapping)
        c = cls()
        c.__dict__.update(mapping_copy)
        c._apply_defaults()
        return c

    @staticmethod
    def validate(config_keys: Union[tuple[str, ...], dict[str, Any]]) -> None:
        """Validate a :class:`~eodag.api.provider.ProviderConfig`

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

    def update(self, config: Union[Self, dict[str, Any]]) -> None:
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
        """Create a copy of this :class:`~eodag.api.provider.ProviderConfig` with a different name.

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

    :param config: Provider configuration as :meth:`~eodag.api.provider.ProviderConfig` instance or :class:`dict`
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
    >>> 'S2_MSI_L1C' in provider.collections_config
    True
    >>> provider.priority  # Default priority
    0
    """

    _name: str
    _config: ProviderConfig
    collections_fetched: bool

    def __init__(self, config: Union[ProviderConfig, dict[str, Any]]):
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

    def _repr_html_(self, embedded: bool = False) -> str:
        """HTML representation for Jupyter/IPython display."""
        group_display = f" ({self.group})" if self.group else ""
        thead = (
            f"""<thead><tr><td style='text-align: left; color: grey;'>
                {type(self).__name__}("<span style='color: black'>{self.name}{group_display}</span>")</td></tr></thead>
            """
            if not embedded
            else ""
        )
        tr_style = "style='background-color: transparent;'" if embedded else ""

        summaries = {
            "name": self.name,
            "title": self.config.description or "",
            "url": self.config.url or "",
            "priority": self.priority,
        }
        if self.group:
            summaries["group"] = self.group

        col_html_table = dict_to_html_table(summaries, depth=1, brackets=False)

        return (
            f"<table>{thead}<tbody>"
            f"<tr {tr_style}><td style='text-align: left;'>"
            f"{col_html_table}</td></tr>"
            "</tbody></table>"
        )

    @property
    def config(self) -> ProviderConfig:
        """
        Provider configuration (read-only assignment).

        To update configuration safely, use :meth:`~eodag.api.provider.Provider.update_from_config`
        which handles metadata mapping and other provider-specific logic.

        Note: Direct config modification (``config.update()``, ``config.name = ...``)
        bypasses important provider validation.
        """
        return self._config

    @property
    def name(self) -> str:
        """The name of the provider."""
        return self._name

    @property
    def title(self) -> Optional[str]:
        """The title of the provider."""
        return getattr(self.config, "description", None)

    @property
    def url(self) -> Optional[str]:
        """The url of the provider."""
        return getattr(self.config, "url", None)

    @property
    def collections_config(self) -> dict[str, Any]:
        """Return the collections configuration dictionary for this provider."""
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
        """Return True if the provider can fetch collections."""
        return bool(
            getattr(self.search_config, "discover_collections", {}).get("fetch_url")
        )

    @property
    def unparsable_properties(self) -> set[str]:
        """Return set of unparsable properties from
        :attr:`~eodag.config.PluginConfig.DiscoverCollections.generic_collection_unparsable_properties`, if any.
        """
        if not self.fetchable or self.search_config is None:
            return set()

        props = getattr(
            getattr(self.search_config, "discover_collections", None),
            "generic_collection_unparsable_properties",
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
                        return

    def delete_collection(self, name: str) -> None:
        """Remove a collection from this provider.

        :param name: The collection name.

        :raises UnsupportedCollection: If the collection is not found.
        """
        try:
            del self.collections_config[name]
        except KeyError:
            msg = f"Collection '{name}' not found in provider '{self.name}'."
            raise UnsupportedCollection(msg)

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

    def update_from_config(self, config: Union[ProviderConfig, dict[str, Any]]) -> None:
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


class ProvidersDict:
    """
    A dictionary-like view over providers stored in the database.

    Providers are read from the ``federation_backends`` table. This class does not
    hold any in-memory state — the database is the single source of truth.

    Create via :meth:`ProvidersDict(db) <__init__>`.
    """

    def __init__(self, db: Any) -> None:
        """
        :param db: A :class:`~eodag.databases.sqlite.SQLiteDatabase` instance.
        """
        self._db = db

    def _provider_from_db(self, name: str) -> Provider:
        """Reconstruct a Provider from database data.

        :param name: The federation backend id
        :returns: A Provider instance
        :raises UnsupportedProvider: If the provider is not found in the database
        """
        fb = self._db.get_federation_backends([name])
        if name not in fb:
            raise UnsupportedProvider(f"Provider '{name}' not found.")
        data = fb[name]
        config_dict = {"name": name, **data["metadata"], **data["plugins_config"], "priority": data["priority"]}
        # Load collection-level configs (products) from collections_federation_backends
        coll_configs = self._db.get_collection_configs_for_backend(name)
        if coll_configs:
            products = {}
            for coll_id, coll_pc in coll_configs.items():
                # coll_pc is {"search": {...}} or {"api": {...}}
                for _topic, topic_conf in coll_pc.items():
                    products[coll_id] = topic_conf
                    break
            config_dict["products"] = products
        provider = Provider(config_dict)
        provider.collections_fetched = bool(data["metadata"].get("last_fetch"))
        return provider

    def __contains__(self, item: object) -> bool:
        """
        Check if a provider is in the dictionary by name or :class:`~eodag.api.provider.Provider` instance.

        :param item: Provider name or Provider instance to check.
        :return: True if the provider is in the dictionary, False otherwise.
        """
        name = item.name if isinstance(item, Provider) else item
        if isinstance(name, str):
            return name in self._db.list_federation_backend_names(enabled_only=True)
        return False

    def __getitem__(self, key: str) -> Provider:
        return self._provider_from_db(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self._provider_from_db(key)
        except UnsupportedProvider:
            return default

    def __iter__(self) -> Iterator[str]:
        return iter(self._db.list_federation_backend_names(enabled_only=True))

    def __len__(self) -> int:
        return len(self._db.list_federation_backend_names(enabled_only=True))

    def keys(self) -> list[str]:
        return self._db.list_federation_backend_names(enabled_only=True)

    def values(self) -> list[Provider]:
        return [self._provider_from_db(n) for n in self._db.list_federation_backend_names(enabled_only=True)]

    def items(self) -> list[tuple[str, Provider]]:
        names = self._db.list_federation_backend_names(enabled_only=True)
        return [(n, self._provider_from_db(n)) for n in names]

    def pop(self, key: str, *args: Any) -> Any:
        """Disable a provider in the DB and return it."""
        try:
            provider = self._provider_from_db(key)
        except UnsupportedProvider:
            if args:
                return args[0]
            raise
        self._db.set_federation_backends_enabled([key], False)
        return provider
    def __repr__(self) -> str:
        """
        String representation of :class:`~eodag.api.provider.ProvidersDict`.

        :return: String listing provider names.
        """
        return f"ProvidersDict({self.names})"

    def _repr_html_(self, embeded=False) -> str:
        """
        HTML representation for Jupyter/IPython display.

        :return: HTML string representation of the :class:`~eodag.api.provider.ProvidersDict`.
        """
        longest_name = max([len(k) for k in self.keys()])
        thead = (
            f"""<thead><tr><td style='text-align: left; color: grey;'>
                {type(self).__name__}&ensp;({len(self)})
                </td></tr></thead>
            """
            if not embeded
            else ""
        )
        tr_style = "style='background-color: transparent;'" if embeded else ""
        return (
            f"<table>{thead}"
            + "".join(
                [
                    f"""<tr {tr_style}><td style='text-align: left;'>
                <details><summary style='color: grey;'>
                    <span style='color: black; font-family: monospace;'>{k}:{'&nbsp;' * (longest_name - len(k))}</span>
                    Provider(
                        {"'priority': '<span style='color: black'>" + str(v.priority) + "</span>',&ensp;"
                         if v.priority is not None else ""}
                        {"'title': '<span style='color: black'>"
                         + shorten(v.title, width=70, placeholder="[...]") + "</span>',&ensp;"
                         if v.title else ""}
                        {"'url': '" + str_as_href(v.url) + "'" if v.url else ""}
                    )
                </summary>
                    {v._repr_html_(embedded=True)}
                </details>
                </td></tr>
                """
                    for k, v in self.items()
                ]
            )
            + "</table>"
        )

    @property
    def names(self) -> list[str]:
        """
        List of provider names.

        :return: List of provider names sorted by priority DESC then name ASC.
        """
        return self._db.list_federation_backend_names()

    @property
    def groups(self) -> list[str]:
        """
        List of provider groups if exist or names.

        :return: List of provider groups if exist or names.
        """
        return self._db.list_federation_backend_groups()

    @property
    def configs(self) -> dict[str, ProviderConfig]:
        """
        Dictionary of provider configs keyed by provider name.

        :return: Dictionary mapping provider name to :class:`~eodag.api.provider.ProviderConfig`.
        """
        return {name: self._provider_from_db(name).config for name in self._db.list_federation_backend_names(enabled_only=True)}

    @property
    def priorities(self) -> dict[str, int]:
        """
        Dictionary of provider priorities keyed by provider name.

        :return: Dictionary mapping provider name to priority integer.
        """
        return self._db.get_federation_backend_priorities()

    def get_config(self, provider: str) -> Optional[ProviderConfig]:
        """
        Get a :class:`~eodag.api.provider.ProviderConfig` from provider name.

        :param provider: The provider name.
        :return: The :class:`~eodag.api.provider.ProviderConfig` if found, otherwise None.
        """
        prov = self.get(provider)
        return prov.config if prov else None

    def filter(self, q: Optional[str] = None) -> ProvidersDict:
        """
        Return providers whose name, group, description, URL or collection matches the free-text query.

        Supports logical operators with parenthesis (``AND``/``OR``/``NOT``), quoted phrases (``"exact phrase"``),
        ``*`` and ``?`` wildcards.

        If no query is provided, returns all providers.

        :param q: Free-text parameter to filter providers. If None, returns all providers.
        :return: matching Provider objects in a :class:`~eodag.api.provider.ProvidersDict`.
        """
        if not q:
            return self

        # TODO: implement DB-backed free-text filtering
        free_text_query = compile_free_text_query(q)
        searchable_attributes = {"name", "group", "description", "products"}

        # For now, materialize from DB and filter in Python
        matching_names: list[str] = []
        for name in self._db.list_federation_backend_names(enabled_only=True):
            p = self._provider_from_db(name)
            searchables = {
                k: v for k, v in p.config.__dict__.items() if k in searchable_attributes
            }
            if free_text_query(searchables):
                matching_names.append(name)

        # Return a filtered view backed by the same DB
        return _FilteredProvidersDict(self._db, matching_names)

    def filter_by_name_or_group(
        self, name_or_group: Optional[str] = None
    ) -> list[str]:
        """
        Return provider names matching the given ``name_or_group``.

        :param name_or_group: The provider name or group to filter by. If None, returns all.
        :return: List of provider name strings.
        """
        return self._db.filter_federation_backends(name_or_group)


class _FilteredProvidersDict(ProvidersDict):
    """A ProvidersDict restricted to a subset of provider names."""

    def __init__(self, db: Any, allowed_names: list[str]) -> None:
        super().__init__(db)
        self._allowed = allowed_names

    def __contains__(self, item: object) -> bool:
        name = item.name if isinstance(item, Provider) else item
        return isinstance(name, str) and name in self._allowed

    def __iter__(self) -> Iterator[str]:
        return iter(self._allowed)

    def __len__(self) -> int:
        return len(self._allowed)

    def keys(self) -> list[str]:
        return list(self._allowed)

    def values(self) -> list[Provider]:
        return [self._provider_from_db(n) for n in self._allowed]

    def items(self) -> list[tuple[str, Provider]]:
        return [(n, self._provider_from_db(n)) for n in self._allowed]

    @property
    def names(self) -> list[str]:
        return list(self._allowed)


# ---------------------------------------------------------------------------
# Standalone helpers to build / merge provider configurations
# ---------------------------------------------------------------------------


def _get_whitelisted_configs(
    configs: Mapping[str, Union[ProviderConfig, dict[str, Any]]],
) -> Mapping[str, Union[ProviderConfig, dict[str, Any]]]:
    """Filter configs according to the ``EODAG_PROVIDERS_WHITELIST`` env var."""
    whitelist = set(os.getenv("EODAG_PROVIDERS_WHITELIST", "").split(","))
    if not whitelist or whitelist == {""}:
        return configs
    return {name: conf for name, conf in configs.items() if name in whitelist}


def _share_credentials(providers: dict[str, Provider]) -> None:
    """Share credentials between plugins with matching criteria."""
    auth_confs_with_creds: list[PluginConfig] = []
    for provider in providers.values():
        auth_confs_with_creds.extend(provider._get_auth_confs_with_credentials())
    if not auth_confs_with_creds:
        return
    for provider in providers.values():
        provider._copy_matching_credentials(auth_confs_with_creds)


def merge_provider_configs(
    providers: dict[str, Provider],
    configs: Mapping[str, Union[ProviderConfig, dict[str, Any]]],
) -> None:
    """Merge *configs* into *providers* in-place.

    Existing providers are updated; new ones are created.  Respects the
    ``EODAG_PROVIDERS_WHITELIST`` env-var when set.

    :param providers: Mutable dict to update.
    :param configs: Provider name → config mapping.
    """
    configs = _get_whitelisted_configs(configs)
    for name, conf in configs.items():
        if isinstance(conf, dict) and conf.get("name") != name:
            if "name" in conf:
                logger.debug(
                    "%s: config name '%s' overridden by dict key", name, conf["name"]
                )
            conf = {**conf, "name": name}
        elif isinstance(conf, ProviderConfig) and conf.name != name:
            raise ValidationError(
                f"ProviderConfig name '{conf.name}' must match dict key '{name}'"
            )

        try:
            if name in providers:
                providers[name].update_from_config(conf)
            else:
                providers[name] = Provider(conf)
            providers[name].collections_fetched = False
        except Exception:
            import traceback

            operation = "updating" if name in providers else "creating"
            logger.warning("%s: skipped %s due to invalid config", name, operation)
            logger.debug("Traceback:\n%s", traceback.format_exc())

    _share_credentials(providers)


def _parse_env_provider_configs() -> dict[str, dict[str, Any]]:
    """Parse ``EODAG__*`` environment variables into a config mapping."""

    def _build_mapping(env_var: str, env_value: str, mapping: dict[str, Any]) -> None:
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
            _build_mapping("__".join(parts[1:]), env_value, new_map)

    logger.debug("Loading configuration from environment variables")
    result: dict[str, dict[str, Any]] = {}
    for env_var in os.environ:
        if env_var.startswith("EODAG__"):
            _build_mapping(
                env_var[len("EODAG__"):].lower(),
                os.environ[env_var],
                result,
            )
    return result


def build_provider_configs(
    configs: Mapping[str, Union[ProviderConfig, dict[str, Any]]],
) -> dict[str, Provider]:
    """Build a ``dict[str, Provider]`` from a configuration mapping.

    :param configs: Provider name → config mapping.
    :returns: A plain dict of providers.
    """
    providers: dict[str, Provider] = {}
    merge_provider_configs(providers, configs)
    return providers


def load_provider_configs(
    default_config: Mapping[str, Union[ProviderConfig, dict[str, Any]]],
    *extra_configs: Mapping[str, Union[ProviderConfig, dict[str, Any]]],
    user_conf_file: Optional[str] = None,
    env_override: bool = True,
) -> dict[str, Provider]:
    """Build providers by merging default, extra, user-file and env configs.

    :param default_config: The base provider configuration mapping.
    :param extra_configs: Additional config mappings to merge (e.g. external plugins).
    :param user_conf_file: Path to a YAML user configuration file.
    :param env_override: Whether to apply ``EODAG__*`` environment variable overrides.
    :returns: A plain dict of providers.
    """
    providers = build_provider_configs(default_config)

    for cfg in extra_configs:
        merge_provider_configs(providers, cfg)

    if user_conf_file:
        logger.info("Loading user configuration from: %s", os.path.abspath(user_conf_file))
        try:
            with open(os.path.abspath(os.path.realpath(user_conf_file)), "r") as fh:
                config_in_file = yaml.safe_load(fh)
        except yaml.parser.ParserError as e:
            logger.error("Unable to load configuration file %s", user_conf_file)
            raise e
        if config_in_file:
            merge_provider_configs(providers, config_in_file)

    if env_override:
        env_configs = _parse_env_provider_configs()
        if env_configs:
            merge_provider_configs(providers, env_configs)

    return providers


def prune_providers(
    providers: dict[str, Provider],
    skipped_plugins: list[str],
    db: Any = None,
) -> None:
    """Remove providers that lack credentials, auth plugins, or use skipped plugins.

    Operates in-place on *providers*.  When *db* is provided, disabled
    providers are also marked as disabled in the database.

    :param providers: Mutable providers dict to prune.
    :param skipped_plugins: Plugin class names that failed to load.
    :param db: Optional :class:`~eodag.databases.sqlite.SQLiteDatabase` —
               when given, pruned providers are disabled in the DB.
    """

    def _remove(name: str) -> None:
        del providers[name]
        if db is not None:
            db.set_federation_backends_enabled([name], False)

    for name, provider in list(providers.items()):
        conf = provider.config

        # remove providers using skipped plugins
        if any(
            isinstance(v, PluginConfig) and getattr(v, "type", None) in skipped_plugins
            for v in conf.__dict__.values()
        ):
            _remove(name)
            logger.debug(
                "%s: provider needing unavailable plugin has been removed", provider
            )
            continue

        # check authentication
        if hasattr(conf, "api") and getattr(conf.api, "need_auth", False):
            if not credentials_in_auth(conf.api):
                _remove(name)
                logger.info(
                    "%s: provider needing auth for search has been pruned because no credentials could be found",
                    provider,
                )

        elif hasattr(conf, "search") and getattr(conf.search, "need_auth", False):
            if not hasattr(conf, "auth") and not hasattr(conf, "search_auth"):
                _remove(name)
                logger.info(
                    "%s: provider needing auth for search has been pruned because no auth plugin could be found",
                    provider,
                )
                continue

            credentials_exist = (
                hasattr(conf, "search_auth")
                and credentials_in_auth(conf.search_auth)
            ) or (
                not hasattr(conf, "search_auth")
                and hasattr(conf, "auth")
                and credentials_in_auth(conf.auth)
            )
            if not credentials_exist:
                _remove(name)
                logger.info(
                    "%s: provider needing auth for search has been pruned because no credentials could be found",
                    provider,
                )

        elif not hasattr(conf, "api") and not hasattr(conf, "search"):
            _remove(name)
            logger.info(
                "%s: provider has been pruned because no api or search plugin could be found",
                provider,
            )
