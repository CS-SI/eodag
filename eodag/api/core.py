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
from operator import itemgetter

import geojson
from pkg_resources import resource_filename
from tqdm import tqdm

from eodag.api.search_result import SearchResult
from eodag.config import (
    SimpleYamlProxyConfig, load_default_config, override_config_from_env, override_config_from_file,
)
from eodag.plugins.manager import PluginManager
from eodag.utils.exceptions import PluginImplementationError, UnsupportedProvider


logger = logging.getLogger('eodag.core')

# pagination defaults
DEFAULT_PAGE = 1
DEFAULT_ITEMS_PER_PAGE = 20


class EODataAccessGateway(object):
    """An API for downloading a wide variety of geospatial products originating from different types of systems.

    :param user_conf_file_path: Path to the user configuration file
    :type user_conf_file_path: str or unicode
    """

    def __init__(self, user_conf_file_path=None):
        self.product_types_config = SimpleYamlProxyConfig(resource_filename('eodag', 'resources/product_types.yml'))
        self.providers_config = load_default_config()

        # First level override: From a user configuration file
        if user_conf_file_path:
            override_config_from_file(self.providers_config, user_conf_file_path)

        # Second level override: From environment variables
        override_config_from_env(self.providers_config)

        self._plugins_manager = PluginManager(self.providers_config)

        # A cache of exhausted providers (providers on which there are no results left
        self._exhausted_providers = set()
        # A state giving the last index used to query a given provider
        self._provider_index_cache = {}

    def drop_cache(self):
        self._provider_index_cache.clear()
        self._exhausted_providers.clear()

    def set_preferred_provider(self, provider):
        """Set max priority for the given provider.

        >>> import eodag.utils.exceptions
        >>> dag = EODataAccessGateway()
        >>> dag.get_preferred_provider()    # This also tests get_preferred_provider method by the way
        ('peps', 1)
        >>> # For the following lines, see http://python3porting.com/problems.html#handling-expected-exceptions
        >>> try:
        ...     dag.set_preferred_provider(u'unknown')
        ...     raise AssertionError(u'UnsupportedProvider exception was not raised as expected')
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

        :param provider: The name of the provider that should be considered as the preferred provider to be used for
                         this instance
        :type provider: str or unicode
        """
        if provider not in self.available_providers():
            raise UnsupportedProvider('This provider is not recognised by eodag')
        preferred_provider, max_priority = self.get_preferred_provider()
        if preferred_provider != provider:
            new_priority = max_priority + 1
            self._plugins_manager.set_priority(provider, new_priority)

    def get_preferred_provider(self):
        """Get the provider currently set as the preferred one for searching products, along with its priority.

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

        :param provider: The name of a provider that must support the product types we are about to list
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
                    product_type = dict(ID=product_type_id, **self.product_types_config[product_type_id])
                    if product_type_id not in product_types:
                        product_types.append(product_type)
                return sorted(product_types, key=itemgetter('ID'))
            raise UnsupportedProvider("The requested provider is not (yet) supported")
        # Only get the product types supported by the available providers
        for provider in self.available_providers():
            current_product_type_ids = [pt['ID'] for pt in product_types]
            product_types.extend([
                pt for pt in self.list_product_types(provider=provider)
                if pt['ID'] not in current_product_type_ids
            ])
        # Return the product_types sorted in lexicographic order of their ID
        return sorted(product_types, key=itemgetter('ID'))

    def available_providers(self):
        """Gives the list of the available providers"""
        return tuple(self.providers_config.keys())

    def search(self, product_type, page=DEFAULT_PAGE, max_results=0, items_per_page=DEFAULT_ITEMS_PER_PAGE,
               start=0, stop=1, with_pagination_info=False, exhaust_provider=False, **kwargs):
        """Look for products matching criteria in known providers.

        The default behaviour is to look for products in the provider with the highest priority. If the search gives
        no results, or if the provider is known to support only a partial collection of the searched product type, the
        search then continues on the other providers supporting the requested product type, ordered by highest
        priority. These priorities are configurable through user configuration file or individual environment variable.

        .. note::
            From the behaviour described here, it is possible to make the search to continue on other providers by
            setting the `partial_support` configuration parameter to `true` for the corresponding product type in the
            configuration of the provider with the highest priority, like for example with an environment variable like
            EODAG__SOBLOO__PRODUCTS__S2_MSI_L1C__PARTIAL_SUPPORT=true

        :param product_type: The product type to search
        :type product_type: str or unicode
        :param page: The page number to return (default: 1)
        :type page: int
        :param start: On which page to start on the providers, indexed as in a list. Search plugin implementations are
                      free to ignore this (default: 0)
        :type start: int
        :param stop: On which page to stop on the providers, indexed as in a list. Search plugin implementations are
                     free to ignore this (default: 1)
        :type stop: int
        :param max_results: The maximum number of results to return. If this number is reached for the preferred
                            provider, the search stops there. Otherwise, it continues on the other providers
                            supporting the requested product type, even if ``partial_support`` is de-activated for
                            the preferred provider and the subsequent providers (default: 0, meaning this constraint
                            is relaxed => search continuation is driven by the ``partial_support`` mechanism)
        :type max_results: int
        :param items_per_page: The number of results that must appear in one single page (default: 20)
        :type items_per_page: int
        :param with_pagination_info: Return the information on pagination with the result. This is useful for
                                     applications that which to implement pagination on top of eodag search interface.
                                     An example is provided in the embedded HTTP server (default: False)
        :type with_pagination_info: bool
        :param exhaust_provider: Retrieve all the results available on each provider (default: False)
        :type exhaust_provider: bool
        :param dict kwargs: some other criteria that will be used to do the search
        :returns: A collection of EO products matching the criteria, the current returned page and the total number of
                  results found
        :rtype: tuple[class:`~eodag.api.search_result.SearchResult`, int, int] or
                class:`~eodag.api.search_result.SearchResult`

        .. note::
            The search interfaces, which are implemented as plugins, are required to return a list as a result of their
            processing. This requirement is enforced here.
        """
        results = SearchResult([])
        if items_per_page is None:
            items_per_page = DEFAULT_ITEMS_PER_PAGE
        if page is None:
            page = DEFAULT_PAGE
        if page > 1:
            start = page - 1
        if start >= stop:   # Ensure we always ask for a range of pages (minimum one page)
            stop = start + 1
        if exhaust_provider:      # Retrieve absolutely all results on a given provider (The greedy way)
            start, stop = 0, -1
        total_results = 0
        # How many results are left to retrieve
        rest = max_results
        for plugin in self._plugins_manager.get_search_plugins(product_type):
            if plugin.provider in self._exhausted_providers:
                logging.debug('Skipping exhausted provider: %s', plugin.provi)
                continue
            logger.info("Searching product type '%s' on provider: %s", product_type, plugin.provider)
            logger.debug('Using plugin class for search: %s', plugin.__class__.__name__)
            auth = self._plugins_manager.get_auth_plugin(product_type, plugin.provider)
            try:
                # Configure the number of items per page
                getattr(plugin.config, 'pagination', {})['items_per_page'] = items_per_page
                if max_results == 0:
                    if with_pagination_info:
                        res, nb_res = plugin.query(product_type, auth=auth, start=start, stop=stop,
                                                   max_count=True, **kwargs)
                    else:
                        res = plugin.query(product_type, auth=auth, start=start, stop=stop, **kwargs)
                        nb_res = len(res)

                    if not isinstance(res, list):
                        raise PluginImplementationError(
                            'The query function of a Search plugin must return a list of results, got {} '
                            'instead'.format(type(res)))
                    total_results += nb_res
                    logger.info("Found %s result(s) on provider '%s'", nb_res, plugin.provider)

                    # Filter and attach to each eoproduct in the result the plugin capable of downloading it (this
                    # is done to enable the eo_product to download itself doing: eo_product.download())
                    # The filtering is done by keeping only those eo_products that intersects the search extent (if
                    # there
                    # was no search extent, search_intersection contains the geometry of the eo_product)
                    # WARNING: this means an eo_product that has an invalid geometry can still be returned as a search
                    # result if there was no search extent (because we will not try to do an intersection)
                    for eo_product in res:
                        if eo_product.search_intersection is not None:
                            download_plugin = self._plugins_manager.get_download_plugin(eo_product)
                            eo_product.register_downloader(download_plugin, auth)

                    # Decide if we should go on with the search using the other search plugins using the
                    # partial_support mechanism. In that case, the following rules makes the search to continue on
                    # other providers:
                    #    1. The currently used plugin is the preferred one (the first), and it returned no result
                    #    2. The currently used plugin supports the product_type partially (partial_support = True)
                    if not plugin.config.products[product_type].get('partial_support', False):
                        if plugin.provider == self.get_preferred_provider()[0] and len(res) == 0:
                            logger.info(
                                "No result from preferred provider: '%s'. Search continues on other providers "
                                "supporting the product type: '%s'", plugin.provider, product_type)
                            continue
                        # Take the results and stop searching
                        results.extend(res)
                        break
                    logger.info(
                        "Detected partial support for product type '%s' on provider '%s'. Search continues on "
                        "other providers supporting it.", product_type, plugin.provider)
                    # Take the current results and keep searching
                    results.extend(res)

                # In case the user specifies the maximum number of results he wants
                nb_res = 0
                if max_results > 0:
                    rest = rest - nb_res
                    start = self._provider_index_cache.get(plugin.provider, 0)
                    stop = start + 1
                    while rest > 0:
                        # Update the stop index with respect to the max_results requested
                        current_planning = (stop - start) * items_per_page
                        if current_planning < rest:
                            gap = rest - current_planning
                            if gap < 0:
                                stop += 1
                            else:
                                gap_pages, gap_rest = divmod(gap, items_per_page if items_per_page != 0 else 1)
                                if gap_rest != 0:
                                    gap_pages += 1
                                stop += gap_pages

                        if with_pagination_info:
                            res, nb_res = plugin.query(product_type, auth=auth, start=start, stop=stop,
                                                       max_count=True, cached=True, **kwargs)
                        else:
                            res = plugin.query(product_type, auth=auth, start=start, stop=stop, **kwargs)
                            nb_res = len(res)
                        if len(res) == 0:
                            self._exhausted_providers.add(plugin.provider)
                            break
                        results.extend(res)
                        rest -= nb_res
                        total_results += nb_res
                    if rest <= 0:
                        self._provider_index_cache[plugin.provider] = stop
                        break
                    else:
                        logger.info("The requested results number is not yet reached: %s over %s => search continues",
                                    len(results) + nb_res, max_results)
            except Exception:
                import traceback as tb
                logger.info("No result from provider '%s' due to an error during search. Raise verbosity of log "
                            "messages for details", plugin.provider)
                logger.info('Search continues on other providers supporting the product type')
                logger.debug('Error while searching on interface %s:\n %s.', plugin, tb.format_exc())
                logger.debug('Ignoring it')
        if with_pagination_info:
            return SearchResult(results), total_results
        return SearchResult(results)

    def crunch(self, results, **kwargs):
        """Apply the filters given through the keyword arguments to the results

        :param results: The results of a eodag search request
        :type results: :class:`~eodag.api.search_result.SearchResult`
        :return: The result of successively applying all the filters to the results
        :rtype: :class:`~eodag.api.search_result.SearchResult`
        """
        search_criteria = kwargs.pop('search_criteria', {})
        for cruncher_name, cruncher_args in kwargs.items():
            cruncher = self._plugins_manager.get_crunch_plugin(cruncher_name, **cruncher_args)
            results = results.crunch(cruncher, **search_criteria)
        return results

    @staticmethod
    def sort_by_extent(searches):
        """Combines multiple SearchResults and return a list of SearchResults sorted by extent.

        :param searches: List of eodag SearchResult
        :type searches: list
        :return: list of :class:`~eodag.api.search_result.SearchResult`
        """
        products_grouped_by_extent = {}

        for search in searches:
            for product in search:
                same_geom = products_grouped_by_extent.setdefault(
                    ''.join([str(round(p, 2)) for p in product.geometry.bounds]), []
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
            logger.info('Downloading %s products', len(search_result))
            with tqdm(search_result, unit='product', desc='Downloading products') as bar:
                for product in bar:
                    try:
                        paths.append(self.download(product, progress_callback=progress_callback))
                    except Exception:
                        import traceback as tb
                        logger.warning('A problem occurred during download of product: %s. Skipping it', product)
                        logger.debug('\n%s', tb.format_exc())
        else:
            logger.info('Empty search result, nothing to be downloaded !')
        return paths

    @staticmethod
    def serialize(search_result, filename='search_results.geojson'):
        """Registers results of a search into a geojson file.

        :param search_result: A collection of EO products resulting from a search
        :type search_result: :class:`~eodag.api.search_result.SearchResult`
        :param filename: The name of the file to generate
        :type filename: str or unicode
        :returns: The name of the created file
        :rtype: str or unicode
        """
        with open(filename, 'w') as fh:
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
        with open(filename, 'r') as fh:
            return SearchResult.from_geojson(geojson.load(fh))

    def download(self, product, progress_callback=None):
        """Download a single product.

        This is an alias to the method of the same name on :class:`~eodag.api.product.EOProduct`, but it performs some
        additional checks like verifying that a downloader and authenticator are registered for the product before
        trying to download it. If the metadata mapping for `downloadLink` is set to something that can be interpreted
        as a link on a local filesystem, the download is skipped (by now, only a link starting with `file://` is
        supported). Therefore, any user that knows how to extract product location from product metadata on a provider
        can override the `downloadLink` metadata mapping in the right way. For example, using the environment variable:
        EODAG__SOBLOO__SEARCH__METADATA_MAPPING__DOWNLOADLINK="file:///{id}" will lead to all `EOProduct`s originating
        from the provider `sobloo` to have their `downloadLink` metadata point to something like: "file:///12345-678",
        making this method immediately return the later string without trying to download the product.

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
        if product.location.startswith('file'):
            logger.info('Local product detected. Download skipped')
            return product.location
        if product.downloader is None:
            auth = product.downloader_auth
            if auth is None:
                auth = self._plugins_manager.get_auth_plugin(product.product_type, product.provider)
            product.register_downloader(
                self._plugins_manager.get_download_plugin(product),
                auth
            )
        return product.download(progress_callback=progress_callback)

    def get_cruncher(self, name, **options):
        plugin_conf = {
            'name': name,
        }
        plugin_conf.update({
            key.replace('-', '_'): val
            for key, val in options.items()
        })
        return self._plugins_manager.get_crunch_plugin(name, **plugin_conf)
