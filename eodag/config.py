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
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import tempfile

import yaml
import yaml.parser
import yaml.constructor

from eodag.utils import utf8_everywhere


logger = logging.getLogger('eodag.config')


class SimpleYamlProxyConfig(object):
    """A simple configuration class acting as a proxy to an underlying dict object as returned by yaml.load"""

    def __init__(self, conf_file_path):
        with open(os.path.abspath(os.path.realpath(conf_file_path)), 'r') as fh:
            try:
                self.source = yaml.load(fh)
                utf8_everywhere(self.source)
            except yaml.parser.ParserError as e:
                print('Unable to load user configuration file')
                raise e

    def __getitem__(self, item):
        return self.source[item]

    def __contains__(self, item):
        return item in self.source

    def __iter__(self):
        return iter(self.source)

    def items(self):
        return self.source.items()

    def values(self):
        return self.source.values()

    def update(self, other):
        if not isinstance(other, self.__class__):
            raise ValueError("'{}' must be of type {}".format(other, self.__class__))
        self.source.update(other.source)


class ProviderConfig(yaml.YAMLObject):
    """Representation of eodag configuration.

    :param name: The name of the provider
    :type name: str or unicode
    :param priority: (optional) The priority of the provider while searching a product. Lower value means lower
                     priority. Defaults to 0
    :type priority: int
    :param api: (optional) The configuration of a plugin of type Api
    :type api: :class:`~eodag.config.PluginConfig`
    :param search: (optional) The configuration of a plugin of type Search
    :type search: :class:`~eodag.config.PluginConfig`
    :param dict products: (optional) The products types supported by the provider
    :param download: (optional) The configuration of a plugin of type Download
    :type download: :class:`~eodag.config.PluginConfig`
    :param auth: (optional) The configuration of a plugin of type Authentication
    :type auth: :class:`~eodag.config.PluginConfig`
    :param dict kwargs: Additional configuration variables for this provider
    """
    yaml_loader = yaml.Loader
    yaml_dumper = yaml.SafeDumper
    yaml_tag = '!provider'

    def __init__(self, name, priority=0, api=None, search=None, products=None, download=None, auth=None, **kwargs):
        self.name = name.replace('-', '_')
        self.priority = priority
        self.api = api
        self.search = search
        self.products = products or {}
        self.download = download
        self.auth = auth
        # self.outputs_prefix = tempfile.gettempdir()
        # self.extract = True
        # each additional parameter becomes an attribute of the instance
        for key, value in kwargs:
            setattr(self, key, value)

    def override_from_file(self, file_path):
        """Override the configuration parameters from a file

        :param file_path: The path to the configuration file to load
        :type file_path: str or unicode
        """
        with open(file_path, 'r') as fd:
            try:
                conf_from_file = yaml.safe_load(fd)
                utf8_everywhere(conf_from_file)
                build_env_from_mapping(conf_from_file)
                self.override_from_env()
            except yaml.constructor.Constructor:
                import traceback
                logger.error("Could not load the config file. Please provide a standard yaml config file. "
                             "Got error:\n%s", traceback.format_exc())

    def override_from_env(self):
        """Override the configuration parameters from environment variables"""
        plugin_params = {'api', 'search', 'download', 'auth'}
        # First override all params at provider-level
        for param_name in set(self.__dict__.keys()).difference(plugin_params):
            default_value = getattr(self, param_name)
            if isinstance(default_value, dict):
                update_mapping_inplace_from_env_var(
                    'EODAG__{}__{}'.format(self.name.upper(), param_name.upper()),
                    default_value
                )
            else:
                env_var_name = 'EODAG__{}__{}'.format(self.name.upper(), param_name.upper())
                setattr(self, param_name, os.environ.get(env_var_name, default_value))

        # Then override plugins configurations
        for param_name in plugin_params:
            default_value = getattr(self, param_name, None)
            if default_value is not None:
                default_value.override_from_env(
                    'EODAG__{}__{}'.format(self.name.upper(), param_name.upper())
                )


class PluginConfig(yaml.YAMLObject):
    """Representation of a plugin config

    :param name: The name of the plugin class to use to instantiate the plugin object
    :type name: str or unicode
    :param dict metadata_mapping: (optional) The mapping between eodag metadata and the plugin specific metadata
    :param dict free_params: (optional) Additional configuration parameters
    """
    yaml_loader = yaml.Loader
    yaml_dumper = yaml.SafeDumper
    yaml_tag = '!plugin'

    def __init__(self, name, metadata_mapping=None, **free_params):
        self.name = name
        self.metadata_mapping = metadata_mapping or {}
        for key, value in free_params:
            setattr(self, key, value)

    def override_from_env(self, prefix):
        """Override configuration from environment variable whose name begin with `prefix`

        :param prefix: The prefix of the env var to look for
        :type prefix: str or unicode
        """
        for attr, value in self.__dict__.items():
            if attr not in ('name', 'metadata_mapping'):
                if isinstance(value, list):
                    continue
                env_var = prefix + '__{}'.format(attr.upper())
                if isinstance(value, dict):
                    update_mapping_inplace_from_env_var(
                        env_var,
                        value
                    )
                else:
                    override = os.environ.get(env_var, getattr(self, attr, None))
                    if attr == 'extract':
                        override = bool(override)
                    setattr(self, attr, override)


def update_mapping_inplace_from_env_var(prefix, mapping, max_depth=3):
    """Recursively update a mapping in place from environment variables that start with `prefix`.

    :param prefix: The prefix with which the environment variable starts
    :type prefix: str or unicode
    :param dict mapping: The mapping to update
    :param max_depth: (optional) The maximum recursion depth allowed
    """
    env_var_pattern = prefix + '__{}'
    scalars = set(
        key for key, value in mapping.items()
        if not isinstance(value, dict) and not isinstance(value, list)
    )
    # First override scalars
    for key in scalars:
        env_var = env_var_pattern.format(key.upper())
        mapping[key] = os.environ.get(env_var, mapping[key])

    nested = set(mapping.keys()).difference(scalars)
    while max_depth >= 0:
        max_depth -= 1
        # Override nested dicts (we don't support lists)
        for key in nested:
            if isinstance(mapping[key], list):
                continue
            env_var = env_var_pattern.format(key)
            if env_var in os.environ:
                update_mapping_inplace_from_env_var(env_var, mapping[key], max_depth=max_depth)


def build_env_from_mapping(mapping, prefix='EODAG__'):
    """Build environment variables from a given mapping with their names starting with `prefix`.

    This function recursively populates `os.environ` with variable whose names start with the `prefix` and the other
    parts of the name come from the `mapping`. For example, a mapping {"var1": {"var2": 1, "var3": 2}} will generate
    EODAG__VAR1__VAR2 and EODAG_VAR1__VAR3 environment variables with values 1 and 2 respectively.

    :param dict mapping: The mapping to be expanded as environment variables
    :param prefix: (Optional) The prefix of the environment variables names
    :type prefix: str or unicode
    """
    try:
        key, value = mapping.popitem()
        if not isinstance(value, list):
            env_var = prefix + key.replace('-', '_').upper()
            if isinstance(value, dict):
                build_env_from_mapping(value, prefix=(env_var + '__'))
            else:
                # Populate the env
                if isinstance(value, bool):
                    os.environ[env_var] = 'true' if value else 'false'
                else:
                    os.environ[env_var] = value
        build_env_from_mapping(mapping, prefix)
    except KeyError:
        return
