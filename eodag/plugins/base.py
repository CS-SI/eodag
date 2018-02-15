# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from eodag.utils.exceptions import PluginNotFoundError


class GeoProductDownloaderPluginMount(type):
    def __init__(cls, name, bases, attrs):
        if not hasattr(cls, 'plugins'):
            # This branch only executes when processing the mount point itself.
            # So, since this is a new plugin type, not an implementation, this
            # class shouldn't be registered as a plugin. Instead, it sets up a
            # list where plugins can be registered later.
            cls.plugins = []
        else:
            # This must be a plugin implementation, which should be registered.
            # Simply appending it to the list is all that's needed to keep
            # track of it later.
            cls.plugins.append(cls)

            # Every plugin class has a name attribute defaulting to the name of the class
            cls.name = cls.__name__
            # Every plugin class has a priority attribute that an instance can override. Minimum priority by default =>
            # an instance must override this with higher priority if it wants to be used
            cls.priority = 0

    def get_plugins(cls, *args, **kwargs):
        return [plugin(*args, **kwargs) for plugin in cls.plugins]

    def get_plugin_by_name(cls, name):
        for plugin in cls.plugins:
            if name == plugin.name:
                return plugin
        raise PluginNotFoundError("'{}' not found for {} class of plugins".format(name, cls))
