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
            'crunch': {
                'plugin': 'VeryComplexCruncher',
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
        """Instantiate the plugins"""
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

        CSWSearch are included by default in the list to enable its instances to take over if they are the preferred
        platforms"""
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

