# -*- coding: utf-8 -*-
# Copyright 2020, CS GROUP - France, http://www.c-s.fr
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
import shutil
from operator import itemgetter

import geojson
import pkg_resources
import yaml.parser
from pkg_resources import resource_filename
from whoosh import fields
from whoosh.fields import Schema
from whoosh.index import create_in, exists_in, open_dir
from whoosh.qparser import QueryParser

from eodag.api.search_result import SearchResult
from eodag.config import (
    SimpleYamlProxyConfig,
    load_default_config,
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
    get_geometry_from_various,
    makedirs,
)
from eodag.utils.exceptions import (
    NoMatchingProductType,
    PluginImplementationError,
    UnsupportedProvider,
)
from eodag.utils.stac_reader import fetch_stac_items

logger = logging.getLogger("eodag.core")

# pagination defaults
DEFAULT_PAGE = 1
DEFAULT_ITEMS_PER_PAGE = 20


class EODataAccessGateway(object):
    """An API for downloading a wide variety of geospatial products originating
    from different types of providers.

    :param user_conf_file_path: Path to the user configuration file
    :type user_conf_file_path: str
    :param locations_conf_path: Path to the locations configuration file
    :type locations_conf_path: str
    """

    def __init__(self, user_conf_file_path=None, locations_conf_path=None):
        self.product_types_config = SimpleYamlProxyConfig(
            resource_filename("eodag", os.path.join("resources/", "product_types.yml"))
        )
        self.providers_config = load_default_config()

        self.conf_dir = os.path.join(os.path.expanduser("~"), ".config", "eodag")
        makedirs(self.conf_dir)

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

        self._plugins_manager = PluginManager(self.providers_config)

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
                        for line in infile:
                            line = line.replace(
                                "/path/to/locations", os.path.join(self.conf_dir, "shp")
                            )
                            outfile.write(line)
                    # copy sample shapefile dir
                    shutil.copytree(
                        resource_filename("eodag", os.path.join("resources", "shp")),
                        os.path.join(self.conf_dir, "shp"),
                    )
        self.set_locations_conf(locations_conf_path)

    def build_index(self):
        """Build a `Whoosh <https://whoosh.readthedocs.io/en/latest/index.html>`_
        index for product types searches.

        .. versionadded:: 1.0
        """
        index_dir = os.path.join(self.conf_dir, ".index")

        # use eodag_version to help keeping index up-to-date
        eodag_version = pkg_resources.get_distribution("eodag").version

        # Handle Python 2/3 compatibility: if index_dir exists and contains a whoosh
        # index, it means it was potentially created with a previous Python 3 eodag
        # session, thus using pickle highest protocol version (version 4 at the time of
        # writing for Python 3). In that case, if the current eodag session is in Python
        # 2 a ValueError will be raised saying that the pickle protocol used to
        # serialized the previous index is incompatible with the current Python version.
        # If that's the case, we first remove the problematic index and create another
        # one from scratch
        try:
            create_index = not exists_in(index_dir)
            # check index version
            if not create_index:
                if self._product_types_index is None:
                    logger.debug("Opening product types index in %s", index_dir)
                    self._product_types_index = open_dir(index_dir)
                try:
                    self.guess_product_type(eodagVersion=eodag_version)
                except NoMatchingProductType:
                    logger.debug(
                        "Out-of-date product types index removed from %s", index_dir
                    )
                    shutil.rmtree(index_dir)
                    create_index = True

        except ValueError as ve:
            if "unsupported pickle protocol" in (
                ve.message if hasattr(ve, "message") else str(ve)
            ):
                shutil.rmtree(index_dir)
                create_index = True
            else:
                logger.error(
                    "Error while building index using whoosh, "
                    "please report this issue and try to delete %s manually",
                    index_dir,
                )
                raise

        if create_index:
            logger.debug("Creating product types index in %s", index_dir)
            makedirs(index_dir)
            product_types_schema = Schema(
                ID=fields.STORED,
                abstract=fields.TEXT,
                instrument=fields.IDLIST,
                platform=fields.ID,
                platformSerialIdentifier=fields.IDLIST,
                processingLevel=fields.ID,
                sensorType=fields.ID,
                eodagVersion=fields.ID,
                license=fields.ID,
                title=fields.ID,
                missionStartDate=fields.ID,
                missionEndDate=fields.ID,
            )
            non_indexable_fields = ["bands"]
            self._product_types_index = create_in(index_dir, product_types_schema)
            ix_writer = self._product_types_index.writer()
            for product_type in self.list_product_types():
                versioned_product_type = dict(
                    product_type, **{"eodagVersion": eodag_version}
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
        >>> config = tempfile.NamedTemporaryFile(delete=True)
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
        >>> dag.set_preferred_provider(u'usgs')
        >>> dag.get_preferred_provider()
        ('usgs', 2)
        >>> dag.set_preferred_provider(u'theia')
        >>> dag.get_preferred_provider()
        ('theia', 3)
        >>> dag.set_preferred_provider(u'usgs')
        >>> dag.get_preferred_provider()
        ('usgs', 4)
        >>> config.close()

        :param provider: The name of the provider that should be considered as the
                         preferred provider to be used for this instance
        :type provider: str
        """
        if provider not in self.available_providers():
            raise UnsupportedProvider("This provider is not recognised by eodag")
        preferred_provider, max_priority = self.get_preferred_provider()
        if preferred_provider != provider:
            new_priority = max_priority + 1
            self._plugins_manager.set_priority(provider, new_priority)

    def get_preferred_provider(self):
        """Get the provider currently set as the preferred one for searching
        products, along with its priority.

        :return: The provider with the maximum priority and its priority
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
        >>> dag.update_providers_config('''
        ...     my_new_provider:
        ...         search:
        ...             type: StacSearch
        ...             api_endpoint: https://api.my_new_provider/search
        ...         products:
        ...             GENERIC_PRODUCT_TYPE:
        ...                 productType: '{productType}'
        ... ''')
        >>> type(dag.providers_config["my_new_provider"])
        <class 'eodag.config.ProviderConfig'>
        >>> dag.providers_config["my_new_provider"].priority
        0

        :param yaml_conf: YAML formated provider configuration
        :type yaml_conf: str
        """
        conf_update = yaml.safe_load(yaml_conf)
        override_config_from_mapping(self.providers_config, conf_update)
        for provider in conf_update.keys():
            provider_config_init(self.providers_config[provider])
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

    def list_product_types(self, provider=None):
        """Lists supported product types.

        :param provider: The name of a provider that must support the product
                         types we are about to list
        :type provider: str
        :returns: The list of the product types that can be accessed using eodag.
        :rtype: list(dict)
        :raises: :class:`~eodag.utils.exceptions.UnsupportedProvider`
        """
        product_types = []
        if provider is not None:
            if provider in self.providers_config:
                provider_supported_products = self.providers_config[provider].products
                for product_type_id in provider_supported_products:
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
                    for pt in self.list_product_types(provider=provider)
                    if pt["ID"] not in current_product_type_ids
                ]
            )
        # Return the product_types sorted in lexicographic order of their ID
        return sorted(product_types, key=itemgetter("ID"))

    def available_providers(self):
        """Gives the list of the available providers"""
        return sorted(tuple(self.providers_config.keys()))

    def guess_product_type(self, **kwargs):
        """Find the eodag product type code that best matches a set of search params

        >>> from eodag import EODataAccessGateway
        >>> dag = EODataAccessGateway()
        >>> dag.guess_product_type(
        ...     instrument="MSI",
        ...     platform="SENTINEL2",
        ...     platformSerialIdentifier="S2A",
        ... ) # doctest: +NORMALIZE_WHITESPACE
        ['S2_MSI_L1C', 'S2_MSI_L2A', 'S2_MSI_L2A_MAJA', 'S2_MSI_L2B_MAJA_SNOW',
            'S2_MSI_L2B_MAJA_WATER', 'S2_MSI_L3A_WASP']
        >>> import eodag.utils.exceptions
        >>> try:
        ...     dag.guess_product_type()
        ...     raise AssertionError(u"NoMatchingProductType exception not raised")
        ... except eodag.utils.exceptions.NoMatchingProductType:
        ...     pass

        :param kwargs: A set of search parameters as keywords arguments
        :return: The best match for the given parameters
        :rtype: str
        :raises: :class:`~eodag.utils.exceptions.NoMatchingProductType`

        .. versionadded:: 1.0
        """
        supported_params = {
            param
            for param in (
                "instrument",
                "platform",
                "platformSerialIdentifier",
                "processingLevel",
                "sensorType",
                "eodagVersion",
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
                    results = searcher.search(query)
                else:
                    results.upgrade_and_extend(searcher.search(query))
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
        **kwargs
    ):
        """Look for products matching criteria on known providers.

        The default behaviour is to look for products on the provider with the
        highest priority supporting the requested product type. These priorities
        are configurable through user configuration file or individual
        environment variable.

        :param page: The page number to return (default: 1)
        :type page: int
        :param items_per_page: The number of results that must appear in one single
                               page (default: 20)
        :type items_per_page: int
        :param raise_errors:  When an error occurs when searching, if this is set to
                              True, the error is raised (default: False)
        :type raise_errors: bool
        :param start: Start sensing time in iso format
        :type start: str
        :param end: End sensing time in iso format
        :type end: str
        :param geom: Dictionnary defining the AOI. Information can be defined in different ways:

                    * with a Shapely geometry object ("obj" as key):
                      ``{"obj": :class:`shapely.geometry.base.BaseGeometry`}``
                    * with a bounding box (dict with keys: "lonmin", "latmin", "lonmax", "latmax"):
                      ``dict.fromkeys(["lonmin", "latmin", "lonmax", "latmax"])``
                    * with a bounding box as list of float:
                      ``[lonmin, latmin, lonmax, latmax]``
                    * with a WKT str
                    The geometry can also be passed as ``<location_name>="<attr_regex>"`` in kwargs
        :type geom: Union[str, dict, shapely.geometry.base.BaseGeometry])
        :param dict kwargs: some other criteria that will be used to do the search,
                            using paramaters compatibles with the provider, or also
                            location filtering by name using locations configuration
                            ``<location_name>="<attr_regex>"`` (e.g.: ``country="PA.`` will use
                            the geometry of the features having the property ISO3 starting with
                            'PA' such as Panama and Pakistan in the shapefile configured with
                            name=country and attr=ISO3)
        :returns: A collection of EO products matching the criteria and the total
                  number of results found
        :rtype: tuple(:class:`~eodag.api.search_result.SearchResult`, int)

        .. versionchanged::
           1.6

                * Any search parameter supported by the provider can be passed as
                  kwargs. Each provider has a 'discover_metadata' configuration
                  with a metadata_pattern (to which the parameter must match) and a
                  search_param setting, defining the way the query will be built.

        .. versionchanged::
           1.0

                * The ``product_type`` parameter is no longer mandatory
                * Support new search parameters compliant with OpenSearch
                * Fails if a suitable product type could not be guessed (returns an
                  empty search result) and if the user is not querying a specific
                  product (by providing ``id`` as search parameter)
                * A search by ID is now performed if a product type can not be guessed
                  from the user input, and if the user has provided an ID as a search
                  criteria (in the keyword arguments)
                * It is now possible to pass in the name of the provider on which to
                  perform the request when searching a product by its ID,
                  for performance reasons. In that case, the search with the product ID
                  will be done directly on that provider

        .. versionchanged::
           0.7.1

                * The search now stops at the first provider that supports the
                  requested product type (removal of the partial mechanism)
                * The method now returns a tuple of 2 elements, the first one
                  being the result and the second one being the total number of
                  results satisfying the criteria on the provider. This is useful
                  for applications wrapping eodag and wishing to implement
                  pagination. An example of this kind of application is the
                  embedded eodag HTTP server. Also useful for informational purposes
                  in the CLI: the user is informed about the total number of results
                  available, and can ask for retrieving a given number of these
                  results (See the help message of the CLI for more information).

        .. note::
            The search interfaces, which are implemented as plugins, are required to
            return a list as a result of their processing. This requirement is
            enforced here.
        """
        product_type = kwargs.get("productType", None)
        if product_type is None:
            try:
                guesses = self.guess_product_type(**kwargs)
                # By now, only use the best bet
                product_type = guesses[0]
            except NoMatchingProductType:
                queried_id = kwargs.get("id", None)
                if queried_id is None:
                    logger.info(
                        "No product type could be guessed with provided arguments"
                    )
                else:
                    provider = kwargs.get("provider", None)
                    return self._search_by_id(kwargs["id"], provider=provider)

        kwargs["productType"] = product_type
        if start is not None:
            kwargs["startTimeFromAscendingNode"] = start
        if end is not None:
            kwargs["completionTimeFromAscendingNode"] = end
        if geom is not None:
            kwargs["geometry"] = geom
        box = kwargs.pop("box", None)
        box = kwargs.pop("bbox", box)
        if geom is None and box is not None:
            kwargs["geometry"] = box

        kwargs["geometry"] = get_geometry_from_various(self.locations_config, **kwargs)
        # remove locations_args from kwargs now that they have been used
        locations_dict = {loc["name"]: loc for loc in self.locations_config}
        for arg in locations_dict.keys():
            kwargs.pop(arg, None)

        plugin = next(
            self._plugins_manager.get_search_plugins(product_type=product_type)
        )
        logger.info(
            "Searching product type '%s' on provider: %s", product_type, plugin.provider
        )
        # add product_types_config to plugin config
        try:
            plugin.config.product_type_config = dict(
                [
                    p
                    for p in self.list_product_types(plugin.provider)
                    if p["ID"] == product_type
                ][0],
                **{"productType": product_type}
            )
        except IndexError:
            plugin.config.product_type_config = dict(
                [
                    p
                    for p in self.list_product_types(plugin.provider)
                    if p["ID"] == GENERIC_PRODUCT_TYPE
                ][0],
                **{"productType": product_type}
            )
        plugin.config.product_type_config.pop("ID", None)

        logger.debug("Using plugin class for search: %s", plugin.__class__.__name__)
        auth = self._plugins_manager.get_auth_plugin(plugin.provider)
        return self._do_search(
            plugin,
            auth=auth,
            page=page,
            items_per_page=items_per_page,
            raise_errors=raise_errors,
            **kwargs
        )

    def _search_by_id(self, uid, provider=None):
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
        :returns: A search result with one EO product or None at all, and the number
                  of EO products retrieved (0 or 1)
        :rtype: tuple(:class:`~eodag.api.search_result.SearchResult`, int)

        .. versionadded:: 1.0
        """
        for plugin in self._plugins_manager.get_search_plugins(provider=provider):
            logger.info(
                "Searching product with id '%s' on provider: %s", uid, plugin.provider
            )
            logger.debug("Using plugin class for search: %s", plugin.__class__.__name__)
            auth = self._plugins_manager.get_auth_plugin(plugin.provider)
            results, _ = self._do_search(plugin, auth=auth, id=uid)
            if len(results) == 1:
                return results, 1
        return SearchResult([]), 0

    def _do_search(self, search_plugin, **kwargs):
        """Internal method that performs a search on a given provider.

        .. versionadded:: 1.0
        """
        results = SearchResult([])
        total_results = 0
        try:
            res, nb_res = search_plugin.query(**kwargs)

            # Only do the pagination computations when it makes sense. For example,
            # for a search by id, we can reasonably guess that the provider will return
            # At most 1 product, so we don't need such a thing as pagination
            page = kwargs.get("page")
            items_per_page = kwargs.get("items_per_page")
            if page and items_per_page:
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
                if eo_product.search_intersection is not None:
                    download_plugin = self._plugins_manager.get_download_plugin(
                        eo_product
                    )
                    eo_product.register_downloader(
                        download_plugin, kwargs.get("auth", None)
                    )

            results.extend(res)
            total_results += nb_res
            logger.info(
                "Found %s result(s) on provider '%s'", nb_res, search_plugin.provider
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
            if kwargs.get("raise_errors"):
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
        :return: The result of successively applying all the filters to the results
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
        :return: list of :class:`~eodag.api.search_result.SearchResult`

        .. versionchanged::
           2.0

                * Renamed from sort_by_extent to group_by_extent to reflect its
                  actual behaviour.
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
        progress_callback=None,
        wait=DEFAULT_DOWNLOAD_WAIT,
        timeout=DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs
    ):
        """Download all products resulting from a search.

        :param search_result: A collection of EO products resulting from a search
        :type search_result: :class:`~eodag.api.search_result.SearchResult`
        :param progress_callback: (optional) A method or a callable object
                                  which takes a current size and a maximum
                                  size as inputs and handle progress bar
                                  creation and update to give the user a
                                  feedback on the download progress
        :type progress_callback: :class:`~eodag.utils.ProgressCallback` or None
        :param wait: (optional) If download fails, wait time in minutes between
                    two download tries of the same product (default=2')
        :type wait: int
        :param timeout: (optional) If download fails, maximum time in minutes
                    before stop retrying to download (default=20')
        :type timeout: int
        :param dict kwargs: `outputs_prefix` (str), `extract` (bool) and
                            `dl_url_params` (dict) can be provided here and will
                            override any other values defined in a configuration file
                            or with environment variables.
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
                progress_callback=progress_callback,
                wait=wait,
                timeout=timeout,
                **kwargs
            )
        else:
            logger.info("Empty search result, nothing to be downloaded !")
        return paths

    @staticmethod
    def serialize(search_result, filename="search_results.geojson"):
        """Registers results of a search into a geojson file.

        :param search_result: A collection of EO products resulting from a search
        :type search_result: :class:`~eodag.api.search_result.SearchResult`
        :param filename: The name of the file to generate
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

    def load_stac_items(
        self,
        filename,
        recursive=False,
        max_connections=100,
        provider=None,
        productType=None,
        **kwargs
    ):
        """Loads STAC items from a geojson file / STAC catalog or collection, and convert to SearchResult.

        Features are parsed using eodag provider configuration, as if they were
        the response content to an API request.

        :param filename: A filename containing features encoded as a geojson
        :type filename: str
        :param recursive: Brownse recursively in child nodes if True
        :type recursive: bool
        :param max_connections: max connections for http requests
        :type max_connections: int
        :param provider: data provider
        :type provider: str
        :param productType: data product type
        :type productType: str
        :param dict kwargs: parameters that will be stored in the result as
                            search criteria
        :returns: The search results encoded in `filename`
        :rtype: :class:`~eodag.api.search_result.SearchResult`
        """
        features = fetch_stac_items(
            filename, recursive=recursive, max_connections=max_connections
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
        plugin._request = lambda url, info_message=None, exception_message=None: MockResponse(
            feature_collection, 200
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
        **kwargs
    ):
        """Download a single product.

        This is an alias to the method of the same name on
        :class:`~eodag.api.product.EOProduct`, but it performs some additional
        checks like verifying that a downloader and authenticator are registered
        for the product before trying to download it. If the metadata mapping for
        `downloadLink` is set to something that can be interpreted as a link on a
        local filesystem, the download is skipped (by now, only a link starting
        with `file://` is supported). Therefore, any user that knows how to extract
        product location from product metadata on a provider can override the
        `downloadLink` metadata mapping in the right way. For example, using the
        environment variable:
        EODAG__SOBLOO__SEARCH__METADATA_MAPPING__DOWNLOADLINK="file:///{id}" will
        lead to all `EOProduct`s originating from the provider `sobloo` to have their
        `downloadLink` metadata point to something like: "file:///12345-678",
        making this method immediately return the later string without trying
        to download the product.

        :param product: The EO product to download
        :type product: :class:`~eodag.api.product.EOProduct`
        :param progress_callback: (optional) A method or a callable object
                                  which takes a current size and a maximum
                                  size as inputs and handle progress bar
                                  creation and update to give the user a
                                  feedback on the download progress
        :type progress_callback: :class:`~eodag.utils.ProgressCallback` or None
        :param wait: (optional) If download fails, wait time in minutes between
                    two download tries (default=2')
        :type wait: int
        :param timeout: (optional) If download fails, maximum time in minutes
                        before stop retrying to download (default=20')
        :type timeout: int
        :param dict kwargs: `outputs_prefix` (str), `extract` (bool) and
                            `dl_url_params` (dict) can be provided as additional kwargs
                            and will override any other values defined in a configuration
                            file or with environment variables.
        :returns: The absolute path to the downloaded product in the local filesystem
        :rtype: str
        :raises: :class:`~eodag.utils.exceptions.PluginImplementationError`
        :raises: :class:`RuntimeError`
        """
        if product.location.startswith("file"):
            logger.info("Local product detected. Download skipped")
            return product.location
        if product.downloader is None:
            auth = product.downloader_auth
            if auth is None:
                auth = self._plugins_manager.get_auth_plugin(product.provider)
            product.register_downloader(
                self._plugins_manager.get_download_plugin(product), auth
            )
        return product.download(
            progress_callback=progress_callback, wait=wait, timeout=timeout, **kwargs
        )

    def get_cruncher(self, name, **options):
        """Build a crunch plugin from a configuration

        :param name: The name of the cruncher to build
        :type name: str
        :param options: The configuration options of the cruncher
        :type options: dict
        :return: The cruncher named ``name``
        :rtype: :class:`~eodag.plugins.crunch.Crunch`
        """
        plugin_conf = {"name": name}
        plugin_conf.update({key.replace("-", "_"): val for key, val in options.items()})
        return self._plugins_manager.get_crunch_plugin(name, **plugin_conf)
