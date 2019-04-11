# -*- coding: utf-8 -*-
# Copyright 2018, CS Systemes d'Information, http://www.c-s.fr
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
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import shutil
from operator import itemgetter

import geojson
from pkg_resources import resource_filename
from tqdm import tqdm
from whoosh import fields
from whoosh.fields import Schema
from whoosh.index import create_in, exists_in, open_dir
from whoosh.qparser import QueryParser

from eodag.api.search_result import SearchResult
from eodag.config import (
    SimpleYamlProxyConfig,
    load_default_config,
    override_config_from_env,
    override_config_from_file,
)
from eodag.plugins.manager import PluginManager
from eodag.utils import makedirs
from eodag.utils.exceptions import (
    NoMatchingProductType,
    PluginImplementationError,
    UnsupportedProvider,
)

logger = logging.getLogger("eodag.core")

# pagination defaults
DEFAULT_PAGE = 1
DEFAULT_ITEMS_PER_PAGE = 20


class EODataAccessGateway(object):
    """An API for downloading a wide variety of geospatial products originating
    from different types of providers.

    :param user_conf_file_path: Path to the user configuration file
    :type user_conf_file_path: str or unicode
    """

    def __init__(self, user_conf_file_path=None):
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

    def build_index(self):
        """Build a `Whoosh <https://whoosh.readthedocs.io/en/latest/index.html>`_
        index for product types searches.

        .. versionadded:: 1.0
        """
        index_dir = os.path.join(self.conf_dir, ".index")

        # Handle Python 2/3 compatibility: if index_dir exists and contains a whoosh index, it means it was
        # potentially created with a previous Python 3 eodag session, thus using pickle highest protocol version
        # (version 4 at the time of writing for Python 3). In that case, if the current eodag session is in Python 2
        # a ValueError will be raised saying that the pickle protocol used to serialized the previous index is
        # incompatible with the current Python version. If that's the case, we first remove the problematic index
        # and create another one from scratch
        try:
            create_index = not exists_in(index_dir)
        except ValueError as ve:
            if "unsupported pickle protocol" in ve.message:
                shutil.rmtree(index_dir)
                create_index = True
            else:
                raise

        if create_index:
            logger.debug("Creating product types index in %s", index_dir)
            makedirs(index_dir)
            product_types_schema = Schema(
                ID=fields.STORED,
                abstract=fields.TEXT,
                instrument=fields.IDLIST(stored=True),
                platform=fields.ID,
                platformSerialIdentifier=fields.IDLIST(stored=True),
                processingLevel=fields.ID,
                sensorType=fields.ID,
            )
            self._product_types_index = create_in(index_dir, product_types_schema)
            ix_writer = self._product_types_index.writer()
            for product_type in self.list_product_types():
                ix_writer.add_document(**product_type)
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
        :type provider: str or unicode
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

    def list_product_types(self, provider=None):
        """Lists supported product types.

        :param provider: The name of a provider that must support the product
                         types we are about to list
        :type provider: str or unicode
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
        ...     platform="S2",
        ...     platformSerialIdentifier="S2A",
        ...     processingLevel="L1C",
        ...     sensorType="OPTICAL"
        ... )
        'S2_MSI_L1C'
        >>> import eodag.utils.exceptions
        >>> try:
        ...     dag.guess_product_type()
        ...     raise AssertionError(u"NoMatchingProductType exception not raised")
        ... except eodag.utils.exceptions.NoMatchingProductType:
        ...     pass

        :param kwargs: A set of search parameters as keywords arguments
        :return: The best match for the given parameters
        :rtype: str or unicode
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
        # By now, only return the best bet
        if guesses:
            return guesses[0]
        raise NoMatchingProductType()

    def search(
        self,
        page=DEFAULT_PAGE,
        items_per_page=DEFAULT_ITEMS_PER_PAGE,
        raise_errors=False,
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
        :param dict kwargs: some other criteria that will be used to do the search
        :returns: A collection of EO products matching the criteria, the current
                  returned page and the total number of results found
        :rtype: tuple(:class:`~eodag.api.search_result.SearchResult`, int)

        .. versionchanged::
           1.0

                * The ``product_type`` parameter is no longer mandatory
                * Support new search parameters compliant with OpenSearch
                * Fails if a suitable product type could not be guessed (returns an
                  empty search result)

        .. versionchanged::
           0.7.1

                * The search now stops at the first provider that supports the
                  requested product type (removal of the
                  partial mechanism)
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
        results = SearchResult([])
        total_results = 0

        product_type = kwargs.pop("productType", None)
        if product_type is None:
            try:
                product_type = self.guess_product_type(**kwargs)
            except NoMatchingProductType:
                logger.error("No product type could be guessed with provided arguments")
                return results

        plugin = next(self._plugins_manager.get_search_plugins(product_type))
        logger.info(
            "Searching product type '%s' on provider: %s", product_type, plugin.provider
        )
        logger.debug("Using plugin class for search: %s", plugin.__class__.__name__)
        auth = self._plugins_manager.get_auth_plugin(product_type, plugin.provider)
        try:
            res, nb_res = plugin.query(
                product_type,
                auth=auth,
                items_per_page=items_per_page,
                page=page,
                **kwargs
            )

            # Take into account the fact that a provider may not return the count of
            # products (in that case, fallback to using the length of the results it
            # returned and the page requested. As an example, check the result of the
            # following request (look for the value of properties.totalResults)
            # https://theia-landsat.cnes.fr/resto/api/collections/Landsat/search.json?
            # maxRecords=1&page=1
            if nb_res == 0:
                nb_res = len(res) * page

            # Attempt to ensure a little bit more coherence. Some providers return a
            # fuzzy number of total results, meaning that you have to keep requesting
            # it until it has returned everything it has to know exactly how many EO
            # products they have in their stock. In that case, we need to replace the
            # returned number of results with the sum of the number of items that were
            # skipped so far and the length of the currently retrieved items. We know
            # there is an incoherence when the number of skipped items is greater than
            # the total number of items returned by the plugin
            nb_skipped_items = items_per_page * (page - 1)
            nb_current_items = len(res)
            if nb_skipped_items > nb_res:
                if nb_res != 0:
                    nb_res = nb_skipped_items + nb_current_items
                # This is for when the returned results is an empty list and the number
                # of results returned is incoherent with the observations. In that case,
                # we assume the total number of results is the number of skipped
                # results. By requesting a lower page than the current one, a user can
                # iteratively reach the last page of results for these criteria on the
                # provider.
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
                    eo_product.register_downloader(download_plugin, auth)

            results.extend(res)
            total_results += nb_res
            logger.info("Found %s result(s) on provider '%s'", nb_res, plugin.provider)
        except Exception as e:
            logger.info(
                "No result from provider '%s' due to an error during search. Raise "
                "verbosity of log messages for details",
                plugin.provider,
            )
            if raise_errors:
                # Raise the error, letting the application wrapping eodag know that
                # something went bad. This way it will be able to decide what to do next
                raise e
            else:
                logger.exception(
                    "Error while searching on provider %s (ignored):", plugin.provider
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
    def sort_by_extent(searches):
        """Combines multiple SearchResults and return a list of SearchResults sorted
        by extent.

        :param searches: List of eodag SearchResult
        :type searches: list
        :return: list of :class:`~eodag.api.search_result.SearchResult`
        """
        products_grouped_by_extent = {}

        for search in searches:
            for product in search:
                same_geom = products_grouped_by_extent.setdefault(
                    "".join([str(round(p, 2)) for p in product.geometry.bounds]), []
                )
                same_geom.append(product)

        return [
            SearchResult(products_grouped_by_extent[extent_as_wkb_hex])
            for extent_as_wkb_hex in products_grouped_by_extent
        ]

    def download_all(self, search_result, progress_callback=None):
        """Download all products resulting from a search.

        :param search_result: A collection of EO products resulting from a search
        :type search_result: :class:`~eodag.api.search_result.SearchResult`
        :param progress_callback: (optional) A method or a callable object
                                  which takes a current size and a maximum
                                  size as inputs and handle progress bar
                                  creation and update to give the user a
                                  feedback on the download progress
        :type progress_callback: :class:`~eodag.utils.ProgressCallback` or None
        :returns: A collection of the absolute paths to the downloaded products
        :rtype: list
        """
        paths = []
        if search_result:
            logger.info("Downloading %s products", len(search_result))
            with tqdm(
                search_result, unit="product", desc="Downloading products"
            ) as bar:
                for product in bar:
                    try:
                        paths.append(
                            self.download(product, progress_callback=progress_callback)
                        )
                    except Exception:
                        import traceback as tb

                        logger.warning(
                            "A problem occurred during download of product: %s. "
                            "Skipping it",
                            product,
                        )
                        logger.debug("\n%s", tb.format_exc())
        else:
            logger.info("Empty search result, nothing to be downloaded !")
        return paths

    @staticmethod
    def serialize(search_result, filename="search_results.geojson"):
        """Registers results of a search into a geojson file.

        :param search_result: A collection of EO products resulting from a search
        :type search_result: :class:`~eodag.api.search_result.SearchResult`
        :param filename: The name of the file to generate
        :type filename: str or unicode
        :returns: The name of the created file
        :rtype: str or unicode
        """
        with open(filename, "w") as fh:
            geojson.dump(search_result, fh)
        return filename

    @staticmethod
    def deserialize(filename):
        """Loads results of a search from a geojson file.

        :param filename: A filename containing a search result encoded as a geojson
        :type filename: str or unicode
        :returns: The search results encoded in `filename`
        :rtype: :class:`~eodag.api.search_result.SearchResult`
        """
        with open(filename, "r") as fh:
            return SearchResult.from_geojson(geojson.load(fh))

    def download(self, product, progress_callback=None):
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
        :returns: The absolute path to the downloaded product in the local filesystem
        :rtype: str or unicode
        :raises: :class:`~eodag.utils.exceptions.PluginImplementationError`
        :raises: :class:`RuntimeError`
        """
        if product.location.startswith("file"):
            logger.info("Local product detected. Download skipped")
            return product.location
        if product.downloader is None:
            auth = product.downloader_auth
            if auth is None:
                auth = self._plugins_manager.get_auth_plugin(
                    product.product_type, product.provider
                )
            product.register_downloader(
                self._plugins_manager.get_download_plugin(product), auth
            )
        return product.download(progress_callback=progress_callback)

    def get_cruncher(self, name, **options):
        """Build a crunch plugin from a configuration

        :param name: The name of the cruncher to build
        :type name: str of unicode
        :param options: The configuration options of the cruncher
        :type options: dict
        :return: The cruncher named ``name``
        :rtype: :class:`~eodag.plugins.crunch.Crunch`
        """
        plugin_conf = {"name": name}
        plugin_conf.update({key.replace("-", "_"): val for key, val in options.items()})
        return self._plugins_manager.get_crunch_plugin(name, **plugin_conf)
