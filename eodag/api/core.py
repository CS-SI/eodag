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

import datetime
import logging
import os
import re
import shutil
import tempfile
import warnings
from collections import deque
from importlib.metadata import version
from importlib.resources import files as res_files
from operator import itemgetter
from typing import TYPE_CHECKING, Any, Iterator, Optional, Union

import geojson
import yaml.parser

from eodag.api.product.metadata_mapping import (
    NOT_AVAILABLE,
    mtd_cfg_as_conversion_and_querypath,
)
from eodag.api.search_result import SearchResult
from eodag.config import (
    PLUGINS_TOPICS_KEYS,
    PluginConfig,
    SimpleYamlProxyConfig,
    credentials_in_auth,
    get_ext_collections_conf,
    load_default_config,
    load_stac_provider_config,
    load_yml_config,
    override_config_from_env,
    override_config_from_file,
    override_config_from_mapping,
    provider_config_init,
    share_credentials,
)
from eodag.plugins.manager import PluginManager
from eodag.plugins.search import PreparedSearch
from eodag.plugins.search.build_search_result import (
    ALLOWED_KEYWORDS as ECMWF_ALLOWED_KEYWORDS,
)
from eodag.plugins.search.build_search_result import ECMWF_PREFIX, MeteoblueSearch
from eodag.plugins.search.qssearch import PostJsonSearch
from eodag.types import model_fields_to_annotated
from eodag.types.queryables import CommonQueryables, Queryables, QueryablesDict
from eodag.utils import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    DEFAULT_ITEMS_PER_PAGE,
    DEFAULT_MAX_ITEMS_PER_PAGE,
    DEFAULT_PAGE,
    GENERIC_COLLECTION,
    GENERIC_STAC_PROVIDER,
    get_collection_dates,
    get_geometry_from_various,
    makedirs,
    sort_dict,
    string_to_jsonpath,
    uri_to_path,
)
from eodag.utils.dates import rfc3339_str_to_datetime
from eodag.utils.env import is_env_var_true
from eodag.utils.exceptions import (
    AuthenticationError,
    NoMatchingCollection,
    PluginImplementationError,
    RequestError,
    UnsupportedCollection,
    UnsupportedProvider,
)
from eodag.utils.free_text_search import compile_free_text_query
from eodag.utils.stac_reader import fetch_stac_items

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

    from eodag.api.product import EOProduct
    from eodag.plugins.apis.base import Api
    from eodag.plugins.crunch.base import Crunch
    from eodag.plugins.search.base import Search
    from eodag.types import ProviderSortables
    from eodag.types.download_args import DownloadConf
    from eodag.utils import DownloadedCallback, ProgressCallback, Unpack

logger = logging.getLogger("eodag.core")


class EODataAccessGateway:
    """An API for downloading a wide variety of geospatial products originating
    from different types of providers.

    :param user_conf_file_path: (optional) Path to the user configuration file
    :param locations_conf_path: (optional) Path to the locations configuration file
    """

    def __init__(
        self,
        user_conf_file_path: Optional[str] = None,
        locations_conf_path: Optional[str] = None,
    ) -> None:
        collections_config_path = os.getenv("EODAG_COLLECTIONS_CFG_FILE") or str(
            res_files("eodag") / "resources" / "collections.yml"
        )
        self.collections_config = SimpleYamlProxyConfig(collections_config_path)
        self.providers_config = load_default_config()

        env_var_cfg_dir = "EODAG_CFG_DIR"
        self.conf_dir = os.getenv(
            env_var_cfg_dir,
            default=os.path.join(os.path.expanduser("~"), ".config", "eodag"),
        )
        try:
            makedirs(self.conf_dir)
        except OSError as e:
            logger.debug(e)
            tmp_conf_dir = os.path.join(tempfile.gettempdir(), ".config", "eodag")
            logger.warning(
                f"Cannot create configuration directory {self.conf_dir}. "
                + f"Falling back to temporary directory {tmp_conf_dir}."
            )
            if os.getenv(env_var_cfg_dir) is None:
                logger.warning(
                    "You can set the path of the configuration directory "
                    + f"with the environment variable {env_var_cfg_dir}"
                )
            self.conf_dir = tmp_conf_dir
            makedirs(self.conf_dir)

        self._plugins_manager = PluginManager(self.providers_config)
        # use updated providers_config
        self.providers_config = self._plugins_manager.providers_config

        # First level override: From a user configuration file
        if user_conf_file_path is None:
            env_var_name = "EODAG_CFG_FILE"
            standard_configuration_path = os.path.join(self.conf_dir, "eodag.yml")
            user_conf_file_path = os.getenv(env_var_name)
            if user_conf_file_path is None:
                user_conf_file_path = standard_configuration_path
                if not os.path.isfile(standard_configuration_path):
                    shutil.copy(
                        str(
                            res_files("eodag") / "resources" / "user_conf_template.yml"
                        ),
                        standard_configuration_path,
                    )
        override_config_from_file(self.providers_config, user_conf_file_path)

        # Second level override: From environment variables
        override_config_from_env(self.providers_config)

        # share credentials between updated plugins confs
        share_credentials(self.providers_config)

        # init updated providers conf
        strict_mode = is_env_var_true("EODAG_STRICT_COLLECTIONS")
        available_collections = set(self.collections_config.source.keys())

        for provider in self.providers_config.keys():
            provider_config_init(
                self.providers_config[provider],
                load_stac_provider_config(),
            )

            self._sync_provider_collections(
                provider, available_collections, strict_mode
            )
        # init collections configuration
        self._collections_config_init()

        # re-build _plugins_manager using up-to-date providers_config
        self._plugins_manager.rebuild(self.providers_config)

        # store pruned providers configs
        self._pruned_providers_config: dict[str, Any] = {}
        # filter out providers needing auth that have no credentials set
        self._prune_providers_list()

        # Sort providers taking into account of possible new priority orders
        self._plugins_manager.sort_providers()

        # set locations configuration
        if locations_conf_path is None:
            locations_conf_path = os.getenv("EODAG_LOCS_CFG_FILE")
            if locations_conf_path is None:
                locations_conf_path = os.path.join(self.conf_dir, "locations.yml")
                if not os.path.isfile(locations_conf_path):
                    # copy locations conf file and replace path example
                    locations_conf_template = str(
                        res_files("eodag") / "resources" / "locations_conf_template.yml"
                    )
                    with (
                        open(locations_conf_template) as infile,
                        open(locations_conf_path, "w") as outfile,
                    ):
                        # The template contains paths in the form of:
                        # /path/to/locations/file.shp
                        path_template = "/path/to/locations/"
                        for line in infile:
                            line = line.replace(
                                path_template,
                                os.path.join(self.conf_dir, "shp") + os.path.sep,
                            )
                            outfile.write(line)
                    # copy sample shapefile dir
                    shutil.copytree(
                        str(res_files("eodag") / "resources" / "shp"),
                        os.path.join(self.conf_dir, "shp"),
                    )
        self.set_locations_conf(locations_conf_path)

    def _collections_config_init(self) -> None:
        """Initialize collections configuration."""
        for pt_id, pd_dict in self.collections_config.source.items():
            self.collections_config.source[pt_id].setdefault("_id", pt_id)

    def _sync_provider_collections(
        self,
        provider: str,
        available_collections: set[str],
        strict_mode: bool,
    ) -> None:
        """
        Synchronize collections for a provider based on strict or permissive mode.

        In strict mode, removes collections not in available_collections.
        In permissive mode, adds empty collection configs for missing types.

        :param provider: The provider name whose collections should be synchronized.
        :param available_collections: The set of available collection IDs.
        :param strict_mode: If True, remove unknown collections; if False, add empty configs for them.
        :returns: None
        """
        provider_products = self.providers_config[provider].products
        products_to_remove: list[str] = []
        products_to_add: list[str] = []

        for product_id in provider_products:
            if product_id == GENERIC_COLLECTION:
                continue

            if product_id not in available_collections:
                if strict_mode:
                    products_to_remove.append(product_id)
                    continue

                empty_product = {
                    "title": product_id,
                    "description": NOT_AVAILABLE,
                }
                self.collections_config.source[
                    product_id
                ] = empty_product  # will update available_collections
                products_to_add.append(product_id)

        if products_to_add:
            logger.debug(
                "Collections permissive mode, %s added (provider %s)",
                ", ".join(products_to_add),
                provider,
            )

        if products_to_remove:
            logger.debug(
                "Collections strict mode, ignoring %s (provider %s)",
                ", ".join(products_to_remove),
                provider,
            )
            for id in products_to_remove:
                del self.providers_config[provider].products[id]

    def get_version(self) -> str:
        """Get eodag package version"""
        return version("eodag")

    def set_preferred_provider(self, provider: str) -> None:
        """Set max priority for the given provider.

        :param provider: The name of the provider that should be considered as the
                         preferred provider to be used for this instance
        """
        if provider not in self.available_providers():
            raise UnsupportedProvider(
                f"This provider is not recognised by eodag: {provider}"
            )
        preferred_provider, max_priority = self.get_preferred_provider()
        if preferred_provider != provider:
            new_priority = max_priority + 1
            self._plugins_manager.set_priority(provider, new_priority)

    def get_preferred_provider(self) -> tuple[str, int]:
        """Get the provider currently set as the preferred one for searching
        products, along with its priority.

        :returns: The provider with the maximum priority and its priority
        """
        providers_with_priority = [
            (provider, conf.priority)
            for provider, conf in self.providers_config.items()
        ]
        preferred, priority = max(providers_with_priority, key=itemgetter(1))
        return preferred, priority

    def update_providers_config(
        self,
        yaml_conf: Optional[str] = None,
        dict_conf: Optional[dict[str, Any]] = None,
    ) -> None:
        """Update providers configuration with given input.
        Can be used to add a provider to existing configuration or update
        an existing one.

        :param yaml_conf: YAML formated provider configuration
        :param dict_conf: provider configuration as dictionary in place of ``yaml_conf``
        """
        if dict_conf is not None:
            conf_update = dict_conf
        elif yaml_conf is not None:
            conf_update = yaml.safe_load(yaml_conf)
        else:
            return None

        # restore the pruned configuration
        for provider in list(self._pruned_providers_config.keys()):
            if provider in conf_update:
                logger.info(
                    "%s: provider restored from the pruned configurations",
                    provider,
                )
                self.providers_config[provider] = self._pruned_providers_config.pop(
                    provider
                )

        override_config_from_mapping(self.providers_config, conf_update)

        # share credentials between updated plugins confs
        share_credentials(self.providers_config)

        for provider in conf_update.keys():
            provider_config_init(
                self.providers_config[provider],
                load_stac_provider_config(),
            )
            setattr(self.providers_config[provider], "collections_fetched", False)
        # re-create _plugins_manager using up-to-date providers_config
        self._plugins_manager.build_collection_to_provider_config_map()

    def add_provider(
        self,
        name: str,
        url: Optional[str] = None,
        priority: Optional[int] = None,
        search: dict[str, Any] = {"type": "StacSearch"},
        products: dict[str, Any] = {
            GENERIC_COLLECTION: {"_collection": "{collection}"}
        },
        download: dict[str, Any] = {"type": "HTTPDownload", "auth_error_code": 401},
        **kwargs: dict[str, Any],
    ):
        """Adds a new provider.

        ``search``, ``products`` & ``download`` already have default values that will be
        updated (not replaced), with user provided ones:

            * ``search`` : ``{"type": "StacSearch"}``
            * ``products`` : ``{"GENERIC_COLLECTION": {"_collection": "{collection}"}}``
            * ``download`` : ``{"type": "HTTPDownload", "auth_error_code": 401}``

        :param name: Name of provider
        :param url: Provider url, also used as ``search["api_endpoint"]`` if not defined
        :param priority: Provider priority. If None, provider will be set as preferred (highest priority)
        :param search: Search :class:`~eodag.config.PluginConfig` mapping
        :param products: Provider collections mapping
        :param download: Download :class:`~eodag.config.PluginConfig` mapping
        :param kwargs: Additional :class:`~eodag.config.ProviderConfig` mapping
        """
        conf_dict: dict[str, Any] = {
            name: {
                "url": url,
                "search": {"type": "StacSearch", **search},
                "products": {
                    GENERIC_COLLECTION: {"_collection": "{collection}"},
                    **products,
                },
                "download": {
                    "type": "HTTPDownload",
                    "auth_error_code": 401,
                    **download,
                },
                **kwargs,
            }
        }
        if priority is not None:
            conf_dict[name]["priority"] = priority
        # if provided, use url as default search api_endpoint
        if (
            url
            and conf_dict[name].get("search", {})
            and not conf_dict[name]["search"].get("api_endpoint")
        ):
            conf_dict[name]["search"]["api_endpoint"] = url

        # api plugin usage: remove unneeded search/download/auth plugin conf
        if conf_dict[name].get("api"):
            for k in PLUGINS_TOPICS_KEYS:
                if k != "api":
                    conf_dict[name].pop(k, None)

        self.update_providers_config(dict_conf=conf_dict)

        if priority is None:
            self.set_preferred_provider(name)

    def _prune_providers_list(self) -> None:
        """Removes from config providers needing auth that have no credentials set."""
        update_needed = False
        for provider in list(self.providers_config.keys()):
            conf = self.providers_config[provider]

            # remove providers using skipped plugins
            if [
                v
                for v in conf.__dict__.values()
                if isinstance(v, PluginConfig)
                and getattr(v, "type", None) in self._plugins_manager.skipped_plugins
            ]:
                self.providers_config.pop(provider)
                logger.debug(
                    f"{provider}: provider needing unavailable plugin has been removed"
                )
                continue

            # check authentication
            if hasattr(conf, "api") and getattr(conf.api, "need_auth", False):
                credentials_exist = credentials_in_auth(conf.api)
                if not credentials_exist:
                    # credentials needed but not found
                    self._pruned_providers_config[provider] = self.providers_config.pop(
                        provider
                    )
                    update_needed = True
                    logger.info(
                        "%s: provider needing auth for search has been pruned because no credentials could be found",
                        provider,
                    )
            elif hasattr(conf, "search") and getattr(conf.search, "need_auth", False):
                if not hasattr(conf, "auth") and not hasattr(conf, "search_auth"):
                    # credentials needed but no auth plugin was found
                    self._pruned_providers_config[provider] = self.providers_config.pop(
                        provider
                    )
                    update_needed = True
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
                    # credentials needed but not found
                    self._pruned_providers_config[provider] = self.providers_config.pop(
                        provider
                    )
                    update_needed = True
                    logger.info(
                        "%s: provider needing auth for search has been pruned because no credentials could be found",
                        provider,
                    )
            elif not hasattr(conf, "api") and not hasattr(conf, "search"):
                # provider should have at least an api or search plugin
                self._pruned_providers_config[provider] = self.providers_config.pop(
                    provider
                )
                logger.info(
                    "%s: provider has been pruned because no api or search plugin could be found",
                    provider,
                )
                update_needed = True

        if update_needed:
            # rebuild _plugins_manager with updated providers list
            self._plugins_manager.rebuild(self.providers_config)

    def set_locations_conf(self, locations_conf_path: str) -> None:
        """Set locations configuration.
        This configuration (YML format) will contain a shapefile list associated
        to a name and attribute parameters needed to identify the needed geometry.
        You can also configure parent attributes, which can be used for creating
        a catalogs path when using eodag as a REST server.
        Example of locations configuration file content:

        .. code-block:: yaml

            shapefiles:
                - name: country
                  path: /path/to/countries_list.shp
                  attr: ISO3
                - name: department
                  path: /path/to/FR_departments.shp
                  attr: code_insee
                  parent:
                    name: country
                    attr: FRA

        :param locations_conf_path: Path to the locations configuration file
        """
        if os.path.isfile(locations_conf_path):
            locations_config = load_yml_config(locations_conf_path)

            main_key = next(iter(locations_config))
            main_locations_config = locations_config[main_key]

            logger.info("Locations configuration loaded from %s" % locations_conf_path)
            self.locations_config: list[dict[str, Any]] = main_locations_config
        else:
            logger.info(
                "Could not load locations configuration from %s" % locations_conf_path
            )
            self.locations_config = []

    def list_collections(
        self, provider: Optional[str] = None, fetch_providers: bool = True
    ) -> list[dict[str, Any]]:
        """Lists supported collections.

        :param provider: (optional) The name of a provider that must support the product
                         types we are about to list
        :param fetch_providers: (optional) Whether to fetch providers for new product
                                types or not
        :returns: The list of the collections that can be accessed using eodag.
        :raises: :class:`~eodag.utils.exceptions.UnsupportedProvider`
        """
        if fetch_providers:
            # First, update collections list if possible
            self.fetch_collections_list(provider=provider)

        collections: list[dict[str, Any]] = []

        providers_configs = (
            list(self.providers_config.values())
            if not provider
            else [
                p
                for p in self.providers_config.values()
                if provider in [p.name, getattr(p, "group", None)]
            ]
        )

        if provider and not providers_configs:
            raise UnsupportedProvider(
                f"The requested provider is not (yet) supported: {provider}"
            )

        for p in providers_configs:
            for collection_id in p.products:  # type: ignore
                if collection_id == GENERIC_COLLECTION:
                    continue

                config = self.collections_config[collection_id]
                if "alias" in config:
                    collection_id = config["alias"]
                collection = {"ID": collection_id, **config}

                if collection not in collections:
                    collections.append(collection)

        # Return the collections sorted in lexicographic order of their ID
        return sorted(collections, key=itemgetter("ID"))

    def fetch_collections_list(self, provider: Optional[str] = None) -> None:
        """Fetch collections list and update if needed.

        If strict mode is enabled (by setting the ``EODAG_STRICT_COLLECTIONS`` environment variable
        to a truthy value), this method will not fetch or update collections and will return immediately.

        :param provider: The name of a provider or provider-group for which collections
                         list should be updated. Defaults to all providers (None value).
        """
        strict_mode = is_env_var_true("EODAG_STRICT_COLLECTIONS")
        if strict_mode:
            return

        providers_to_fetch = list(self.providers_config.keys())
        # check if some providers are grouped under a group name which is not a provider name
        if provider is not None and provider not in self.providers_config:
            providers_to_fetch = [
                p
                for p, pconf in self.providers_config.items()
                if provider == getattr(pconf, "group", None)
            ]
            if providers_to_fetch:
                logger.info(
                    f"Fetch collections for {provider} group: {', '.join(providers_to_fetch)}"
                )
            else:
                return None
        elif provider is not None:
            providers_to_fetch = [provider]

        # providers discovery confs that are fetchable
        providers_discovery_configs_fetchable: dict[str, Any] = {}
        # check if any provider has not already been fetched for collections
        already_fetched = True
        for provider_to_fetch in providers_to_fetch:
            provider_config = self.providers_config[provider_to_fetch]
            # get discovery conf
            if hasattr(provider_config, "search"):
                provider_search_config = provider_config.search
            elif hasattr(provider_config, "api"):
                provider_search_config = provider_config.api
            else:
                continue
            discovery_conf = getattr(provider_search_config, "discover_collections", {})
            if discovery_conf.get("fetch_url"):
                providers_discovery_configs_fetchable[
                    provider_to_fetch
                ] = discovery_conf
                if not getattr(provider_config, "collections_fetched", False):
                    already_fetched = False

        if not already_fetched:
            # get ext_collections conf
            ext_collections_cfg_file = os.getenv("EODAG_EXT_COLLECTIONS_CFG_FILE")
            if ext_collections_cfg_file is not None:
                ext_collections_conf = get_ext_collections_conf(
                    ext_collections_cfg_file
                )
            else:
                ext_collections_conf = get_ext_collections_conf()

                if not ext_collections_conf:
                    # empty ext_collections conf
                    ext_collections_conf = (
                        self.discover_collections(provider=provider) or {}
                    )

            # update eodag collections list with new conf
            self.update_collections_list(ext_collections_conf)

        # Compare current provider with default one to see if it has been modified
        # and collections list would need to be fetched

        # get ext_collections conf for user modified providers
        default_providers_config = load_default_config()
        for (
            provider,
            user_discovery_conf,
        ) in providers_discovery_configs_fetchable.items():
            # default discover_collections conf
            if provider in default_providers_config:
                default_provider_config = default_providers_config[provider]
                if hasattr(default_provider_config, "search"):
                    default_provider_search_config = default_provider_config.search
                elif hasattr(default_provider_config, "api"):
                    default_provider_search_config = default_provider_config.api
                else:
                    continue
                default_discovery_conf = getattr(
                    default_provider_search_config, "discover_collections", {}
                )
                # compare confs
                if default_discovery_conf["result_type"] == "json" and isinstance(
                    default_discovery_conf["results_entry"], str
                ):
                    default_discovery_conf_parsed = dict(
                        default_discovery_conf,
                        **{
                            "results_entry": string_to_jsonpath(
                                default_discovery_conf["results_entry"], force=True
                            )
                        },
                        **mtd_cfg_as_conversion_and_querypath(
                            dict(
                                generic_collection_id=default_discovery_conf[
                                    "generic_collection_id"
                                ]
                            )
                        ),
                        **dict(
                            generic_collection_parsable_properties=mtd_cfg_as_conversion_and_querypath(
                                default_discovery_conf[
                                    "generic_collection_parsable_properties"
                                ]
                            )
                        ),
                        **dict(
                            generic_collection_parsable_metadata=mtd_cfg_as_conversion_and_querypath(
                                default_discovery_conf[
                                    "generic_collection_parsable_metadata"
                                ]
                            )
                        ),
                    )
                else:
                    default_discovery_conf_parsed = default_discovery_conf
                if (
                    user_discovery_conf == default_discovery_conf
                    or user_discovery_conf == default_discovery_conf_parsed
                ) and (
                    not default_discovery_conf.get("fetch_url")
                    or "ext_collections_conf" not in locals()
                    or "ext_collections_conf" in locals()
                    and (
                        provider in ext_collections_conf
                        or len(ext_collections_conf.keys()) == 0
                    )
                ):
                    continue
                # providers not skipped here should be user-modified
                # or not in ext_collections_conf (if eodag system conf != eodag conf used for ext_collections_conf)

            if not already_fetched:
                # discover collections for user configured provider
                provider_ext_collections_conf = (
                    self.discover_collections(provider=provider) or {}
                )
                # update eodag collections list with new conf
                self.update_collections_list(provider_ext_collections_conf)

    def discover_collections(
        self, provider: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """Fetch providers for collections

        :param provider: The name of a provider or provider-group to fetch. Defaults to
                         all providers (None value).
        :returns: external collections configuration
        """
        grouped_providers = [
            p
            for p, provider_config in self.providers_config.items()
            if provider == getattr(provider_config, "group", None)
        ]
        if provider and provider not in self.providers_config and grouped_providers:
            logger.info(
                f"Discover collections for {provider} group: {', '.join(grouped_providers)}"
            )
        elif provider and provider not in self.providers_config:
            raise UnsupportedProvider(
                f"The requested provider is not (yet) supported: {provider}"
            )
        ext_collections_conf: dict[str, Any] = {}
        providers_to_fetch = [
            p
            for p in (
                [
                    p
                    for p in self.providers_config
                    if p in grouped_providers + [provider]
                ]
                if provider
                else self.available_providers()
            )
        ]
        kwargs: dict[str, Any] = {}
        for provider in providers_to_fetch:
            if hasattr(self.providers_config[provider], "search"):
                search_plugin_config = self.providers_config[provider].search
            elif hasattr(self.providers_config[provider], "api"):
                search_plugin_config = self.providers_config[provider].api
            else:
                return None
            if getattr(search_plugin_config, "discover_collections", {}).get(
                "fetch_url", None
            ):
                search_plugin: Union[Search, Api] = next(
                    self._plugins_manager.get_search_plugins(provider=provider)
                )
                # check after plugin init if still fetchable
                if not getattr(search_plugin.config, "discover_collections", {}).get(
                    "fetch_url"
                ):
                    continue
                # append auth to search plugin if needed
                if getattr(search_plugin.config, "need_auth", False):
                    if auth := self._plugins_manager.get_auth(
                        search_plugin.provider,
                        getattr(search_plugin.config, "api_endpoint", None),
                        search_plugin.config,
                    ):
                        kwargs["auth"] = auth
                    else:
                        logger.debug(
                            f"Could not authenticate on {provider} for collections discovery"
                        )
                        ext_collections_conf[provider] = None
                        continue

                ext_collections_conf[provider] = search_plugin.discover_collections(
                    **kwargs
                )

        return sort_dict(ext_collections_conf)

    def update_collections_list(
        self, ext_collections_conf: dict[str, Optional[dict[str, dict[str, Any]]]]
    ) -> None:
        """Update eodag collections list

        :param ext_collections_conf: external collections configuration
        """
        for provider, new_collections_conf in ext_collections_conf.items():
            if new_collections_conf and provider in self.providers_config:
                try:
                    search_plugin_config = getattr(
                        self.providers_config[provider], "search", None
                    ) or getattr(self.providers_config[provider], "api", None)
                    if search_plugin_config is None:
                        continue
                    if not getattr(
                        search_plugin_config, "discover_collections", {}
                    ).get("fetch_url"):
                        # conf has been updated and provider collections are no more discoverable
                        continue
                    provider_products_config = (
                        self.providers_config[provider].products or {}
                    )
                except UnsupportedProvider:
                    logger.debug(
                        "Ignoring external collections for unknown provider %s",
                        provider,
                    )
                    continue
                new_collections: list[str] = []
                for (
                    new_collection,
                    new_collection_conf,
                ) in new_collections_conf["providers_config"].items():
                    if new_collection not in provider_products_config:
                        for existing_collection in provider_products_config.copy():
                            # compare parsed extracted conf (without metadata_mapping entry)
                            unparsable_keys = (
                                search_plugin_config.discover_collections.get(
                                    "generic_collection_unparsable_properties", {}
                                ).keys()
                            )
                            new_parsed_collections_conf = {
                                k: v
                                for k, v in new_collection_conf.items()
                                if k not in unparsable_keys
                            }
                            if (
                                new_parsed_collections_conf.items()
                                <= provider_products_config[existing_collection].items()
                            ):
                                # new_collections_conf is a subset on an existing conf
                                break
                        else:
                            # new_collection_conf does not already exist, append it
                            # to provider_products_config
                            provider_products_config[
                                new_collection
                            ] = new_collection_conf
                            # to self.collections_config
                            self.collections_config.source.update(
                                {
                                    new_collection: {"_id": new_collection}
                                    | new_collections_conf["collections_config"][
                                        new_collection
                                    ]
                                }
                            )
                            ext_collections_conf[provider] = new_collections_conf
                            new_collections.append(new_collection)
                if new_collections:
                    logger.debug(
                        f"Added {len(new_collections)} collections for {provider}"
                    )

            elif provider not in self.providers_config:
                # unknown provider
                continue
            self.providers_config[provider].collections_fetched = True

        # re-create _plugins_manager using up-to-date providers_config
        self._plugins_manager.build_collection_to_provider_config_map()

    def available_providers(
        self, collection: Optional[str] = None, by_group: bool = False
    ) -> list[str]:
        """Gives the sorted list of the available providers or groups

        The providers or groups are sorted first by their priority level in descending order,
        and then alphabetically in ascending order for providers or groups with the same
        priority level.

        :param collection: (optional) Only list providers configured for this collection
        :param by_group: (optional) If set to True, list groups when available instead
                         of providers, mixed with other providers
        :returns: the sorted list of the available providers or groups
        """

        if collection:
            providers = [
                (v.group if by_group and hasattr(v, "group") else k, v.priority)
                for k, v in self.providers_config.items()
                if collection in getattr(v, "products", {}).keys()
            ]
        else:
            providers = [
                (v.group if by_group and hasattr(v, "group") else k, v.priority)
                for k, v in self.providers_config.items()
            ]

        # If by_group is True, keep only the highest priority for each group
        if by_group:
            group_priority: dict[str, int] = {}
            for name, priority in providers:
                if name not in group_priority or priority > group_priority[name]:
                    group_priority[name] = priority
            providers = list(group_priority.items())

        # Sort by priority (descending) and then by name (ascending)
        providers.sort(key=lambda x: (-x[1], x[0]))

        # Return only the names of the providers or groups
        return [name for name, _ in providers]

    def get_collection_from_alias(self, alias_or_id: str) -> str:
        """Return the ID of a collection by either its ID or alias

        :param alias_or_id: Alias of the collection. If an existing ID is given, this
                            method will directly return the given value.
        :returns: Internal name of the collection.
        """
        collections = [
            k
            for k, v in self.collections_config.items()
            if v.get("alias") == alias_or_id
        ]

        if len(collections) > 1:
            raise NoMatchingCollection(
                f"Too many matching collections for alias {alias_or_id}: {collections}"
            )

        if len(collections) == 0:
            if alias_or_id in self.collections_config:
                return alias_or_id
            else:
                raise NoMatchingCollection(
                    f"Could not find collection from alias or ID {alias_or_id}"
                )

        return collections[0]

    def get_alias_from_collection(self, collection: str) -> str:
        """Return the alias of a collection by its ID. If no alias was defined for the
        given collection, its ID is returned instead.

        :param collection: collection ID
        :returns: Alias of the collection or its ID if no alias has been defined for it.
        """
        if collection not in self.collections_config:
            raise NoMatchingCollection(collection)

        return self.collections_config[collection].get("alias", collection)

    def guess_collection(
        self,
        free_text: Optional[str] = None,
        intersect: bool = False,
        instruments: Optional[str] = None,
        platform: Optional[str] = None,
        constellation: Optional[str] = None,
        processing_level: Optional[str] = None,
        sensor_type: Optional[str] = None,
        keywords: Optional[str] = None,
        description: Optional[str] = None,
        title: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs: Any,
    ) -> list[str]:
        """
        Find EODAG collection IDs that best match a set of search parameters.

        When using several filters, collections that match most of them will be returned at first.

        :param free_text: Free text search filter used to search accross all the following parameters. Handles logical
                          operators with parenthesis (``AND``/``OR``/``NOT``), quoted phrases (``"exact phrase"``),
                          ``*`` and ``?`` wildcards.
        :param intersect: Join results for each parameter using INTERSECT instead of UNION.
        :param instruments: Instruments parameter.
        :param platform: Platform parameter.
        :param constellation: Constellation parameter.
        :param processing_level: Processing level parameter.
        :param sensor_type: Sensor type parameter.
        :param keywords: Keywords parameter.
        :param description: description parameter.
        :param title: Title parameter.
        :param start_date: start date for datetime filtering. Not used by free_text
        :param end_date: end date for datetime filtering. Not used by free_text
        :returns: The best match for the given parameters.
        :raises: :class:`~eodag.utils.exceptions.NoMatchingCollection`
        """
        if collection := kwargs.get("collection"):
            return [collection]

        filters: dict[str, str] = {
            k: v
            for k, v in {
                "instruments": instruments,
                "constellation": constellation,
                "platform": platform,
                "processing:level": processing_level,
                "eodag:sensor_type": sensor_type,
                "keywords": keywords,
                "description": description,
                "title": title,
            }.items()
            if v is not None
        }

        only_dates = (
            True
            if (not free_text and not filters and (start_date or end_date))
            else False
        )

        free_text_evaluator = (
            compile_free_text_query(free_text) if free_text else lambda _: True
        )

        guesses_with_score: list[tuple[str, int]] = []

        for pt_id, pt_dict in self.collections_config.source.items():
            if (
                pt_id == GENERIC_COLLECTION
                or pt_id not in self._plugins_manager.collection_to_provider_config_map
            ):
                continue

            score = 0  # how many filters matched

            # free text search
            if free_text:
                match = free_text_evaluator(pt_dict)
                if match:
                    score += 1
                elif intersect:
                    continue  # must match all filters

            # individual filters
            if filters:
                filters_matching_method = all if intersect else any
                filters_evaluators = {
                    filter_name: compile_free_text_query(value)
                    for filter_name, value in filters.items()
                    if value is not None
                }

                filter_matches = [
                    filters_evaluators[filter_name]({filter_name: pt_dict[filter_name]})
                    for filter_name, value in filters.items()
                    if filter_name in pt_dict
                ]

                if filters_matching_method(filter_matches):
                    # add number of True matches to score
                    score += sum(filter_matches)
                elif intersect:
                    continue  # must match all filters

            if score == 0 and not only_dates:
                continue

            # datetime filtering
            if start_date or end_date:
                min_aware = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
                max_aware = datetime.datetime.max.replace(tzinfo=datetime.timezone.utc)

                col_start, col_end = get_collection_dates(pt_dict)

                max_start = max(
                    rfc3339_str_to_datetime(start_date) if start_date else min_aware,
                    rfc3339_str_to_datetime(col_start) if col_start else min_aware,
                )
                min_end = min(
                    rfc3339_str_to_datetime(end_date) if end_date else max_aware,
                    rfc3339_str_to_datetime(col_end) if col_end else max_aware,
                )
                if not (max_start <= min_end):
                    continue

            pt_alias = pt_dict.get("alias", pt_id)
            guesses_with_score.append((pt_alias, score))

        if guesses_with_score:
            # sort by score descending, then pt_id for stability
            guesses_with_score.sort(key=lambda x: (-x[1], x[0]))
            return [pt_id for pt_id, _ in guesses_with_score]

        raise NoMatchingCollection()

    def search(
        self,
        page: int = DEFAULT_PAGE,
        items_per_page: Optional[int] = DEFAULT_ITEMS_PER_PAGE,
        raise_errors: bool = False,
        start: Optional[str] = None,
        end: Optional[str] = None,
        geom: Optional[Union[str, dict[str, float], BaseGeometry]] = None,
        locations: Optional[dict[str, str]] = None,
        provider: Optional[str] = None,
        count: bool = False,
        validate: Optional[bool] = True,
        **kwargs: Any,
    ) -> SearchResult:
        """Look for products matching criteria on known providers.

        The default behaviour is to look for products on the provider with the
        highest priority supporting the requested collection. These priorities
        are configurable through user configuration file or individual environment variable.
        If the request to the provider with the highest priority fails or is empty, the data
        will be request from the provider with the next highest priority.
        Only if the request fails for all available providers, an error will be thrown.

        :param page: (optional) The page number to return (**deprecated**, use
                     :meth:`eodag.api.search_result.SearchResult.next_page` instead)
        :param items_per_page: (optional) The number of results that must appear in one single
                               page. If ``None``, the maximum number possible will be used.
        :param raise_errors:  (optional) When an error occurs when searching, if this is set to
                              True, the error is raised
        :param start: (optional) Start sensing time in ISO 8601 format (e.g. "1990-11-26",
                      "1990-11-26T14:30:10.153Z", "1990-11-26T14:30:10+02:00", ...).
                      If no time offset is given, the time is assumed to be given in UTC.
        :param end: (optional) End sensing time in ISO 8601 format (e.g. "1990-11-26",
                    "1990-11-26T14:30:10.153Z", "1990-11-26T14:30:10+02:00", ...).
                    If no time offset is given, the time is assumed to be given in UTC.
        :param geom: (optional) Search area that can be defined in different ways:

                     * with a Shapely geometry object:
                       :class:`shapely.geometry.base.BaseGeometry`
                     * with a bounding box (dict with keys: "lonmin", "latmin", "lonmax", "latmax"):
                       ``dict.fromkeys(["lonmin", "latmin", "lonmax", "latmax"])``
                     * with a bounding box as list of float:
                       ``[lonmin, latmin, lonmax, latmax]``
                     * with a WKT str
        :param locations: (optional) Location filtering by name using locations configuration
                          ``{"<location_name>"="<attr_regex>"}``. For example, ``{"country"="PA."}`` will use
                          the geometry of the features having the property ISO3 starting with
                          'PA' such as Panama and Pakistan in the shapefile configured with
                          name=country and attr=ISO3
        :param provider: (optional) the provider to be used. If set, search fallback will be disabled.
                         If not set, the configured preferred provider will be used at first
                         before trying others until finding results.
        :param count: (optional) Whether to run a query with a count request or not
        :param validate: (optional) Set to True to validate search parameters
                         before sending the query to the provider
        :param kwargs: Some other criteria that will be used to do the search,
                       using paramaters compatibles with the provider
        :returns: A set of EO products matching the criteria

        .. versionchanged:: v3.0.0b1
            ``search()`` method now returns only a single :class:`~eodag.api.search_result.SearchResult`
            instead of a 2 values tuple.

        .. note::
            The search interfaces, which are implemented as plugins, are required to
            return a list as a result of their processing. This requirement is
            enforced here.
        """
        if page != DEFAULT_PAGE:
            warnings.warn(
                "Usage of deprecated search parameter 'page' "
                "(Please use 'SearchResult.next_page()' instead)"
                " -- Deprecated since v3.9.0",
                DeprecationWarning,
                stacklevel=2,
            )

        search_plugins, search_kwargs = self._prepare_search(
            start=start,
            end=end,
            geom=geom,
            locations=locations,
            provider=provider,
            **kwargs,
        )
        if search_kwargs.get("id"):
            # Don't validate requests by ID. "id" is not queryable.
            return self._search_by_id(
                search_kwargs.pop("id"),
                provider=provider,
                raise_errors=raise_errors,
                validate=False,
                **search_kwargs,
            )
        # remove datacube query string from kwargs which was only needed for search-by-id
        search_kwargs.pop("_dc_qs", None)
        # add page parameter
        search_kwargs["page"] = page

        errors: list[tuple[str, Exception]] = []
        # Loop over available providers and return the first non-empty results
        for i, search_plugin in enumerate(search_plugins):
            search_plugin.clear()

            # add appropriate items_per_page value
            search_kwargs["items_per_page"] = (
                items_per_page
                if items_per_page is not None
                else getattr(search_plugin.config, "pagination", {}).get(
                    "max_items_per_page", DEFAULT_MAX_ITEMS_PER_PAGE
                )
            )

            search_results = self._do_search(
                search_plugin,
                count=count,
                raise_errors=raise_errors,
                validate=validate,
                **search_kwargs,
            )
            errors.extend(search_results.errors)
            if len(search_results) == 0 and i < len(search_plugins) - 1:
                logger.warning(
                    f"No result could be obtained from provider {search_plugin.provider}, "
                    "we will try to get the data from another provider",
                )
            elif len(search_results) > 0:
                search_results.errors = errors
                return search_results

        if i > 1:
            logger.error("No result could be obtained from any available provider")
        return SearchResult([], 0, errors) if count else SearchResult([], errors=errors)

    @_deprecated(
        reason="Please use 'SearchResult.next_page()' instead",
        version="v3.9.0",
    )
    def search_iter_page(
        self,
        items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
        start: Optional[str] = None,
        end: Optional[str] = None,
        geom: Optional[Union[str, dict[str, float], BaseGeometry]] = None,
        locations: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> Iterator[SearchResult]:
        """Iterate over the pages of a products search.

        .. deprecated:: v3.9.0
            Please use :meth:`eodag.api.search_result.SearchResult.next_page` instead.

        :param items_per_page: (optional) The number of results requested per page
        :param start: (optional) Start sensing time in ISO 8601 format (e.g. "1990-11-26",
                      "1990-11-26T14:30:10.153Z", "1990-11-26T14:30:10+02:00", ...).
                      If no time offset is given, the time is assumed to be given in UTC.
        :param end: (optional) End sensing time in ISO 8601 format (e.g. "1990-11-26",
                    "1990-11-26T14:30:10.153Z", "1990-11-26T14:30:10+02:00", ...).
                    If no time offset is given, the time is assumed to be given in UTC.
        :param geom: (optional) Search area that can be defined in different ways:

                     * with a Shapely geometry object:
                       :class:`shapely.geometry.base.BaseGeometry`
                     * with a bounding box (dict with keys: "lonmin", "latmin", "lonmax", "latmax"):
                       ``dict.fromkeys(["lonmin", "latmin", "lonmax", "latmax"])``
                     * with a bounding box as list of float:
                       ``[lonmin, latmin, lonmax, latmax]``
                     * with a WKT str
        :param locations: (optional) Location filtering by name using locations configuration
                          ``{"<location_name>"="<attr_regex>"}``. For example, ``{"country"="PA."}`` will use
                          the geometry of the features having the property ISO3 starting with
                          'PA' such as Panama and Pakistan in the shapefile configured with
                          name=country and attr=ISO3
        :param kwargs: Some other criteria that will be used to do the search,
                       using paramaters compatibles with the provider
        :returns: An iterator that yields page per page a set of EO products
                  matching the criteria
        """
        search_plugins, search_kwargs = self._prepare_search(
            start=start, end=end, geom=geom, locations=locations, **kwargs
        )
        for i, search_plugin in enumerate(search_plugins):
            try:
                return self.search_iter_page_plugin(
                    items_per_page=items_per_page,
                    search_plugin=search_plugin,
                    **search_kwargs,
                )
            except RequestError:
                if i < len(search_plugins) - 1:
                    logger.warning(
                        "No result could be obtained from provider %s, "
                        "we will try to get the data from another provider",
                        search_plugin.provider,
                    )
                else:
                    logger.error(
                        "No result could be obtained from any available provider"
                    )
                    raise
        raise RequestError("No result could be obtained from any available provider")

    @_deprecated(
        reason="Please use 'SearchResult.next_page()' instead",
        version="v3.9.0",
    )
    def search_iter_page_plugin(
        self,
        search_plugin: Union[Search, Api],
        items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
        **kwargs: Any,
    ) -> Iterator[SearchResult]:
        """Iterate over the pages of a products search using a given search plugin.

        .. deprecated:: v3.9.0
            Please use :meth:`eodag.api.search_result.SearchResult.next_page` instead.

        :param items_per_page: (optional) The number of results requested per page
        :param kwargs: Some other criteria that will be used to do the search,
                       using parameters compatibles with the provider
        :param search_plugin: search plugin to be used
        :returns: An iterator that yields page per page a set of EO products
                  matching the criteria
        """
        kwargs.update(
            page=1,
            items_per_page=items_per_page,
        )
        try:
            # remove unwanted kwargs for _do_search
            kwargs.pop("raise_errors", None)
            search_result = self._do_search(search_plugin, raise_errors=True, **kwargs)
            search_result.raise_errors = True

        except Exception:
            logger.warning(
                "error at retrieval of data from %s, for params: %s",
                search_plugin.provider,
                str(kwargs),
            )
            raise

        if len(search_result) == 0:
            return
        # remove unwanted kwargs for next_page
        if kwargs.get("count") is True:
            kwargs["count"] = False
        kwargs.pop("page", None)
        search_result.search_params = kwargs
        if search_result._dag is None:
            search_result._dag = self

        yield search_result

        for next_result in search_result.next_page():
            if len(next_result) == 0:
                break
            yield next_result

    def search_all(
        self,
        items_per_page: Optional[int] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        geom: Optional[Union[str, dict[str, float], BaseGeometry]] = None,
        locations: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> SearchResult:
        """Search and return all the products matching the search criteria.

        It iterates over the pages of a search query and collects all the returned
        products into a single :class:`~eodag.api.search_result.SearchResult` instance.

        Requests are attempted to all providers of the product ordered by descending piority.

        :param items_per_page: (optional) The number of results requested internally per
                               page. The maximum number of items than can be requested
                               at once to a provider has been configured in EODAG for
                               some of them. If items_per_page is None and this number
                               is available for the searched provider, it is used to
                               limit the number of requests made. This should also
                               reduce the time required to collect all the products
                               matching the search criteria. If this number is not
                               available, a default value of 50 is used instead.
                               items_per_page can also be set to any arbitrary value.
        :param start: (optional) Start sensing time in ISO 8601 format (e.g. "1990-11-26",
                      "1990-11-26T14:30:10.153Z", "1990-11-26T14:30:10+02:00", ...).
                      If no time offset is given, the time is assumed to be given in UTC.
        :param end: (optional) End sensing time in ISO 8601 format (e.g. "1990-11-26",
                    "1990-11-26T14:30:10.153Z", "1990-11-26T14:30:10+02:00", ...).
                    If no time offset is given, the time is assumed to be given in UTC.
        :param geom: (optional) Search area that can be defined in different ways:

                     * with a Shapely geometry object:
                       :class:`shapely.geometry.base.BaseGeometry`
                     * with a bounding box (dict with keys: "lonmin", "latmin", "lonmax", "latmax"):
                       ``dict.fromkeys(["lonmin", "latmin", "lonmax", "latmax"])``
                     * with a bounding box as list of float:
                       ``[lonmin, latmin, lonmax, latmax]``
                     * with a WKT str
        :param locations: (optional) Location filtering by name using locations configuration
                          ``{"<location_name>"="<attr_regex>"}``. For example, ``{"country"="PA."}`` will use
                          the geometry of the features having the property ISO3 starting with
                          'PA' such as Panama and Pakistan in the shapefile configured with
                          name=country and attr=ISO3
        :param kwargs: Some other criteria that will be used to do the search,
                       using parameters compatible with the provider
        :returns: An iterator that yields page per page a set of EO products
                  matching the criteria
        """
        # remove unwanted count
        kwargs.pop("count", None)

        # First search
        search_results = self.search(
            items_per_page=items_per_page,
            start=start,
            end=end,
            geom=geom,
            locations=locations,
            **kwargs,
        )
        if len(search_results) == 0:
            return search_results

        try:
            search_results.raise_errors = True

            # consume iterator
            deque(search_results.next_page(update=True))

            logger.info(
                "Found %s result(s) on provider '%s'",
                len(search_results),
                search_results[0].provider,
            )
        except RequestError:
            logger.warning(
                "Found %s result(s) on provider '%s', but it may be incomplete "
                "as it ended with an error",
                len(search_results),
                search_results[0].provider,
            )

        return search_results

    def _search_by_id(
        self, uid: str, provider: Optional[str] = None, **kwargs: Any
    ) -> SearchResult:
        """Internal method that enables searching a product by its id.

        Keeps requesting providers until a result matching the id is supplied. The
        search plugins should be developed in the way that enable them to handle the
        support of a search by id by the providers. The providers are requested one by
        one, in the order defined by their priorities. Be aware that because of that,
        the search can be slow, if the priority order is such that the provider that
        contains the requested product has the lowest priority. However, you can always
        speed up a little the search by passing the name of the provider on which to
        perform the search, if this information is available

        :param uid: The uid of the EO product
        :param provider: (optional) The provider on which to search the product.
                         This may be useful for performance reasons when the user
                         knows this product is available on the given provider
        :param kwargs: Search criteria to help finding the right product
        :returns: A search result with one EO product or None at all
        """
        collection = kwargs.get("collection")
        if collection is not None:
            try:
                collection = self.get_collection_from_alias(collection)
            except NoMatchingCollection:
                logger.debug("collection %s not found", collection)
        get_search_plugins_kwargs = dict(provider=provider, collection=collection)
        search_plugins = self._plugins_manager.get_search_plugins(
            **get_search_plugins_kwargs
        )
        # datacube query string
        _dc_qs = kwargs.pop("_dc_qs", None)

        results = SearchResult([])

        for plugin in search_plugins:
            logger.info(
                "Searching product with id '%s' on provider: %s", uid, plugin.provider
            )
            logger.debug("Using plugin class for search: %s", plugin.__class__.__name__)
            plugin.clear()

            # adds maximal pagination to be able to do a search-all + crunch if more
            # than one result are returned
            items_per_page = plugin.config.pagination.get(
                "max_items_per_page", DEFAULT_MAX_ITEMS_PER_PAGE
            )
            kwargs.update(items_per_page=items_per_page)
            if isinstance(plugin, PostJsonSearch):
                kwargs.update(
                    items_per_page=items_per_page,
                    _dc_qs=_dc_qs,
                )
            else:
                kwargs.update(
                    items_per_page=items_per_page,
                )

            try:
                # if more than one results are found, try getting them all and then filter using crunch
                for page_results in self.search_iter_page_plugin(
                    search_plugin=plugin,
                    id=uid,
                    **kwargs,
                ):
                    results.data.extend(page_results.data)
            except Exception as e:
                if kwargs.get("raise_errors"):
                    raise
                logger.warning(e)
                results.errors.append((plugin.provider, e))
                continue

            # try using crunch to get unique result
            if (
                len(results) > 1
                and len(filtered := results.filter_property(id=uid)) == 1
            ):
                results = filtered

            if len(results) == 1:
                if not results[0].collection:
                    # guess collection from properties
                    guesses = self.guess_collection(**results[0].properties)
                    results[0].collection = guesses[0]
                    # reset driver
                    results[0].driver = results[0].get_driver()
                results.number_matched = 1
                return results
            elif len(results) > 1:
                logger.info(
                    "Several products found for this id (%s). You may try searching using more selective criteria.",
                    results,
                )
        return SearchResult([], 0, results.errors)

    def _fetch_external_collection(self, provider: str, collection: str):
        plugins = self._plugins_manager.get_search_plugins(provider=provider)
        plugin = next(plugins)

        # check after plugin init if still fetchable
        if not getattr(plugin.config, "discover_collections", {}).get("fetch_url"):
            return None

        kwargs: dict[str, Any] = {"collection": collection}

        # append auth if needed
        if getattr(plugin.config, "need_auth", False):
            if auth := self._plugins_manager.get_auth(
                plugin.provider,
                getattr(plugin.config, "api_endpoint", None),
                plugin.config,
            ):
                kwargs["auth"] = auth

        collection_config = plugin.discover_collections(**kwargs)
        self.update_collections_list({provider: collection_config})

    def _prepare_search(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        geom: Optional[Union[str, dict[str, float], BaseGeometry]] = None,
        locations: Optional[dict[str, str]] = None,
        provider: Optional[str] = None,
        **kwargs: Any,
    ) -> tuple[list[Union[Search, Api]], dict[str, Any]]:
        """Internal method to prepare the search kwargs and get the search plugins.

        Product query:
          * By id (plus optional 'provider')
          * By search params:
            * collection query:
              * By collection (e.g. 'S2_MSI_L1C')
              * By params (e.g. 'platform'), see guess_collection
            * dates: 'start' and/or 'end'
            * geometry: 'geom' or 'bbox' or 'box'
            * search locations
            * TODO: better expose cloudCover
            * other search params are passed to Searchplugin.query()

        :param start: (optional) Start sensing time in ISO 8601 format (e.g. "1990-11-26",
                      "1990-11-26T14:30:10.153Z", "1990-11-26T14:30:10+02:00", ...).
                      If no time offset is given, the time is assumed to be given in UTC.
        :param end: (optional) End sensing time in ISO 8601 format (e.g. "1990-11-26",
                    "1990-11-26T14:30:10.153Z", "1990-11-26T14:30:10+02:00", ...).
                    If no time offset is given, the time is assumed to be given in UTC.
        :param geom: (optional) Search area that can be defined in different ways (see search)
        :param locations: (optional) Location filtering by name using locations configuration
        :param provider: provider to be used, if no provider is given or the collection
                        is not available for the provider, the preferred provider is used
        :param kwargs: Some other criteria
                       * id and/or a provider for a search by
                       * search criteria to guess the collection
                       * other criteria compatible with the provider
        :returns: Search plugins list and the prepared kwargs to make a query.
        """
        collection: Optional[str] = kwargs.get("collection")
        if collection is None:
            try:
                guesses = self.guess_collection(**kwargs)

                # guess_collection raises a NoMatchingCollection error if no product
                # is found. Here, the supported search params are removed from the
                # kwargs if present, not to propagate them to the query itself.
                for param in (
                    "instruments",
                    "constellation",
                    "platform",
                    "processing:level",
                    "eodag:sensor_type",
                ):
                    kwargs.pop(param, None)

                # By now, only use the best bet
                collection = guesses[0]
            except NoMatchingCollection:
                queried_id = kwargs.get("id")
                if queried_id is None:
                    logger.info(
                        "No collection could be guessed with provided arguments"
                    )
                else:
                    return [], kwargs

        if collection is not None:
            try:
                collection = self.get_collection_from_alias(collection)
            except NoMatchingCollection:
                logger.info("unknown collection " + collection)
        kwargs["collection"] = collection

        if start is not None:
            kwargs["start_datetime"] = start
        if end is not None:
            kwargs["end_datetime"] = end
        if "box" in kwargs or "bbox" in kwargs:
            logger.warning(
                "'box' or 'bbox' parameters are only supported for backwards "
                " compatibility reasons. Usage of 'geom' is recommended."
            )
        if geom is not None:
            kwargs["geometry"] = geom
        box = kwargs.pop("box", None)
        box = kwargs.pop("bbox", box)
        if geom is None and box is not None:
            kwargs["geometry"] = box

        kwargs["locations"] = locations
        kwargs["geometry"] = get_geometry_from_various(self.locations_config, **kwargs)
        # remove locations_args from kwargs now that they have been used
        locations_dict = {loc["name"]: loc for loc in self.locations_config}
        for arg in locations_dict.keys():
            kwargs.pop(arg, None)
        del kwargs["locations"]

        # fetch collections list if collection is unknown
        if (
            collection
            not in self._plugins_manager.collection_to_provider_config_map.keys()
        ):
            if provider and collection:
                # fetch ref for given provider and collection
                logger.debug(
                    f"Fetching external collections sources to find {provider} {collection} collection"
                )
                self.fetch_collections_list(provider)
                if (
                    collection
                    not in self._plugins_manager.collection_to_provider_config_map.keys()
                ):
                    # Try to get specific collection from external provider
                    logger.debug(f"Fetching {provider} to find {collection} collection")
                    self._fetch_external_collection(provider, collection)
            if not provider:
                # no provider or still not found -> fetch all external collections
                logger.debug(
                    f"Fetching external collections sources to find {collection} collection"
                )
                self.fetch_collections_list()

        preferred_provider = self.get_preferred_provider()[0]

        search_plugins: list[Union[Search, Api]] = []
        for plugin in self._plugins_manager.get_search_plugins(
            collection=collection, provider=provider
        ):
            # exclude MeteoblueSearch plugins from search fallback for unknown collection
            if (
                provider != plugin.provider
                and preferred_provider != plugin.provider
                and collection not in self.collections_config
                and isinstance(plugin, MeteoblueSearch)
            ):
                continue
            search_plugins.append(plugin)

        if not provider:
            provider = preferred_provider
        providers = [plugin.provider for plugin in search_plugins]
        if provider not in providers:
            logger.debug(
                "Collection '%s' is not available with preferred provider '%s'.",
                collection,
                provider,
            )
        else:
            provider_plugin = list(
                filter(lambda p: p.provider == provider, search_plugins)
            )[0]
            search_plugins.remove(provider_plugin)
            search_plugins.insert(0, provider_plugin)
        # Add collections_config to plugin config. This dict contains product
        # type metadata that will also be stored in each product's properties.
        for search_plugin in search_plugins:
            if collection is not None:
                self._attach_collection_config(search_plugin, collection)

        return search_plugins, kwargs

    def _do_search(
        self,
        search_plugin: Union[Search, Api],
        count: bool = False,
        raise_errors: bool = False,
        validate: Optional[bool] = True,
        **kwargs: Any,
    ) -> SearchResult:
        """Internal method that performs a search on a given provider.

        :param search_plugin: A search plugin
        :param count: (optional) Whether to run a query with a count request or not
        :param raise_errors: (optional) When an error occurs when searching, if this is set to
                             True, the error is raised
        :param kwargs: Some other criteria that will be used to do the search
        :param validate: (optional) Set to True to validate search parameters
                         before sending the query to the provider
        :returns: A collection of EO products matching the criteria
        """
        logger.info("Searching on provider %s", search_plugin.provider)
        max_items_per_page = getattr(search_plugin.config, "pagination", {}).get(
            "max_items_per_page", DEFAULT_MAX_ITEMS_PER_PAGE
        )
        if (
            kwargs.get("items_per_page", DEFAULT_ITEMS_PER_PAGE) > max_items_per_page
            and max_items_per_page > 0
        ):
            logger.warning(
                "EODAG believes that you might have asked for more products/items "
                "than the maximum allowed by '%s': %s > %s. Try to lower "
                "the value of 'items_per_page' and get the next page (e.g. 'page=2'), "
                "or directly use the 'search_all' method.",
                search_plugin.provider,
                kwargs["items_per_page"],
                max_items_per_page,
            )

        errors: list[tuple[str, Exception]] = []

        try:
            prep = PreparedSearch(count=count)
            prep.raise_errors = raise_errors

            # append auth if needed
            if getattr(search_plugin.config, "need_auth", False):
                if auth := self._plugins_manager.get_auth(
                    search_plugin.provider,
                    getattr(search_plugin.config, "api_endpoint", None),
                    search_plugin.config,
                ):
                    prep.auth = auth

            prep.items_per_page = kwargs.pop("items_per_page", None)
            prep.next_page_token = kwargs.pop("next_page_token", None)
            prep.page = kwargs.pop("page", None)

            if (
                search_plugin.config.pagination.get("next_page_token_key", "page")
                == "page"
                and prep.items_per_page is not None
                and prep.next_page_token is None
                and prep.page is not None
            ):
                prep.next_page_token = str(
                    prep.page
                    - 1
                    + search_plugin.config.pagination.get("start_page", DEFAULT_PAGE)
                )

            # remove None values and convert param names to their pydantic alias if any
            search_params = {}
            ecmwf_queryables = [
                f"{ECMWF_PREFIX[:-1]}_{k}" for k in ECMWF_ALLOWED_KEYWORDS
            ]
            for param, value in kwargs.items():
                if value is None:
                    continue
                if param in Queryables.model_fields:
                    param_alias = Queryables.model_fields[param].alias or param
                    search_params[param_alias] = value
                elif param in ecmwf_queryables:
                    # alias equivalent for ECMWF queryables
                    search_params[
                        re.sub(rf"^{ECMWF_PREFIX[:-1]}_", f"{ECMWF_PREFIX}", param)
                    ] = value
                else:
                    # remove `provider:` or `provider_` prefix if any
                    search_params[
                        re.sub(r"^" + search_plugin.provider + r"[_:]", "", param)
                    ] = value

            if validate:
                search_plugin.validate(search_params, prep.auth)

            search_result = search_plugin.query(prep, **search_params)

            if not isinstance(search_result.data, list):
                raise PluginImplementationError(
                    "The query function of a Search plugin must return a list of "
                    "results, got {} instead".format(type(search_result.data))
                )
            # Filter and attach to each eoproduct in the result the plugin capable of
            # downloading it (this is done to enable the eo_product to download itself
            # doing: eo_product.download()). The filtering is done by keeping only
            # those eo_products that intersects the search extent (if there was no
            # search extent, search_intersection contains the geometry of the
            # eo_product)
            # WARNING: this means an eo_product that has an invalid geometry can still
            # be returned as a search result if there was no search extent (because we
            # will not try to do an intersection)
            for eo_product in search_result.data:
                # if product_type is not defined, try to guess using properties
                if eo_product.product_type is None:
                    pattern = re.compile(r"[^\w,]+")
                    try:
                        guesses = self.guess_product_type(
                            intersect=False,
                            **{
                                k: pattern.sub("", str(v).upper())
                                for k, v in eo_product.properties.items()
                                if k
                                in [
                                    "instrument",
                                    "platform",
                                    "platformSerialIdentifier",
                                    "processingLevel",
                                    "sensorType",
                                    "keywords",
                                ]
                                and v is not None
                            },
                        )
                    except NoMatchingCollection:
                        pass
                    else:
                        eo_product.product_type = guesses[0]

                try:
                    if eo_product.product_type is not None:
                        eo_product.product_type = self.get_product_type_from_alias(
                            eo_product.product_type
                        )
                except NoMatchingCollection:
                    logger.debug("product type %s not found", eo_product.product_type)

                if eo_product.search_intersection is not None:
                    eo_product._register_downloader_from_manager(self._plugins_manager)

            search_result._dag = self
            return search_result

        except Exception as e:
            if raise_errors:
                # Raise the error, letting the application wrapping eodag know that
                # something went bad. This way it will be able to decide what to do next
                raise
            else:
                logger.exception(
                    "Error while searching on provider %s (ignored):",
                    search_plugin.provider,
                )
                errors.append((search_plugin.provider, e))
                return SearchResult([], 0, errors)

    def crunch(self, results: SearchResult, **kwargs: Any) -> SearchResult:
        """Apply the filters given through the keyword arguments to the results

        :param results: The results of a eodag search request
        :returns: The result of successively applying all the filters to the results
        """
        search_criteria = kwargs.pop("search_criteria", {})
        for cruncher_name, cruncher_args in kwargs.items():
            cruncher = self._plugins_manager.get_crunch_plugin(
                cruncher_name, **cruncher_args
            )
            results = results.crunch(cruncher, **search_criteria)
        return results

    @staticmethod
    def group_by_extent(searches: list[SearchResult]) -> list[SearchResult]:
        """Combines multiple SearchResults and return a list of SearchResults grouped
        by extent (i.e. bounding box).

        :param searches: List of eodag SearchResult
        :returns: list of :class:`~eodag.api.search_result.SearchResult`
        """
        # Dict with extents as keys, each extent being defined by a str
        # "{minx}{miny}{maxx}{maxy}" (each float rounded to 2 dec).
        products_grouped_by_extent: dict[str, Any] = {}

        for search in searches:
            for product in search:
                same_geom = products_grouped_by_extent.setdefault(
                    "".join([str(round(p, 2)) for p in product.geometry.bounds]), []
                )
                same_geom.append(product)

        return [
            SearchResult(products_grouped_by_extent[extent_as_str])
            for extent_as_str in products_grouped_by_extent
        ]

    def download_all(
        self,
        search_result: SearchResult,
        downloaded_callback: Optional[DownloadedCallback] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Unpack[DownloadConf],
    ) -> list[str]:
        """Download all products resulting from a search.

        :param search_result: A set of EO products resulting from a search
        :param downloaded_callback: (optional) A method or a callable object which takes
                                    as parameter the ``product``. You can use the base class
                                    :class:`~eodag.utils.DownloadedCallback` and override
                                    its ``__call__`` method. Will be called each time a product
                                    finishes downloading
        :param progress_callback: (optional) A method or a callable object
                                  which takes a current size and a maximum
                                  size as inputs and handle progress bar
                                  creation and update to give the user a
                                  feedback on the download progress
        :param wait: (optional) If download fails, wait time in minutes between
                     two download tries of the same product
        :param timeout: (optional) If download fails, maximum time in minutes
                        before stop retrying to download
        :param kwargs: Additional keyword arguments from the download plugin configuration class that can
                       be provided to override any other values defined in a configuration file
                       or with environment variables:

                       * ``output_dir`` - where to store downloaded products, as an absolute file path
                         (Default: local temporary directory)
                       * ``output_extension`` - downloaded file extension
                       * ``extract`` - whether to extract the downloaded products, only applies to archived products
                       * ``dl_url_params`` - additional parameters to pass over to the download url as an url parameter
                       * ``delete_archive`` - whether to delete the downloaded archives
                       * ``asset`` - regex filter to identify assets to download
        :returns: A collection of the absolute paths to the downloaded products
        """
        paths = []
        if search_result:
            logger.info("Downloading %s products", len(search_result))
            # Get download plugin using first product assuming product from several provider
            # aren't mixed into a search result
            download_plugin = self._plugins_manager.get_download_plugin(
                search_result[0]
            )
            paths = download_plugin.download_all(
                search_result,
                downloaded_callback=downloaded_callback,
                progress_callback=progress_callback,
                wait=wait,
                timeout=timeout,
                **kwargs,
            )
        else:
            logger.info("Empty search result, nothing to be downloaded !")
        return paths

    @staticmethod
    def serialize(
        search_result: SearchResult, filename: str = "search_results.geojson"
    ) -> str:
        """Registers results of a search into a geojson file.
        The output is a FeatureCollection containing the EO products as features,
        with additional metadata such as ``number_matched``, ``next_page_token``,
        and ``search_params`` stored in the properties.

        :param search_result: A set of EO products resulting from a search
        :param filename: (optional) The name of the file to generate
        :returns: The name of the created file
        """
        with open(filename, "w") as fh:
            geojson.dump(search_result.as_geojson_object(), fh)
        return filename

    @staticmethod
    def deserialize(filename: str) -> SearchResult:
        """Loads results of a search from a geojson file.

        :param filename: A filename containing a search result encoded as a geojson
        :returns: The search results encoded in `filename`
        """
        with open(filename, "r") as fh:
            return SearchResult.from_geojson(geojson.load(fh))

    def deserialize_and_register(self, filename: str) -> SearchResult:
        """Loads results of a search from a geojson file and register
        products with the information needed to download itself.

        This method also sets the internal EODataAccessGateway instance on the products,
        enabling pagination (e.g. access to next pages) if available.

        :param filename: A filename containing a search result encoded as a geojson
        :returns: The search results encoded in `filename`, ready for download and pagination
        """
        products = self.deserialize(filename)
        products._dag = self
        for i, product in enumerate(products):
            if product.downloader is None:
                downloader = self._plugins_manager.get_download_plugin(product)
                auth = product.downloader_auth
                if auth is None:
                    auth = self._plugins_manager.get_auth_plugin(downloader, product)
                products[i].register_downloader(downloader, auth)

        return products

    def download(
        self,
        product: EOProduct,
        progress_callback: Optional[ProgressCallback] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Unpack[DownloadConf],
    ) -> str:
        """Download a single product.

        This is an alias to the method of the same name on
        :class:`~eodag.api.product._product.EOProduct`, but it performs some additional
        checks like verifying that a downloader and authenticator are registered
        for the product before trying to download it.

        If the metadata mapping for ``eodag:download_link`` is set to something that can be
        interpreted as a link on a
        local filesystem, the download is skipped (by now, only a link starting
        with ``file:/`` is supported). Therefore, any user that knows how to extract
        product location from product metadata on a provider can override the
        ``eodag:download_link`` metadata mapping in the right way. For example, using the
        environment variable:
        ``EODAG__CREODIAS__SEARCH__METADATA_MAPPING__EODAG_DOWNLOAD_LINK="file:///{id}"`` will
        lead to all :class:`~eodag.api.product._product.EOProduct`'s originating from the
        provider ``creodias`` to have their ``eodag:download_link`` metadata point to something like:
        ``file:///12345-678``, making this method immediately return the later string without
        trying to download the product.

        :param product: The EO product to download
        :param progress_callback: (optional) A method or a callable object
                                  which takes a current size and a maximum
                                  size as inputs and handle progress bar
                                  creation and update to give the user a
                                  feedback on the download progress
        :param wait: (optional) If download fails, wait time in minutes between
                    two download tries
        :param timeout: (optional) If download fails, maximum time in minutes
                        before stop retrying to download
        :param kwargs: Additional keyword arguments from the download plugin configuration class that can
                       be provided to override any other values defined in a configuration file
                       or with environment variables:

                       * ``output_dir`` - where to store downloaded products, as an absolute file path
                         (Default: local temporary directory)
                       * ``output_extension`` - downloaded file extension
                       * ``extract`` - whether to extract the downloaded products, only applies to archived products
                       * ``dl_url_params`` - additional parameters to pass over to the download url as an url parameter
                       * ``delete_archive`` - whether to delete the downloaded archives
                       * ``asset`` - regex filter to identify assets to download
        :returns: The absolute path to the downloaded product in the local filesystem
        :raises: :class:`~eodag.utils.exceptions.PluginImplementationError`
        :raises: :class:`RuntimeError`
        """
        if product.location.startswith("file:/"):
            logger.info("Local product detected. Download skipped")
            return uri_to_path(product.location)
        self._setup_downloader(product)
        path = product.download(
            progress_callback=progress_callback, wait=wait, timeout=timeout, **kwargs
        )

        return path

    def _setup_downloader(self, product: EOProduct) -> None:
        if product.downloader is None:
            downloader = self._plugins_manager.get_download_plugin(product)
            auth = product.downloader_auth
            if auth is None:
                auth = self._plugins_manager.get_auth_plugin(downloader, product)
            product.register_downloader(downloader, auth)

    def get_cruncher(self, name: str, **options: Any) -> Crunch:
        """Build a crunch plugin from a configuration

        :param name: The name of the cruncher to build
        :param options: The configuration options of the cruncher
        :returns: The cruncher named ``name``
        """
        plugin_conf = {"name": name}
        plugin_conf.update({key.replace("-", "_"): val for key, val in options.items()})
        return self._plugins_manager.get_crunch_plugin(name, **plugin_conf)

    def list_queryables(
        self,
        provider: Optional[str] = None,
        fetch_providers: bool = True,
        **kwargs: Any,
    ) -> QueryablesDict:
        """Fetch the queryable properties for a given collection and/or provider.

        :param provider: (optional) The provider.
        :param fetch_providers: If new collections should be fetched from the providers; default: True
        :param kwargs: additional filters for queryables (`collection` or other search
                       arguments)

        :raises UnsupportedCollection: If the specified collection is not available for the
                                        provider.

        :returns: A :class:`~eodag.api.product.queryables.QuerybalesDict` containing the EODAG queryable
                  properties, associating parameters to their annotated type, and a additional_properties attribute
        """
        # only fetch providers if collection is not found
        available_collections: list[str] = [
            pt["ID"]
            for pt in self.list_collections(provider=provider, fetch_providers=False)
        ]
        collection: Optional[str] = kwargs.get("collection")
        coll_alias: Optional[str] = collection

        if collection:
            if collection not in available_collections:
                if fetch_providers:
                    # fetch providers and try again
                    available_collections = [
                        pt["ID"]
                        for pt in self.list_collections(
                            provider=provider, fetch_providers=True
                        )
                    ]
                raise UnsupportedCollection(f"{collection} is not available.")
            try:
                kwargs["collection"] = collection = self.get_collection_from_alias(
                    collection
                )
            except NoMatchingCollection as e:
                raise UnsupportedCollection(f"{collection} is not available.") from e

        if not provider and not collection:
            return QueryablesDict(
                additional_properties=True,
                **model_fields_to_annotated(CommonQueryables.model_fields),
            )

        additional_properties = False
        additional_information = []
        queryable_properties: dict[str, Any] = {}

        for plugin in self._plugins_manager.get_search_plugins(collection, provider):
            # attach collection config
            collection_configs: dict[str, Any] = {}
            if collection:
                self._attach_collection_config(plugin, collection)
                collection_configs[collection] = plugin.config.collection_config
            else:
                for pt in available_collections:
                    self._attach_collection_config(plugin, pt)
                    collection_configs[pt] = plugin.config.collection_config

            # authenticate if required
            if getattr(plugin.config, "need_auth", False) and (
                auth := self._plugins_manager.get_auth_plugin(plugin)
            ):
                try:
                    plugin.auth = auth.authenticate()
                except AuthenticationError:
                    logger.debug(
                        "queryables from provider %s could not be fetched due to an authentication error",
                        plugin.provider,
                    )

            # use queryables aliases
            kwargs_alias = {**kwargs}
            for search_param, field_info in Queryables.model_fields.items():
                if search_param in kwargs and field_info.alias:
                    kwargs_alias[field_info.alias] = kwargs_alias.pop(search_param)

            plugin_queryables = plugin.list_queryables(
                kwargs_alias,
                available_collections,
                collection_configs,
                collection,
                coll_alias,
            )

            if plugin_queryables.additional_information:
                additional_information.append(
                    f"{plugin.provider}: {plugin_queryables.additional_information}"
                )
            queryable_properties = {**plugin_queryables, **queryable_properties}
            additional_properties = (
                additional_properties or plugin_queryables.additional_properties
            )

        return QueryablesDict(
            additional_properties=additional_properties,
            additional_information=" | ".join(additional_information),
            **queryable_properties,
        )

    def available_sortables(self) -> dict[str, Optional[ProviderSortables]]:
        """For each provider, gives its available sortable parameter(s) and its maximum
        number of them if it supports the sorting feature, otherwise gives None.

        :returns: A dictionary with providers as keys and dictionary of sortable parameter(s) and
                  its (their) maximum number as value(s).
        :raises: :class:`~eodag.utils.exceptions.UnsupportedProvider`
        """
        sortables: dict[str, Optional[ProviderSortables]] = {}
        provider_search_plugins = self._plugins_manager.get_search_plugins()
        for provider_search_plugin in provider_search_plugins:
            provider = provider_search_plugin.provider
            if not hasattr(provider_search_plugin.config, "sort"):
                sortables[provider] = None
                continue
            sortable_params = list(
                provider_search_plugin.config.sort.get("sort_param_mapping", {}).keys()
            )
            if not provider_search_plugin.config.sort.get("max_sort_params"):
                sortables[provider] = {
                    "sortables": sortable_params,
                    "max_sort_params": None,
                }
                continue
            sortables[provider] = {
                "sortables": sortable_params,
                "max_sort_params": provider_search_plugin.config.sort[
                    "max_sort_params"
                ],
            }
        return sortables

    def _attach_collection_config(self, plugin: Search, collection: str) -> None:
        """
        Attach collections_config to plugin config. This dict contains product
        type metadata that will also be stored in each product's properties.
        """
        try:
            plugin.config.collection_config = dict(
                [
                    p
                    for p in self.list_collections(
                        plugin.provider, fetch_providers=False
                    )
                    if p["_id"] == collection
                ][0],
                **{"collection": collection},
            )
            # If the product isn't in the catalog, it's a generic collection.
        except IndexError:
            # Construct the GENERIC_COLLECTION metadata
            plugin.config.collection_config = dict(
                ID=GENERIC_COLLECTION,
                **self.collections_config[GENERIC_COLLECTION],
                collection=collection,
            )
        # Remove the ID since this is equal to collection.
        plugin.config.collection_config.pop("ID", None)

    def import_stac_items(self, items_urls: list[str]) -> SearchResult:
        """Import STAC items from a list of URLs and convert them to SearchResult.

        - Origin provider and download links will be set if item comes from an EODAG
          server.
        - If item comes from a known EODAG provider, result will be registered to it,
          ready to download and its metadata normalized.
        - If item comes from an unknown provider, a generic STAC provider will be used.

        :param items_urls: A list of STAC items URLs to import
        :returns: A SearchResult containing the imported STAC items
        """
        json_items = []
        for item_url in items_urls:
            json_items.extend(fetch_stac_items(item_url))

        # add a generic STAC provider that might be needed to handle the items
        self.add_provider(GENERIC_STAC_PROVIDER)

        results = SearchResult([])
        for json_item in json_items:
            if search_result := SearchResult._from_stac_item(
                json_item, self._plugins_manager
            ):
                results.extend(search_result)

        return results
