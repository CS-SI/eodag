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
from operator import attrgetter

import geojson
from pkg_resources import resource_filename
from tqdm import tqdm

from eodag.api.search_result import SearchResult
from eodag.config import (
    SimpleYamlProxyConfig, load_default_config, override_config_from_file,
    override_config_from_env,
)
from eodag.plugins.instances_manager import PluginInstancesManager
from eodag.utils import ProgressCallback
from eodag.utils.exceptions import PluginImplementationError, UnsupportedProvider


logger = logging.getLogger('eodag.core')


class EODataAccessGateway(object):
    """An API for downloading a wide variety of geospatial products originating from different types of systems.

    :param user_conf_file_path: Path to the user configuration file
    :type user_conf_file_path: str or unicode
    :param providers_file_path: Path to the internal file where systems containing eo products are configured
    :type providers_file_path: str or unicode
    """

    def __init__(self, user_conf_file_path=None):
        self.product_types_config = SimpleYamlProxyConfig(resource_filename('eodag', 'resources/product_types.yml'))
        self.providers_config = load_default_config()

        # First level override: From a user configuration file
        override_config_from_file(self.providers_config, user_conf_file_path)

        # Second level override: From environment variables
        override_config_from_env(self.providers_config)

        self._plugins_manager = PluginInstancesManager(self.providers_config)

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
            # Update the interfaces cache to take into account the fact that the preferred provider has changed
            if 'search' in self._plugins_cache:
                for search_interfaces in self._plugins_cache['search'].values():
                    for iface in search_interfaces:
                        if iface.instance_name == provider:
                            iface.priority = new_priority

    def get_preferred_provider(self):
        """Get the provider currently set as the preferred one for searching products, along with its priority.

        :return: The provider with the maximum priority and its priority
        :rtype: tuple(str, int)
        """
        preferred, priority = max(((provider, conf.priority) for provider, conf in self.providers_config.items()),
                                  key=lambda item: item[1])
        return preferred, priority

    def list_product_types(self, provider=None):
        """Lists supported product types.

        :param provider: The name of a provider that must support the product types we are about to list
        :type provider: str or unicode
        :returns: The list of the product types that can be accessed using eodag.
        :rtype: list(dict)
        :raises: :class:`~eodag.utils.exceptions.UnsupportedProvider`
        """
        if provider is not None:
            if provider in self.providers_config:
                provider_supported_products = self.providers_config[provider]['products']
                return [dict(
                    ID=code,
                    **self.product_types_config[code]
                ) for code in provider_supported_products]
            raise UnsupportedProvider("The requested provider is not (yet) supported")
        return [dict(
            ID=code,
            **value
        ) for code, value in self.product_types_config.items()]

    def available_providers(self):
        """Gives the list of the available providers"""
        return tuple(self.providers_config.keys())

    def search(self, product_type, **kwargs):
        """Look for products matching criteria in known systems.

        :param product_type: The product type to search
        :type product_type: str or unicode
        :param dict kwargs: some other criteria that will be used to do the search
        :returns: A collection of EO products matching the criteria
        :rtype: :class:`~eodag.api.search_result.SearchResult`

        .. note::
            The search interfaces, which are implemented as plugins, are required to return a list as a result of their
            processing. This requirement is enforced here.
        """
        results = SearchResult([])
        for plugin in self._plugins_manager.get_search_plugins(product_type):
            logger.info("Searching product type '%s' on provider: %s", product_type, plugin.provider)
            logger.debug('Using plugin class for search: %s', plugin.__class__.__name__)
            auth = self._plugins_manager.get_auth_plugin(product_type, plugin.provider)
            try:
                res = plugin.query(product_type, auth=auth, **kwargs)
                logger.info("Found %s result(s) on provider '%s'", len(res), plugin.provider)
                if not isinstance(res, list):
                    raise PluginImplementationError(
                        'The query function of a Search plugin must return a list of results, got {} '
                        'instead'.format(type(res)))
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
                        results.append(eo_product)
                # Decide if we should go on with the search using the other search plugins. This happens in
                # 2 cases:
                # 1. The currently used plugin is the preferred one (the first), and it returned no result
                # 2. The currently used plugin supports the product_type partially
                if not plugin.config.products[product_type].get('partial_support', False):
                    if plugin.provider == self.get_preferred_provider()[0] and len(res) == 0:
                        logger.info(
                            "No result from preferred provider: '%s'. Search continues on other providers "
                            "supporting the product type: '%s'", plugin.provider, product_type)
                        continue
                    break
                logger.info(
                    "Detected partial support for product type '%s' on preferred provider '%s'. Search continues on "
                    "other providers supporting it.", product_type, plugin.provider)
            except Exception:
                import traceback as tb
                logger.info("No result from provider '%s' due to an error during search. Raise verbosity of log "
                            "messages for details", plugin.provider)
                logger.info('Search continues on other providers supporting the product type')
                logger.debug('Error while searching on interface %s:\n %s.', plugin, tb.format_exc())
                logger.debug('Ignoring it')
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
                    paths.append(self.download(product, progress_callback=progress_callback))
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
        trying to download it. If EODAG is installed on a machine that can see the product as local, no download is
        tried and the location of the product is immediately returned instead.

        .. warning::

            Be careful to adequately configure your eodag install so that it can see local products. This means that
            if you install it on a machine that can see products from specific providers as local, you must override
            the '<provider>.search.product_location_scheme' config parameter through either the environment variable
            'EODAG__<PROVIDER>__SEARCH__PRODUCT_LOCATION_SCHEME' (notice the double underscore, they are equivalent to
            the dots in '<provider>.search.product_location_scheme') or through your user configuration file. Set this
            parameter to 'file' (other network location schemes emulating the local 'file' scheme may be supported in
            the future).

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
        return self._plugins_manager.instantiate_plugin_by_config('crunch', plugin_conf)
