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

import pkg_resources

from eodag.plugins.apis.base import Api
from eodag.plugins.authentication.base import Authentication
from eodag.plugins.base import EODAGPluginMount
from eodag.plugins.crunch.base import Crunch
from eodag.plugins.download.base import Download
from eodag.plugins.search.base import Search
from eodag.utils.exceptions import UnsupportedProductType


logger = logging.getLogger('eodag.plugins.manager')


class PluginManager(object):
    """A manager for the plugins.

    The role of instances of this class (normally only one instance exists, created during instantiation of
    :class:`~eodag.api.core.EODataAccessGateway`. But nothing is done to enforce this) is to instantiate the plugins
    according to the providers configuration, keep track of them in memory, and manage a cache of plugins already
    constructed. The providers configuration contains information such as the name of the provider, the internet
    endpoint for accessing it, and the plugins to use to perform defined actions (search, download, authenticate,
    crunch).

    :param providers_config: The configuration with all information about the providers supported by the `eodag`
    :type providers_config: dict
    """
    supported_topics = {'search', 'download', 'crunch', 'auth', 'api'}

    def __init__(self, providers_config):
        self.providers_config = providers_config
        # Load all the plugins. This will make all plugin classes of a particular type to be available in the base
        # plugin class's 'plugins' attribute. For example, by importing module 'eodag.plugins.search.resto', the plugin
        # 'RestoSearch' will be available in self.supported_topics['search'].plugins
        for topic in self.supported_topics:
            # This way of discovering plugins means that anyone can create eodag plugins as a separate python package
            # (though it must require eodag), and have it discovered as long as they declare an entry point of the type
            # 'eodag.plugins.search' for example in its setup script. See the setup script of eodag for an example of
            # how to do this.
            for entry_point in pkg_resources.iter_entry_points('eodag.plugins.{}'.format(topic)):
                try:
                    entry_point.load()
                except ImportError:
                    import traceback as tb
                    logger.warning('Unable to load plugin: %s.', entry_point.name)
                    logger.warning('Reason:\n%s', tb.format_exc())
                    logger.warning('Check that the plugin module (%s) is importable', entry_point.module_name)
        self.product_type_to_provider_config_map = {}
        for provider_config in providers_config.values():
            for product_type in provider_config.products:
                product_type_providers = self.product_type_to_provider_config_map.setdefault(product_type, [])
                product_type_providers.append(provider_config)
                product_type_providers.sort(key=attrgetter('priority'), reverse=True)
        self._built_plugins_cache = {}

    def get_search_plugins(self, product_type):
        """Build and return all the search plugins supporting the given product type, ordered by highest priority.

        :param product_type: The product type that the constructed plugins must support
        :type product_type: str or unicode
        :returns: All the plugins supporting the product type, one by one (a generator object)
        :rtype: types.GeneratorType(:class:`~eodag.plugins.search.Search`)
        """
        try:
            for config in self.product_type_to_provider_config_map[product_type]:
                try:
                    config.search.products = config.products
                    config.search.priority = config.priority
                    plugin = self._build_plugin(config.name, config.search, Search)
                    yield plugin
                except AttributeError:
                    config.api.products = config.products
                    config.api.priority = config.priority
                    plugin = self._build_plugin(config.name, config.api, Api)
                    yield plugin
        except KeyError:
            raise UnsupportedProductType(product_type)

    def get_download_plugin(self, product):
        """Build and return the download plugin capable of downloading the given product.


        :param product: The product to get a download plugin for
        :type product: :class:`~eodag.api.product._product.EOProduct`
        :returns: The download plugin capable of downloading the product
        :rtype: :class:`~eodag.plugins.download.Download`
        """
        for plugin_conf in self.product_type_to_provider_config_map[product.product_type]:
            if plugin_conf.name == product.provider:
                try:
                    plugin_conf.download.priority = plugin_conf.priority
                    plugin = self._build_plugin(product.provider, plugin_conf.download, Download)
                    return plugin
                except AttributeError:
                    plugin_conf.api.priority = plugin_conf.priority
                    plugin = self._build_plugin(product.provider, plugin_conf.api, Api)
                    return plugin

    def get_auth_plugin(self, product_type, provider):
        """Build and return the authentication plugin for the given product_type and provider

        :param product_type: The product type for which to get the authentication plugin
        :type product_type: str or unicode
        :param provider: The provider for which to get the authentication plugin
        :type provider: str or unicode
        :returns: The Authentication plugin for the provider
        :rtype: :class:`~eodag.plugins.authentication.Authentication`
        """
        for plugin_conf in self.product_type_to_provider_config_map[product_type]:
            if plugin_conf.name == provider:
                try:
                    plugin_conf.auth.priority = plugin_conf.priority
                    plugin = self._build_plugin(provider, plugin_conf.auth, Authentication)
                    return plugin
                except AttributeError:
                    # We guess the plugin being built is of type Api, therefore no need for an Auth plugin.
                    return None

    @staticmethod
    def get_crunch_plugin(name, **options):
        """Instantiate a eodag Crunch plugin whom class name is `name`, and configure it with the `options`

        :param name: The name of the Crunch plugin to instantiate
        :type name: str or unicode
        :param options: The configuration parameters of the cruncher
        :type options: dict
        :return: The cruncher named `name`
        :rtype: :class:`~eodag.plugins.crunch.Crunch`
        """
        Klass = Crunch.get_plugin_by_class_name(name)
        return Klass(options)

    def set_priority(self, provider, priority):
        """Set the priority of the given provider

        :param provider: The provider which is assigned the priority
        :type provider: str or unicode
        :param priority: The priority to assign to the provider
        :type priority: int
        """
        # Update the priority in the configurations so that it is taken into account when a plugin of this provider is
        # latterly built
        for product_type, provider_configs in self.product_type_to_provider_config_map.items():
            for config in provider_configs:
                if config.name == provider:
                    config.priority = priority
            # Sort the provider configs, taking into account the new priority order
            provider_configs.sort(key=attrgetter('priority'), reverse=True)
        # Update the priority of already built plugins of the given provider
        for provider_name, topic_class in self._built_plugins_cache:
            if provider_name == provider:
                self._built_plugins_cache[(provider, topic_class)].priority = priority

    def _build_plugin(self, provider, plugin_conf, topic_class):
        """Build the plugin of the given topic with the given plugin configuration and registered as the given provider

        :param provider: The provider for which to build the plugin
        :type provider: str or unicode
        :param plugin_conf: The configuration of the plugin to be built
        :type plugin_conf: :class:`~eodag.config.PluginConfig`
        :param topic_class: The type of plugin to build
        :type topic_class: :class:`~eodag.plugin.base.PluginTopic`
        :returns: The built plugin
        :rtype: :class:`~eodag.plugin.search.Search` or :class:`~eodag.plugin.download.Download` or
                :class:`~eodag.plugin.authentication.Authentication` or :class:`~eodag.plugin.crunch.Crunch`
        """
        cached_instance = self._built_plugins_cache.setdefault((provider, topic_class.__name__), None)
        if cached_instance is not None:
            return cached_instance
        plugin_class = EODAGPluginMount.get_plugin_by_class_name(
            topic_class,
            getattr(plugin_conf, 'type')
        )
        plugin = plugin_class(provider, plugin_conf)
        self._built_plugins_cache[(provider, topic_class.__name__)] = plugin
        return plugin
