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
import logging
import os
import re
import shutil
from operator import itemgetter

import geojson
import pkg_resources
import yaml.parser
from pkg_resources import resource_filename
from whoosh import analysis, fields
from whoosh.fields import Schema
from whoosh.index import create_in, exists_in, open_dir
from whoosh.qparser import QueryParser

from eodag.api.product.metadata_mapping import mtd_cfg_as_jsonpath
from eodag.api.search_result import SearchResult
from eodag.config import (
    SimpleYamlProxyConfig,
    get_ext_product_types_conf,
    load_default_config,
    load_stac_provider_config,
    load_yml_config,
    override_config_from_env,
    override_config_from_file,
    override_config_from_mapping,
    provider_config_init,
)
from eodag.plugins.download.base import DEFAULT_DOWNLOAD_TIMEOUT, DEFAULT_DOWNLOAD_WAIT
from eodag.plugins.manager import PluginManager
from eodag.utils import (
    GENERIC_PRODUCT_TYPE,
    MockResponse,
    _deprecated,
    get_geometry_from_various,
    makedirs,
    obj_md5sum,
    uri_to_path,
)
from eodag.utils.exceptions import (
    AuthenticationError,
    NoMatchingProductType,
    PluginImplementationError,
    UnsupportedProvider,
)
from eodag.utils.stac_reader import HTTP_REQ_TIMEOUT, fetch_stac_items

logger = logging.getLogger("eodag.core")

# pagination defaults
DEFAULT_PAGE = 1
DEFAULT_ITEMS_PER_PAGE = 20
# Default maximum number of items per page requested by search_all. 50 instead of
# 20 (DEFAULT_ITEMS_PER_PAGE) to increase it to the known and currentminimum
# value (mundi)
DEFAULT_MAX_ITEMS_PER_PAGE = 50


class EODataAccessGateway(object):
    """An API for downloading a wide variety of geospatial products originating
    from different types of providers.

    :param user_conf_file_path: (optional) Path to the user configuration file
    :type user_conf_file_path: str
    :param locations_conf_path: (optional) Path to the locations configuration file
    :type locations_conf_path: str
    """

    def __init__(self, user_conf_file_path=None, locations_conf_path=None):
        product_types_config_path = resource_filename(
            "eodag", os.path.join("resources/", "product_types.yml")
        )
        self.product_types_config = SimpleYamlProxyConfig(product_types_config_path)
        self.product_types_config_md5 = obj_md5sum(self.product_types_config.source)
        self.providers_config = load_default_config()

        self.conf_dir = os.path.join(os.path.expanduser("~"), ".config", "eodag")
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
                        resource_filename(
                            "eodag", os.path.join("resources", "user_conf_template.yml")
                        ),
                        standard_configuration_path,
                    )
        override_config_from_file(self.providers_config, user_conf_file_path)

        # Second level override: From environment variables
        override_config_from_env(self.providers_config)

        # init updated providers conf
        stac_provider_config = load_stac_provider_config()
        for provider in self.providers_config.keys():
            provider_config_init(self.providers_config[provider], stac_provider_config)

        # re-create _plugins_manager using up-to-date providers_config
        self._plugins_manager = PluginManager(self.providers_config)
        # use updated and checked providers_config
        self.providers_config = self._plugins_manager.providers_config

        # filter out providers needing auth that have no credentials set
        self._prune_providers_list()

        # Sort providers taking into account of possible new priority orders
        self._plugins_manager.sort_providers()

        # Build a search index for product types
        self._product_types_index = None
        self.build_index()

        # set locations configuration
        if locations_conf_path is None:
            locations_conf_path = os.getenv("EODAG_LOCS_CFG_FILE")
            if locations_conf_path is None:
                locations_conf_path = os.path.join(self.conf_dir, "locations.yml")
                if not os.path.isfile(locations_conf_path):
                    # copy locations conf file and replace path example
                    locations_conf_template = resource_filename(
                        "eodag",
                        os.path.join("resources", "locations_conf_template.yml"),
                    )
                    with open(locations_conf_template) as infile, open(
                        locations_conf_path, "w"
                    ) as outfile:
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
                        resource_filename("eodag", os.path.join("resources", "shp")),
                        os.path.join(self.conf_dir, "shp"),
                    )
        self.set_locations_conf(locations_conf_path)

    def get_version(self):
        """Get eodag package version"""
        return pkg_resources.get_distribution("eodag").version

    def build_index(self):
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
                shutil.rmtree(index_dir)
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
            try:
                self.guess_product_type(md5=self.product_types_config_md5)
            except NoMatchingProductType:
                create_index = True
            finally:
                if create_index:
                    shutil.rmtree(index_dir)
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
                ID=fields.STORED,
                abstract=fields.TEXT,
                instrument=fields.IDLIST,
                platform=fields.ID,
                platformSerialIdentifier=fields.IDLIST,
                processingLevel=fields.ID,
                sensorType=fields.ID,
                md5=fields.ID,
                license=fields.ID,
                title=fields.ID,
                missionStartDate=fields.ID,
                missionEndDate=fields.ID,
                keywords=fields.KEYWORD(analyzer=kw_analyzer),
            )
            non_indexable_fields = []
            self._product_types_index = create_in(index_dir, product_types_schema)
            ix_writer = self._product_types_index.writer()
            for product_type in self.list_product_types(fetch_providers=False):
                versioned_product_type = dict(
                    product_type, **{"md5": self.product_types_config_md5}
                )
                # add to index
                ix_writer.add_document(
                    **{
                        k: v
                        for k, v in versioned_product_type.items()
                        if k not in non_indexable_fields
                    }
                )
            ix_writer.commit()
        else:
            if self._product_types_index is None:
                logger.debug("Opening product types index in %s", index_dir)
                self._product_types_index = open_dir(index_dir)

    def set_preferred_provider(self, provider):
        """Set max priority for the given provider.

        >>> import tempfile, os
        >>> config = tempfile.NamedTemporaryFile(delete=False)
        >>> dag = EODataAccessGateway(user_conf_file_path=os.path.join(
        ...     tempfile.gettempdir(), config.name))
        >>> # This also tests get_preferred_provider method by the way
        >>> dag.get_preferred_provider()
        ('peps', 1)
        >>> # For the following lines, see
        >>> # http://python3porting.com/problems.html#handling-expected-exceptions
        >>> import eodag.utils.exceptions
        >>> try:
        ...     dag.set_preferred_provider(u'unknown')
        ...     raise AssertionError(u'UnsupportedProvider exception was not raised'
        ...                           'as expected')
        ... except eodag.utils.exceptions.UnsupportedProvider:
        ...     pass
        >>> dag.set_preferred_provider(u'creodias')
        >>> dag.get_preferred_provider()
        ('creodias', 2)
        >>> dag.set_preferred_provider(u'theia')
        >>> dag.get_preferred_provider()
        ('theia', 3)
        >>> dag.set_preferred_provider(u'creodias')
        >>> dag.get_preferred_provider()
        ('creodias', 4)
        >>> config.close()
        >>> os.unlink(config.name)

        :param provider: The name of the provider that should be considered as the
                         preferred provider to be used for this instance
        :type provider: str
        """
        if provider not in self.available_providers():
            raise UnsupportedProvider(
                f"This provider is not recognised by eodag: {provider}"
            )
        preferred_provider, max_priority = self.get_preferred_provider()
        if preferred_provider != provider:
            new_priority = max_priority + 1
            self._plugins_manager.set_priority(provider, new_priority)

    def get_preferred_provider(self):
        """Get the provider currently set as the preferred one for searching
        products, along with its priority.

        :returns: The provider with the maximum priority and its priority
        :rtype: tuple(str, int)
        """
        providers_with_priority = [
            (provider, conf.priority)
            for provider, conf in self.providers_config.items()
        ]
        preferred, priority = max(providers_with_priority, key=itemgetter(1))
        return preferred, priority

    def update_providers_config(self, yaml_conf):
        """Update providers configuration with given input.
        Can be used to add a provider to existing configuration or update
        an existing one.

        >>> from eodag import EODataAccessGateway
        >>> dag = EODataAccessGateway()
        >>> new_config = '''
        ...     my_new_provider:
        ...         search:
        ...             type: StacSearch
        ...             api_endpoint: https://api.my_new_provider/search
        ...         products:
        ...             GENERIC_PRODUCT_TYPE:
        ...                 productType: '{productType}'
        ... '''
        >>> # add new provider
        >>> dag.update_providers_config(new_config)
        >>> type(dag.providers_config["my_new_provider"])
        <class 'eodag.config.ProviderConfig'>
        >>> dag.providers_config["my_new_provider"].priority
        0
        >>> # run 2nd time (update provider)
        >>> update_config = '''
        ...     my_new_provider:
        ...         search:
        ...             type: StacSearch
        ...             api_endpoint: https://api.my_new_provider/search
        ...         products:
        ...             GENERIC_PRODUCT_TYPE:
        ...                 productType: '{productType}'
        ... '''
        >>> dag.update_providers_config(new_config)

        :param yaml_conf: YAML formated provider configuration
        :type yaml_conf: str
        """
        conf_update = yaml.safe_load(yaml_conf)
        # check if metada-mapping as already been built as jsonpath in providers_config
        for provider, provider_conf in conf_update.items():
            if (
                provider in self.providers_config
                and "metadata_mapping" in provider_conf.get("search", {})
            ):
                search_plugin_key = "search"
            elif (
                provider in self.providers_config
                and "metadata_mapping" in provider_conf.get("api", {})
            ):
                search_plugin_key = "api"
            else:
                continue
            # get some already configured value
            configured_metadata_mapping = getattr(
                self.providers_config[provider], search_plugin_key
            ).metadata_mapping
            some_configured_value = next(iter(configured_metadata_mapping.values()))
            # check if the configured value has already been built as jsonpath
            if (
                isinstance(some_configured_value, list)
                and isinstance(some_configured_value[1], tuple)
                or isinstance(some_configured_value, tuple)
            ):
                # also build as jsonpath the incoming conf
                mtd_cfg_as_jsonpath(
                    conf_update[provider][search_plugin_key]["metadata_mapping"],
                    conf_update[provider][search_plugin_key]["metadata_mapping"],
                )

        override_config_from_mapping(self.providers_config, conf_update)
        stac_provider_config = load_stac_provider_config()
        for provider in conf_update.keys():
            provider_config_init(self.providers_config[provider], stac_provider_config)
        # re-create _plugins_manager using up-to-date providers_config
        self._plugins_manager.build_product_type_to_provider_config_map()

    def _prune_providers_list(self):
        """Removes from config providers needing auth that have no credentials set."""
        update_needed = False
        for provider in list(self.providers_config.keys()):
            conf = self.providers_config[provider]

            if hasattr(conf, "api") and getattr(conf.api, "need_auth", False):
                credentials_exist = any(
                    [
                        cred is not None
                        for cred in getattr(conf.api, "credentials", {}).values()
                    ]
                )
                if not credentials_exist:
                    # credentials needed but not found
                    del self.providers_config[provider]
                    update_needed = True
                    logger.info(
                        "%s: provider needing auth for search has been pruned because no crendentials could be found",
                        provider,
                    )
            elif hasattr(conf, "search") and getattr(conf.search, "need_auth", False):
                if not hasattr(conf, "auth"):
                    # credentials needed but no auth plugin was found
                    del self.providers_config[provider]
                    update_needed = True
                    logger.info(
                        "%s: provider needing auth for search has been pruned because no auth plugin could be found",
                        provider,
                    )
                    continue
                credentials_exist = any(
                    [
                        cred is not None
                        for cred in getattr(conf.auth, "credentials", {}).values()
                    ]
                )
                if not credentials_exist:
                    # credentials needed but not found
                    del self.providers_config[provider]
                    update_needed = True
                    logger.info(
                        "%s: provider needing auth for search has been pruned because no crendentials could be found",
                        provider,
                    )
            elif not hasattr(conf, "api") and not hasattr(conf, "search"):
                # provider should have at least an api or search plugin
                del self.providers_config[provider]
                logger.info(
                    "%s: provider has been pruned because no api or search plugin could be found",
                    provider,
                )
                update_needed = True

        if update_needed:
            # rebuild _plugins_manager with updated providers list
            self._plugins_manager = PluginManager(self.providers_config)

    def set_locations_conf(self, locations_conf_path):
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
        :type locations_conf_path: str
        """
        if os.path.isfile(locations_conf_path):
            locations_config = load_yml_config(locations_conf_path)

            main_key = next(iter(locations_config))
            locations_config = locations_config[main_key]

            logger.info("Locations configuration loaded from %s" % locations_conf_path)
            self.locations_config = locations_config
        else:
            logger.info(
                "Could not load locations configuration from %s" % locations_conf_path
            )
            self.locations_config = []

    def list_product_types(self, provider=None, fetch_providers=True):
        """Lists supported product types.

        :param provider: (optional) The name of a provider that must support the product
                         types we are about to list
        :type provider: str
        :param fetch_providers: (optional) Whether to fetch providers for new product
                                types or not
        :type fetch_providers: bool
        :returns: The list of the product types that can be accessed using eodag.
        :rtype: list(dict)
        :raises: :class:`~eodag.utils.exceptions.UnsupportedProvider`
        """
        if fetch_providers:
            # First, update product types list if possible
            self.fetch_product_types_list(provider=provider)

        product_types = []
        if provider is not None:
            if provider in self.providers_config:
                provider_supported_products = self.providers_config[provider].products
                for product_type_id in provider_supported_products:
                    if product_type_id == GENERIC_PRODUCT_TYPE:
                        continue
                    product_type = dict(
                        ID=product_type_id, **self.product_types_config[product_type_id]
                    )
                    if product_type_id not in product_types:
                        product_types.append(product_type)
                return sorted(product_types, key=itemgetter("ID"))
            raise UnsupportedProvider("The requested provider is not (yet) supported")
        # Only get the product types supported by the available providers
        for provider in self.available_providers():
            current_product_type_ids = [pt["ID"] for pt in product_types]
            product_types.extend(
                [
                    pt
                    for pt in self.list_product_types(
                        provider=provider, fetch_providers=False
                    )
                    if pt["ID"] not in current_product_type_ids
                ]
            )
        # Return the product_types sorted in lexicographic order of their ID
        return sorted(product_types, key=itemgetter("ID"))

    def fetch_product_types_list(self, provider=None):
        """Fetch product types list and update if needed

        :param provider: (optional) The name of a provider for which product types list
                         should be updated. Defaults to all providers (None value).
        :type provider: str
        """
        if provider is not None and provider not in self.providers_config:
            return
        # check if any provider has already been fetched for product types
        # (no need go get ext_product_types conf)
        already_fetched = False
        for provider, provider_config in self.providers_config.items():
            if getattr(provider_config, "product_types_fetched", False):
                already_fetched = True
                break

        if not already_fetched:
            # get ext_product_types conf
            if "EODAG_EXT_PRODUCT_TYPES_CFG_FILE" in os.environ:
                ext_product_types_conf = get_ext_product_types_conf(
                    os.environ["EODAG_EXT_PRODUCT_TYPES_CFG_FILE"]
                )
            else:
                ext_product_types_conf = get_ext_product_types_conf()

                if not ext_product_types_conf:
                    # empty ext_product_types conf
                    ext_product_types_conf = self.discover_product_types()

            # update eodag product types list with new conf
            self.update_product_types_list(ext_product_types_conf)

        # get ext_product_types conf for user modified providers
        default_providers_config = load_default_config()
        for provider, user_provider_config in self.providers_config.items():
            # user discover_product_types conf
            if hasattr(user_provider_config, "search"):
                user_provider_search_config = user_provider_config.search
            elif hasattr(user_provider_config, "api"):
                user_provider_search_config = user_provider_config.api
            else:
                continue
            user_discovery_conf = getattr(
                user_provider_search_config, "discover_product_types", {}
            )
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
                if default_discovery_conf == user_discovery_conf and (
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

            # discover product types for user configured provider
            provider_ext_product_types_conf = self.discover_product_types(
                provider=provider
            )

            # update eodag product types list with new conf
            self.update_product_types_list(provider_ext_product_types_conf)

    def discover_product_types(self, provider=None):
        """Fetch providers for product types

        :param provider: (optional) The name of a provider to fetch. Defaults to all
                         providers (None value).
        :type provider: str
        :returns: external product types configuration
        :rtype: dict
        """
        ext_product_types_conf = {}
        providers_to_fetch = [
            p
            for p in (
                [
                    provider,
                ]
                if provider
                else self.available_providers()
            )
        ]
        for provider in providers_to_fetch:
            if hasattr(self.providers_config[provider], "search"):
                search_plugin_config = self.providers_config[provider].search
            elif hasattr(self.providers_config[provider], "api"):
                search_plugin_config = self.providers_config[provider].api
            else:
                return
            if getattr(search_plugin_config, "discover_product_types", None):
                search_plugin = next(
                    self._plugins_manager.get_search_plugins(provider=provider)
                )
                # append auth to search plugin if needed
                if getattr(search_plugin.config, "need_auth", False):
                    auth_plugin = self._plugins_manager.get_auth_plugin(
                        search_plugin.provider
                    )
                    if callable(getattr(auth_plugin, "authenticate", None)):
                        search_plugin.auth = auth_plugin.authenticate()
                    else:
                        raise AuthenticationError(
                            f"Could not authenticate using {auth_plugin} plugin"
                        )

                ext_product_types_conf[
                    provider
                ] = search_plugin.discover_product_types()

        return ext_product_types_conf

    def update_product_types_list(self, ext_product_types_conf):
        """Update eodag product types list

        :param ext_product_types_conf: external product types configuration
        :type ext_product_types_conf: dict
        """
        for provider, new_product_types_conf in ext_product_types_conf.items():
            if new_product_types_conf:
                try:
                    if hasattr(self.providers_config[provider], "search"):
                        search_plugin_config = self.providers_config[provider].search
                    elif hasattr(self.providers_config[provider], "api"):
                        search_plugin_config = self.providers_config[provider].api
                    else:
                        continue
                    provider_products_config = self.providers_config[provider].products
                except UnsupportedProvider:
                    logger.debug(
                        "Ignoring external product types for unknown provider %s",
                        provider,
                    )
                    continue
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
                            logger.debug(
                                f"Added product type {new_product_type} for {provider}"
                            )

            self.providers_config[provider].product_types_fetched = True

        # re-create _plugins_manager using up-to-date providers_config
        self._plugins_manager.build_product_type_to_provider_config_map()

        # rebuild index after product types list update
        self.build_index()

    def available_providers(self, product_type=None):
        """Gives the sorted list of the available providers

        :param product_type: (optional) Only list providers configured for this product_type
        :type product_type: str
        :returns: the sorted list of the available providers
        :rtype: list
        """

        if product_type:
            return sorted(
                k
                for k, v in self.providers_config.items()
                if product_type in getattr(v, "products", {}).keys()
            )
        else:
            return sorted(tuple(self.providers_config.keys()))

    def guess_product_type(self, **kwargs):
        """Find the eodag product type code that best matches a set of search params

        :param kwargs: A set of search parameters as keywords arguments
        :returns: The best match for the given parameters
        :rtype: str
        :raises: :class:`~eodag.utils.exceptions.NoMatchingProductType`
        """
        supported_params = {
            param
            for param in (
                "instrument",
                "platform",
                "platformSerialIdentifier",
                "processingLevel",
                "sensorType",
                "keywords",
                "md5",
            )
            if kwargs.get(param, None) is not None
        }
        with self._product_types_index.searcher() as searcher:
            results = None
            # For each search key, do a guess and then upgrade the result (i.e. when
            # merging results, if a hit appears in both results, its position is raised
            # to the top. This way, the top most result will be the hit that best
            # matches the given queries. Put another way, this best guess is the one
            # that crosses the highest number of search params from the given queries
            for search_key in supported_params:
                query = QueryParser(search_key, self._product_types_index.schema).parse(
                    kwargs[search_key]
                )
                if results is None:
                    results = searcher.search(query, limit=None)
                else:
                    results.upgrade_and_extend(searcher.search(query, limit=None))
            guesses = [r["ID"] for r in results or []]
        if guesses:
            return guesses
        raise NoMatchingProductType()

    def search(
        self,
        page=DEFAULT_PAGE,
        items_per_page=DEFAULT_ITEMS_PER_PAGE,
        raise_errors=False,
        start=None,
        end=None,
        geom=None,
        locations=None,
        **kwargs,
    ):
        """Look for products matching criteria on known providers.

        The default behaviour is to look for products on the provider with the
        highest priority supporting the requested product type. These priorities
        are configurable through user configuration file or individual
        environment variable.

        :param page: (optional) The page number to return
        :type page: int
        :param items_per_page: (optional) The number of results that must appear in one single
                               page
        :type items_per_page: int
        :param raise_errors:  (optional) When an error occurs when searching, if this is set to
                              True, the error is raised
        :type raise_errors: bool
        :param start: (optional) Start sensing time in ISO 8601 format (e.g. "1990-11-26",
                      "1990-11-26T14:30:10.153Z", "1990-11-26T14:30:10+02:00", ...).
                      If no time offset is given, the time is assumed to be given in UTC.
        :type start: str
        :param end: (optional) End sensing time in ISO 8601 format (e.g. "1990-11-26",
                    "1990-11-26T14:30:10.153Z", "1990-11-26T14:30:10+02:00", ...).
                    If no time offset is given, the time is assumed to be given in UTC.
        :type end: str
        :param geom: (optional) Search area that can be defined in different ways:

                     * with a Shapely geometry object:
                       :class:`shapely.geometry.base.BaseGeometry`
                     * with a bounding box (dict with keys: "lonmin", "latmin", "lonmax", "latmax"):
                       ``dict.fromkeys(["lonmin", "latmin", "lonmax", "latmax"])``
                     * with a bounding box as list of float:
                       ``[lonmin, latmin, lonmax, latmax]``
                     * with a WKT str
        :type geom: Union[str, dict, shapely.geometry.base.BaseGeometry]
        :param locations: (optional) Location filtering by name using locations configuration
                          ``{"<location_name>"="<attr_regex>"}``. For example, ``{"country"="PA."}`` will use
                          the geometry of the features having the property ISO3 starting with
                          'PA' such as Panama and Pakistan in the shapefile configured with
                          name=country and attr=ISO3
        :type locations: dict
        :param kwargs: Some other criteria that will be used to do the search,
                       using paramaters compatibles with the provider
        :type kwargs: Union[int, str, bool, dict]
        :returns: A collection of EO products matching the criteria and the total
                  number of results found
        :rtype: tuple(:class:`~eodag.api.search_result.SearchResult`, int)

        .. note::
            The search interfaces, which are implemented as plugins, are required to
            return a list as a result of their processing. This requirement is
            enforced here.
        """
        search_kwargs = self._prepare_search(
            start=start, end=end, geom=geom, locations=locations, **kwargs
        )
        search_plugin = search_kwargs.pop("search_plugin", None)
        if search_kwargs.get("id"):
            # remove auth from search_kwargs as a loop over providers will be performed
            search_kwargs.pop("auth", None)
            return self._search_by_id(search_kwargs.pop("id"), **search_kwargs)
        search_kwargs.update(
            page=page,
            items_per_page=items_per_page,
        )
        search_plugin.clear()
        return self._do_search(
            search_plugin, count=True, raise_errors=raise_errors, **search_kwargs
        )

    def search_iter_page(
        self,
        items_per_page=DEFAULT_ITEMS_PER_PAGE,
        start=None,
        end=None,
        geom=None,
        locations=None,
        **kwargs,
    ):
        """Iterate over the pages of a products search.

        :param items_per_page: (optional) The number of results requested per page
        :type items_per_page: int
        :param start: (optional) Start sensing time in ISO 8601 format (e.g. "1990-11-26",
                      "1990-11-26T14:30:10.153Z", "1990-11-26T14:30:10+02:00", ...).
                      If no time offset is given, the time is assumed to be given in UTC.
        :type start: str
        :param end: (optional) End sensing time in ISO 8601 format (e.g. "1990-11-26",
                    "1990-11-26T14:30:10.153Z", "1990-11-26T14:30:10+02:00", ...).
                    If no time offset is given, the time is assumed to be given in UTC.
        :type end: str
        :param geom: (optional) Search area that can be defined in different ways:

                     * with a Shapely geometry object:
                       :class:`shapely.geometry.base.BaseGeometry`
                     * with a bounding box (dict with keys: "lonmin", "latmin", "lonmax", "latmax"):
                       ``dict.fromkeys(["lonmin", "latmin", "lonmax", "latmax"])``
                     * with a bounding box as list of float:
                       ``[lonmin, latmin, lonmax, latmax]``
                     * with a WKT str
        :type geom: Union[str, dict, shapely.geometry.base.BaseGeometry]
        :param locations: (optional) Location filtering by name using locations configuration
                          ``{"<location_name>"="<attr_regex>"}``. For example, ``{"country"="PA."}`` will use
                          the geometry of the features having the property ISO3 starting with
                          'PA' such as Panama and Pakistan in the shapefile configured with
                          name=country and attr=ISO3
        :type locations: dict
        :param kwargs: Some other criteria that will be used to do the search,
                       using paramaters compatibles with the provider
        :type kwargs: Union[int, str, bool, dict]
        :returns: An iterator that yields page per page a collection of EO products
                  matching the criteria
        :rtype: Iterator[:class:`~eodag.api.search_result.SearchResult`]
        """
        search_kwargs = self._prepare_search(
            start=start, end=end, geom=geom, locations=locations, **kwargs
        )
        search_plugin = search_kwargs.pop("search_plugin")
        iteration = 1
        # Store the search plugin config pagination.next_page_url_tpl to reset it later
        # since it might be modified if the next_page_url mechanism is used by the
        # plugin. (same thing for next_page_query_obj, next_page_query_obj with POST reqs)
        pagination_config = getattr(search_plugin.config, "pagination", {})
        prev_next_page_url_tpl = pagination_config.get("next_page_url_tpl", None)
        prev_next_page_query_obj = pagination_config.get("next_page_query_obj", None)
        # Page has to be set to a value even if use_next is True, this is required
        # internally by the search plugin (see collect_search_urls)
        search_kwargs.update(
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
                products, _ = self._do_search(
                    search_plugin, count=False, raise_errors=True, **search_kwargs
                )
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

            if len(products) > 0:
                # The first products between two iterations are compared. If they
                # are actually the same product, it means the iteration failed at
                # progressing for some reason. This is implemented as a workaround
                # to some search plugins/providers not handling pagination.
                product = products[0]
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
                yield products
                prev_product = product
                # Prevent a last search if the current one returned less than the
                # maximum number of items asked for.
                if len(products) < items_per_page:
                    last_page_with_products = iteration
                    break
            else:
                last_page_with_products = iteration - 1
                break
            iteration += 1
            search_kwargs["page"] = iteration
        logger.debug(
            "Iterate over pages: last products found on page %s",
            last_page_with_products,
        )

    def search_all(
        self,
        items_per_page=None,
        start=None,
        end=None,
        geom=None,
        locations=None,
        **kwargs,
    ):
        """Search and return all the products matching the search criteria.

        It iterates over the pages of a search query and collects all the returned
        products into a single :class:`~eodag.api.search_result.SearchResult` instance.

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
        :type items_per_page: int
        :param start: (optional) Start sensing time in ISO 8601 format (e.g. "1990-11-26",
                      "1990-11-26T14:30:10.153Z", "1990-11-26T14:30:10+02:00", ...).
                      If no time offset is given, the time is assumed to be given in UTC.
        :type start: str
        :param end: (optional) End sensing time in ISO 8601 format (e.g. "1990-11-26",
                    "1990-11-26T14:30:10.153Z", "1990-11-26T14:30:10+02:00", ...).
                    If no time offset is given, the time is assumed to be given in UTC.
        :type end: str
        :param geom: (optional) Search area that can be defined in different ways:

                     * with a Shapely geometry object:
                       :class:`shapely.geometry.base.BaseGeometry`
                     * with a bounding box (dict with keys: "lonmin", "latmin", "lonmax", "latmax"):
                       ``dict.fromkeys(["lonmin", "latmin", "lonmax", "latmax"])``
                     * with a bounding box as list of float:
                       ``[lonmin, latmin, lonmax, latmax]``
                     * with a WKT str
        :type geom: Union[str, dict, shapely.geometry.base.BaseGeometry]
        :param locations: (optional) Location filtering by name using locations configuration
                          ``{"<location_name>"="<attr_regex>"}``. For example, ``{"country"="PA."}`` will use
                          the geometry of the features having the property ISO3 starting with
                          'PA' such as Panama and Pakistan in the shapefile configured with
                          name=country and attr=ISO3
        :type locations: dict
        :param kwargs: Some other criteria that will be used to do the search,
                       using paramaters compatibles with the provider
        :type kwargs: Union[int, str, bool, dict]
        :returns: An iterator that yields page per page a collection of EO products
                  matching the criteria
        :rtype: Iterator[:class:`~eodag.api.search_result.SearchResult`]
        """
        # Get the search plugin and the maximized value
        # of items_per_page if defined for the provider used.
        try:
            product_type = (
                kwargs.get("productType", None) or self.guess_product_type(**kwargs)[0]
            )
        except NoMatchingProductType:
            product_type = GENERIC_PRODUCT_TYPE
        search_plugin = next(
            self._plugins_manager.get_search_plugins(product_type=product_type)
        )
        if items_per_page is None:
            items_per_page = search_plugin.config.pagination.get(
                "max_items_per_page", DEFAULT_MAX_ITEMS_PER_PAGE
            )

        logger.debug(
            "Searching for all the products with provider %s and a maximum of %s "
            "items per page.",
            search_plugin.provider,
            items_per_page,
        )
        all_results = SearchResult([])
        for page_results in self.search_iter_page(
            items_per_page=items_per_page,
            start=start,
            end=end,
            geom=geom,
            locations=locations,
            **kwargs,
        ):
            all_results.data.extend(page_results.data)
        logger.info(
            "Found %s result(s) on provider '%s'",
            len(all_results),
            search_plugin.provider,
        )
        return all_results

    def _search_by_id(self, uid, provider=None, **kwargs):
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
        :type uid: str
        :param provider: (optional) The provider on which to search the product.
                         This may be useful for performance reasons when the user
                         knows this product is available on the given provider
        :type provider: str
        :param kwargs: Search criteria to help finding the right product
        :type kwargs: Any
        :returns: A search result with one EO product or None at all, and the number
                  of EO products retrieved (0 or 1)
        :rtype: tuple(:class:`~eodag.api.search_result.SearchResult`, int)
        """
        for plugin in self._plugins_manager.get_search_plugins(provider=provider):
            logger.info(
                "Searching product with id '%s' on provider: %s", uid, plugin.provider
            )
            logger.debug("Using plugin class for search: %s", plugin.__class__.__name__)
            auth = self._plugins_manager.get_auth_plugin(plugin.provider)
            results, _ = self._do_search(plugin, auth=auth, id=uid, **kwargs)
            if len(results) == 1:
                if not results[0].product_type:
                    # guess product type from properties
                    guesses = self.guess_product_type(**results[0].properties)
                    results[0].product_type = guesses[0]
                    # reset driver
                    results[0].driver = results[0].get_driver()
                return results, 1
            elif len(results) > 1:
                logger.info(
                    "Several products found for this id (%s). You may try searching using more selective criteria.",
                    results,
                )
        return SearchResult([]), 0

    def _prepare_search(
        self, start=None, end=None, geom=None, locations=None, **kwargs
    ):
        """Internal method to prepare the search kwargs and get the search
        and auth plugins.

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
        :type start: str
        :param end: (optional) End sensing time in ISO 8601 format (e.g. "1990-11-26",
                    "1990-11-26T14:30:10.153Z", "1990-11-26T14:30:10+02:00", ...).
                    If no time offset is given, the time is assumed to be given in UTC.
        :type end: str
        :param geom: (optional) Search area that can be defined in different ways (see search)
        :type geom: Union[str, dict, shapely.geometry.base.BaseGeometry]
        :param locations: (optional) Location filtering by name using locations configuration
        :type locations: dict
        :param kwargs: Some other criteria
                       * id and/or a provider for a search by
                       * search criteria to guess the product type
                       * other criteria compatible with the provider
        :type kwargs: Any
        :returns: The prepared kwargs to make a query.
        :rtype: dict
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
                    return kwargs

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

        search_plugin = next(
            self._plugins_manager.get_search_plugins(product_type=product_type)
        )
        if search_plugin.provider != self.get_preferred_provider()[0]:
            logger.warning(
                "Product type '%s' is not available with provider '%s'. "
                "Searching it on provider '%s' instead.",
                product_type,
                self.get_preferred_provider()[0],
                search_plugin.provider,
            )
        else:
            logger.info(
                "Searching product type '%s' on provider: %s",
                product_type,
                search_plugin.provider,
            )
        # Add product_types_config to plugin config. This dict contains product
        # type metadata that will also be stored in each product's properties.
        try:
            search_plugin.config.product_type_config = dict(
                [
                    p
                    for p in self.list_product_types(
                        search_plugin.provider, fetch_providers=False
                    )
                    if p["ID"] == product_type
                ][0],
                **{"productType": product_type},
            )
        # If the product isn't in the catalog, it's a generic product type.
        except IndexError:
            # Construct the GENERIC_PRODUCT_TYPE metadata
            search_plugin.config.product_type_config = dict(
                ID=GENERIC_PRODUCT_TYPE,
                **self.product_types_config[GENERIC_PRODUCT_TYPE],
                productType=product_type,
            )
        # Remove the ID since this is equal to productType.
        search_plugin.config.product_type_config.pop("ID", None)

        logger.debug(
            "Using plugin class for search: %s", search_plugin.__class__.__name__
        )
        auth_plugin = self._plugins_manager.get_auth_plugin(search_plugin.provider)

        # append auth to search plugin if needed
        if getattr(search_plugin.config, "need_auth", False) and callable(
            getattr(auth_plugin, "authenticate", None)
        ):
            search_plugin.auth = auth_plugin.authenticate()

        return dict(search_plugin=search_plugin, auth=auth_plugin, **kwargs)

    def _do_search(self, search_plugin, count=True, raise_errors=False, **kwargs):
        """Internal method that performs a search on a given provider.

        :param search_plugin: A search plugin
        :type search_plugin: eodag.plugins.base.Search
        :param count: (optional) Whether to run a query with a count request or not
        :type count: bool
        :param raise_errors: (optional) When an error occurs when searching, if this is set to
                             True, the error is raised
        :type raise_errors: bool
        :param kwargs: Some other criteria that will be used to do the search
        :type kwargs: Any
        :returns: A collection of EO products matching the criteria and the total
                  number of results found if count is True else None
        :rtype: tuple(:class:`~eodag.api.search_result.SearchResult`, int or None)
        """
        max_items_per_page = search_plugin.config.pagination.get(
            "max_items_per_page", DEFAULT_MAX_ITEMS_PER_PAGE
        )
        if kwargs.get("items_per_page", DEFAULT_ITEMS_PER_PAGE) > max_items_per_page:
            logger.warning(
                "EODAG believes that you might have asked for more products/items "
                "than the maximum allowed by '%s': %s > %s. Try to lower "
                "the value of 'items_per_page' and get the next page (e.g. 'page=2'), "
                "or directly use the 'search_all' method.",
                search_plugin.provider,
                kwargs["items_per_page"],
                max_items_per_page,
            )

        results = SearchResult([])
        total_results = 0
        try:
            res, nb_res = search_plugin.query(count=count, **kwargs)

            # Only do the pagination computations when it makes sense. For example,
            # for a search by id, we can reasonably guess that the provider will return
            # At most 1 product, so we don't need such a thing as pagination
            page = kwargs.get("page")
            items_per_page = kwargs.get("items_per_page")
            if page and items_per_page and count:
                # Take into account the fact that a provider may not return the count of
                # products (in that case, fallback to using the length of the results it
                # returned and the page requested. As an example, check the result of
                # the following request (look for the value of properties.totalResults)
                # https://theia-landsat.cnes.fr/resto/api/collections/Landsat/search.json?
                # maxRecords=1&page=1
                if nb_res == 0:
                    nb_res = len(res) * page

                # Attempt to ensure a little bit more coherence. Some providers return
                # a fuzzy number of total results, meaning that you have to keep
                # requesting it until it has returned everything it has to know exactly
                # how many EO products they have in their stock. In that case, we need
                # to replace the returned number of results with the sum of the number
                # of items that were skipped so far and the length of the currently
                # retrieved items. We know there is an incoherence when the number of
                # skipped items is greater than the total number of items returned by
                # the plugin
                nb_skipped_items = items_per_page * (page - 1)
                nb_current_items = len(res)
                if nb_skipped_items > nb_res:
                    if nb_res != 0:
                        nb_res = nb_skipped_items + nb_current_items
                    # This is for when the returned results is an empty list and the
                    # number of results returned is incoherent with the observations.
                    # In that case, we assume the total number of results is the number
                    # of skipped results. By requesting a lower page than the current
                    # one, a user can iteratively reach the last page of results for
                    # these criteria on the provider.
                    else:
                        nb_res = nb_skipped_items

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
                            **{
                                # k:str(v) for k,v in eo_product.properties.items()
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
                            }
                        )
                    except NoMatchingProductType:
                        pass
                    else:
                        eo_product.product_type = guesses[0]
                if eo_product.search_intersection is not None:
                    download_plugin = self._plugins_manager.get_download_plugin(
                        eo_product
                    )
                    eo_product.register_downloader(
                        download_plugin, kwargs.get("auth", None)
                    )

            results.extend(res)
            total_results = None if nb_res is None else total_results + nb_res
            if count:
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
        except Exception:
            logger.info(
                "No result from provider '%s' due to an error during search. Raise "
                "verbosity of log messages for details",
                search_plugin.provider,
            )
            if raise_errors:
                # Raise the error, letting the application wrapping eodag know that
                # something went bad. This way it will be able to decide what to do next
                raise
            else:
                logger.exception(
                    "Error while searching on provider %s (ignored):",
                    search_plugin.provider,
                )
        return SearchResult(results), total_results

    def crunch(self, results, **kwargs):
        """Apply the filters given through the keyword arguments to the results

        :param results: The results of a eodag search request
        :type results: :class:`~eodag.api.search_result.SearchResult`
        :returns: The result of successively applying all the filters to the results
        :rtype: :class:`~eodag.api.search_result.SearchResult`
        """
        search_criteria = kwargs.pop("search_criteria", {})
        for cruncher_name, cruncher_args in kwargs.items():
            cruncher = self._plugins_manager.get_crunch_plugin(
                cruncher_name, **cruncher_args
            )
            results = results.crunch(cruncher, **search_criteria)
        return results

    @staticmethod
    def group_by_extent(searches):
        """Combines multiple SearchResults and return a list of SearchResults grouped
        by extent (i.e. bounding box).

        :param searches: List of eodag SearchResult
        :type searches: list
        :returns: list of :class:`~eodag.api.search_result.SearchResult`
        """
        # Dict with extents as keys, each extent being defined by a str
        # "{minx}{miny}{maxx}{maxy}" (each float rounded to 2 dec).
        products_grouped_by_extent = {}

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
        search_result,
        downloaded_callback=None,
        progress_callback=None,
        wait=DEFAULT_DOWNLOAD_WAIT,
        timeout=DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs,
    ):
        """Download all products resulting from a search.

        :param search_result: A collection of EO products resulting from a search
        :type search_result: :class:`~eodag.api.search_result.SearchResult`
        :param downloaded_callback: (optional) A method or a callable object which takes
                                    as parameter the ``product``. You can use the base class
                                    :class:`~eodag.utils.DownloadedCallback` and override
                                    its ``__call__`` method. Will be called each time a product
                                    finishes downloading
        :type downloaded_callback: Callable[[:class:`~eodag.api.product._product.EOProduct`], None]
                                   or None
        :param progress_callback: (optional) A method or a callable object
                                  which takes a current size and a maximum
                                  size as inputs and handle progress bar
                                  creation and update to give the user a
                                  feedback on the download progress
        :type progress_callback: :class:`~eodag.utils.ProgressCallback` or None
        :param wait: (optional) If download fails, wait time in minutes between
                     two download tries of the same product
        :type wait: int
        :param timeout: (optional) If download fails, maximum time in minutes
                        before stop retrying to download
        :type timeout: int
        :param kwargs: `outputs_prefix` (str), `extract` (bool), `delete_archive` (bool)
                        and `dl_url_params` (dict) can be provided as additional kwargs
                        and will override any other values defined in a configuration
                        file or with environment variables.
        :type kwargs: Union[str, bool, dict]
        :returns: A collection of the absolute paths to the downloaded products
        :rtype: list
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
    def serialize(search_result, filename="search_results.geojson"):
        """Registers results of a search into a geojson file.

        :param search_result: A collection of EO products resulting from a search
        :type search_result: :class:`~eodag.api.search_result.SearchResult`
        :param filename: (optional) The name of the file to generate
        :type filename: str
        :returns: The name of the created file
        :rtype: str
        """
        with open(filename, "w") as fh:
            geojson.dump(search_result, fh)
        return filename

    @staticmethod
    def deserialize(filename):
        """Loads results of a search from a geojson file.

        :param filename: A filename containing a search result encoded as a geojson
        :type filename: str
        :returns: The search results encoded in `filename`
        :rtype: :class:`~eodag.api.search_result.SearchResult`
        """
        with open(filename, "r") as fh:
            return SearchResult.from_geojson(geojson.load(fh))

    def deserialize_and_register(self, filename):
        """Loads results of a search from a geojson file and register
        products with the information needed to download itself

        :param filename: A filename containing a search result encoded as a geojson
        :type filename: str
        :returns: The search results encoded in `filename`
        :rtype: :class:`~eodag.api.search_result.SearchResult`
        """
        products = self.deserialize(filename)
        for i, product in enumerate(products):
            if product.downloader is None:
                auth = product.downloader_auth
                if auth is None:
                    auth = self._plugins_manager.get_auth_plugin(product.provider)
                products[i].register_downloader(
                    self._plugins_manager.get_download_plugin(product), auth
                )
        return products

    @_deprecated(
        reason="Use the StaticStacSearch search plugin instead", version="2.2.1"
    )
    def load_stac_items(
        self,
        filename,
        recursive=False,
        max_connections=100,
        provider=None,
        productType=None,
        timeout=HTTP_REQ_TIMEOUT,
        **kwargs,
    ):
        """Loads STAC items from a geojson file / STAC catalog or collection, and convert to SearchResult.

        Features are parsed using eodag provider configuration, as if they were
        the response content to an API request.

        :param filename: A filename containing features encoded as a geojson
        :type filename: str
        :param recursive: (optional) Browse recursively in child nodes if True
        :type recursive: bool
        :param max_connections: (optional) Maximum number of connections for HTTP requests
        :type max_connections: int
        :param provider: (optional) Data provider
        :type provider: str
        :param productType: (optional) Data product type
        :type productType: str
        :param timeout: (optional) Timeout in seconds for each internal HTTP request
        :type timeout: float
        :param kwargs: Parameters that will be stored in the result as
                       search criteria
        :type kwargs: Any
        :returns: The search results encoded in `filename`
        :rtype: :class:`~eodag.api.search_result.SearchResult`

        .. deprecated:: 2.2.1
           Use the :class:`~eodag.plugins.search.static_stac_search.StaticStacSearch` search plugin instead.
        """
        features = fetch_stac_items(
            filename,
            recursive=recursive,
            max_connections=max_connections,
            timeout=timeout,
        )
        nb_features = len(features)
        feature_collection = geojson.FeatureCollection(features)
        feature_collection["context"] = {
            "limit": nb_features,
            "matched": nb_features,
            "returned": nb_features,
        }

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

        # save preferred_provider and use provided one instead
        preferred_provider, _ = self.get_preferred_provider()
        self.set_preferred_provider(provider)
        products, _ = self.search(productType=productType, **kwargs)
        # restore preferred_provider
        self.set_preferred_provider(preferred_provider)

        # restore plugin._request
        plugin._request = plugin_request

        return products

    def download(
        self,
        product,
        progress_callback=None,
        wait=DEFAULT_DOWNLOAD_WAIT,
        timeout=DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs,
    ):
        """Download a single product.

        This is an alias to the method of the same name on
        :class:`~eodag.api.product._product.EOProduct`, but it performs some additional
        checks like verifying that a downloader and authenticator are registered
        for the product before trying to download it.

        If the metadata mapping for ``downloadLink`` is set to something that can be
        interpreted as a link on a
        local filesystem, the download is skipped (by now, only a link starting
        with ``file://`` is supported). Therefore, any user that knows how to extract
        product location from product metadata on a provider can override the
        ``downloadLink`` metadata mapping in the right way. For example, using the
        environment variable:
        ``EODAG__SOBLOO__SEARCH__METADATA_MAPPING__DOWNLOADLINK="file:///{id}"`` will
        lead to all :class:`~eodag.api.product._product.EOProduct`'s originating from the
        provider ``sobloo`` to have their ``downloadLink`` metadata point to something like:
        ``file:///12345-678``, making this method immediately return the later string without
        trying to download the product.

        :param product: The EO product to download
        :type product: :class:`~eodag.api.product._product.EOProduct`
        :param progress_callback: (optional) A method or a callable object
                                  which takes a current size and a maximum
                                  size as inputs and handle progress bar
                                  creation and update to give the user a
                                  feedback on the download progress
        :type progress_callback: :class:`~eodag.utils.ProgressCallback` or None
        :param wait: (optional) If download fails, wait time in minutes between
                    two download tries
        :type wait: int
        :param timeout: (optional) If download fails, maximum time in minutes
                        before stop retrying to download
        :type timeout: int
        :param kwargs: `outputs_prefix` (str), `extract` (bool), `delete_archive` (bool)
                        and `dl_url_params` (dict) can be provided as additional kwargs
                        and will override any other values defined in a configuration
                        file or with environment variables.
        :type kwargs: Union[str, bool, dict]
        :returns: The absolute path to the downloaded product in the local filesystem
        :rtype: str
        :raises: :class:`~eodag.utils.exceptions.PluginImplementationError`
        :raises: :class:`RuntimeError`
        """
        if product.location.startswith("file://"):
            logger.info("Local product detected. Download skipped")
            return uri_to_path(product.location)
        if product.downloader is None:
            auth = product.downloader_auth
            if auth is None:
                auth = self._plugins_manager.get_auth_plugin(product.provider)
            product.register_downloader(
                self._plugins_manager.get_download_plugin(product), auth
            )
        path = product.download(
            progress_callback=progress_callback, wait=wait, timeout=timeout, **kwargs
        )

        return path

    def get_cruncher(self, name, **options):
        """Build a crunch plugin from a configuration

        :param name: The name of the cruncher to build
        :type name: str
        :param options: The configuration options of the cruncher
        :type options: dict
        :returns: The cruncher named ``name``
        :rtype: :class:`~eodag.plugins.crunch.Crunch`
        """
        plugin_conf = {"name": name}
        plugin_conf.update({key.replace("-", "_"): val for key, val in options.items()})
        return self._plugins_manager.get_crunch_plugin(name, **plugin_conf)
