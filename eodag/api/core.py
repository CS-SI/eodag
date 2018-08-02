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
from eodag.config import SimpleYamlProxyConfig
from eodag.plugins.instances_manager import PluginInstancesManager
from eodag.utils import ProgressCallback
from eodag.utils.exceptions import PluginImplementationError, UnsupportedProvider


logger = logging.getLogger('eodag.core')


class SatImagesAPI(object):
    """An API for downloading a wide variety of geospatial products originating from different types of systems.

    :param user_conf_file_path: Path to the user configuration file
    :type user_conf_file_path: str or unicode
    :param providers_file_path: Path to the internal file where systems containing eo products are configured
    :type providers_file_path: str or unicode
    """

    def __init__(self, user_conf_file_path=None, providers_file_path=None):
        self.providers_config = SimpleYamlProxyConfig(resource_filename('eodag', 'resources/providers.yml'))
        self.product_types_config = SimpleYamlProxyConfig(resource_filename('eodag', 'resources/product_types.yml'))
        if providers_file_path is not None:
            # TODO : the update method is very rudimentary by now => this doesn't work if we are trying to override a
            # TODO (continues) : param within an instance configuration
            self.providers_config.update(SimpleYamlProxyConfig(providers_file_path))
        if user_conf_file_path:
            self.user_config = SimpleYamlProxyConfig(user_conf_file_path)

            # Override system default config with user values for some keys
            for instance_name, instance_config in self.user_config.items():
                if isinstance(instance_config, dict):
                    if instance_name in self.providers_config:
                        if 'credentials' in instance_config:
                            if 'api' in self.providers_config[instance_name]:
                                self.providers_config[instance_name]['api'].update(instance_config)
                            else:
                                auth_conf = self.providers_config[instance_name].setdefault('auth', {})
                                auth_conf.update(instance_config)
                        for key in ('outputs_prefix', 'extract'):
                            if key in self.user_config:
                                user_spec = self.user_config[key]
                                if 'api' in self.providers_config[instance_name]:
                                    default_dl_option = self.providers_config[instance_name]['api'].setdefault(
                                        key,
                                        '/data/satellites_images/' if key == 'outputs_prefix' else True)
                                else:
                                    if 'download' in self.providers_config[instance_name]:
                                        default_dl_option = self.providers_config[instance_name].get(
                                            'download', {}
                                        ).setdefault(
                                            key,
                                            '/data/satellites_images/' if key == 'outputs_prefix' else True
                                        )
                                    else:
                                        default_dl_option = user_spec  # allows skipping next if block
                                if default_dl_option != user_spec:
                                    if 'api' in self.providers_config[instance_name]:
                                        self.providers_config[instance_name]['api'][key] = user_spec
                                    else:
                                        self.providers_config[instance_name]['download'][key] = user_spec
        self._plugins_manager = PluginInstancesManager(self.providers_config)
        self._plugins_cache = {}

    def set_preferred_provider(self, provider):
        """Set max priority for the given provider.

        >>> import eodag.utils.exceptions
        >>> dag = SatImagesAPI()
        >>> dag.get_preferred_provider()    # This also tests get_preferred_provider method by the way
        ('airbus-ds', 1)
        >>> # For the following lines, see http://python3porting.com/problems.html#handling-expected-exceptions
        >>> try:
        ...     dag.set_preferred_provider(u'unknown')
        ...     raise AssertionError(u'UnsupportedProvider exception was not raised as expected')
        ... except eodag.utils.exceptions.UnsupportedProvider:
        ...     pass
        >>> dag.set_preferred_provider(u'USGS')
        >>> dag.get_preferred_provider()
        ('USGS', 2)
        >>> dag.set_preferred_provider(u'theia')
        >>> dag.get_preferred_provider()
        ('theia', 3)
        >>> dag.set_preferred_provider(u'USGS')
        >>> dag.get_preferred_provider()
        ('USGS', 4)

        :param provider: The name of the provider that should be considered as the preferred provider to be used for
                         this instance
        :type provider: str or unicode
        """
        if provider not in self.available_providers():
            raise UnsupportedProvider('This provider is not recognised by eodag')
        preferred_provider, max_priority = self.get_preferred_provider()
        if preferred_provider != provider:
            new_priority = max_priority + 1
            self.providers_config[provider]['priority'] = new_priority
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
        # Note: if a provider config doesn't have 'priority' key, it is considered to have minimum priority (0)
        preferred, config = max(((provider, conf) for provider, conf in self.providers_config.items()),
                                key=lambda item: item[1].get('priority', 0))
        return preferred, config.get('priority', 0)

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
        return [provider for provider in self.providers_config]

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
        search_plugins = self._build_search_plugins(product_type)
        results = SearchResult([])
        for idx, plugin in enumerate(search_plugins):
            logger.debug('Using plugin for search: %s on provider: %s', plugin.name, plugin.instance_name)
            auth = self._build_auth_plugin(plugin.instance_name)
            try:
                r = plugin.query(product_type, auth=auth, **kwargs)
                if not isinstance(r, list):
                    raise PluginImplementationError(
                        'The query function of a Search plugin must return a list of results, got {} '
                        'instead'.format(type(r)))
                # Filter and attach to each eoproduct in the result the plugin capable of downloading it (this
                # is done to enable the eo_product to download itself doing: eo_product.download())
                # The filtering is done by keeping only those eo_products that intersects the search extent (if there
                # was no search extent, search_intersection contains the geometry of the eo_product)
                # WARNING: this means an eo_product that has an invalid geometry can still be returned as a search
                # result if there was no search extent (because we will not try to do an intersection)
                for eo_product in r:
                    if eo_product.search_intersection is not None:
                        if 'download' in self.providers_config[eo_product.provider]:
                            topic = 'download'
                        else:
                            topic = 'api'
                        eo_product.register_downloader(
                            self._build_provider_plugin(eo_product.provider, topic),
                            auth
                        )
                        results.append(eo_product)
                # Decide if we should go on with the search using the other search plugins. This happens in 2 cases:
                # 1. The currently used plugin is the preferred one (the first), and it returned no result
                # 2. The currently used plugin supports the product_type partially
                if not plugin.config.get('products', {}).get(product_type, {}).get('partial', False):
                    if idx == 0 and len(search_plugins) > 1 and len(r) == 0:
                        logger.debug(
                            "No result from preferred provider: '%r'. Search continues on other providers "
                            "supporting the product type: '%r'", plugin.instance_name, product_type)
                        continue
                    break
                logger.debug("Detected partial product type '%s' on priviledged instance '%s'. Search continues on "
                             "other instances supporting it.", product_type, plugin.instance_name)
            except RuntimeError as rte:
                if 'Unknown product type' in rte.args:
                    logger.debug('Product type %s not known by %s instance', product_type, plugin.instance_name)
                else:
                    raise rte
            except Exception:
                import traceback as tb
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
            with tqdm(search_result, unit='product', desc='Downloading products') as bar:
                for product in bar:
                    paths.append(self.download(product, progress_callback=progress_callback))
        else:
            print('Empty search result, nothing to be downloaded !')
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

        .. warning::
            As a side effect, this method changes the `location` attribute of an :class:`~eodag.api.product.EOProduct`.
            So be aware that you may not be able to download the product again if you didn't store its remote location
            somewhere first before downloading it, unless the download failed or the download plugin didn't returned
            the local path of the downloaded resource

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
        if progress_callback is None:
            progress_callback = ProgressCallback()

        download_plugin = self._build_download_plugin(product)
        logger.debug('Using download plugin: %s for provider: %s', download_plugin.name, download_plugin.instance_name)
        try:
            auth = None
            # We need to authenticate only if we are not on the platform where the product lives
            if not download_plugin.config.get('on_site', False):
                auth = self._build_auth_plugin(download_plugin.instance_name)
            else:
                logger.debug('On site usage detected. Authentication for download skipped !')
            if auth:
                auth = auth.authenticate()
            product_location = download_plugin.download(product, auth=auth, progress_callback=progress_callback)
            if product_location is None:
                logger.warning('The download method of a Download plugin should return the absolute path to the '
                               'downloaded resource')
            else:
                logger.debug('Product location updated from %s to %s', product.location, product_location)
                # Update the product location if and only if a path was returned by the download plugin
                product.location = 'file://{}'.format(product_location)
            return product_location
        except TypeError as e:
            # Enforcing the requirement for download plugins to implement a download method with auth kwarg
            if any("got an unexpected keyword argument 'auth'" in arg for arg in e):
                raise PluginImplementationError('The download method of a Download plugin must support auth keyword '
                                                'argument')
            raise e
        except RuntimeError as rte:
            # Skip download errors, allowing other downloads to take place anyway
            if 'is incompatible with download plugin' in rte:
                logger.warning('Download plugin incompatibility found. Skipping download...')
            else:
                raise rte

    def _build_auth_plugin(self, provider_name):
        if 'auth' in self.providers_config[provider_name]:
            logger.debug('Authentication initialisation for provider: %s', provider_name)
            plugin = self._build_provider_plugin(provider_name, 'auth')
            logger.debug("Initialized %r Authentication plugin for provider: '%s'", plugin, provider_name)
            return plugin

    def _build_search_plugins(self, product_type):
        """Look for search interfaces to use, based on the configuration of the api"""
        logger.debug('Looking for the appropriate Search instance(s) to use for product type: %s', product_type)
        previous = self._plugins_cache.setdefault('search', {}).setdefault(product_type, [])
        if not previous:
            search_plugins = self._plugins_manager.instantiate_configured_plugins(
                topics=('search', 'api'),
                product_type_id=product_type
            )
            # Store the newly instantiated plugins in the cache
            previous.extend(search_plugins)
        # The searcher used will be the one with highest priority
        previous.sort(key=attrgetter('priority'), reverse=True)
        logger.debug("Found %s Search instance(s) for product type '%s' (ordered by highest priority): %r",
                     len(previous), product_type, previous)
        return previous

    def _build_download_plugin(self, product):
        """Look for a download plugin to use, based on the configuration of the api and the product to download"""
        logger.debug('Looking for the appropriate Download plugin to use for product: %r', product)
        if 'download' in self.providers_config[product.provider]:
            topic = 'download'
        else:
            topic = 'api'
        plugin = self._build_provider_plugin(product.provider, topic)
        logger.debug('Found Download plugin for product %r: %s', product, plugin)
        return plugin

    def _build_provider_plugin(self, provider, topic):
        """Build the plugin of type topic for provider

        :param provider: The provider for which to build topic plugin
        :type provider: str or unicode
        :param topic: The type of plugin to build for provider (one of: 'auth', 'search', 'download'). Note that this
                      method is not intended to be used for 'crunch' plugins, because these are generally not tied to a
                      specific provider
        :type topic: str or unicode
        :returns: The plugin instance corresponding to the topic for the specified provider
        :rtype: a :class:`~eodag.plugins.base.PluginTopic` subclass's instance
        """
        previous = self._plugins_cache.setdefault(topic, {}).setdefault(provider, None)
        if previous is None:
            previous = self._plugins_manager.instantiate_plugin_by_config(
                topic_name=topic,
                topic_config=self.providers_config[provider][topic],
                iname=provider,
            )
        return previous

    def get_cruncher(self, name, **options):
        plugin_conf = {
            'plugin': name,
        }
        plugin_conf.update({
            key.replace('-', '_'): val
            for key, val in options.items()
        })
        return self._plugins_manager.instantiate_plugin_by_config('crunch', plugin_conf)
