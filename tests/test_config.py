# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

import os
import sys
import tempfile
import unittest

import yaml.parser

from .context import config


VALID_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'resources', 'mock_providers.yml')
INVALID_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'resources', 'invalid_system_conf.yml')


class TestConfig(unittest.TestCase):

    @unittest.skipIf(sys.version_info.major > 2, 'No need to test unicode in Python 3')
    def test_valid_config_file_ok(self):
        """All strings in the configuration should be unicode"""
        config_tested = config.SimpleYamlProxyConfig(VALID_CONFIG_PATH)
        self.assertIsInstance(config_tested.source, dict)
        self._recursively_assert_unicode(config_tested.source)

    def test_config_dict_like_interface(self):
        """All config keys should be accessible like in a Python dict"""
        config_tested = config.SimpleYamlProxyConfig(VALID_CONFIG_PATH)
        self.assertTrue('mock-provider-9' in config_tested)
        with self.assertRaises(KeyError):
            _ = config_tested['NOTFOUND']
        self.assertIn(config_tested['mock-provider-9'], config_tested.values())
        self.assertIn(('mock-provider-9', config_tested['mock-provider-9']), config_tested.items())
        self.assertTrue([key for key in config_tested])

    def test_config_update(self):
        """Update method should only work with SimpleYamlProxyConfig objects"""
        config_tested = config.SimpleYamlProxyConfig(VALID_CONFIG_PATH)
        self.assertRaises(ValueError, config_tested.update, [])
        tmpfile = tempfile.NamedTemporaryFile(mode='w')
        yaml.dump({'instance-x': {}}, tmpfile)
        config_tested.update(config.SimpleYamlProxyConfig(conf_file_path=tmpfile.name))
        self.assertIn('instance-x', config_tested)

    def _recursively_assert_unicode(self, mapping):
        for key, value in mapping.items():
            if isinstance(value, dict):
                self._recursively_assert_unicode(value)
            elif isinstance(value, basestring):
                self.assertIsInstance(value, unicode)

    def test_invalid_config_file_raises_error(self):
        """An invalid yaml config file should raise an error"""
        self.assertRaises(yaml.parser.ParserError, config.SimpleYamlProxyConfig, INVALID_CONFIG_PATH)
