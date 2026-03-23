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
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator, Optional, Union, cast

import geojson
import yaml
from pydantic import BaseModel

from eodag.api.collection import Collection, CollectionsDict, CollectionsList
from eodag.api.product.metadata_mapping import (
    NOT_AVAILABLE,
    mtd_cfg_as_conversion_and_querypath,
)
from eodag.api.provider import Provider, ProvidersDict
from eodag.api.search_result import SearchResult
from eodag.config import (
    CollectionProviderConfig,
    PluginConfig,
    ProviderConfig,
    SimpleYamlProxyConfig,
    disable_providers,
    extract_credentials,
    get_ext_collections_conf,
    load_default_config,
    load_provider_configs,
    load_yml_config,
    merge_provider_configs,
)
from eodag.databases.sqlite import SQLiteDatabase
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
    PLUGINS_TOPIC_KEYS,
    CredsStoreType,
    _deprecated,
    get_geometry_from_various,
    makedirs,
    sort_dict,
    string_to_jsonpath,
    update_nested_dict,
    uri_to_path,
)
from eodag.utils.env import is_env_var_true
from eodag.utils.exceptions import (
    AuthenticationError,
    NoMatchingCollection,
    PluginImplementationError,
    RequestError,
    UnsupportedProvider,
    ValidationError,
)
from eodag.utils.stac_reader import fetch_stac_items

if TYPE_CHECKING:
    from concurrent.futures import ThreadPoolExecutor
    from shapely.geometry.base import BaseGeometry

    from eodag.api.product import EOProduct
    from eodag.databases.base import Database
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

    db: Database
    _creds_store: CredsStoreType

    def __init__(
        self,
        user_conf_file_path: Optional[str] = None,
        locations_conf_path: Optional[str] = None,
        db: Optional[Database] = None,
    ) -> None:
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

        self.db = (
            db
            if db is not None
            else SQLiteDatabase(os.path.join(self.conf_dir, "eodag.db"))
        )
        collections_config_path = os.getenv("EODAG_COLLECTIONS_CFG_FILE") or str(
            res_files("eodag") / "resources" / "collections.yml"
        )
        collections_config_dict = SimpleYamlProxyConfig(collections_config_path).source

        collections_dict = CollectionsDict.from_configs(collections_config_dict)
        self.db.upsert_collections(collections_dict)

        # First level override: From a user configuration file
        if user_conf_file_path is None:
            env_var_name = "EODAG_CFG_FILE"
            standard_configuration_path = os.path.join(self.conf_dir, "eodag.yml")
            user_conf_file_path = os.getenv(env_var_name)
            if user_conf_file_path is None:
                user_conf_file_path = standard_configuration_path
                source = str(
                    res_files("eodag") / "resources" / "user_conf_template.yml"
                )
                if os.path.isfile(source) and not os.path.isfile(
                    standard_configuration_path
                ):
                    shutil.copy(
                        source,
                        standard_configuration_path,
                    )

        # Build providers: default → external plugins → user YAML → env vars
        configs = load_provider_configs(
            load_default_config(),
            *(
                [self._plugins_manager.external_providers_config]
                if self._plugins_manager.external_providers_config
                else []
            ),
            user_conf_file=user_conf_file_path,
        )
        disable_providers(configs, self._plugins_manager.skipped_plugins)

        self._creds_store = extract_credentials(configs)
        self.db.upsert_fb_configs(list(configs.values()))
        self._plugins_manager = PluginManager(db=self.db, creds_store=self._creds_store)

        self._bulk_sync_collections()

        self.set_locations_conf(locations_conf_path)

    def _bulk_sync_collections(self) -> None:
        """Synchronize collections for all providers in a single DB query.

        In permissive mode, adds empty collection to config for missing types.
        """
        # TODO: is this still needed  ?? maybe refactor to better integrate with DB ?
        all_config_ids = self.db.get_all_collection_ids_for_backends() - {
            GENERIC_COLLECTION
        }
        if not all_config_ids:
            return

        known_ids = set(self.list_collections(ids=list(all_config_ids)).ids)
        missing_ids = all_config_ids - known_ids

        if not missing_ids:
            return

        strict_mode = is_env_var_true("EODAG_STRICT_COLLECTIONS")
        if strict_mode:
            logger.debug(
                "Collections strict mode, ignoring %s",
                ", ".join(missing_ids),
            )
            # Remove unknown collections from provider configs
            self.db.delete_collections_federation_backends(list(missing_ids))
        else:
            collections_to_add = [
                Collection(id=coll_id, title=coll_id, description=NOT_AVAILABLE)
                for coll_id in missing_ids
            ]
            self.db.upsert_collections(CollectionsDict(collections_to_add))
            logger.debug(
                "Collections permissive mode, %s added",
                ", ".join(missing_ids),
            )

    @property
    def providers(self) -> ProvidersDict:
        """Providers of eodag configuration sorted by priority in descending order and by name in ascending order."""
        return self.get_providers(enabled=True)

    def get_version(self) -> str:
        """Get eodag package version"""
        return version("eodag")

    def get_providers(
        self,
        collection: Optional[str] = None,
        enabled: Optional[bool] = None,
        limit: Optional[int] = None,
        names: Optional[list[str]] = None,
    ) -> ProvidersDict:
        """
        Liste les providers depuis la base, avec filtres éventuels.
        Retourne un ProvidersDict (si pas names_only), ou une liste de dicts/noms.
        """
        providers = self.db.get_federation_backends(
            collection=collection, enabled=enabled, limit=limit, names=names
        )

        return ProvidersDict(
            {
                name: Provider(name=name, **content)
                for name, content in providers.items()
            }
        )

    def set_preferred_provider(self, provider: str) -> None:
        """Set max priority for the given provider.

        :param provider: The name of the provider that should be considered as the
                         preferred provider to be used for this instance
        """
        if not self.get_providers(names=[provider]):
            raise UnsupportedProvider(
                f"This provider is not recognised by eodag: {provider}"
            )
        preferred = self.get_providers(limit=1)[0]
        if preferred.name != provider:
            new_priority = preferred.priority + 1
            self.db.set_priority(provider, new_priority)

    def get_preferred_provider(self) -> tuple[str, int]:
        """Get the provider currently set as the preferred one for searching
        products, along with its priority.

        :returns: The provider with the maximum priority and its priority
        """
        providers = self.get_providers(limit=1)
        return providers[0].name, providers[0].priority

    def update_providers_config(
        self,
        yaml_conf: str | None = None,
        dict_conf: dict[str, Any] | None = None,
    ) -> None:
        """
        Update provider configurations using patch semantics.
        """

        if dict_conf is not None:
            patch_conf = dict_conf
        elif yaml_conf is not None:
            patch_conf = yaml.safe_load(yaml_conf)
        else:
            return

        if not patch_conf:
            return

        def _touched_collections(patch: dict[str, Any]) -> set[str]:
            touched: set[str] = set()
            products = patch.get("products")
            if isinstance(products, dict):
                touched |= set(products.keys())
            download = patch.get("download")
            if isinstance(download, dict):
                dl_products = download.get("products")
                if isinstance(dl_products, dict):
                    touched |= set(dl_products.keys())
            return touched

        provider_configs: dict[str, ProviderConfig] = {}

        for name, patch in patch_conf.items():
            patch_dict = patch if isinstance(patch, dict) else patch.__dict__
            touched_collections = _touched_collections(patch_dict)

            base_mapping = self.db.get_fb_config(name, collections=touched_collections)
            base_mapping["enabled"] = True

            provider_configs[name] = ProviderConfig.from_mapping(base_mapping)

        merge_provider_configs(provider_configs, patch_conf)
        update_nested_dict(self._creds_store, extract_credentials(provider_configs))
        disable_providers(provider_configs, self._plugins_manager.skipped_plugins)

        self.db.upsert_fb_configs(list(provider_configs.values()))

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
        :param kwargs: Additional :class:`~eodag.api.provider.ProviderConfig` mapping
        """
        conf_dict: dict[str, Any] = {
            name: {
                "name": name,
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
            for k in PLUGINS_TOPIC_KEYS:
                if k != "api":
                    conf_dict[name].pop(k, None)

        self.update_providers_config(dict_conf=conf_dict)

        if priority is None:
            self.set_preferred_provider(name)

    def set_locations_conf(self, locations_conf_path: Optional[str]) -> None:
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
        if locations_conf_path is None:
            locations_conf_path = os.getenv("EODAG_LOCS_CFG_FILE")
            if locations_conf_path is None:
                locations_conf_path = os.path.join(self.conf_dir, "locations.yml")
                if not os.path.isfile(locations_conf_path):
                    # Ensure the directory exists
                    os.makedirs(os.path.dirname(locations_conf_path), exist_ok=True)

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

    def get_collection(
        self, id: str, providers: Optional[list[str]] = None
    ) -> Optional[Collection]:
        """Get a collection by its id.

        :param id: The collection id
        :param providers: (optional) A list of provider names to filter the collection search.
            If None, all providers will be considered.
        :returns: The collection having the given id if it exists, None otherwise
        """
        return self.list_collections(ids=[id], providers=providers).get(id)

    def list_collections(
        self,
        geometry: Optional[Union[BaseGeometry, dict[str, Any], str]] = None,
        datetime: Optional[Union[datetime.datetime, str]] = None,
        limit: Optional[int] = None,
        q: Optional[str] = None,
        ids: Optional[list[str]] = None,
        providers: Optional[list[str]] = None,
        cql2_text: Optional[str] = None,
        cql2_json: Optional[dict[str, Any]] = None,
        sortby: Optional[list[dict[str, str]]] = None,
    ) -> CollectionsList:
        """Search and list collections matching the given filters.

        :param geometry: (optional) Search area as a Shapely geometry, a bounding-box
                         dict, or a WKT string
        :param datetime: (optional) Temporal filter as an RFC 3339 string or interval
                         (e.g. ``"2021-01-01T00:00:00Z/2022-01-01T00:00:00Z"``,
                         ``"../2021-06-01T00:00:00Z"``, ``"2022-01-01T00:00:00Z/.."``).
        :param limit: (optional) Maximum number of collections to return
        :param q: (optional) Free-text search terms (STAC ``q`` parameter)
        :param cql2_text: (optional) CQL2 text filter expression
        :param cql2_json: (optional) CQL2 JSON filter expression
        :param sortby: (optional) STAC sort extension objects, e.g.
                       ``[{"field": "datetime", "direction": "desc"}]``
        :returns: A :class:`~eodag.api.collection.CollectionsList` of matching
                  collections with a ``number_matched`` attribute.
        :raises ValueError: If both ``cql2_text`` and ``cql2_json`` are provided,
                            or if ``sortby`` contains invalid fields/directions.
        :raises: :class:`~eodag.utils.exceptions.UnsupportedProvider`
        """
        if providers:
            all_names = self.db.list_federation_backend_names(enabled_only=False)
            all_groups = self.db.list_federation_backend_groups(enabled_only=False)
            known = set(all_names) | set(all_groups)
            unknown = set(providers) - known
            if unknown:
                raise UnsupportedProvider(
                    f"This provider is not recognised by eodag: {', '.join(unknown)}"
                )
            # Resolve provider groups to actual provider names for DB query
            resolved: list[str] = []
            for p in providers:
                members = self.db.filter_federation_backends(p, enabled_only=False)
                resolved.extend(members)
            providers = resolved
        try:
            collections, number_matched = self.db.collections_search(
                geometry=geometry,
                datetime=datetime,
                limit=limit,
                q=q,
                ids=ids,
                federation_backends=providers,
                cql2_text=cql2_text,
                cql2_json=cql2_json,
                sortby=sortby,
            )
        except ValueError as e:
            raise ValidationError(f"Invalid input for listing collections: {e}")

        return CollectionsList(
            [Collection.create_with_dag(dag=self, **c) for c in collections],
            number_matched,
        )

    def fetch_collections_list(self, provider: Optional[str] = None) -> None:
        """Fetch collections list and update if needed.

        If strict mode is enabled (by setting the ``EODAG_STRICT_COLLECTIONS`` environment variable
        to a truthy value), this method will not fetch or update collections and will return immediately.

        :param provider: The name of a provider or provider-group for which collections
                         list should be updated. Defaults to all providers (None value).
        """
        # TODO: Review this function to adjust with the DB.
        # TODO: behavior needs to be defined properly
        strict_mode = is_env_var_true("EODAG_STRICT_COLLECTIONS")
        if strict_mode:
            return

        # providers discovery confs that are fetchable
        providers_discovery_configs_fetchable: dict[
            str, PluginConfig.DiscoverCollections
        ] = {}
        # check if any provider has not already been fetched for collections
        already_fetched = True
        # filter backends by name or group, then check fetchable
        backend_names = self.db.filter_federation_backends(provider)
        fetchable_backends = self.db.get_federation_backends_fetchable(backend_names)
        for fb in fetchable_backends:
            fb_id = fb["id"]
            discover_conf = fb["plugins_config"]["search"]["discover_collections"]
            providers_discovery_configs_fetchable[fb_id] = discover_conf
            last_fetch = self.db.get_federation_backend_last_fetch(fb_id)
            if not last_fetch:
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
        default_providers = load_default_config()
        for (
            provider,
            user_discovery_conf,
        ) in providers_discovery_configs_fetchable.items():
            # default discover_collections conf
            if provider in default_providers:
                default_provider = default_providers[provider]
                default_search_config = getattr(
                    default_provider, "search", None
                ) or getattr(default_provider, "api", None)
                if not default_search_config:
                    continue

                default_discovery_conf = default_search_config.discover_collections

                # compare confs
                if default_discovery_conf["result_type"] == "json" and isinstance(
                    default_discovery_conf["results_entry"], str
                ):
                    default_discovery_conf_parsed = cast(
                        PluginConfig.DiscoverCollections,
                        dict(
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

        backend_names = self.db.filter_federation_backends(provider)

        if provider and not backend_names:
            raise UnsupportedProvider(
                f"The requested provider is not (yet) supported: {provider}"
            )

        ext_collections_conf: dict[str, Any] = {}

        kwargs: dict[str, Any] = {}
        fetchable_backends = self.db.get_federation_backends_fetchable(backend_names)
        for fb in fetchable_backends:
            p_name = fb["id"]

            search_plugin: Union[Search, Api] = next(
                self._plugins_manager.get_search_plugins(provider=p_name)
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
                        f"Could not authenticate on {p_name} for collections discovery"
                    )
                    ext_collections_conf[p_name] = None
                    continue

            ext_collections_conf[p_name] = search_plugin.discover_collections(**kwargs)

        return sort_dict(ext_collections_conf)

    def update_collections_list(
        self, ext_collections_conf: dict[str, Optional[dict[str, dict[str, Any]]]]
    ) -> None:
        """Update eodag collections list

        :param ext_collections_conf: external collections configuration
        """
        # TODO: review this method as well!
        all_new_collections: list[Collection] = []
        all_backend_names = self.db.list_federation_backend_names(enabled_only=False)

        for provider, new_collections_conf in ext_collections_conf.items():
            if new_collections_conf and provider in all_backend_names:
                fb_data = self.db.get_federation_backends([provider]).get(provider, {})
                fb_pc = fb_data.get("plugins_config", {})
                search_conf = fb_pc.get("search") or fb_pc.get("api")
                fetchable = bool(
                    search_conf
                    and search_conf.get("discover_collections", {}).get("fetch_url")
                )
                if not fetchable:
                    continue

                provider_products_config_raw = (
                    self.db.get_collection_configs_for_backend(provider)
                )
                # Unwrap topic key: {coll_id: {"search": conf}} -> {coll_id: conf}
                provider_products_config: dict[str, Any] = {}
                for coll_id, wrapped in provider_products_config_raw.items():
                    for _topic, conf in wrapped.items():
                        provider_products_config[coll_id] = conf
                        break

                new_collections = 0
                bad_formatted_col_count = 0

                # unparsable_properties from discover_collections conf
                discover_conf = search_conf.get("discover_collections", {})
                unparsable_keys = set(
                    discover_conf.get(
                        "generic_collection_unparsable_properties", {}
                    ).keys()
                )
                for (
                    new_collection,
                    new_collection_conf,
                ) in new_collections_conf["providers_config"].items():
                    if new_collection not in provider_products_config:
                        for existing_collection in provider_products_config.copy():
                            # compare parsed extracted conf (without metadata_mapping entry)

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
                            try:
                                new_coll_obj = Collection(
                                    id=new_collection,
                                    **new_collections_conf["collections_config"][
                                        new_collection
                                    ],
                                )
                            except ValidationError:
                                # skip collection if there is a problem with its id (missing or not a string)
                                logger.debug(
                                    (
                                        "Collection %s has been pruned on provider %s "
                                        "because its id was incorrectly parsed for eodag"
                                    ),
                                    new_collection,
                                    provider,
                                )
                            else:
                                # new_collection_conf does not already exist, append it
                                # to self.collections_config
                                all_new_collections.append(new_coll_obj)

                                # to provider_products_config
                                provider_products_config[
                                    new_collection
                                ] = new_collection_conf
                                ext_collections_conf[provider] = new_collections_conf
                                new_collections += 1

                                # increase the increment if the new collection had
                                # bad formatted attributes in the external config
                                for field, v in new_collections_conf[
                                    "collections_config"
                                ][new_collection].items():
                                    field_from_alias = (
                                        Collection.get_collection_field_from_alias(
                                            field
                                        )
                                    )

                                    # a field was bad formatted if it was not part of the model fields
                                    if field_from_alias not in Collection.model_fields:
                                        bad_formatted_col_count += 1
                                        break

                                    default = Collection.model_fields[
                                        field_from_alias
                                    ].get_default()
                                    default_json = (
                                        default.model_dump(mode="json")
                                        if isinstance(default, BaseModel)
                                        else default
                                    )
                                    formatted_v = new_coll_obj.__dict__[
                                        field_from_alias
                                    ]

                                    # a field was bad formatted also if its value has been reformatted to its
                                    # default value and it is not a static field or without a null value

                                    # NOTE: this check works while there is no transformation of values in model
                                    # validators to make them pass for fields where the default value is not null.
                                    # For instance, for a field "foo" with default value "bar" having "BAR" in input,
                                    # if a "before" validator uses "lower()" without raising an error, the input would
                                    # be considered as well formatted while increment would increase as
                                    # "v != default_json" statement would give True.
                                    if (
                                        formatted_v == default
                                        and v != default_json
                                        and (
                                            field_from_alias
                                            not in Collection.__static_fields__
                                            or v is not None
                                        )
                                    ):
                                        bad_formatted_col_count += 1
                                        break

                if new_collections:
                    logger.debug(
                        "Added %s collections for %s", new_collections, provider
                    )
                    if bad_formatted_col_count > 0:
                        logger.debug(
                            "bad formatted attributes skipped for %s collection(s) on %s",
                            bad_formatted_col_count,
                            provider,
                        )

                    # Persist new collection-provider links to DB
                    new_coll_fb_configs = [
                        CollectionProviderConfig(
                            coll_id,
                            provider,
                            {"search": coll_conf}
                            if not fb_pc.get("api")
                            else {"api": coll_conf},
                        )
                        for coll_id, coll_conf in provider_products_config.items()
                        if coll_id
                        not in self.db.get_collection_configs_for_backend(provider)
                    ]
                    if new_coll_fb_configs:
                        self.db.upsert_collections_federation_backends(
                            new_coll_fb_configs
                        )

            elif provider not in all_backend_names:
                # unknown provider
                continue

            self.db.set_federation_backend_last_fetch(
                provider, datetime.datetime.now(datetime.timezone.utc).isoformat()
            )

        if all_new_collections:
            self.db.upsert_collections(CollectionsDict(all_new_collections))

    @_deprecated(
        reason="Please use 'EODataAccessGateway.providers' instead",
        version="4.0.0",
    )
    def available_providers(
        self, collection: Optional[str] = None, by_group: bool = False
    ) -> list[str]:
        """Gives the sorted list of the available providers or groups

        .. deprecated:: v4.0.0
            Please use :attr:`eodag.api.core.EODataAccessGateway.providers` instead.

        The providers or groups are sorted first by their priority level in descending order,
        and then alphabetically in ascending order for providers or groups with the same
        priority level.

        :param collection: (optional) Only list providers configured for this collection
        :param by_group: (optional) If set to True, list groups when available instead
                         of providers, mixed with other providers
        :returns: the sorted list of the available providers or groups
        """
        candidates = []

        # use DB to get providers sorted by priority
        if collection:
            # only providers configured for this collection
            fb_configs = self.db.get_collection_federation_backends(collection)
            all_fb = self.db.get_federation_backends(list(fb_configs.keys()))
        else:
            all_fb = self.db.get_federation_backends()

        for key, fb_data in sorted(
            all_fb.items(), key=lambda item: (-item[1]["priority"], item[0])
        ):
            if not fb_data.get("enabled"):
                continue
            group = (fb_data.get("metadata") or {}).get("group")
            name = group if by_group and group else key
            candidates.append((name, fb_data["priority"]))

        if by_group:
            # Keep only the highest-priority entry per group
            grouped: dict[str, int] = {}
            for name, priority in candidates:
                if name not in grouped or priority > grouped[name]:
                    grouped[name] = priority
            candidates = list(grouped.items())

        return [name for name, _ in candidates]

    @_deprecated(
        reason="Please use 'EODataAccessGateway.get_collection' instead",
        version="5.0.0",
    )
    def get_collection_from_alias(self, alias_or_id: str) -> str:
        """Return the id of a collection by either its id or alias

        :param alias_or_id: Alias of the collection. If an existing id is given, this
                            method will directly return the given value.
        :returns: Internal name of the collection.
        """
        collections = self.list_collections(ids=[alias_or_id])

        if len(collections) > 1:
            raise NoMatchingCollection(
                f"Too many matching collections for alias {alias_or_id}: {collections}"
            )

        if len(collections) == 0:
            raise NoMatchingCollection(
                f"Could not find collection from alias or id {alias_or_id}"
            )

        return collections[0]._id or collections[0].id

    @_deprecated(
        reason="Please use 'EODataAccessGateway.get_collection' instead",
        version="5.0.0",
    )
    def get_alias_from_collection(self, collection: str) -> str:
        """Return the alias of a collection by its id. If no alias was defined for the
        given collection, its id is returned instead.

        :param collection: collection id
        :returns: Alias of the collection or its id if no alias has been defined for it.
        """
        coll_id = self.get_collection(collection)

        if not coll_id:
            raise NoMatchingCollection(collection)

        return coll_id.id

    @_deprecated(
        reason="Please use 'EODataAccessGateway.list_collections' instead.",
        version="5.0.0",
    )
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
        """Find collections best matching a set of search parameters.

        .. deprecated:: v5.0.0
            Use :meth:`list_collections` with ``q`` / ``datetime`` instead.

        Delegates to :meth:`list_collections` using ``q`` for free-text /
        filter values and ``datetime`` for temporal bounds.

        :param free_text: Free text search terms (supports ``AND``/``OR``,
                          quoted phrases, ``*``/``?`` wildcards).
        :param intersect: (ignored, kept for backwards compatibility)
        :param instruments: Instruments value added to ``q``.
        :param platform: Platform value added to ``q``.
        :param constellation: Constellation value added to ``q``.
        :param processing_level: Processing level value added to ``q``.
        :param sensor_type: Sensor type value added to ``q``.
        :param keywords: Keywords value added to ``q``.
        :param description: Description value added to ``q``.
        :param title: Title value added to ``q``.
        :param start_date: Start date for datetime filtering (RFC 3339).
        :param end_date: End date for datetime filtering (RFC 3339).
        :returns: Matching collections ranked by FTS relevance.
        :raises: :class:`~eodag.utils.exceptions.NoMatchingCollection`
        """
        # Shortcut: explicit collection id/alias
        if coll_id := kwargs.get("collection"):
            coll = self.get_collection(coll_id)
            return [coll.id if coll else coll_id]

        q_sep = " AND " if intersect else " OR "
        q_terms: list[str] = []
        if free_text:
            q_terms.append(free_text)
        for value in (
            instruments,
            platform,
            constellation,
            processing_level,
            sensor_type,
            keywords,
            description,
            title,
        ):
            if value is not None:
                # Quote multi-word values as FTS5 phrases
                if " " in value and not (value.startswith('"') and value.endswith('"')):
                    value = f'"{value}"'
                q_terms.append(value)

        # Build datetime string from start_date / end_date
        dt: Optional[str] = None
        if start_date and end_date:
            dt = f"{start_date}/{end_date}"
        elif start_date:
            dt = f"{start_date}/.."
        elif end_date:
            dt = f"../{end_date}"

        if not q_terms and not dt:
            raise NoMatchingCollection("No search terms provided to guess collection")

        results = self.list_collections(
            q=q_sep.join(q_terms) if q_terms else None,
            datetime=dt,
        )

        if not results:
            raise NoMatchingCollection(
                "Could not find any collection matching the given parameters"
            )

        return results.ids

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
                " -- Deprecated since v4.0.0",
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
                if count and search_results.number_matched:
                    logger.info(
                        "Found %s result(s) on provider '%s'",
                        search_results.number_matched,
                        search_results[0].provider,
                    )
                return search_results

        if i > 1:
            logger.error("No result could be obtained from any available provider")
        return SearchResult([], 0, errors) if count else SearchResult([], errors=errors)

    @_deprecated(
        reason="Please use 'SearchResult.next_page()' instead",
        version="4.0.0",
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

        .. deprecated:: v4.0.0
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
        version="4.0.0",
    )
    def search_iter_page_plugin(
        self,
        search_plugin: Union[Search, Api],
        items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
        **kwargs: Any,
    ) -> Iterator[SearchResult]:
        """Iterate over the pages of a products search using a given search plugin.

        .. deprecated:: v4.0.0
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
            search_results.number_matched = len(search_results)
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
        collection_id = kwargs.get("collection")
        coll = self.get_collection(collection_id) if collection_id else None
        collection = coll._id if coll else collection_id
        if collection_id and not coll:
            logger.debug("collection %s not found", collection_id)
        get_search_plugins_kwargs = dict(provider=provider, collection=collection)

        search_plugins = self._plugin_manager.get_search_plugins(
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
        plugins = self._plugin_manager.get_search_plugins(provider=provider)
        plugin = next(plugins)

        # check after plugin init if still fetchable
        if not getattr(plugin.config, "discover_collections", {}).get("fetch_url"):
            return None

        kwargs: dict[str, Any] = {"collection": collection}

        # append auth if needed
        if getattr(plugin.config, "need_auth", False):
            if auth := self.get_auth(
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
            coll = self.get_collection(collection)
            if coll:
                collection = coll._id
            else:
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

        preferred_provider = self.get_preferred_provider()[0]

        collection_exists = bool(self.get_collection(collection))

        search_plugins: list[Union[Search, Api]] = []

        self.db.get_config
        providers = self.get_providers(collection=collection, enabled=True)

        for plugin in self._plugin_manager.get_search_plugins(
            collection=collection, provider=provider
        ):
            # exclude MeteoblueSearch plugins from search fallback for unknown collection
            if (
                provider != plugin.provider
                and preferred_provider != plugin.provider
                and not collection_exists
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

        return collection, kwargs

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
                if auth := self.get_auth(
                    search_plugin.provider,
                    getattr(search_plugin.config, "api_endpoint", None),
                    search_plugin.config,
                ):
                    prep.auth = auth

            prep.items_per_page = kwargs.pop("items_per_page", None)
            prep.next_page_token = kwargs.pop("next_page_token", None)
            prep.next_page_token_key = kwargs.pop(
                "next_page_token_key", None
            ) or search_plugin.config.pagination.get("next_page_token_key", "page")
            prep.page = kwargs.pop("page", None)

            if (
                prep.next_page_token_key == "page"
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
            queryables_fields = Queryables.from_stac_models().model_fields
            ecmwf_queryables = [
                f"{ECMWF_PREFIX[:-1]}_{k}" for k in ECMWF_ALLOWED_KEYWORDS
            ]
            for param, value in kwargs.items():
                if value is None:
                    continue
                if param in queryables_fields:
                    param_alias = queryables_fields[param].alias or param
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
                # if collection is not defined, try to guess using properties
                if eo_product.collection is None:
                    pattern = re.compile(r"[^\w,]+")
                    try:
                        guesses = self.guess_collection(
                            intersect=False,
                            **{
                                k: pattern.sub("", str(v).upper())
                                for k, v in eo_product.properties.items()
                                if k
                                in [
                                    "instruments",
                                    "constellation",
                                    "platform",
                                    "processing:level",
                                    "eodag:sensor_type",
                                    "keywords",
                                ]
                                and v is not None
                            },
                        )
                    except NoMatchingCollection:
                        pass
                    else:
                        eo_product.collection = guesses[0]

                if eo_product.search_intersection is not None:
                    eo_product._register_downloader(self)

            # Make next_page not available if the current one returned less than the maximum number of items asked for.
            if not prep.items_per_page or len(search_result) < prep.items_per_page:
                search_result.next_page_token = None

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
            cruncher = PluginManager.get_crunch_plugin(cruncher_name, **cruncher_args)
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
        executor: Optional[ThreadPoolExecutor] = None,
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
        :param executor: (optional) An executor to download EO products of ``search_result`` in parallel
                                    which will also be reused to download assets of these products in parallel.
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
            # Get download plugin using first product assuming all plugins use base.Download.download_all
            download_plugin = self._plugins_manager.get_download_plugin(
                search_result[0]
            )
            paths = download_plugin.download_all(
                search_result,
                downloaded_callback=downloaded_callback,
                progress_callback=progress_callback,
                executor=executor,
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
        search_result_dict = search_result.as_geojson_object()
        # add self link
        search_result_dict.setdefault("links", [])
        search_result_dict["links"].append(
            {
                "rel": "self",
                "href": f"{filename}",
                "type": "application/json",
            },
        )
        # write search results
        with open(filename, "w") as fh:
            geojson.dump(search_result_dict, fh)
            logger.debug("Search results saved to %s", filename)
        # write collection(s)
        if search_result._dag is None:
            return filename
        collections = set(p.collection for p in search_result)
        existing_collections = search_result._dag.list_collections(
            ids=list(collections)
        )
        for collection in collections:
            collection_obj = existing_collections.get(collection) or Collection(
                id=collection
            )
            collection_dict = collection_obj.model_dump(
                display_extensions=True,
                mode="json",
                exclude_none=True,
                exclude={"alias"},
            )
            # add links
            collection_dict["links"].append(
                {
                    "rel": "self",
                    "href": f"{collection}.json",
                    "type": "application/json",
                },
            )
            with open(Path(filename).parent / f"{collection}.json", "w") as fh:
                geojson.dump(collection_dict, fh)
                logger.debug("Collection '%s' saved to %s", collection, fh.name)

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
        executor: Optional[ThreadPoolExecutor] = None,
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
        :param executor: (optional) An executor to download assets of ``product`` in parallel if it has any. If ``None``
                         , a default executor will be created
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
            progress_callback=progress_callback,
            executor=executor,
            wait=wait,
            timeout=timeout,
            **kwargs,
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
        return PluginManager.get_crunch_plugin(name, **plugin_conf)

    def list_queryables(
        self,
        provider: Optional[str] = None,
        **kwargs: Any,
    ) -> QueryablesDict:
        """Fetch the queryable properties for a given collection and/or provider.

        :param provider: (optional) The provider.
        :param kwargs: additional filters for queryables (`collection` or other search arguments)
        :returns: A :class:`~eodag.api.product.queryables.QueryablesDict` containing the EODAG queryable
                  properties, associating parameters to their annotated type, and a additional_properties attribute
        """
        available_collections = self.list_collections(
            providers=[provider] if provider else None
        ).ids
        collection: Optional[str] = kwargs.get("collection")
        coll_alias: Optional[str] = collection

        if collection:
            coll = self.get_collection(
                collection, providers=[provider] if provider else None
            )
            kwargs["collection"] = collection = coll._id if coll else collection

        if not provider and not collection:
            return QueryablesDict(
                additional_properties=True,
                **model_fields_to_annotated(CommonQueryables.model_fields),
            )

        additional_properties = False
        additional_information = []
        queryable_properties: dict[str, Any] = {}

        for plugin in self._plugin_manager.get_search_plugins(collection, provider):
            # attach collection config
            collection_configs: dict[str, Any] = {}
            if collection:
                self._attach_collection_config(plugin, collection)
                collection_configs[collection] = plugin.config.collection_config
            else:
                for col in available_collections:
                    self._attach_collection_config(plugin, col)
                    collection_configs[col] = plugin.config.collection_config

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
            queryables_fields = Queryables.from_stac_models().model_fields
            for search_param, field_info in queryables_fields.items():
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
        coll = self.get_collection(collection, providers=[plugin.provider])

        plugin.provider

        if coll:
            plugin.config.collection_config = coll.model_dump(
                mode="json", exclude={"id"}
            ) | {"collection": coll._id}

        # If the product isn't in the catalog, it's a generic collection.
        else:
            # Construct the GENERIC_COLLECTION metadata
            plugin.config.collection_config = dict(
                **self.get_collection(GENERIC_COLLECTION).model_dump(
                    mode="json", exclude={"id"}
                ),
                collection=collection,
            )

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
            if search_result := SearchResult._from_stac_item(json_item, self):
                results.extend(search_result)

        return results
