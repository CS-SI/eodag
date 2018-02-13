# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
import logging
import os
from operator import attrgetter

import click

from eodag.config import SimpleYamlProxyConfig
from eodag.plugins.instances_manager import PluginInstancesManager
from eodag.utils import maybe_generator
from eodag.utils.exceptions import PluginImplementationError


logger = logging.getLogger('eodag.core')


class SatImagesAPI(object):
    """An API for downloading a wide variety of geospatial products originating from different types of systems."""

    def __init__(self, user_conf_file_path=None, system_conf_file_path=None):
        self.system_config = SimpleYamlProxyConfig(os.path.join(
            os.path.dirname(os.path.abspath(os.path.realpath(__file__))),
            os.pardir, 'resources', 'system_conf_default.yml'
        ))
        if system_conf_file_path is not None:
            # TODO : the update method is very rudimentary by now => this doesn't work if we are trying to override a
            # TODO (continues) : param within an instance configuration
            self.system_config.update(SimpleYamlProxyConfig(system_conf_file_path))
        if user_conf_file_path:
            self.user_config = SimpleYamlProxyConfig(user_conf_file_path)

            # Override system default config with user values for some keys
            for instance_name, instance_config in self.user_config.items():
                if isinstance(instance_config, dict):
                    if instance_name in self.system_config:
                        if 'credentials' in instance_config:
                            if 'api' in self.system_config[instance_name]:
                                self.system_config[instance_name]['api'].update(instance_config)
                            else:
                                auth_conf = self.system_config[instance_name].setdefault('auth', {})
                                auth_conf.update(instance_config)
                        for key in ('outputs_prefix', 'extract'):
                            if key in self.user_config:
                                user_spec = self.user_config[key]
                                if 'api' in self.system_config[instance_name]:
                                    default_dl_option = self.system_config[instance_name]['api'].setdefault(
                                        key,
                                        '/data/satellites_images/' if key == 'outputs_prefix' else True
                                    )
                                else:
                                    if 'download' in self.system_config[instance_name]:
                                        default_dl_option = self.system_config[instance_name].get('download',
                                                                                                  {}).setdefault(
                                            # noqa
                                            key,
                                            '/data/satellites_images/' if key == 'outputs_prefix' else True
                                        )
                                    else:
                                        default_dl_option = user_spec  # allows skipping next if block
                                if default_dl_option != user_spec:
                                    if 'api' in self.system_config[instance_name]:
                                        self.system_config[instance_name]['api'][key] = user_spec
                                    else:
                                        self.system_config[instance_name]['download'][key] = user_spec
        self.pim = PluginInstancesManager(self.system_config)
        # Prepare the api to perform its main operations
        self.search_interfaces = self.__get_searchers()
        self.download_interfaces = self.__get_downloaders()
        self.crunchers = self.__get_crunchers()
        if len(self.search_interfaces) == 1:
            # If we only have one interface, reduce the list of downloaders and crunchers to have only one instance (the
            # one corresponding to the unique search interface)
            self.download_interfaces = self.download_interfaces[:1]
            self.crunchers = self.crunchers[:1]

    def search(self, product_type, **kwargs):
        """Look for products matching criteria in known systems.

        The interfaces are required to return a list as a result of their processing, we enforce this requirement here.
        """
        results = []
        # "recursive" search
        for iface in self.search_interfaces:
            logger.debug('Using interface for search: %s on instance *%s*', iface.name, iface.instance_name)
            auth = self.__get_authenticator(iface.instance_name)
            try:
                r = iface.query(product_type, auth=auth, **kwargs)
                if not isinstance(r, list):
                    raise PluginImplementationError(
                        'The query function of a Search plugin must return a list of results, got {} '
                        'instead'.format(type(r))
                    )
                results.extend(r)
            except RuntimeError as rte:
                if 'Unknown product type' in rte.args:
                    logger.debug('Product type %s not known by %s instance', product_type, iface.instance_name)
                else:
                    raise rte
        return results

    def crunch(self, results):
        """Consolidate results of a search (prepare for downloading)"""
        crunched_results = []
        for cruncher in self.crunchers:
            crunched_results.extend(
                cruncher.proceed(results)
            )
        return crunched_results

    def download_all(self, products):
        """Download all products of a search"""
        if products:
            with click.progressbar(products, fill_char='O', length=len(products), width=0,
                                   label='Downloading products') as bar:
                for product in bar:
                    for path in self.__download(product):
                        yield path
        else:
            click.echo('Empty product list, nothing to be downloaded !')

    def __download(self, product):
        """Download a single product"""
        # try to download the product from all the download interfaces known (functionality introduced by the necessity
        # to take into account that a product type may be distributed to many instances)
        for iface in self.download_interfaces:
            logger.debug('Using interface for download : %s on instance *%s*', iface.name, iface.instance_name)
            try:
                auth = self.__get_authenticator(iface.instance_name)
                if auth:
                    auth = auth.authenticate()
                for local_filename in maybe_generator(iface.download(product, auth=auth)):
                    if local_filename is None:
                        logger.debug('The download method of a Download plugin should return the absolute path to the '
                                     'downloaded resource or a generator of absolute paths to the downloaded and '
                                     'extracted resource')
                    yield local_filename
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
        if 'auth' in self.system_config[instance_name]:
            logger.debug('Authentication initialisation for instance %s', instance_name)
            return self.pim.instantiate_plugin_by_config(
                topic_name='auth',
                topic_config=self.system_config[instance_name]['auth']
            )

    def __get_searchers(self):
        """Look for a search interface to use, based on the configuration of the api"""
        logger.debug('Looking for the appropriate Search instance to use')
        search_plugin_instances = self.pim.instantiate_configured_plugins(topics=('search', 'api'))
        # The searcher used will be the one with higher priority
        search_plugin_instances.sort(key=attrgetter('priority'), reverse=True)
        selected_instance = search_plugin_instances[0]
        for name, prod in selected_instance.config.get('products', {}).items():
            # If a known product is a subset of its type, we will perform search on all configured instances
            if prod.get('partial'):
                logger.debug("Detected partial product type '%s' on instance '%s' => recursive search and download "
                             "activated", name, selected_instance.instance_name)
                return search_plugin_instances
        return [selected_instance]

    def __get_downloaders(self):
        logger.debug('Looking for the appropriate Download instance to use')
        dl_plugin_instances = self.pim.instantiate_configured_plugins(topics=('download', 'api'))
        dl_plugin_instances.sort(key=attrgetter('priority'), reverse=True)
        return dl_plugin_instances

    def __get_crunchers(self):
        """Get a list of plugins to use for preparing search results for download"""
        logger.debug('Getting the list of Crunch plugin instances to use')
        crunchers = self.pim.instantiate_configured_plugins(topics=('crunch',))
        crunchers.sort(key=attrgetter('priority'), reverse=True)
        return crunchers
