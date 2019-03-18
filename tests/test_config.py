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
from __future__ import unicode_literals

import os
import tempfile
import unittest

import yaml.parser
from six import StringIO

from tests.context import ValidationError, config


class TestProviderConfig(unittest.TestCase):

    def test_provider_config_name(self):
        """Name config parameter must be slugified"""
        unslugified_provider_name = 'some $provider-name. Really ugly'
        slugified_provider_name = 'some_provider_name_really_ugly'

        stream = StringIO(
            '''!provider
            name: {}
            api: !plugin
                type: MyPluginClass
            products:
                EODAG_PRODUCT_TYPE: provider_product_type
            '''.format(unslugified_provider_name)
        )
        provider_config = yaml.load(stream, Loader=yaml.Loader)
        self.assertEqual(provider_config.name, slugified_provider_name)

    def test_provider_config_valid(self):
        """Provider config must be valid"""
        # Not defining any plugin at all
        invalid_stream = StringIO('''!provider\nname: my_provider''')
        self.assertRaises(ValidationError, yaml.load, invalid_stream, Loader=yaml.Loader)

        # Not defining a class for a plugin
        invalid_stream = StringIO(
            '''!provider
                name: my_provider
                search: !plugin
                    param: value
            ''')
        self.assertRaises(ValidationError, yaml.load, invalid_stream, Loader=yaml.Loader)

        # Not giving a name to the provider
        invalid_stream = StringIO(
            '''!provider
                api: !plugin
                    type: MyPluginClass
            ''')
        self.assertRaises(ValidationError, yaml.load, invalid_stream, Loader=yaml.Loader)

        # Specifying an api plugin and a search or download or auth plugin at the same type
        invalid_stream1 = StringIO(
            '''!provider
                api: !plugin
                    type: MyPluginClass
                search: !plugin
                    type: MyPluginClass2
            ''')
        invalid_stream2 = StringIO(
            '''!provider
                api: !plugin
                    type: MyPluginClass
                download: !plugin
                    type: MyPluginClass3
            ''')
        invalid_stream3 = StringIO(
            '''!provider
                api: !plugin
                    type: MyPluginClass
                auth: !plugin
                    type: MyPluginClass4
            ''')
        self.assertRaises(ValidationError, yaml.load, invalid_stream1, Loader=yaml.Loader)
        self.assertRaises(ValidationError, yaml.load, invalid_stream2, Loader=yaml.Loader)
        self.assertRaises(ValidationError, yaml.load, invalid_stream3, Loader=yaml.Loader)

    def test_provider_config_update(self):
        """A provider config must be update-able with a dict"""
        valid_stream = StringIO(
            '''!provider
                name: provider
                provider_param: val
                api: !plugin
                    type: MyPluginClass
                    plugin_param1: value1
                    pluginParam2: value2
        ''')
        provider_config = yaml.load(valid_stream, Loader=yaml.Loader)
        overrides = {
            'provider_param': 'new val',
            'api': {
                'pluginparam2': 'newVal',
                'newParam': 'val'
            }
        }
        provider_config.update(overrides)
        self.assertEqual(provider_config.provider_param, 'new val')
        self.assertEqual(provider_config.api.pluginParam2, 'newVal')
        self.assertTrue(hasattr(provider_config.api, 'newParam'))
        self.assertEqual(provider_config.api.newParam, 'val')


class TestPluginConfig(unittest.TestCase):

    def test_plugin_config_valid(self):
        """A plugin config must specify a valid plugin type"""
        # A stream configuring a plugin without specifying the "type" key
        invalid_stream = StringIO(
            '''!plugin
                    param: value
        ''')
        self.assertRaises(ValidationError, yaml.load, invalid_stream, Loader=yaml.Loader)

        valid_stream = StringIO(
            '''!plugin
                    type: MySearchPlugin
                    param1: value
        ''')
        self.assertIsInstance(yaml.load(valid_stream, Loader=yaml.Loader), config.PluginConfig)

    def test_plugin_config_update(self):
        """A plugin config must be update-able by a dict"""
        valid_stream = StringIO(
            '''!plugin
                    type: MyPluginClass
                    plugin_param1: value1
                    pluginParam2:
                        sub_param1: v1
                        subParam_2: v2
        ''')
        plugin_config = yaml.load(valid_stream, Loader=yaml.Loader)
        overrides = {
            'type': 'MyOtherPlugin',
            'new_plugin_param': 'a value',
            'pluginparam2': {
                'sub_param1': 'new_val1'
            }
        }
        plugin_config.update(overrides)
        self.assertEqual(plugin_config.type, 'MyOtherPlugin')
        self.assertEqual(plugin_config.pluginParam2['sub_param1'], 'new_val1')
        self.assertTrue(hasattr(plugin_config, 'new_plugin_param'))
        self.assertEqual(plugin_config.new_plugin_param, 'a value')


class TestConfigFunctions(unittest.TestCase):

    def test_load_default_config(self):
        """Default config must be successfully loaded"""
        conf = config.load_default_config()
        self.assertIsInstance(conf, dict)
        for key, value in conf.items():
            # keys of the default conf dict are the names of the provider
            self.assertEqual(key, value.name)
            # providers implementing download or api store their downloaded products in tempdir by default
            download_plugin = getattr(value, 'download', getattr(value, 'api', None))
            if download_plugin is not None:
                self.assertEqual(download_plugin.outputs_prefix, tempfile.gettempdir())
            # priority is set to 0 unless you are 'peps' provider
            if key == 'peps':
                self.assertEqual(value.priority, 1)
            else:
                self.assertEqual(value.priority, 0)

    def test_override_config_from_file(self):
        """Default configuration must be overridden from a conf file"""
        default_config = config.load_default_config()
        file_path_override = os.path.join(os.path.dirname(__file__), 'resources', 'file_config_override.yml')
        # Content of file_config_override.yml
        # usgs:
        #   priority: 5
        #   api:
        #       extract: False
        #       credentials:
        #           username: usr
        #           password: pwd
        #
        # aws_s3_sentinel2_l1c:
        #   search:
        #       product_location_scheme: file
        #   auth:
        #       credentials:
        #           aws_access_key_id: access-key-id
        #           aws_secret_access_key: secret-access-key
        #
        # peps:
        #   download:
        #       outputs_prefix: /data
        config.override_config_from_file(default_config, file_path_override)
        usgs_conf = default_config['usgs']
        self.assertEqual(usgs_conf.priority, 5)
        self.assertEqual(usgs_conf.api.extract, False)
        self.assertEqual(usgs_conf.api.credentials['username'], 'usr')
        self.assertEqual(usgs_conf.api.credentials['password'], 'pwd')

        aws_conf = default_config['aws_s3_sentinel2_l1c']
        self.assertEqual(aws_conf.search.product_location_scheme, 'file')
        self.assertEqual(aws_conf.auth.credentials['aws_access_key_id'], 'access-key-id')
        self.assertEqual(aws_conf.auth.credentials['aws_secret_access_key'], 'secret-access-key')

        peps_conf = default_config['peps']
        self.assertEqual(peps_conf.download.outputs_prefix, '/data')

    def test_override_config_from_env(self):
        """Default configuration must be overridden by environment variables"""
        default_config = config.load_default_config()
        os.environ['EODAG__USGS__PRIORITY'] = '5'
        os.environ['EODAG__USGS__API__EXTRACT'] = 'false'
        os.environ['EODAG__USGS__API__CREDENTIALS__USERNAME'] = 'usr'
        os.environ['EODAG__USGS__API__CREDENTIALS__PASSWORD'] = 'pwd'
        os.environ['EODAG__AWS_S3_SENTINEL2_L1C__SEARCH__PRODUCT_LOCATION_SCHEME'] = 'file'
        os.environ['EODAG__AWS_S3_SENTINEL2_L1C__AUTH__CREDENTIALS__AWS_ACCESS_KEY_ID'] = 'access-key-id'
        os.environ['EODAG__AWS_S3_SENTINEL2_L1C__AUTH__CREDENTIALS__AWS_SECRET_ACCESS_KEY'] = 'secret-access-key'
        os.environ['EODAG__PEPS__DOWNLOAD__OUTPUTS_PREFIX'] = '/data'

        config.override_config_from_env(default_config)
        usgs_conf = default_config['usgs']
        self.assertEqual(usgs_conf.priority, 5)
        self.assertEqual(usgs_conf.api.extract, False)
        self.assertEqual(usgs_conf.api.credentials['username'], 'usr')
        self.assertEqual(usgs_conf.api.credentials['password'], 'pwd')

        aws_conf = default_config['aws_s3_sentinel2_l1c']
        self.assertEqual(aws_conf.search.product_location_scheme, 'file')
        self.assertEqual(aws_conf.auth.credentials['aws_access_key_id'], 'access-key-id')
        self.assertEqual(aws_conf.auth.credentials['aws_secret_access_key'], 'secret-access-key')

        peps_conf = default_config['peps']
        self.assertEqual(peps_conf.download.outputs_prefix, '/data')
