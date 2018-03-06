# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
import os
import sys
import unittest

import yaml.parser

from .context import config


VALID_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'resources', 'valid_system_conf.yml')
INVALID_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'resources', 'invalid_system_conf.yml')


class TestConfig(unittest.TestCase):

    @unittest.skipIf(sys.version_info.major > 2, 'No need to test unicode in Python 3')
    def test_valid_config_file_ok(self):
        """All strings in the configuration should be unicode"""
        config_tested = config.SimpleYamlProxyConfig(VALID_CONFIG_PATH)
        self.assertIsInstance(config_tested.source, dict)
        self._recursively_assert_unicode(config_tested.source)

    def _recursively_assert_unicode(self, mapping):
        for key, value in mapping.items():
            if isinstance(value, dict):
                self._recursively_assert_unicode(value)
            elif isinstance(value, basestring):
                self.assertIsInstance(value, unicode)

    def test_invalid_config_file_raises_error(self):
        """An invalid yaml config file should raise an error"""
        self.assertRaises(yaml.parser.ParserError, config.SimpleYamlProxyConfig, INVALID_CONFIG_PATH)
