# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
from operator import attrgetter

import click
import geojson

from eodag.api.search_result import SearchResult
from eodag.config import SimpleYamlProxyConfig
from eodag.plugins.instances_manager import PluginInstancesManager
from eodag.utils.exceptions import PluginImplementationError


logger = logging.getLogger(b'eodag.core')


class SatImagesAPI(object):
    """An API for downloading a wide variety of geospatial products originating from different types of systems.

    :param user_conf_file_path: Path to the user configuration file
    :type user_conf_file_path: str or unicode
    :param system_conf_file_path: Path to the internal file where systems containing eo products are configured
    :type system_conf_file_path: str or unicode
    """

    def __init__(self, user_conf_file_path=None, providers_file_path=None):
        self.providers_config = SimpleYamlProxyConfig(os.path.join(
            os.path.dirname(os.path.abspath(os.path.realpath(__file__))),
            os.pardir, 'resources', 'providers.yml'
        ))
        self.product_types_config = SimpleYamlProxyConfig(os.path.join(
            os.path.dirname(os.path.abspath(os.path.realpath(__file__))),
            os.pardir, 'resources', 'product_types.yml'
        ))
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
                                        '/data/satellites_images/' if key == 'outputs_prefix' else True
                                    )
                                else:
                                    if 'download' in self.providers_config[instance_name]:
                                        default_dl_option = self.providers_config[instance_name].get('download',
                                                                                                     {}).setdefault(
                                            # noqa
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
        self.pim = PluginInstancesManager(self.providers_config)
        self.__interfaces_cache = {}

    def list_product_types(self):
        """Lists supported product types.

        :returns: The list of the product types that can be accessed using eodag.
        :rtype: list(dict)
        """
        return [dict(
            ID=_id,
            **value
        ) for _id, value in self.product_types_config.items()]

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
        search_interfaces = self.__get_searchers(product_type)
        results = []
        for idx, iface in enumerate(search_interfaces):
            logger.debug('Using interface for search: %s on instance *%s*', iface.name, iface.instance_name)
            auth = self.__get_authenticator(iface.instance_name)
            try:
                r = iface.query(product_type, auth=auth, **kwargs)
                if not isinstance(r, list):
                    raise PluginImplementationError(
                        'The query function of a Search plugin must return a list of results, got {} '
                        'instead'.format(type(r))
                    )
                # Only keep those eo_products that intersects the search extent (if there was no search extent,
                # search_intersection contains the geometry of the eo_product)
                # WARNING: this means an eo_product that has an invalid geometry can still be returned as a search
                # result if there was no search extent (an intersection will not be tried)
                results.extend(filter(lambda eo_product: eo_product.search_intersection is not None, r))
                # Decide if we should go on with the search (if the iface stores the product_type partially)
                if idx == 0:
                    if not iface.config.get('products', {}).get(product_type, {}).get('partial', False):
                        if len(search_interfaces) > 1 and len(r) == 0:
                            logger.debug(
                                "No result from preferred interface: '%r'. Search continues on other instances "
                                "supporting product type: '%r'", iface.instance_name, product_type)
                            continue
                        break
                    logger.debug("Detected partial product type '%s' on priviledged instance '%s'. Search continues on "
                                 "other instances supporting it.", product_type, iface.instance_name)
            except RuntimeError as rte:
                if 'Unknown product type' in rte.args:
                    logger.debug('Product type %s not known by %s instance', product_type, iface.instance_name)
                else:
                    raise rte
            except Exception as any_other_exception:
                logger.debug('Error while searching on interface %s: %s.', iface, any_other_exception)
                logger.debug('Ignoring it')
        return SearchResult(results)

    def download_all(self, search_result):
        """Download all products resulting from a search.

        :param search_result: A collection of EO products resulting from a search
        :type search_result: :class:`~eodag.api.search_result.SearchResult`
        :returns: A Generator that yields the absolute path to the downloaded resource
        :rtype: str or unicode
        """
        if search_result:
            with click.progressbar(search_result, fill_char='O', length=len(search_result), width=0,
                                   label='Downloading products') as bar:
                for product in bar:
                    for path in self.__download(product):
                        yield path
        else:
            click.echo('Empty search result, nothing to be downloaded !')

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

    def __download(self, product):
        """Download a single product.

        :param product: The EO product to download
        :type product: :class:`~eodag.api.product.EOProduct`
        :returns: The absolute path to the downloaded product in the local filesystem
        :rtype: str or unicode
        :raises: :class:`~eodag.utils.exceptions.PluginImplementationError`
        :raises: :class:`RuntimeError`
        """
        # try to download the product from all the download interfaces known (functionality introduced by the necessity
        # to take into account that a product type may be distributed to many instances)
        download_interfaces = self.__get_downloaders(product)
        for iface in download_interfaces:
            logger.debug('Using interface for download : %s on instance *%s*', iface.name, iface.instance_name)
            try:
                auth = None
                if not iface.config.get('on_site', False):
                    auth = self.__get_authenticator(iface.instance_name)
                else:
                    logger.debug('On site usage detected. Authentication for download skipped !')
                if auth:
                    auth = auth.authenticate()
                for local_filepath in product.download(iface, auth):
                    if local_filepath is None:
                        logger.debug('The download method of a Download plugin should return the absolute path to the '
                                     'downloaded resource or a generator of absolute paths to the downloaded and '
                                     'extracted resource')
                    yield local_filepath
            except TypeError as e:
                # Enforcing the requirement for download plugins to implement a download method with auth kwarg
                if any("got an unexpected keyword argument 'auth'" in arg for arg in e.args):
                    raise PluginImplementationError(
                        'The download method of a Download plugin must support auth keyword argument'
                    )
                raise e
            except RuntimeError as rte:
                # Skip download errors, allowing other downloads to take place anyway
                if 'is incompatible with download plugin' in rte.args[0]:
                    logger.warning('Download plugin incompatibility found. Skipping download...')
                else:
                    raise rte

    def __get_authenticator(self, instance_name):
        if 'auth' in self.providers_config[instance_name]:
            logger.debug('Authentication initialisation for instance %s', instance_name)
            previous = (self.__interfaces_cache.setdefault('auth', {})
                                               .setdefault(instance_name, []))
            if not previous:
                previous.append(self.pim.instantiate_plugin_by_config(
                    topic_name='auth',
                    topic_config=self.providers_config[instance_name]['auth'],
                    iname=instance_name,
                ))
            logger.debug("Initialized %r Authentication plugin for instance '%s'", previous[0], instance_name)
            return previous[0]

    def __get_searchers(self, product_type):
        """Look for a search interface to use, based on the configuration of the api"""
        logger.debug('Looking for the appropriate Search instance(s) to use for product type: %s', product_type)
        previous = (self.__interfaces_cache.setdefault('search', {})
                                           .setdefault(product_type, []))
        if not previous:
            search_plugin_instances = self.pim.instantiate_configured_plugins(
                topics=('search', 'api'),
                pt_matching=product_type
            )
            # The searcher used will be the one with higher priority
            search_plugin_instances.sort(key=attrgetter('priority'), reverse=True)

            # Store the newly instantiated interfaces in the interface cache
            previous.extend(search_plugin_instances)
        logger.debug("Found %s Search instance(s) for product type '%s' (ordered by highest priority): %r",
                     len(previous), product_type, previous)
        return previous

    def __get_downloaders(self, product):
        """Look for a download interface to use, based on the configuration of the api and the product to download"""
        logger.debug('Looking for the appropriate Download instance to use for product: %r', product)
        previous = (self.__interfaces_cache.setdefault('download', {})
                                           .setdefault(product.producer, []))
        if not previous:
            dl_plugin_instances = self.pim.instantiate_configured_plugins(
                topics=('download', 'api'),
                only=[product.producer]
            )
            dl_plugin_instances.sort(key=attrgetter('priority'), reverse=True)

            # Store the newly instantiated interfaces in the interface cache
            previous.extend(dl_plugin_instances)
        logger.debug('Found %s Download instance(s) for product %r (ordered by highest priority): %s',
                     len(previous), product, previous)
        return previous

    def get_cruncher(self, name, **options):
        plugin_conf = {
            'plugin': name,
        }
        plugin_conf.update({
            key.replace('-', '_'): val
            for key, val in options.items()
        })
        return self.pim.instantiate_plugin_by_config('crunch', plugin_conf)
