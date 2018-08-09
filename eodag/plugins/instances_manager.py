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
from collections import Iterable

import pkg_resources

from eodag.plugins.apis.base import Api
from eodag.plugins.authentication.base import Authentication
from eodag.plugins.base import GeoProductDownloaderPluginMount
from eodag.plugins.crunch.base import Crunch
from eodag.plugins.download.base import Download
from eodag.plugins.search.base import Search


logger = logging.getLogger('eodag.plugins.instances_manager')


class PluginInstancesManager(object):
    """A manager for the plugins instances.

    The role of instances of this class (normally only one instance exists, created during instantiation of
    :class:`~eodag.api.core.EODataAccessGateway`, and referenced by :attr:`eodag.api.core.EODataAccessGateway.pim` -
    pim stands for plugin instances manager. But nothing is done to enforce this) is to instantiate the plugins
    according to the providers configuration, and keep track of them in memory. The providers configuration contains
    information such as the name of the provider, the internet endpoint for accessing it, and the plugins to use to
    perform defined actions (search, download, authenticate, crunch).

    If the providers configuration looks like this::

        conf = {
            'theia': {
                'search': {
                    'plugin': 'RestoSearch',
                    'api_endpoint': ...,
                    ...
                },
                'download': {
                    'plugin': 'HTTPDownload',
                    ...
                },
                'crunch': {
                    'plugin': 'VeryComplexCruncher',
                    ...
                }
            },
            ...
        }

    the manager will ask to the :class:`~eodag.plugins.search.base.Search` class to give it back the
    :class:`~eodag.plugins.search.resto.RestoSearch` plugin class by calling
    ``Search.get_plugin_by_name(conf['theia']['search']['plugin'])``, so that it can create its ``theia`` instance
    with ``conf['theia']['search']`` configuration.

    :param providers_config: The configuration with all information about the providers supported by the `eodag`
    :type providers_config: :class:`~eodag.config.SimpleYamlProxyConfig`
    """
    supported_topics = {
        'search': Search,
        'download': Download,
        'crunch': Crunch,
        'auth': Authentication,
        'api': Api,
    }

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

    def instantiate_configured_plugins(self, topics, product_type_id='', providers=None):
        """Instantiate all known plugins of particular type.

        :param topics: An iterable of plugin topics (e.g: ``('search', 'download')``).
        :type topics: :class:`~collections.Iterable(str)`
        :param product_type_id: (optional) A product type ID, that will help to filter which instances to create (the
                                ones which explicitly support the product type as can be seen in the providers config).
        :type product_type_id: str or unicode
        :param providers: (optional) An iterable of tuples (provider_name, priority) to enable instantiating only these
                          providers with the given priority (they should be still configured for this to work).
        :type providers: Iterable(tuple(str, int))
        :returns: A list of instantiated and configured plugins of the given topics and supporting the given product
                  type, or only the plugins corresponding to the topics for the providers specified in ``providers``.
        :rtype: list
        :raises: :class:`AssertionError` if neither ``product_type_id`` nor ``providers`` keyword arguments is given.
        """
        assert any((product_type_id, providers)), ("You should provide at least one of 'product_type_id' or "
                                                   "'providers' parameters")
        if isinstance(topics, Iterable):
            instances = []
            for topic in topics:
                instances.extend(
                    self._instantiate(topic, providers=self._filter_providers(topic, product_type_id, providers)))
        else:
            instances = self._instantiate(topics, providers=self._filter_providers(topics, product_type_id, providers))
        return instances

    def instantiate_plugin_by_config(self, topic_name, topic_config, base=None, iname='', priority=None):
        """Creates an instance of a type of plugin based on a configuration suited for this type of plugin.

        :param topic_name: The name of the type of plugin to instantiate (e.g: ``'search'``)
        :type topic_name: str or unicode
        :param dict topic_config: A configuration compatible for the type of plugin to instantiate
        :param base: (optional) The python class corresponding to the `topic_name`
        :type base: subclass of :class:`~eodag.plugins.base.PluginTopic` or None
        :param str iname: (optional) The name to give to the created instance
        :param priority: The priority that will be given to the created instance
        :type priority: int or None
        :returns: An instance of a subclass of `base` or the class corresponding to `topic_name`
        """
        logger.debug("Creating '%s' plugin instance with config '%s'", topic_name.upper(),
                     {key: value for key, value in topic_config.items() if key != 'credentials'})
        PluginBaseClass = base or self._get_base_class(topic_name)
        PluginClass = GeoProductDownloaderPluginMount.get_plugin_by_name(
            PluginBaseClass,
            topic_config['plugin']
        )
        instance = PluginClass(topic_config)
        # Each instance will be identified by its name, independently of the plugin implementation
        instance.instance_name = iname
        # Update instance priority
        if priority and priority != instance.priority:
            instance.priority = priority
        return instance

    def instantiate_plugin_by_name(self, topic, name):
        """Creates an instance of a type of plugin based on its name (the name of the Python class of the plugin).

        This method is intended to be used for 'config-free' plugins (e.g. Crunch plugins). These are plugins that do
        not need configuration to be instantiated.

        :param topic: The type of plugin to be instantiated (e.g.: 'crunch')
        :type topic: str or unicode
        :param name: The name of the Python class representing the plugin
        :type name: str or unicode
        :returns: An instance of the class corresponding to `name`
        """
        logger.debug("Creating '%s' plugin instance with name '%s' (config-free instance)", topic.upper(), name)
        PluginBaseClass = self._get_base_class(topic)
        PluginClass = GeoProductDownloaderPluginMount.get_plugin_by_name(PluginBaseClass, name)
        return PluginClass()

    def _get_topics(self, provider):
        """Returns all the plugin topics configured for a provider.

        Plugin topics are defined as configuration keys of a provider's config which indexes a dict with one
        ``'plugin'`` key.

        :param provider: The name of the provider
        :type provider: str or unicode
        :return: The list of supported plugin topics configured for this provider
        :rtype: list(str)
        """
        provider_config = self.providers_config[provider]
        return [topic for topic in provider_config if 'plugin' in provider_config[topic]]

    def _filter_providers(self, topic, product_type_id, selected):
        """Returns a list of providers to be instantiated according to the product type and the topic.

        :param topic: The plugin topic for which the providers should be configured to be selected
        :type topic: str or unicode
        :param product_type_id: The ID of the product type to be supported by the selected providers
        :type product_type_id: str or unicode
        :param selected: A list of providers that the user wants to instantiate
        :type selected: list(tuple(str, int))
        :returns: The providers that support the given product type id and their priorities
        :rtype: list(tuple(str, int))
        """
        if selected is not None:
            return [
                (provider, priority)
                for provider, priority in selected
                if topic in self.providers_config[provider]
            ]
        return [
            # If the priority is not set in the config, the default priority is 0
            (provider, provider_config.get('priority', 0))
            for provider, provider_config in self.providers_config.items()
            if topic in provider_config and product_type_id in provider_config['products']
        ]

    def _instantiate(self, topic, providers=None):
        """Instantiate a set of providers' topic plugins.

        :param topic: The plugin topic for which we should instantiate the providers' plugins (e.g. ``'search'``)
        :type topic: str or unicode
        :param providers: Restrict instantiation to these providers
        :type providers: list(tuple(str, int))
        :return: The instances requested
        :rtype: list
        """
        instances = []
        PluginBaseClass = self._get_base_class(topic)
        if providers is not None:
            selected_providers = [
                (name, self.providers_config[name], priority)
                for name, priority in providers
            ]
        else:
            #  If providers is not given, all providers supporting topic are instantiated with equal priority of 0
            selected_providers = [
                (name, provider_config, 0)
                for name, provider_config in self.providers_config.items()
                if topic in provider_config
            ]
        search_or_api = topic in ('search', 'api')
        if selected_providers:
            logger.debug('Creating configured *%s* plugin instances', topic.upper())
        for provider_name, provider_config, provider_priority in selected_providers:
            logger.debug("Creating '%s' plugin instance with name '%s'", topic.upper(), provider_name)
            # Hack to nest 'products' config key under 'search' or 'api' config key of the provider. This is done
            # to make the mapping between eodag's product type codes and provider's product type codes available to
            # the Search and Api plugins, considering the way plugins are instantiated (they get config[topic] as
            # initialisation parameter. See the instantiate_plugin_by_config method)
            if search_or_api:
                provider_config[topic].setdefault('products', provider_config['products'])
            instance = self.instantiate_plugin_by_config(
                topic,
                provider_config[topic],
                base=PluginBaseClass,
                iname=provider_name,
                priority=provider_priority
            )
            instances.append(instance)
        return instances

    def _get_base_class(self, topic):
        try:
            PluginBaseClass = self.supported_topics[topic]
        except KeyError:
            raise RuntimeError(
                "Topic '{}' is not supported by the plugin system. Choose between {}".format(
                    topic,
                    ', '.join(self.supported_topics.keys())))
        return PluginBaseClass
