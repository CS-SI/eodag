# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
import unittest

from satdl.plugins.search.base import MisconfiguredError
from tests.context import Search


class TestPluginSearchBase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        class SearchPlugin(Search):
            def query(self, *args, **kwargs):
                pass
        cls.PluginClass = SearchPlugin

    def test_implements_all_abstract_methods(self):
        class SearchPlugin(Search):
            """A dumb search plugin not implementing any of the search method"""
            pass
        instance = SearchPlugin({'api_endpoint': 'http://www.valid.url/path/to/api'})
        self.assertRaises(NotImplementedError, instance.query)

    @unittest.skip('No good technique to enforce raising an exception on empty name at the moment')
    def test_empty_plugin_name(self):
        """Overriding plugin name with an empty string leads to error"""
        class OverridingNameSearchPlugin(Search):
            name = ''

            def query(self):
                pass

        self.assertRaises(NotImplementedError, OverridingNameSearchPlugin)

    def test_config_structure_ok(self):
        """SystemConfig of a Search plugin instance must have 3 mandatory keys and one or more optional keys"""
        mandatory_keys_nbr = 2
        instance_without_optional_key = self.PluginClass({
            'api_endpoint': 'http://www.valid.url/path/to/api'
        })
        self.assertIn('api_endpoint', instance_without_optional_key.config)
        self.assertIn('products', instance_without_optional_key.config)
        self.assertEqual(
            len(instance_without_optional_key.config.keys()),
            mandatory_keys_nbr
        )

        other_config = {
            'api_endpoint': 'http://www.valid.url/path/to/api',
            'option': 'value'
        }
        instance_with_optional_config = self.PluginClass(other_config)
        self.assertIn('api_endpoint', instance_with_optional_config.config)
        self.assertIn('products', instance_with_optional_config.config)
        self.assertEqual(
            len(instance_with_optional_config.config.keys()),
            mandatory_keys_nbr + 1  # Only 'option' is a optional key
        )

    def test_config_product_type_is_a_dict(self):
        """productType system_config must be a dictionary"""
        self.assertRaises(
            MisconfiguredError,
            self.PluginClass,
            {'products': ['a', 'b', 'c'], 'api_endpoint': 'http://www.valid.url/path/to/api'}
        )
        self.assertTrue(self.PluginClass({
            'products': {'a': 'p1', 'b': 'p2'},
            'api_endpoint': 'http://www.valid.url/path/to/api'
        }))
        self.assertTrue(self.PluginClass({
            'option': 'value',
            'api_endpoint': 'http://www.valid.url/path/to/api'
        }))
        self.assertTrue(self.PluginClass({
            'api_endpoint': 'http://www.valid.url/path/to/api',
        }))

    def test_plugin_instance_config_api_endpoint_mandatory(self):
        """A plugin instance must be constructed with a valid api_endpoint system_config key"""
        # Makes no sense to instantiate a Search plugin without an api endpoint url
        self.assertRaises(MisconfiguredError, self.PluginClass, {})
        self.assertRaises(MisconfiguredError, self.PluginClass, {'products': {'a': 'p1', 'b': 'p2'}})

        # When an api endpoint url is given in the configuration, it must be a valid url
        self.assertRaises(
            MisconfiguredError,
            self.PluginClass,
            {'api_endpoint': 'invalid_url'}
        )
        self.assertRaises(
            MisconfiguredError,
            self.PluginClass,
            {'api_endpoint': ''}
        )
        self.assertTrue(self.PluginClass({
            'api_endpoint': 'http://www.valid.dom/path/to/api'
        }))

    @unittest.skip('Does not belong to this set of tests')
    def test_config_plugin_name_ok(self):
        """Plugin name in system_config must be plugin class name"""
        instance = self.PluginClass({
            'plugin': 'SearchPlugin',
            'api_endpoint': 'http://www.valid.url/path/to/api'
        })
        self.assertEqual(instance.name, instance.config['plugin'])

    @unittest.skip('Does not belong to this set of tests')
    def test_config_plugin_exists(self):
        """Plugin key in system_config should be registered in plugin list"""
        instance = self.PluginClass({
            'plugin': 'SearchPlugin',
            'api_endpoint': 'http://www.valid.url/path/to/api'
        })
        self.assertIn(instance.config['plugin'], map(lambda pl: pl.name, Search.plugins))

