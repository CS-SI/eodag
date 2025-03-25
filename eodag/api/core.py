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
from importlib.metadata import version
from importlib.resources import files as res_files
from operator import itemgetter
from typing import TYPE_CHECKING, Any, Iterator, Optional, Union

import geojson
import yaml.parser
from whoosh import analysis, fields
from whoosh.fields import Schema
from whoosh.index import exists_in, open_dir
from whoosh.qparser import QueryParser

from eodag.api.product.metadata_mapping import (
    ONLINE_STATUS,
    mtd_cfg_as_conversion_and_querypath,
)
from eodag.api.search_result import SearchResult
from eodag.config import (
    PLUGINS_TOPICS_KEYS,
    PluginConfig,
    SimpleYamlProxyConfig,
    credentials_in_auth,
    get_ext_product_types_conf,
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
from eodag.plugins.search.build_search_result import MeteoblueSearch
from eodag.plugins.search.qssearch import PostJsonSearch
from eodag.types import model_fields_to_annotated
from eodag.types.queryables import CommonQueryables, QueryablesDict
from eodag.types.whoosh import EODAGQueryParser, create_in
from eodag.utils import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    DEFAULT_ITEMS_PER_PAGE,
    DEFAULT_MAX_ITEMS_PER_PAGE,
    DEFAULT_PAGE,
    GENERIC_PRODUCT_TYPE,
    HTTP_REQ_TIMEOUT,
    MockResponse,
    _deprecated,
    get_geometry_from_various,
    makedirs,
    obj_md5sum,
    sort_dict,
    string_to_jsonpath,
    uri_to_path,
)
from eodag.utils.exceptions import (
    AuthenticationError,
    EodagError,
    NoMatchingProductType,
    PluginImplementationError,
    RequestError,
    UnsupportedProductType,
    UnsupportedProvider,
)
from eodag.utils.rest import rfc3339_str_to_datetime
from eodag.utils.stac_reader import fetch_stac_items

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry
    from whoosh.index import Index

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
        product_types_config_path = os.getenv("EODAG_PRODUCT_TYPES_CFG_FILE") or str(
            res_files("eodag") / "resources" / "product_types.yml"
        )
        self.product_types_config = SimpleYamlProxyConfig(product_types_config_path)
        self.product_types_config_md5 = obj_md5sum(self.product_types_config.source)
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
        for provider in self.providers_config.keys():
            provider_config_init(
                self.providers_config[provider],
                load_stac_provider_config(),
            )

        # re-build _plugins_manager using up-to-date providers_config
        self._plugins_manager.rebuild(self.providers_config)

        # store pruned providers configs
        self._pruned_providers_config: dict[str, Any] = {}
        # filter out providers needing auth that have no credentials set
        self._prune_providers_list()

        # Sort providers taking into account of possible new priority orders
        self._plugins_manager.sort_providers()

        # Build a search index for product types
        self._product_types_index: Optional[Index] = None
        self.build_index()

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

    def get_version(self) -> str:
        """Get eodag package version"""
        return version("eodag")

    def build_index(self) -> None:
        """Build a `Whoosh <https://whoosh.readthedocs.io/en/latest/index.html>`_
        index for product types searches.
        """
        index_dir = os.path.join(self.conf_dir, ".index")

        try:
            create_index = not exists_in(index_dir)
        except ValueError as ve:
            # Whoosh uses pickle internally. New versions of Python sometimes introduce
            # a new pickle protocol (e.g. 3.4 -> 4, 3.8 -> 5), the new version not
            # being supported by previous versions of Python (e.g. Python 3.7 doesn't
            # support Protocol 5). In that case, we need to recreate the .index.
            if "unsupported pickle protocol" in str(ve):
                logger.debug("Need to recreate whoosh .index: '%s'", ve)
                create_index = True
            # Unexpected error
            else:
                logger.error(
                    "Error while opening .index using whoosh, "
                    "please report this issue and try to delete '%s' manually",
                    index_dir,
                )
                raise
        # check index version
        if not create_index:
            if self._product_types_index is None:
                logger.debug("Opening product types index in %s", index_dir)
                self._product_types_index = open_dir(index_dir)

            with self._product_types_index.searcher() as searcher:
                p = QueryParser("md5", self._product_types_index.schema, plugins=[])
                query = p.parse(self.product_types_config_md5)
                results = searcher.search(query, limit=1)

                if not results:
                    create_index = True
                    logger.debug(
                        "Out-of-date product types index removed from %s", index_dir
                    )

        if create_index:
            logger.debug("Creating product types index in %s", index_dir)
            makedirs(index_dir)

            kw_analyzer = (
                analysis.CommaSeparatedTokenizer()
                | analysis.LowercaseFilter()
                | analysis.SubstitutionFilter("-", "")
                | analysis.SubstitutionFilter("_", "")
            )

            product_types_schema = Schema(
                ID=fields.ID(stored=True),
                abstract=fields.TEXT,
                instrument=fields.IDLIST,
                platform=fields.ID,
                platformSerialIdentifier=fields.IDLIST,
                processingLevel=fields.ID,
                sensorType=fields.ID,
                md5=fields.ID,
                license=fields.ID,
                title=fields.TEXT,
                missionStartDate=fields.STORED,
                missionEndDate=fields.STORED,
                keywords=fields.KEYWORD(analyzer=kw_analyzer),
                stacCollection=fields.STORED,
            )
            self._product_types_index = create_in(index_dir, product_types_schema)
            ix_writer = self._product_types_index.writer()
            for product_type in self.list_product_types(fetch_providers=False):
                versioned_product_type = dict(
                    product_type, **{"md5": self.product_types_config_md5}
                )
                # add to index
                try:
                    ix_writer.add_document(
                        **{
                            k: v
                            for k, v in versioned_product_type.items()
                            if k in product_types_schema.names()
                        }
                    )
                except TypeError as e:
                    logger.error(
                        f"Cannot write product type {product_type['ID']} into index. e={e} product_type={product_type}"
                    )
            ix_writer.commit()

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
            setattr(self.providers_config[provider], "product_types_fetched", False)
        # re-create _plugins_manager using up-to-date providers_config
        self._plugins_manager.build_product_type_to_provider_config_map()

    def add_provider(
        self,
        name: str,
        url: Optional[str] = None,
        priority: Optional[int] = None,
        search: dict[str, Any] = {"type": "StacSearch"},
        products: dict[str, Any] = {
            GENERIC_PRODUCT_TYPE: {"productType": "{productType}"}
        },
        download: dict[str, Any] = {"type": "HTTPDownload", "auth_error_code": 401},
        **kwargs: dict[str, Any],
    ):
        """Adds a new provider.

        ``search``, ``products`` & ``download`` already have default values that will be
        updated (not replaced), with user provided ones:

            * ``search`` : ``{"type": "StacSearch"}``
            * ``products`` : ``{"GENERIC_PRODUCT_TYPE": {"productType": "{productType}"}}``
            * ``download`` : ``{"type": "HTTPDownload", "auth_error_code": 401}``

        :param name: Name of provider
        :param url: Provider url, also used as ``search["api_endpoint"]`` if not defined
        :param priority: Provider priority. If None, provider will be set as preferred (highest priority)
        :param search: Search :class:`~eodag.config.PluginConfig` mapping
        :param products: Provider product types mapping
        :param download: Download :class:`~eodag.config.PluginConfig` mapping
        :param kwargs: Additional :class:`~eodag.config.ProviderConfig` mapping
        """
        conf_dict: dict[str, Any] = {
            name: {
                "url": url,
                "search": {"type": "StacSearch", **search},
                "products": {
                    GENERIC_PRODUCT_TYPE: {"productType": "{productType}"},
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

    def list_product_types(
        self, provider: Optional[str] = None, fetch_providers: bool = True
    ) -> list[dict[str, Any]]:
        """Lists supported product types.

        :param provider: (optional) The name of a provider that must support the product
                         types we are about to list
        :param fetch_providers: (optional) Whether to fetch providers for new product
                                types or not
        :returns: The list of the product types that can be accessed using eodag.
        :raises: :class:`~eodag.utils.exceptions.UnsupportedProvider`
        """
        if fetch_providers:
            # First, update product types list if possible
            self.fetch_product_types_list(provider=provider)

        product_types: list[dict[str, Any]] = []

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
            for product_type_id in p.products:  # type: ignore
                if product_type_id == GENERIC_PRODUCT_TYPE:
                    continue
                config = self.product_types_config[product_type_id]
                config["_id"] = product_type_id
                if "alias" in config:
                    product_type_id = config["alias"]
                product_type = {"ID": product_type_id, **config}
                if product_type not in product_types:
                    product_types.append(product_type)

        # Return the product_types sorted in lexicographic order of their ID
        return sorted(product_types, key=itemgetter("ID"))

    def fetch_product_types_list(self, provider: Optional[str] = None) -> None:
        """Fetch product types list and update if needed

        :param provider: The name of a provider or provider-group for which product types
                         list should be updated. Defaults to all providers (None value).
        """
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
                    f"Fetch product types for {provider} group: {', '.join(providers_to_fetch)}"
                )
            else:
                return None
        elif provider is not None:
            providers_to_fetch = [provider]

        # providers discovery confs that are fetchable
        providers_discovery_configs_fetchable: dict[str, Any] = {}
        # check if any provider has not already been fetched for product types
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
            discovery_conf = getattr(
                provider_search_config, "discover_product_types", {}
            )
            if discovery_conf.get("fetch_url", None):
                providers_discovery_configs_fetchable[
                    provider_to_fetch
                ] = discovery_conf
                if not getattr(provider_config, "product_types_fetched", False):
                    already_fetched = False

        if not already_fetched:
            # get ext_product_types conf
            ext_product_types_cfg_file = os.getenv("EODAG_EXT_PRODUCT_TYPES_CFG_FILE")
            if ext_product_types_cfg_file is not None:
                ext_product_types_conf = get_ext_product_types_conf(
                    ext_product_types_cfg_file
                )
            else:
                ext_product_types_conf = get_ext_product_types_conf()

                if not ext_product_types_conf:
                    # empty ext_product_types conf
                    ext_product_types_conf = (
                        self.discover_product_types(provider=provider) or {}
                    )

            # update eodag product types list with new conf
            self.update_product_types_list(ext_product_types_conf)

        # Compare current provider with default one to see if it has been modified
        # and product types list would need to be fetched

        # get ext_product_types conf for user modified providers
        default_providers_config = load_default_config()
        for (
            provider,
            user_discovery_conf,
        ) in providers_discovery_configs_fetchable.items():
            # default discover_product_types conf
            if provider in default_providers_config:
                default_provider_config = default_providers_config[provider]
                if hasattr(default_provider_config, "search"):
                    default_provider_search_config = default_provider_config.search
                elif hasattr(default_provider_config, "api"):
                    default_provider_search_config = default_provider_config.api
                else:
                    continue
                default_discovery_conf = getattr(
                    default_provider_search_config, "discover_product_types", {}
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
                                generic_product_type_id=default_discovery_conf[
                                    "generic_product_type_id"
                                ]
                            )
                        ),
                        **dict(
                            generic_product_type_parsable_properties=mtd_cfg_as_conversion_and_querypath(
                                default_discovery_conf[
                                    "generic_product_type_parsable_properties"
                                ]
                            )
                        ),
                        **dict(
                            generic_product_type_parsable_metadata=mtd_cfg_as_conversion_and_querypath(
                                default_discovery_conf[
                                    "generic_product_type_parsable_metadata"
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
                    not default_discovery_conf.get("fetch_url", None)
                    or "ext_product_types_conf" not in locals()
                    or "ext_product_types_conf" in locals()
                    and (
                        provider in ext_product_types_conf
                        or len(ext_product_types_conf.keys()) == 0
                    )
                ):
                    continue
                # providers not skipped here should be user-modified
                # or not in ext_product_types_conf (if eodag system conf != eodag conf used for ext_product_types_conf)

            if not already_fetched:
                # discover product types for user configured provider
                provider_ext_product_types_conf = (
                    self.discover_product_types(provider=provider) or {}
                )
                # update eodag product types list with new conf
                self.update_product_types_list(provider_ext_product_types_conf)

    def discover_product_types(
        self, provider: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """Fetch providers for product types

        :param provider: The name of a provider or provider-group to fetch. Defaults to
                         all providers (None value).
        :returns: external product types configuration
        """
        grouped_providers = [
            p
            for p, provider_config in self.providers_config.items()
            if provider == getattr(provider_config, "group", None)
        ]
        if provider and provider not in self.providers_config and grouped_providers:
            logger.info(
                f"Discover product types for {provider} group: {', '.join(grouped_providers)}"
            )
        elif provider and provider not in self.providers_config:
            raise UnsupportedProvider(
                f"The requested provider is not (yet) supported: {provider}"
            )
        ext_product_types_conf: dict[str, Any] = {}
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
            if getattr(search_plugin_config, "discover_product_types", {}).get(
                "fetch_url", None
            ):
                search_plugin: Union[Search, Api] = next(
                    self._plugins_manager.get_search_plugins(provider=provider)
                )
                # check after plugin init if still fetchable
                if not getattr(search_plugin.config, "discover_product_types", {}).get(
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
                            f"Could not authenticate on {provider} for product types discovery"
                        )
                        ext_product_types_conf[provider] = None
                        continue

                ext_product_types_conf[provider] = search_plugin.discover_product_types(
                    **kwargs
                )

        return sort_dict(ext_product_types_conf)

    def update_product_types_list(
        self, ext_product_types_conf: dict[str, Optional[dict[str, dict[str, Any]]]]
    ) -> None:
        """Update eodag product types list

        :param ext_product_types_conf: external product types configuration
        """
        for provider, new_product_types_conf in ext_product_types_conf.items():
            if new_product_types_conf and provider in self.providers_config:
                try:
                    search_plugin_config = getattr(
                        self.providers_config[provider], "search", None
                    ) or getattr(self.providers_config[provider], "api", None)
                    if search_plugin_config is None:
                        continue
                    if not getattr(
                        search_plugin_config, "discover_product_types", {}
                    ).get("fetch_url", None):
                        # conf has been updated and provider product types are no more discoverable
                        continue
                    provider_products_config = (
                        self.providers_config[provider].products or {}
                    )
                except UnsupportedProvider:
                    logger.debug(
                        "Ignoring external product types for unknown provider %s",
                        provider,
                    )
                    continue
                new_product_types: list[str] = []
                for (
                    new_product_type,
                    new_product_type_conf,
                ) in new_product_types_conf["providers_config"].items():
                    if new_product_type not in provider_products_config:
                        for existing_product_type in provider_products_config.copy():
                            # compare parsed extracted conf (without metadata_mapping entry)
                            unparsable_keys = (
                                search_plugin_config.discover_product_types.get(
                                    "generic_product_type_unparsable_properties", {}
                                ).keys()
                            )
                            new_parsed_product_types_conf = {
                                k: v
                                for k, v in new_product_type_conf.items()
                                if k not in unparsable_keys
                            }
                            if (
                                new_parsed_product_types_conf.items()
                                <= provider_products_config[
                                    existing_product_type
                                ].items()
                            ):
                                # new_product_types_conf is a subset on an existing conf
                                break
                        else:
                            # new_product_type_conf does not already exist, append it
                            # to provider_products_config
                            provider_products_config[
                                new_product_type
                            ] = new_product_type_conf
                            # to self.product_types_config
                            self.product_types_config.source.update(
                                {
                                    new_product_type: new_product_types_conf[
                                        "product_types_config"
                                    ][new_product_type]
                                }
                            )
                            self.product_types_config_md5 = obj_md5sum(
                                self.product_types_config.source
                            )
                            ext_product_types_conf[provider] = new_product_types_conf
                            new_product_types.append(new_product_type)
                if new_product_types:
                    logger.debug(
                        f"Added {len(new_product_types)} product types for {provider}"
                    )

            elif provider not in self.providers_config:
                # unknown provider
                continue
            self.providers_config[provider].product_types_fetched = True

        # re-create _plugins_manager using up-to-date providers_config
        self._plugins_manager.build_product_type_to_provider_config_map()

        # rebuild index after product types list update
        self.build_index()

    def available_providers(
        self, product_type: Optional[str] = None, by_group: bool = False
    ) -> list[str]:
        """Gives the sorted list of the available providers or groups

        The providers or groups are sorted first by their priority level in descending order,
        and then alphabetically in ascending order for providers or groups with the same
        priority level.

        :param product_type: (optional) Only list providers configured for this product_type
        :param by_group: (optional) If set to True, list groups when available instead
                         of providers, mixed with other providers
        :returns: the sorted list of the available providers or groups
        """

        if product_type:
            providers = [
                (v.group if by_group and hasattr(v, "group") else k, v.priority)
                for k, v in self.providers_config.items()
                if product_type in getattr(v, "products", {}).keys()
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

    def get_product_type_from_alias(self, alias_or_id: str) -> str:
        """Return the ID of a product type by either its ID or alias

        :param alias_or_id: Alias of the product type. If an existing ID is given, this
                            method will directly return the given value.
        :returns: Internal name of the product type.
        """
        product_types = [
            k
            for k, v in self.product_types_config.items()
            if v.get("alias", None) == alias_or_id
        ]

        if len(product_types) > 1:
            raise NoMatchingProductType(
                f"Too many matching product types for alias {alias_or_id}: {product_types}"
            )

        if len(product_types) == 0:
            if alias_or_id in self.product_types_config:
                return alias_or_id
            else:
                raise NoMatchingProductType(
                    f"Could not find product type from alias or ID {alias_or_id}"
                )

        return product_types[0]

    def get_alias_from_product_type(self, product_type: str) -> str:
        """Return the alias of a product type by its ID. If no alias was defined for the
        given product type, its ID is returned instead.

        :param product_type: product type ID
        :returns: Alias of the product type or its ID if no alias has been defined for it.
        """
        if product_type not in self.product_types_config:
            raise NoMatchingProductType(product_type)

        return self.product_types_config[product_type].get("alias", product_type)

    def guess_product_type(
        self,
        free_text: Optional[str] = None,
        intersect: bool = False,
        instrument: Optional[str] = None,
        platform: Optional[str] = None,
        platformSerialIdentifier: Optional[str] = None,
        processingLevel: Optional[str] = None,
        sensorType: Optional[str] = None,
        keywords: Optional[str] = None,
        abstract: Optional[str] = None,
        title: Optional[str] = None,
        missionStartDate: Optional[str] = None,
        missionEndDate: Optional[str] = None,
        **kwargs: Any,
    ) -> list[str]:
        """
        Find EODAG product type IDs that best match a set of search parameters.

        See https://whoosh.readthedocs.io/en/latest/querylang.html#the-default-query-language
          for syntax.

        :param free_text: Whoosh-compatible free text search filter used to search
                        accross all the following parameters
        :param intersect: Join results for each parameter using INTERSECT instead of UNION.
        :param instrument: Instrument parameter.
        :param platform: Platform parameter.
        :param platformSerialIdentifier: Platform serial identifier parameter.
        :param processingLevel: Processing level parameter.
        :param sensorType: Sensor type parameter.
        :param keywords: Keywords parameter.
        :param abstract: Abstract parameter.
        :param title: Title parameter.
        :param missionStartDate: start date for datetime filtering. Not used by free_text
        :param missionEndDate: end date for datetime filtering. Not used by free_text
        :returns: The best match for the given parameters.
        :raises: :class:`~eodag.utils.exceptions.NoMatchingProductType`
        """
        if productType := kwargs.get("productType"):
            return [productType]

        if not self._product_types_index:
            raise EodagError("Missing product types index")

        filters = {
            "instrument": instrument,
            "platform": platform,
            "platformSerialIdentifier": platformSerialIdentifier,
            "processingLevel": processingLevel,
            "sensorType": sensorType,
            "keywords": keywords,
            "abstract": abstract,
            "title": title,
        }
        joint = " AND " if intersect else " OR "
        filters_text = joint.join(
            [f"{k}:({v})" for k, v in filters.items() if v is not None]
        )

        text = f"({free_text})" if free_text else ""
        if free_text and filters_text:
            text += joint
        if filters_text:
            text += f"({filters_text})"

        if not text and (missionStartDate or missionEndDate):
            text = "*"

        with self._product_types_index.searcher() as searcher:
            p = EODAGQueryParser(list(filters.keys()), self._product_types_index.schema)
            query = p.parse(text)
            results = searcher.search(query, limit=None)

            guesses: list[dict[str, str]] = [dict(r) for r in results or []]

        # datetime filtering
        if missionStartDate or missionEndDate:
            min_aware = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
            max_aware = datetime.datetime.max.replace(tzinfo=datetime.timezone.utc)
            guesses = [
                g
                for g in guesses
                if (
                    max(
                        rfc3339_str_to_datetime(missionStartDate)
                        if missionStartDate
                        else min_aware,
                        rfc3339_str_to_datetime(g["missionStartDate"])
                        if g.get("missionStartDate")
                        else min_aware,
                    )
                    <= min(
                        rfc3339_str_to_datetime(missionEndDate)
                        if missionEndDate
                        else max_aware,
                        rfc3339_str_to_datetime(g["missionEndDate"])
                        if g.get("missionEndDate")
                        else max_aware,
                    )
                )
            ]

        if guesses:
            return [g["ID"] for g in guesses or []]

        raise NoMatchingProductType()

    def search(
        self,
        page: int = DEFAULT_PAGE,
        items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
        raise_errors: bool = False,
        start: Optional[str] = None,
        end: Optional[str] = None,
        geom: Optional[Union[str, dict[str, float], BaseGeometry]] = None,
        locations: Optional[dict[str, str]] = None,
        provider: Optional[str] = None,
        count: bool = False,
        **kwargs: Any,
    ) -> SearchResult:
        """Look for products matching criteria on known providers.

        The default behaviour is to look for products on the provider with the
        highest priority supporting the requested product type. These priorities
        are configurable through user configuration file or individual environment variable.
        If the request to the provider with the highest priority fails or is empty, the data
        will be request from the provider with the next highest priority.
        Only if the request fails for all available providers, an error will be thrown.

        :param page: (optional) The page number to return
        :param items_per_page: (optional) The number of results that must appear in one single
                               page
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
        :param kwargs: Some other criteria that will be used to do the search,
                       using paramaters compatibles with the provider
        :returns: A collection of EO products matching the criteria

        .. versionchanged:: v3.0.0b1
            ``search()`` method now returns only a single :class:`~eodag.api.search_result.SearchResult`
            instead of a 2 values tuple.

        .. note::
            The search interfaces, which are implemented as plugins, are required to
            return a list as a result of their processing. This requirement is
            enforced here.
        """
        search_plugins, search_kwargs = self._prepare_search(
            start=start,
            end=end,
            geom=geom,
            locations=locations,
            provider=provider,
            **kwargs,
        )
        if search_kwargs.get("id"):
            return self._search_by_id(
                search_kwargs.pop("id"),
                provider=provider,
                raise_errors=raise_errors,
                **search_kwargs,
            )
        # remove datacube query string from kwargs which was only needed for search-by-id
        search_kwargs.pop("_dc_qs", None)

        search_kwargs.update(
            page=page,
            items_per_page=items_per_page,
        )

        errors: list[tuple[str, Exception]] = []
        # Loop over available providers and return the first non-empty results
        for i, search_plugin in enumerate(search_plugins):
            search_plugin.clear()
            search_results = self._do_search(
                search_plugin,
                count=count,
                raise_errors=raise_errors,
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
        :returns: An iterator that yields page per page a collection of EO products
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

    def search_iter_page_plugin(
        self,
        search_plugin: Union[Search, Api],
        items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
        **kwargs: Any,
    ) -> Iterator[SearchResult]:
        """Iterate over the pages of a products search using a given search plugin.

        :param items_per_page: (optional) The number of results requested per page
        :param kwargs: Some other criteria that will be used to do the search,
                       using parameters compatibles with the provider
        :param search_plugin: search plugin to be used
        :returns: An iterator that yields page per page a collection of EO products
                  matching the criteria
        """

        iteration = 1
        # Store the search plugin config pagination.next_page_url_tpl to reset it later
        # since it might be modified if the next_page_url mechanism is used by the
        # plugin. (same thing for next_page_query_obj, next_page_query_obj with POST reqs)
        pagination_config = getattr(search_plugin.config, "pagination", {})
        prev_next_page_url_tpl = pagination_config.get("next_page_url_tpl", None)
        prev_next_page_query_obj = pagination_config.get("next_page_query_obj", None)
        # Page has to be set to a value even if use_next is True, this is required
        # internally by the search plugin (see collect_search_urls)
        kwargs.update(
            page=1,
            items_per_page=items_per_page,
        )
        prev_product = None
        next_page_url = None
        next_page_query_obj = None
        while True:
            if iteration > 1 and next_page_url:
                pagination_config["next_page_url_tpl"] = next_page_url
            if iteration > 1 and next_page_query_obj:
                pagination_config["next_page_query_obj"] = next_page_query_obj
            logger.info("Iterate search over multiple pages: page #%s", iteration)
            try:
                # remove unwanted kwargs for _do_search
                kwargs.pop("count", None)
                kwargs.pop("raise_errors", None)
                search_result = self._do_search(
                    search_plugin, count=False, raise_errors=True, **kwargs
                )
            except Exception:
                logger.warning(
                    "error at retrieval of data from %s, for params: %s",
                    search_plugin.provider,
                    str(kwargs),
                )
                raise
            finally:
                # we don't want that next(search_iter_page(...)) modifies the plugin
                # indefinitely. So we reset after each request, but before the generator
                # yields, the attr next_page_url (to None) and
                # config.pagination["next_page_url_tpl"] (to its original value).
                next_page_url = getattr(search_plugin, "next_page_url", None)
                next_page_query_obj = getattr(search_plugin, "next_page_query_obj", {})
                next_page_merge = getattr(search_plugin, "next_page_merge", None)

                if next_page_url:
                    search_plugin.next_page_url = None
                    if prev_next_page_url_tpl:
                        search_plugin.config.pagination[
                            "next_page_url_tpl"
                        ] = prev_next_page_url_tpl
                if next_page_query_obj:
                    if prev_next_page_query_obj:
                        search_plugin.config.pagination[
                            "next_page_query_obj"
                        ] = prev_next_page_query_obj
                    # Update next_page_query_obj for next page req
                    if next_page_merge:
                        search_plugin.next_page_query_obj = dict(
                            getattr(search_plugin, "query_params", {}),
                            **next_page_query_obj,
                        )
                    else:
                        search_plugin.next_page_query_obj = next_page_query_obj

            if len(search_result) > 0:
                # The first products between two iterations are compared. If they
                # are actually the same product, it means the iteration failed at
                # progressing for some reason. This is implemented as a workaround
                # to some search plugins/providers not handling pagination.
                product = search_result[0]
                if (
                    prev_product
                    and product.properties["id"] == prev_product.properties["id"]
                    and product.provider == prev_product.provider
                ):
                    logger.warning(
                        "Iterate over pages: stop iterating since the next page "
                        "appears to have the same products as in the previous one. "
                        "This provider may not implement pagination.",
                    )
                    last_page_with_products = iteration - 1
                    break
                yield search_result
                prev_product = product
                # Prevent a last search if the current one returned less than the
                # maximum number of items asked for.
                if len(search_result) < items_per_page:
                    last_page_with_products = iteration
                    break
            else:
                last_page_with_products = iteration - 1
                break
            iteration += 1
            kwargs["page"] = iteration
        logger.debug(
            "Iterate over pages: last products found on page %s",
            last_page_with_products,
        )

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
        :returns: An iterator that yields page per page a collection of EO products
                  matching the criteria
        """
        # Get the search plugin and the maximized value
        # of items_per_page if defined for the provider used.
        try:
            product_type = self.get_product_type_from_alias(
                self.guess_product_type(**kwargs)[0]
            )
        except NoMatchingProductType:
            product_type = GENERIC_PRODUCT_TYPE
        else:
            # fetch product types list if product_type is unknown
            if (
                product_type
                not in self._plugins_manager.product_type_to_provider_config_map.keys()
            ):
                logger.debug(
                    f"Fetching external product types sources to find {product_type} product type"
                )
                self.fetch_product_types_list()

        search_plugins, search_kwargs = self._prepare_search(
            start=start, end=end, geom=geom, locations=locations, **kwargs
        )
        for i, search_plugin in enumerate(search_plugins):
            itp = (
                items_per_page
                or getattr(search_plugin.config, "pagination", {}).get(
                    "max_items_per_page"
                )
                or DEFAULT_MAX_ITEMS_PER_PAGE
            )
            logger.info(
                "Searching for all the products with provider %s and a maximum of %s "
                "items per page.",
                search_plugin.provider,
                itp,
            )
            all_results = SearchResult([])
            try:
                for page_results in self.search_iter_page_plugin(
                    items_per_page=itp,
                    search_plugin=search_plugin,
                    **search_kwargs,
                ):
                    all_results.data.extend(page_results.data)
                logger.info(
                    "Found %s result(s) on provider '%s'",
                    len(all_results),
                    search_plugin.provider,
                )
                return all_results
            except RequestError:
                if len(all_results) == 0 and i < len(search_plugins) - 1:
                    logger.warning(
                        "No result could be obtained from provider %s, "
                        "we will try to get the data from another provider",
                        search_plugin.provider,
                    )
                elif len(all_results) == 0:
                    logger.error(
                        "No result could be obtained from any available provider"
                    )
                    raise
                elif len(all_results) > 0:
                    logger.warning(
                        "Found %s result(s) on provider '%s', but it may be incomplete "
                        "as it ended with an error",
                        len(all_results),
                        search_plugin.provider,
                    )
                    return all_results
        raise RequestError("No result could be obtained from any available provider")

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
        product_type = kwargs.get("productType", None)
        if product_type is not None:
            try:
                product_type = self.get_product_type_from_alias(product_type)
            except NoMatchingProductType:
                logger.debug("product type %s not found", product_type)
        get_search_plugins_kwargs = dict(provider=provider, product_type=product_type)
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
                if not results[0].product_type:
                    # guess product type from properties
                    guesses = self.guess_product_type(**results[0].properties)
                    results[0].product_type = guesses[0]
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

    def _fetch_external_product_type(self, provider: str, product_type: str):
        plugins = self._plugins_manager.get_search_plugins(provider=provider)
        plugin = next(plugins)

        # check after plugin init if still fetchable
        if not getattr(plugin.config, "discover_product_types", {}).get("fetch_url"):
            return None

        kwargs: dict[str, Any] = {"productType": product_type}

        # append auth if needed
        if getattr(plugin.config, "need_auth", False):
            if auth := self._plugins_manager.get_auth(
                plugin.provider,
                getattr(plugin.config, "api_endpoint", None),
                plugin.config,
            ):
                kwargs["auth"] = auth

        product_type_config = plugin.discover_product_types(**kwargs)
        self.update_product_types_list({provider: product_type_config})

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
            * productType query:
              * By product type (e.g. 'S2_MSI_L1C')
              * By params (e.g. 'platform'), see guess_product_type
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
        :param provider: provider to be used, if no provider is given or the product type
                        is not available for the provider, the preferred provider is used
        :param kwargs: Some other criteria
                       * id and/or a provider for a search by
                       * search criteria to guess the product type
                       * other criteria compatible with the provider
        :returns: Search plugins list and the prepared kwargs to make a query.
        """
        product_type = kwargs.get("productType", None)
        if product_type is None:
            try:
                guesses = self.guess_product_type(**kwargs)

                # guess_product_type raises a NoMatchingProductType error if no product
                # is found. Here, the supported search params are removed from the
                # kwargs if present, not to propagate them to the query itself.
                for param in (
                    "instrument",
                    "platform",
                    "platformSerialIdentifier",
                    "processingLevel",
                    "sensorType",
                ):
                    kwargs.pop(param, None)

                # By now, only use the best bet
                product_type = guesses[0]
            except NoMatchingProductType:
                queried_id = kwargs.get("id", None)
                if queried_id is None:
                    logger.info(
                        "No product type could be guessed with provided arguments"
                    )
                else:
                    return [], kwargs

        if product_type is not None:
            try:
                product_type = self.get_product_type_from_alias(product_type)
            except NoMatchingProductType:
                logger.info("unknown product type " + product_type)
        kwargs["productType"] = product_type

        if start is not None:
            kwargs["startTimeFromAscendingNode"] = start
        if end is not None:
            kwargs["completionTimeFromAscendingNode"] = end
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

        # fetch product types list if product_type is unknown
        if (
            product_type
            not in self._plugins_manager.product_type_to_provider_config_map.keys()
        ):
            if provider:
                # Try to get specific product type from external provider
                logger.debug(f"Fetching {provider} to find {product_type} product type")
                self._fetch_external_product_type(provider, product_type)
            if not provider:
                # no provider or still not found -> fetch all external product types
                logger.debug(
                    f"Fetching external product types sources to find {product_type} product type"
                )
                self.fetch_product_types_list()

        preferred_provider = self.get_preferred_provider()[0]

        search_plugins: list[Union[Search, Api]] = []
        for plugin in self._plugins_manager.get_search_plugins(
            product_type=product_type, provider=provider
        ):
            # exclude MeteoblueSearch plugins from search fallback for unknown product_type
            if (
                provider != plugin.provider
                and preferred_provider != plugin.provider
                and product_type not in self.product_types_config
                and isinstance(plugin, MeteoblueSearch)
            ):
                continue
            search_plugins.append(plugin)

        if not provider:
            provider = preferred_provider
        providers = [plugin.provider for plugin in search_plugins]
        if provider not in providers:
            logger.debug(
                "Product type '%s' is not available with preferred provider '%s'.",
                product_type,
                provider,
            )
        else:
            provider_plugin = list(
                filter(lambda p: p.provider == provider, search_plugins)
            )[0]
            search_plugins.remove(provider_plugin)
            search_plugins.insert(0, provider_plugin)
        # Add product_types_config to plugin config. This dict contains product
        # type metadata that will also be stored in each product's properties.
        for search_plugin in search_plugins:
            self._attach_product_type_config(search_plugin, product_type)

        return search_plugins, kwargs

    def _do_search(
        self,
        search_plugin: Union[Search, Api],
        count: bool = False,
        raise_errors: bool = False,
        **kwargs: Any,
    ) -> SearchResult:
        """Internal method that performs a search on a given provider.

        :param search_plugin: A search plugin
        :param count: (optional) Whether to run a query with a count request or not
        :param raise_errors: (optional) When an error occurs when searching, if this is set to
                             True, the error is raised
        :param kwargs: Some other criteria that will be used to do the search
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

        results: list[EOProduct] = []
        total_results: Optional[int] = 0 if count else None

        errors: list[tuple[str, Exception]] = []

        try:
            prep = PreparedSearch(count=count)

            # append auth if needed
            if getattr(search_plugin.config, "need_auth", False):
                if auth := self._plugins_manager.get_auth(
                    search_plugin.provider,
                    getattr(search_plugin.config, "api_endpoint", None),
                    search_plugin.config,
                ):
                    prep.auth = auth

            prep.page = kwargs.pop("page", None)
            prep.items_per_page = kwargs.pop("items_per_page", None)

            res, nb_res = search_plugin.query(prep, **kwargs)

            if not isinstance(res, list):
                raise PluginImplementationError(
                    "The query function of a Search plugin must return a list of "
                    "results, got {} instead".format(type(res))
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
            for eo_product in res:
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
                    except NoMatchingProductType:
                        pass
                    else:
                        eo_product.product_type = guesses[0]

                try:
                    if eo_product.product_type is not None:
                        eo_product.product_type = self.get_product_type_from_alias(
                            eo_product.product_type
                        )
                except NoMatchingProductType:
                    logger.debug("product type %s not found", eo_product.product_type)

                if eo_product.search_intersection is not None:
                    download_plugin = self._plugins_manager.get_download_plugin(
                        eo_product
                    )
                    if len(eo_product.assets) > 0:
                        matching_url = next(iter(eo_product.assets.values()))["href"]
                    elif eo_product.properties.get("storageStatus") != ONLINE_STATUS:
                        matching_url = eo_product.properties.get(
                            "orderLink"
                        ) or eo_product.properties.get("downloadLink")
                    else:
                        matching_url = eo_product.properties.get("downloadLink")

                    try:
                        auth_plugin = next(
                            self._plugins_manager.get_auth_plugins(
                                search_plugin.provider,
                                matching_url=matching_url,
                                matching_conf=download_plugin.config,
                            )
                        )
                    except StopIteration:
                        auth_plugin = None
                    eo_product.register_downloader(download_plugin, auth_plugin)

            results.extend(res)
            total_results = (
                None
                if (nb_res is None or total_results is None)
                else total_results + nb_res
            )
            if count and nb_res is not None:
                logger.info(
                    "Found %s result(s) on provider '%s'",
                    nb_res,
                    search_plugin.provider,
                )
                # Hitting for instance
                # https://theia.cnes.fr/atdistrib/resto2/api/collections/SENTINEL2/
                #   search.json?startDate=2019-03-01&completionDate=2019-06-15
                #   &processingLevel=LEVEL2A&maxRecords=1&page=1
                # returns a number (properties.totalResults) that is the number of
                # products in the collection (here SENTINEL2) instead of the estimated
                # total number of products matching the search criteria (start/end date).
                # Remove this warning when this is fixed upstream by THEIA.
                if search_plugin.provider == "theia":
                    logger.warning(
                        "Results found on provider 'theia' is the total number of products "
                        "available in the searched collection (e.g. SENTINEL2) instead of "
                        "the total number of products matching the search criteria"
                    )
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
        return SearchResult(results, total_results, errors)

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

        :param search_result: A collection of EO products resulting from a search
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

        :param search_result: A collection of EO products resulting from a search
        :param filename: (optional) The name of the file to generate
        :returns: The name of the created file
        """
        with open(filename, "w") as fh:
            geojson.dump(search_result, fh)
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
        products with the information needed to download itself

        :param filename: A filename containing a search result encoded as a geojson
        :returns: The search results encoded in `filename`
        """
        products = self.deserialize(filename)
        for i, product in enumerate(products):
            if product.downloader is None:
                downloader = self._plugins_manager.get_download_plugin(product)
                auth = product.downloader_auth
                if auth is None:
                    auth = self._plugins_manager.get_auth_plugin(downloader, product)
                products[i].register_downloader(downloader, auth)

        return products

    @_deprecated(
        reason="Use the StaticStacSearch search plugin instead", version="2.2.1"
    )
    def load_stac_items(
        self,
        filename: str,
        recursive: bool = False,
        max_connections: int = 100,
        provider: Optional[str] = None,
        productType: Optional[str] = None,
        timeout: int = HTTP_REQ_TIMEOUT,
        ssl_verify: bool = True,
        **kwargs: Any,
    ) -> SearchResult:
        """Loads STAC items from a geojson file / STAC catalog or collection, and convert to SearchResult.

        Features are parsed using eodag provider configuration, as if they were
        the response content to an API request.

        :param filename: A filename containing features encoded as a geojson
        :param recursive: (optional) Browse recursively in child nodes if True
        :param max_connections: (optional) Maximum number of connections for concurrent HTTP requests
        :param provider: (optional) Data provider
        :param productType: (optional) Data product type
        :param timeout: (optional) Timeout in seconds for each internal HTTP request
        :param kwargs: Parameters that will be stored in the result as
                       search criteria
        :returns: The search results encoded in `filename`

        .. deprecated:: 2.2.1
           Use the :class:`~eodag.plugins.search.static_stac_search.StaticStacSearch` search plugin instead.
        """
        features = fetch_stac_items(
            filename,
            recursive=recursive,
            max_connections=max_connections,
            timeout=timeout,
            ssl_verify=ssl_verify,
        )
        feature_collection = geojson.FeatureCollection(features)

        plugin = next(
            self._plugins_manager.get_search_plugins(
                product_type=productType, provider=provider
            )
        )
        # save plugin._request and mock it to make return loaded static results
        plugin_request = plugin._request
        plugin._request = (
            lambda url, info_message=None, exception_message=None: MockResponse(
                feature_collection, 200
            )
        )

        search_result = self.search(
            productType=productType, provider=provider, **kwargs
        )

        # restore plugin._request
        plugin._request = plugin_request

        return search_result

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

        If the metadata mapping for ``downloadLink`` is set to something that can be
        interpreted as a link on a
        local filesystem, the download is skipped (by now, only a link starting
        with ``file:/`` is supported). Therefore, any user that knows how to extract
        product location from product metadata on a provider can override the
        ``downloadLink`` metadata mapping in the right way. For example, using the
        environment variable:
        ``EODAG__CREODIAS__SEARCH__METADATA_MAPPING__DOWNLOADLINK="file:///{id}"`` will
        lead to all :class:`~eodag.api.product._product.EOProduct`'s originating from the
        provider ``creodias`` to have their ``downloadLink`` metadata point to something like:
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
        """Fetch the queryable properties for a given product type and/or provider.

        :param provider: (optional) The provider.
        :param fetch_providers: If new product types should be fetched from the providers; default: True
        :param kwargs: additional filters for queryables (`productType` or other search
                       arguments)

        :raises UnsupportedProductType: If the specified product type is not available for the
                                        provider.

        :returns: A :class:`~eodag.api.product.queryables.QuerybalesDict` containing the EODAG queryable
                  properties, associating parameters to their annotated type, and a additional_properties attribute
        """
        # only fetch providers if product type is not found
        available_product_types: list[str] = [
            pt["ID"]
            for pt in self.list_product_types(provider=provider, fetch_providers=False)
        ]
        product_type: Optional[str] = kwargs.get("productType")
        pt_alias: Optional[str] = product_type

        if product_type:
            if product_type not in available_product_types:
                if fetch_providers:
                    # fetch providers and try again
                    available_product_types = [
                        pt["ID"]
                        for pt in self.list_product_types(
                            provider=provider, fetch_providers=True
                        )
                    ]
                raise UnsupportedProductType(f"{product_type} is not available.")
            try:
                kwargs["productType"] = product_type = self.get_product_type_from_alias(
                    product_type
                )
            except NoMatchingProductType as e:
                raise UnsupportedProductType(f"{product_type} is not available.") from e

        if not provider and not product_type:
            return QueryablesDict(
                additional_properties=True,
                **model_fields_to_annotated(CommonQueryables.model_fields),
            )

        additional_properties = False
        additional_information = []
        queryable_properties: dict[str, Any] = {}

        for plugin in self._plugins_manager.get_search_plugins(product_type, provider):
            # attach product type config
            product_type_configs: dict[str, Any] = {}
            if product_type:
                self._attach_product_type_config(plugin, product_type)
                product_type_configs[product_type] = plugin.config.product_type_config
            else:
                for pt in available_product_types:
                    self._attach_product_type_config(plugin, pt)
                    product_type_configs[pt] = plugin.config.product_type_config

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

            plugin_queryables = plugin.list_queryables(
                kwargs,
                available_product_types,
                product_type_configs,
                product_type,
                pt_alias,
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

    def _attach_product_type_config(self, plugin: Search, product_type: str) -> None:
        """
        Attach product_types_config to plugin config. This dict contains product
        type metadata that will also be stored in each product's properties.
        """
        try:
            plugin.config.product_type_config = dict(
                [
                    p
                    for p in self.list_product_types(
                        plugin.provider, fetch_providers=False
                    )
                    if p["_id"] == product_type
                ][0],
                **{"productType": product_type},
            )
            # If the product isn't in the catalog, it's a generic product type.
        except IndexError:
            # Construct the GENERIC_PRODUCT_TYPE metadata
            plugin.config.product_type_config = dict(
                ID=GENERIC_PRODUCT_TYPE,
                **self.product_types_config[GENERIC_PRODUCT_TYPE],
                productType=product_type,
            )
        # Remove the ID since this is equal to productType.
        plugin.config.product_type_config.pop("ID", None)
