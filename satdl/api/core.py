# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
import logging
import os
from operator import attrgetter

import click

from satdl.config import SimpleYamlProxyConfig
from satdl.plugins.instances_manager import PluginInstancesManager
from satdl.utils.exceptions import PluginImplementationError


logger = logging.getLogger('satdl.core')


class SatImagesAPI(object):
    """An API for downloading a wide variety of geospatial products originating from different types of systems."""

    def __init__(self, user_conf_file_path=None, system_conf_file_path=None):
        self.system_config = SimpleYamlProxyConfig(
            os.path.join(os.path.abspath(os.path.realpath(__file__)), '..', '..', '..', 'system_conf_default.yml')
        )
        if system_conf_file_path is not None:
            # TODO : the update method is very rudimentary by now => this doesn't work if we are trying to override a
            # TODO (continues) : param within an instance configuration
            self.system_config.update(SimpleYamlProxyConfig(system_conf_file_path))
        self.user_config = SimpleYamlProxyConfig(user_conf_file_path)
        # By now only auth system config can be overriden by user credentials
        for instance_name in self.user_config:
            if instance_name in self.system_config:
                if 'credentials' in self.user_config[instance_name]:
                    self.system_config[instance_name]['auth'].update(self.user_config[instance_name])
                if 'outputs_prefix' in self.user_config:
                    user_spec = self.user_config['outputs_prefix']
                    default_outputs_prefix = self.system_config[instance_name]['download'].setdefault(
                        'outputs_prefix',
                        '/data/satellites_images/'
                    )
                    if default_outputs_prefix != user_spec:
                        self.system_config[instance_name]['download']['outputs_prefix'] = user_spec
        self.pim = PluginInstancesManager(self.system_config)

    def search(self, product_type, **kwargs):
        """Look for products matching criteria in known systems.

        The interfaces are required to return a list as a result of their processing, we enforce this requirement here.
        """
        interface = self.__get_searcher()
        logger.debug('Using interface for search: %s on instance *%s*', interface.name, interface.instance_name)
        query_params = self.__get_interface_query_params(interface, kwargs)
        results = interface.query(product_type, **query_params)
        if not isinstance(results, list):
            raise PluginImplementationError(
                'The query function of a Search plugin must return a list of results, got {} '
                'instead'.format(type(results))
            )
        return results

    def filter(self, results):
        """Consolidate results of a search (prep for downloading)"""
        return results
        # interface = self.__get_consolidator(results)
        # return interface.process()

    def download_all(self, products):
        """Download all products of a search"""
        if products:
            with click.progressbar(
                    products,
                    fill_char='O',
                    item_show_func=lambda prod: click.echo(
                        'Downloaded {}'.format(prod.local_filename)
                    ) if prod else click.echo('Missing local path to the downloaded product'),
                    length=len(products),
                    width=0,  # Full terminal width
                    label='Downloading products'
            ) as bar:
                for product in bar:
                    yield self.__download(product)
        else:
            click.echo('Empty product list, nothing to be downloaded !')

    def __download(self, product):
        """Download a single product"""
        interface = self.__get_downloader()
        logger.debug('Using interface for download : %s on instance *%s*', interface.name, interface.instance_name)
        authentication = None
        if interface.authenticate:
            logger.debug('Authentication required for interface : %s on instance *%s*', interface.name,
                         interface.instance_name)
            authenticator = self.pim.instantiate_plugin_by_config(
                topic_name='auth',
                topic_config=self.system_config[interface.instance_name]['auth']
            )
            authentication = authenticator.authenticate()
        try:
            local_filename = interface.download(product, auth=authentication)
            if local_filename is None:
                logger.debug(
                    'The download method of a Download plugin should return the absolute path to the '
                    'downloaded resource'
                )
            else:
                return local_filename
        except TypeError as e:
            # Enforcing the requirement for download plugins to implement a download method with auth kwarg
            if any("got an unexpected keyword argument 'auth'" in arg for arg in e.args):
                raise PluginImplementationError(
                    'The download method of a Download plugin must support auth keyword argument'
                )
            raise e

    def __get_searcher(self):
        """Look for a search interface to use, based on the configuration of the api"""
        logger.debug('Looking for the appropriate Search instance to use')
        search_plugin_instances = self.pim.instantiate_configured_plugins(topic='search')
        # The searcher used will be the one with higher priority
        search_plugin_instances.sort(key=attrgetter('priority'), reverse=True)
        return search_plugin_instances[0]

    def __get_downloader(self):
        logger.debug('Looking for the appropriate Download instance to use')
        dl_plugin_instances = self.pim.instantiate_configured_plugins(topic='download')
        dl_plugin_instances.sort(key=attrgetter('priority'), reverse=True)
        return dl_plugin_instances[0]

    def __get_consolidator(self, search_result):
        from .plugins.filter.base import Filter
        for consolidator in Filter.plugins:
            if True:
                return consolidator()

    def __get_interface_query_params(self, interface, generic_query_params):
        """If a mapping should be done for the interface, do it here"""
        return generic_query_params
