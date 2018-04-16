# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging
from collections import Iterable

from eodag import plugins
from eodag.plugins.apis.base import Api
from eodag.plugins.authentication.base import Authentication
from eodag.plugins.base import GeoProductDownloaderPluginMount
from eodag.plugins.download.base import Download
from eodag.plugins.crunch.base import Crunch
from eodag.plugins.search.base import Search
from eodag.utils.import_system import import_all_modules


logger = logging.getLogger(b'eodag.plugins.instances_manager')


class PluginInstancesManager(object):
    """A manager for the plugins instances.

    The role of this class is to instantiate the plugins according to a configuration, and keep track of them in memory.
    If the configuration looks like this::

        conf = {
            'eocloud': {
                'search': {
                    'plugin': 'RestoSearch',
                    'api_endpoint': ...,
                    'products': {...},
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
    ``Search.get_plugin_by_name(conf['eocloud']['search']['plugin'])``, so that it can create its ``eocloud`` instance
    with ``conf['eocloud']['search']`` configuration.

    :param config: The configuration with all information about the systems supported by the `eodag`
    :type config: :class:`~eodag.config.SimpleYamlProxyConfig`
    """
    supported_topics = {
        'search': Search,
        'download': Download,
        'crunch': Crunch,
        'auth': Authentication,
        'api': Api,
    }

    def __init__(self, config):
        self.instances_config = config
        # Load all the plugins. This will make all plugin classes of a particular type to be available in the base
        # plugin class's 'plugins' attribute. For example, by importing module 'plugins.search.resto', the plugin
        # 'RestoSearch' will be available in self.supported_topics['search'].plugins
        import_all_modules(plugins, depth=2, exclude=('base', __name__.split('.')[-1],))

    def instantiate_configured_plugins(self, topics, pt_matching='', only=None):
        """Instantiate all known plugins of particular type.

        :param topics: An iterable of plugin topics (e.g: ``('search', 'download')``)
        :type topics: :class:`~collections.Iterable(str)`
        :param pt_matching: (optional) A product type, that will help to filter which instances to create (the ones
                            which explicitly support the product type as mentioned in the configuration)
        :type pt_matching: str or unicode
        :param only: (optional) An iterable of instance names to enable instantiating only these instances (they should
                     be stilled configured for this to work)
        :type only: Iterable
        :returns: A list of instantiated and configured plugins
        :rtype: list
        """
        if isinstance(topics, Iterable):
            instances = []
            for topic in topics:
                instances.extend(self.__get_instances(
                    topic,
                    only=self.__filter_instances(topic, pt_matching) + (only or [])
                ))
        else:
            instances = self.__get_instances(topics, only=self.__filter_instances(topics, pt_matching))
        return instances

    def __filter_instances(self, topic, pt):
        """Returns a list of instances names supporting a particular product type.

        :param topic: The plugin topic (e.g.: 'search')
        :type topic: str or unicode
        :param pt: The product type to be supported by the plugin
        :type pt: str or unicode
        :returns: The topic's plugin instances supporting the product type
        :rtype: list

        .. Notes:
            1. Only apply to the search topic by now
            2. CSWSearch are included by default in the list to enable its instances to take over if they are the preferred
            platforms
        """
        if topic == 'search':
            return [
                system
                for system, config in self.instances_config.items()
                if (('products' in config.get(topic, {}) and pt in config.get(topic, {}).get('products'))
                    or config.get(topic, {}).get('plugin') == 'CSWSearch')
            ]
        return []

    def __get_instances(self, topic, only=None):
        instances = []
        logger.debug('Creating configured *%s* plugin instances', topic.upper())
        PluginBaseClass = self.__get_base_class(topic)
        for instance_name, instance_config in self.instances_config.items():
            # If only is given, only instantiate this subset of instances
            if only and isinstance(only, Iterable) and instance_name not in only:
                continue
            if topic in instance_config:
                logger.debug("Creating '%s' plugin instance with name '%s'", topic.upper(), instance_name)
                instance = self.instantiate_plugin_by_config(
                    topic,
                    instance_config[topic],
                    base=PluginBaseClass,
                    iname=instance_name,
                    priority=instance_config.get('priority')
                )
                instances.append(instance)
            else:
                logger.debug("Skipping '%(top)s' plugin creation for instance '%(ins)s': not an instance of '%(top)s'",
                             {'top': topic.upper(), 'ins': instance_name})
        return instances

    def __get_base_class(self, topic):
        try:
            PluginBaseClass = self.supported_topics[topic]
        except KeyError:
            raise RuntimeError(
                "Topic '{}' is not supported by the plugin system. Choose between {}".format(
                    topic,
                    ', '.join(self.supported_topics.keys())
                )
            )
        return PluginBaseClass

    def instantiate_plugin_by_config(self, topic_name, topic_config, base=None, iname='', priority=None):
        """Creates an instance of a type of plugin based on a configuration suited for this type of plugin.

        :param topic_name: The name of the type of plugin to instantiate (e.g: `'search'`)
        :type topic_name: str or unicode
        :param dict topic_config: A configuration compatible for the type of plugin to instantiate
        :param base: (optional) The python class corresponding to the `topic_name`
        :type base: subclass of :class:`~eodag.plugins.base.PluginTopic` or None
        :param str iname: (optional) The name to give to the created instance
        :param priority: The priority that will be given to the created instance
        :type priority: int or None
        :returns: An instance of a subclass of `base` or the class corresponding to `topic_name`
        """
        logger.debug("Creating '%s' plugin instance with config '%s'", topic_name.upper(), topic_config)
        PluginBaseClass = base or self.__get_base_class(topic_name)
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
        PluginBaseClass = self.__get_base_class(topic)
        PluginClass = GeoProductDownloaderPluginMount.get_plugin_by_name(PluginBaseClass, name)
        return PluginClass()

