# -*- coding: utf-8 -*-
# Copyright 2020, CS GROUP - France, http://www.c-s.fr
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

import ast
import copy
import logging
import os
import tempfile
from collections import defaultdict

import jsonpath_rw as jsonpath
import yaml
import yaml.constructor
import yaml.parser
from pkg_resources import resource_filename

from eodag.utils import merge_mappings, slugify, utf8_everywhere
from eodag.utils.exceptions import ValidationError

logger = logging.getLogger("eodag.config")


class SimpleYamlProxyConfig(object):
    """A simple configuration class acting as a proxy to an underlying dict object
    as returned by yaml.load"""

    def __init__(self, conf_file_path):
        with open(os.path.abspath(os.path.realpath(conf_file_path)), "r") as fh:
            try:
                self.source = yaml.load(fh, Loader=yaml.SafeLoader)
                utf8_everywhere(self.source)
            except yaml.parser.ParserError as e:
                print("Unable to load user configuration file")
                raise e

    def __getitem__(self, item):
        return self.source[item]

    def __contains__(self, item):
        return item in self.source

    def __iter__(self):
        return iter(self.source)

    def items(self):
        """Iterate over keys and values of source"""
        return self.source.items()

    def values(self):
        """Iterate over values of source"""
        return self.source.values()

    def update(self, other):
        """Update a :class:`~eodag.config.SimpleYamlProxyConfig`"""
        if not isinstance(other, self.__class__):
            raise ValueError("'{}' must be of type {}".format(other, self.__class__))
        self.source.update(other.source)


class ProviderConfig(yaml.YAMLObject):
    """Representation of eodag configuration.

    :param name: The name of the provider
    :type name: str or unicode
    :param priority: (optional) The priority of the provider while searching a product.
                     Lower value means lower priority. (Default: 0)
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
    yaml_tag = "!provider"

    @classmethod
    def from_yaml(cls, loader, node):
        """Build a :class:`~eodag.config.ProviderConfig` from Yaml"""
        cls.validate(tuple(node_key.value for node_key, _ in node.value))
        for node_key, node_value in node.value:
            if node_key.value == "name":
                node_value.value = slugify(node_value.value).replace("-", "_")
                break
        return loader.construct_yaml_object(node, cls)

    @classmethod
    def from_mapping(cls, mapping):
        """Build a :class:`~eodag.config.ProviderConfig` from a mapping"""
        cls.validate(mapping)
        for key in ("api", "search", "download", "auth"):
            if key in mapping:
                mapping[key] = PluginConfig.from_mapping(mapping[key])
        c = cls()
        c.__dict__.update(mapping)
        return c

    @staticmethod
    def validate(config_keys):
        """Validate a :class:`~eodag.config.ProviderConfig`"""
        if "name" not in config_keys:
            raise ValidationError("Provider config must have name key")
        if not any(k in config_keys for k in ("api", "search", "download", "auth")):
            raise ValidationError("A provider must implement at least one plugin")
        if "api" in config_keys and any(
            k in config_keys for k in ("search", "download", "auth")
        ):
            raise ValidationError(
                "A provider implementing an Api plugin must not implement any other "
                "type of plugin"
            )

    def update(self, mapping):
        """Update the configuration parameters with values from `mapping`

        :param dict mapping: The mapping from which to override configuration parameters
        """
        if mapping is None:
            mapping = {}
        merge_mappings(
            self.__dict__,
            {
                key: value
                for key, value in mapping.items()
                if key not in ("name", "api", "search", "download", "auth")
                and value is not None
            },
        )
        for key in ("api", "search", "download", "auth"):
            current_value = getattr(self, key, None)
            if current_value is not None:
                current_value.update(mapping.get(key, {}))


class PluginConfig(yaml.YAMLObject):
    """Representation of a plugin config

    :param name: The name of the plugin class to use to instantiate the plugin object
    :type name: str or unicode
    :param dict metadata_mapping: (optional) The mapping between eodag metadata and
                                  the plugin specific metadata
    :param dict free_params: (optional) Additional configuration parameters
    """

    yaml_loader = yaml.Loader
    yaml_dumper = yaml.SafeDumper
    yaml_tag = "!plugin"

    @classmethod
    def from_yaml(cls, loader, node):
        """Build a :class:`~eodag.config.PluginConfig` from Yaml"""
        cls.validate(tuple(node_key.value for node_key, _ in node.value))
        return loader.construct_yaml_object(node, cls)

    @classmethod
    def from_mapping(cls, mapping):
        """Build a :class:`~eodag.config.PluginConfig` from a mapping"""
        c = cls()
        c.__dict__.update(mapping)
        return c

    @staticmethod
    def validate(config_keys):
        """Validate a :class:`~eodag.config.PluginConfig`"""
        if "type" not in config_keys:
            raise ValidationError(
                "A Plugin config must specify the Plugin it configures"
            )

    def update(self, mapping):
        """Update the configuration parameters with values from `mapping`

        :param dict mapping: The mapping from which to override configuration parameters
        """
        if mapping is None:
            mapping = {}
        merge_mappings(
            self.__dict__, {k: v for k, v in mapping.items() if v is not None}
        )


def load_default_config():
    """Build the providers configuration into a dictionnary

    :returns: The default provider's configuration
    :rtype: dict
    """
    config = {}
    with open(resource_filename("eodag", "resources/providers.yml"), "r") as fh:
        try:
            # Providers configs are stored in this file as separated yaml documents
            # Load all of it
            providers_configs = yaml.load_all(fh, Loader=yaml.Loader)
        except yaml.parser.ParserError as e:
            logger.error("Unable to load configuration")
            raise e
        for provider_config in providers_configs:
            # For all providers, set the default outputs_prefix of its download plugin
            # as tempdir in a portable way
            for param_name in ("download", "api"):
                if param_name in vars(provider_config):
                    param_value = getattr(provider_config, param_name)
                    param_value.outputs_prefix = tempfile.gettempdir()
            # Set default priority to 0
            provider_config.__dict__.setdefault("priority", 0)
            config[provider_config.name] = provider_config
        return config


def override_config_from_file(config, file_path):
    """Override a configuration with the values in a file

    :param dict config: An eodag providers configuration dictionary
    :param file_path: The path to the file from where the new values will be read
    :type file_path: str or unicode
    """
    logger.info("Loading user configuration from: %s", os.path.abspath(file_path))
    with open(os.path.abspath(os.path.realpath(file_path)), "r") as fh:
        try:
            config_in_file = yaml.safe_load(fh)
            if config_in_file is None:
                return
            utf8_everywhere(config_in_file)
        except yaml.parser.ParserError as e:
            logger.error("Unable to load user configuration file")
            raise e
    override_config_from_mapping(config, config_in_file)


def override_config_from_env(config):
    """Override a configuration with environment variables values

    :param dict config: An eodag providers configuration dictionary
    """

    def build_mapping_from_env(env_var, env_value, mapping):
        """Recursively build a dictionary from an environment variable.

        The environment variable must respect the pattern: KEY1__KEY2__[...]__KEYN.
        It will be transformed to::

            {
                "key1": {
                    "key2": {
                        {...}
                    }
                }
            }

        :param env_var: The environment variable to be transformed into a dictionary
        :type env_var: str or unicode
        :param env_value: The value from environment variable
        :type env_value: str or unicode
        :param dict mapping: The mapping in which the value will be created
        """
        parts = env_var.split("__")
        if len(parts) == 1:
            mapping[parts[0]] = env_value
        else:
            new_map = mapping.setdefault(parts[0], {})
            build_mapping_from_env("__".join(parts[1:]), env_value, new_map)

    mapping_from_env = {}
    for env_var in os.environ:
        if env_var.startswith("EODAG__"):
            build_mapping_from_env(
                env_var[len("EODAG__") :].lower(),  # noqa
                os.environ[env_var],
                mapping_from_env,
            )

    override_config_from_mapping(config, mapping_from_env)


def override_config_from_mapping(config, mapping):
    """Override a configuration with the values in a mapping

    :param dict config: An eodag providers configuration dictionary
    :param dict mapping: The mapping containing the values to be overriden
    """
    for provider, new_conf in mapping.items():
        old_conf = config.get(provider)
        if old_conf is not None:
            old_conf.update(new_conf)
        else:
            logger.warning(
                "%s: unknown provider found in user conf, trying to use provided configuration",
                provider,
            )
            try:
                mapping[provider] = ProviderConfig.from_mapping(new_conf)
            except ValidationError as e:
                logger.warning("%s skipped: %s", provider, e)


def load_yml_config(yml_path):
    """Build a conf dictionnary from given yml absolute path

    :returns: The yml configuration file
    :rtype: dict
    """
    config = SimpleYamlProxyConfig(yml_path)
    return dict_items_recursive_apply(config.source, string_to_jsonpath)


def load_stac_config():
    """Build the stac configuration into a dictionnary

    :returns: The stac configuration
    :rtype: dict
    """
    return load_yml_config(
        resource_filename("eodag", os.path.join("resources/", "stac.yml"))
    )


def load_stac_api_config():
    """Build the stac API configuration into a dictionnary

    :returns: The stac API configuration
    :rtype: dict
    """
    return load_yml_config(
        resource_filename("eodag", os.path.join("resources/", "stac_api.yml"))
    )


def load_stac_provider_config():
    """Build the stac provider configuration into a dictionnary

    :returns: The stac provider configuration
    :rtype: dict
    """
    return SimpleYamlProxyConfig(
        resource_filename("eodag", os.path.join("resources/", "stac_provider.yml"))
    ).source


def format_dict_items(config_dict, **format_variables):
    """Recursive apply string.format(**format_variables) to dict elements

    >>> format_dict_items(
    ...     {"foo": {"bar": "{a}"}, "baz": ["{b}?", "{b}!"]},
    ...     **{"a": "qux", "b":"quux"},
    ... ) == {"foo": {"bar": "qux"}, "baz": ["quux?", "quux!"]}
    True

    :param config_dict: dictionnary having values that need to be parsed
    :type config_dict: dict
    :param format_variables: variables used as args for parsing
    :type format_variables: dict
    :returns: updated dict
    :rtype: dict
    """
    return dict_items_recursive_apply(config_dict, format_string, **format_variables)


def jsonpath_parse_dict_items(jsonpath_dict, values_dict):
    """Recursive parse jsonpath elements in dict

    >>> import jsonpath_rw as jsonpath
    >>> jsonpath_parse_dict_items(
    ...     {"foo": {"bar": jsonpath.parse("$.a.b")}, "qux": [jsonpath.parse("$.c"), jsonpath.parse("$.c")]},
    ...     {"a":{"b":"baz"}, "c":"quux"}
    ... ) == {'foo': {'bar': 'baz'}, 'qux': ['quux', 'quux']}
    True

    :param jsonpath_dict: dictionnary having values that need to be parsed
    :type jsonpath_dict: dict
    :param values_dict: values dict used as args for parsing
    :type values_dict: dict
    :returns: updated dict
    :rtype: dict
    """
    return dict_items_recursive_apply(jsonpath_dict, parse_jsonpath, **values_dict)


def dict_items_recursive_apply(config_dict, apply_method, **apply_method_parameters):
    """Recursive apply method to dict elements

    >>> dict_items_recursive_apply(
    ...     {"foo": {"bar":"baz"}, "qux": ["a","b"]},
    ...     lambda k,v,x: v.upper()+x, **{"x":"!"}
    ... ) == {'foo': {'bar': 'BAZ!'}, 'qux': ['A!', 'B!']}
    True

    :param config_dict: input dictionnary containing nested lists/dicts
    :type config_dict: dict
    :param apply_method: method to be applied to dict elements
    :type apply_method: :func:`apply_method`
    :param apply_method_parameters: optional parameters passed to the method
    :type apply_method_parameters: dict
    :returns: updated dict
    :rtype: dict
    """
    result_dict = copy.deepcopy(config_dict)
    for dict_k, dict_v in result_dict.items():
        if isinstance(dict_v, dict):
            result_dict[dict_k] = dict_items_recursive_apply(
                dict_v, apply_method, **apply_method_parameters
            )
        elif any(isinstance(dict_v, t) for t in (list, tuple)):
            result_dict[dict_k] = list_items_recursive_apply(
                dict_v, apply_method, **apply_method_parameters
            )
        else:
            result_dict[dict_k] = apply_method(
                dict_k, dict_v, **apply_method_parameters
            )

    return result_dict


def list_items_recursive_apply(config_list, apply_method, **apply_method_parameters):
    """Recursive apply method to list elements

    >>> list_items_recursive_apply(
    ...     [{"foo": {"bar":"baz"}}, "qux"],
    ...     lambda k,v,x: v.upper()+x,
    ...     **{"x":"!"})
    [{'foo': {'bar': 'BAZ!'}}, 'QUX!']

    :param config_list: input list containing nested lists/dicts
    :type config_list: list
    :param apply_method: method to be applied to list elements
    :type apply_method: :func:`apply_method`
    :param apply_method_parameters: optional parameters passed to the method
    :type apply_method_parameters: dict
    :returns: updated list
    :rtype: list
    """
    result_list = copy.deepcopy(config_list)
    for list_idx, list_v in enumerate(result_list):
        if isinstance(list_v, dict):
            result_list[list_idx] = dict_items_recursive_apply(
                list_v, apply_method, **apply_method_parameters
            )
        elif any(isinstance(list_v, t) for t in (list, tuple)):
            result_list[list_idx] = list_items_recursive_apply(
                list_v, apply_method, **apply_method_parameters
            )
        else:
            result_list[list_idx] = apply_method(
                list_idx, list_v, **apply_method_parameters
            )

    return result_list


def string_to_jsonpath(key, str_value):
    """Get jsonpath for "$.foo.bar" like string

    >>> string_to_jsonpath(None, "$.foo.bar")
    Child(Child(Root(), Fields('foo')), Fields('bar'))

    :param key: input item key
    :type key: str
    :param str_value: input item value, to be converted
    :type str_value: str
    :returns: parsed value
    :rtype: str
    """
    if "$." in str(str_value):
        try:
            return jsonpath.parse(str_value)
        except Exception:  # jsonpath_rw does not provide a proper exception
            # If str_value does not contain a jsonpath, return it as is
            return str_value
    else:
        return str_value


def format_string(key, str_to_format, **format_variables):
    """Format "{foo}" like string

    >>> format_string(None, "foo {bar}, {baz} ?", **{"bar": "qux", "baz": "quux"})
    'foo qux, quux ?'

    :param key: input item key
    :type key: str
    :param str_to_format: input item value, to be parsed
    :type str_to_format: str
    :returns: parsed value
    :rtype: str
    """
    if isinstance(str_to_format, str):
        # defaultdict usage will return "" for missing keys in format_args
        try:
            result = str_to_format.format_map(defaultdict(str, **format_variables))
        except TypeError:
            logger.error("Unable to format str=%s" % str_to_format)
            raise

        # try to convert string to python object
        try:
            return ast.literal_eval(result)
        except (SyntaxError, ValueError):
            return result
    else:
        return str_to_format


def parse_jsonpath(key, jsonpath_obj, **values_dict):
    """Parse jsonpah in jsonpath_obj using values_dict

    >>> import jsonpath_rw as jsonpath
    >>> parse_jsonpath(None, jsonpath.parse("$.foo.bar"), **{"foo":{"bar":"baz"}})
    'baz'

    :param key: input item key
    :type key: str
    :param jsonpath_obj: input item value, to be parsed
    :type jsonpath_obj: str
    :param values_dict: values used as args for parsing
    :type values_dict: dict
    :returns: parsed value
    :rtype: str
    """
    if isinstance(jsonpath_obj, jsonpath.jsonpath.Child):
        match = jsonpath_obj.find(values_dict)
        return match[0].value if len(match) == 1 else None
    else:
        return jsonpath_obj


def update_nested_dict(old_dict, new_dict):
    """Update recursively old_dict items with new_dict ones

    >>> update_nested_dict(
    ...     {"a": {"a.a": 1, "a.b": 2}, "b": 3},
    ...     {"a": {"a.a": 10}}
    ... ) == {'a': {'a.a': 10, 'a.b': 2}, 'b': 3}
    True

    :param old_dict: dict to be updated
    :type old_dict: dict
    :param new_dict: incomming dict
    :type new_dict: dict
    :returns: updated dict
    :rtype: dict
    """
    for k, v in new_dict.items():
        if k in old_dict.keys():
            if isinstance(v, dict) and isinstance(old_dict[k], dict):
                old_dict[k] = update_nested_dict(old_dict[k], v)
            elif v:
                old_dict[k] = v
        else:
            old_dict[k] = v
    return old_dict
