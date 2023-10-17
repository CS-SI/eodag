# -*- coding: utf-8 -*-
# Copyright 2018, CS GROUP - France, https://www.csgroup.eu/
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
from typing import Any, List

from eodag.config import PluginConfig
from eodag.utils.exceptions import PluginNotFoundError


class EODAGPluginMount(type):
    """Plugin mount"""

    def __init__(cls, name: str, bases, attrs):
        if not hasattr(cls, "plugins"):
            # This branch only executes when processing the mount point itself.
            # So, since this is a new plugin type, not an implementation, this
            # class shouldn't be registered as a plugin. Instead, it sets up a
            # list where plugins can be registered later.
            cls.plugins: List[EODAGPluginMount] = []
        else:
            # This must be a plugin implementation, which should be registered.
            # Simply appending it to the list is all that's needed to keep
            # track of it later.
            cls.plugins.append(cls)

    def get_plugins(cls, *args: Any, **kwargs: Any):
        """Get plugins"""
        return [plugin(*args, **kwargs) for plugin in cls.plugins]

    def get_plugin_by_class_name(cls, name: str):
        """Get plugin by class_name"""
        for plugin in cls.plugins:
            if name == plugin.__name__:
                return plugin
        raise PluginNotFoundError(
            "'{}' not found for {} class of plugins".format(name, cls)
        )


class PluginTopic(metaclass=EODAGPluginMount):
    """Base of all plugin topics in eodag"""

    def __init__(self, provider: str, config: PluginConfig):
        self.config = config
        self.provider = provider

    def __repr__(self):
        return "{}(provider={}, priority={}, topic={})".format(
            self.__class__.__name__,
            self.provider,
            self.config.priority,
            self.__class__.mro()[-3].__name__,
        )
