# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
import logging

from eodag import plugins
from eodag.plugins.authentication.base import Authentication
from eodag.plugins.base import GeoProductDownloaderPluginMount
from eodag.plugins.download.base import Download
from eodag.plugins.filter.base import Filter
from eodag.plugins.search.base import Search
from eodag.utils.import_system import import_all_modules


logger = logging.getLogger('eodag.plugins.instances_manager')


class PluginInstancesManager(object):
    """A manager for the plugins instances.

    The role of this class is to instantiate the plugins according to a configuration, and keep track of them in memory.
    If the configuration looks like this:
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
            'filter': {
                'plugin': 'VeryComplexFilter',
                ...
            }
        },
        ...
    },
    the manager will ask to the .search.base.Search class to give to it the RestoSearch plugin class by calling
    Search.get_plugin_by_name(conf['eocloud']['search']['plugin']), so that it can create its eocloud instance with
    conf['eocloud']['search'] configuration.
    """
    supported_topics = {
        'search': Search,
        'download': Download,
        'filter': Filter,
        'auth': Authentication,
    }

    def __init__(self, config):
        self.instances_config = config
        # Load all the plugins. This will make all plugin classes of a particular type to be available in the base
        # plugin class's 'plugins' attribute. For example, by importing module 'plugins.search.resto', the plugin
        # 'RestoSearch' will be available in self.supported_topics['search'].plugins
        import_all_modules(plugins, depth=2, exclude=('base', __name__.split('.')[-1],))

    def instantiate_configured_plugins(self, topic):
        """Instantiate the plugins"""
        logger.debug('Creating configured *%s* plugin instances', topic.upper())
        PluginBaseClass = self.__get_base_class(topic)
        instances = []
        for instance_name, instance_config in self.instances_config.items():
            logger.debug('Creating *%s* plugin instance with name *%s*', topic.upper(), instance_name)
            PluginClass = GeoProductDownloaderPluginMount.get_plugin_by_name(
                PluginBaseClass,
                instance_config[topic]['plugin']
            )
            instance = PluginClass(instance_config[topic])
            # Each instance will be identified by its name, independently of the plugin implementation
            instance.instance_name = instance_name
            # Update instance priority
            instance.priority = instance_config.get('priority', instance.priority)
            instances.append(instance)
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

    def instantiate_plugin_by_config(self, topic_name, topic_config):
        logger.debug('Creating *%s* plugin instance with config %s', topic_name.upper(), topic_config)
        PluginBaseClass = self.__get_base_class(topic_name)
        PluginClass = GeoProductDownloaderPluginMount.get_plugin_by_name(
            PluginBaseClass,
            topic_config['plugin']
        )
        return PluginClass(topic_config)

