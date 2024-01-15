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

import os
import tempfile
import unittest
from io import StringIO
from tempfile import TemporaryDirectory

import yaml.parser
from pkg_resources import resource_filename

from tests.context import (
    EXT_PRODUCT_TYPES_CONF_URI,
    HTTP_REQ_TIMEOUT,
    TEST_RESOURCES_PATH,
    USER_AGENT,
    EODataAccessGateway,
    ValidationError,
    config,
    get_ext_product_types_conf,
    load_stac_provider_config,
    merge_configs,
)
from tests.utils import mock


class TestProviderConfig(unittest.TestCase):
    def test_provider_config_name(self):
        """Name config parameter must be slugified"""
        unslugified_provider_name = "some $provider-name. Really ugly"
        slugified_provider_name = "some_provider_name_really_ugly"

        stream = StringIO(
            """!provider
            name: {}
            api: !plugin
                type: MyPluginClass
            products:
                EODAG_PRODUCT_TYPE: provider_product_type
            """.format(
                unslugified_provider_name
            )
        )
        provider_config = yaml.load(stream, Loader=yaml.Loader)
        self.assertEqual(provider_config.name, slugified_provider_name)

    def test_provider_config_valid(self):
        """Provider config must be valid"""
        # Not defining any plugin at all
        invalid_stream = StringIO("""!provider\nname: my_provider""")
        self.assertRaises(
            ValidationError, yaml.load, invalid_stream, Loader=yaml.Loader
        )

        # Not defining a class for a plugin
        invalid_stream = StringIO(
            """!provider
                name: my_provider
                search: !plugin
                    param: value
            """
        )
        self.assertRaises(
            ValidationError, yaml.load, invalid_stream, Loader=yaml.Loader
        )

        # Not giving a name to the provider
        invalid_stream = StringIO(
            """!provider
                api: !plugin
                    type: MyPluginClass
            """
        )
        self.assertRaises(
            ValidationError, yaml.load, invalid_stream, Loader=yaml.Loader
        )

        # Specifying an api plugin and a search or download or auth plugin at the same
        # type
        invalid_stream1 = StringIO(
            """!provider
                api: !plugin
                    type: MyPluginClass
                search: !plugin
                    type: MyPluginClass2
            """
        )
        invalid_stream2 = StringIO(
            """!provider
                api: !plugin
                    type: MyPluginClass
                download: !plugin
                    type: MyPluginClass3
            """
        )
        invalid_stream3 = StringIO(
            """!provider
                api: !plugin
                    type: MyPluginClass
                auth: !plugin
                    type: MyPluginClass4
            """
        )
        self.assertRaises(
            ValidationError, yaml.load, invalid_stream1, Loader=yaml.Loader
        )
        self.assertRaises(
            ValidationError, yaml.load, invalid_stream2, Loader=yaml.Loader
        )
        self.assertRaises(
            ValidationError, yaml.load, invalid_stream3, Loader=yaml.Loader
        )

    def test_provider_config_update(self):
        """A provider config must be update-able with a dict"""
        valid_stream = StringIO(
            """!provider
                name: provider
                provider_param: val
                api: !plugin
                    type: MyPluginClass
                    plugin_param1: value1
                    pluginParam2: value2
        """
        )
        provider_config = yaml.load(valid_stream, Loader=yaml.Loader)
        overrides = {
            "provider_param": "new val",
            "api": {"pluginparam2": "newVal", "newParam": "val"},
        }
        provider_config.update(overrides)
        self.assertEqual(provider_config.provider_param, "new val")
        self.assertEqual(provider_config.api.pluginParam2, "newVal")
        self.assertTrue(hasattr(provider_config.api, "newParam"))
        self.assertEqual(provider_config.api.newParam, "val")

    def test_provider_config_merge(self):
        """Merge 2 providers configs"""
        config_stream1 = StringIO(
            """!provider
                name: provider1
                provider_param: val
                provider_param2: val2
                api: !plugin
                    type: MyPluginClass
                    plugin_param1: value1
                    pluginParam2: value2
        """
        )
        config_stream2 = StringIO(
            """!provider
                name: provider1
                provider_param: val1
                provider_param3: val3
                api: !plugin
                    type: MyPluginClass
                    pluginParam2: value3
        """
        )
        provider_config1 = yaml.load(config_stream1, Loader=yaml.Loader)
        provider_config2 = yaml.load(config_stream2, Loader=yaml.Loader)

        providers_config = {
            "provider1": provider_config1,
            "provider2": provider_config1,
        }

        merge_configs(
            providers_config,
            {"provider1": provider_config2, "provider3": provider_config1},
        )
        self.assertEqual(len(providers_config), 3)
        self.assertEqual(providers_config["provider1"].provider_param, "val1")
        self.assertEqual(providers_config["provider1"].provider_param2, "val2")
        self.assertEqual(providers_config["provider1"].provider_param3, "val3")
        self.assertEqual(providers_config["provider1"].api.plugin_param1, "value1")
        self.assertEqual(providers_config["provider1"].api.pluginParam2, "value3")


class TestPluginConfig(unittest.TestCase):
    def test_plugin_config_valid(self):
        """A plugin config must specify a valid plugin type"""
        # A stream configuring a plugin without specifying the "type" key
        invalid_stream = StringIO(
            """!plugin
                    param: value
        """
        )
        self.assertRaises(
            ValidationError, yaml.load, invalid_stream, Loader=yaml.Loader
        )

        valid_stream = StringIO(
            """!plugin
                    type: MySearchPlugin
                    param1: value
        """
        )
        self.assertIsInstance(
            yaml.load(valid_stream, Loader=yaml.Loader), config.PluginConfig
        )

    def test_plugin_config_update(self):
        """A plugin config must be update-able by a dict"""
        valid_stream = StringIO(
            """!plugin
                    type: MyPluginClass
                    plugin_param1: value1
                    pluginParam2:
                        sub_param1: v1
                        subParam_2: v2
        """
        )
        plugin_config = yaml.load(valid_stream, Loader=yaml.Loader)
        overrides = {
            "type": "MyOtherPlugin",
            "new_plugin_param": "a value",
            "pluginparam2": {"sub_param1": "new_val1"},
        }
        plugin_config.update(overrides)
        self.assertEqual(plugin_config.type, "MyOtherPlugin")
        self.assertEqual(plugin_config.pluginParam2["sub_param1"], "new_val1")
        self.assertTrue(hasattr(plugin_config, "new_plugin_param"))
        self.assertEqual(plugin_config.new_plugin_param, "a value")


class TestConfigFunctions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestConfigFunctions, cls).setUpClass()
        # mock os.environ to empty env
        cls.mock_os_environ = mock.patch.dict(os.environ, {}, clear=True)
        cls.mock_os_environ.start()

    @classmethod
    def tearDownClass(cls):
        super(TestConfigFunctions, cls).tearDownClass()
        # stop os.environ
        cls.mock_os_environ.stop()

    def test_load_default_config(self):
        """Default config must be successfully loaded"""
        conf = config.load_default_config()
        self.assertIsInstance(conf, dict)
        for key, value in conf.items():
            # keys of the default conf dict are the names of the provider
            self.assertEqual(key, value.name)
            # providers implementing download or api store their downloaded products in
            # tempdir by default
            download_plugin = getattr(value, "download", getattr(value, "api", None))
            if download_plugin is not None:
                self.assertEqual(download_plugin.outputs_prefix, tempfile.gettempdir())
            # priority is set to 0 unless you are 'peps' provider
            if key == "peps":
                self.assertEqual(value.priority, 1)
            else:
                self.assertEqual(value.priority, 0)

    def test_override_config_from_str(self):
        """Default configuration must be overridden from a yaml conf str"""
        default_config = config.load_default_config()
        conf_update = yaml.safe_load(
            """
            my_new_provider:
                priority: 4
                search:
                    type: StacSearch
                    api_endpoint: https://api.my_new_provider/search
                products:
                    S2_MSI_L1C:
                        productType: sentinel2_l1c
                    GENERIC_PRODUCT_TYPE:
                        productType: '{productType}'
                download:
                    type: AwsDownload
                    base_uri: https://api.my_new_provider
                    flatten_top_dirs: True
                auth:
                    type: AwsAuth
                    credentials:
                        aws_access_key_id: access-key-id
                        aws_secret_access_key: secret-access-key
            """
        )
        config.override_config_from_mapping(default_config, conf_update)

        my_new_provider_conf = default_config["my_new_provider"]
        self.assertEqual(my_new_provider_conf.priority, 4)
        self.assertIsInstance(my_new_provider_conf.search, config.PluginConfig)
        self.assertEqual(
            my_new_provider_conf.products["S2_MSI_L1C"]["productType"], "sentinel2_l1c"
        )
        self.assertEqual(
            my_new_provider_conf.auth.credentials["aws_secret_access_key"],
            "secret-access-key",
        )

    def test_override_config_from_file(self):
        """Default configuration must be overridden from a conf file

        # noqa: E800
        Content of file_config_override.yml
        usgs:
          priority: 5
          api:
              extract: False
              credentials:
                  username: usr
                  password: pwd

        aws_eos:
          search:
              product_location_scheme: file
          auth:
              credentials:
                  apikey: api-key
                  aws_access_key_id: access-key-id
                  aws_secret_access_key: secret-access-key

        peps:
          download:
              outputs_prefix: /data

        theia:
            download:
                outputs_prefix:

        my_new_provider:
            priority: 4
            search:
                type: StacSearch
                api_endpoint: https://api.my_new_provider/search
            products:
                S2_MSI_L1C:
                  productType: sentinel2_l1c
                GENERIC_PRODUCT_TYPE:
                  productType: '{productType}'
            download:
                type: AwsDownload
                base_uri: https://api.my_new_provider
                flatten_top_dirs: True
            auth:
                type: AwsAuth
                credentials:
                  aws_access_key_id: access-key-id
                  aws_secret_access_key: secret-access-key
        """
        default_config = config.load_default_config()
        file_path_override = os.path.join(
            os.path.dirname(__file__), "resources", "file_config_override.yml"
        )

        config.override_config_from_file(default_config, file_path_override)
        usgs_conf = default_config["usgs"]
        self.assertEqual(usgs_conf.priority, 5)
        self.assertEqual(usgs_conf.api.extract, False)
        self.assertEqual(usgs_conf.api.credentials["username"], "usr")
        self.assertEqual(usgs_conf.api.credentials["password"], "pwd")

        aws_conf = default_config["aws_eos"]
        self.assertEqual(aws_conf.search.product_location_scheme, "file")
        self.assertEqual(aws_conf.auth.credentials["apikey"], "api-key")
        self.assertEqual(
            aws_conf.auth.credentials["aws_access_key_id"], "access-key-id"
        )
        self.assertEqual(
            aws_conf.auth.credentials["aws_secret_access_key"], "secret-access-key"
        )

        peps_conf = default_config["peps"]
        self.assertEqual(peps_conf.download.outputs_prefix, "/data")

        theia_conf = default_config["theia"]
        self.assertEqual(theia_conf.download.outputs_prefix, tempfile.gettempdir())

        my_new_provider_conf = default_config["my_new_provider"]
        self.assertEqual(my_new_provider_conf.priority, 4)
        self.assertIsInstance(my_new_provider_conf.search, config.PluginConfig)
        self.assertEqual(my_new_provider_conf.search.type, "StacSearch")
        self.assertEqual(
            my_new_provider_conf.search.api_endpoint,
            "https://api.my_new_provider/search",
        )
        self.assertIsInstance(my_new_provider_conf.products, dict)
        self.assertEqual(
            my_new_provider_conf.products["S2_MSI_L1C"]["productType"], "sentinel2_l1c"
        )
        self.assertEqual(
            my_new_provider_conf.products["GENERIC_PRODUCT_TYPE"]["productType"],
            "{productType}",
        )
        self.assertIsInstance(my_new_provider_conf.download, config.PluginConfig)
        self.assertEqual(my_new_provider_conf.download.type, "AwsDownload")
        self.assertEqual(
            my_new_provider_conf.download.base_uri, "https://api.my_new_provider"
        )
        self.assertTrue(my_new_provider_conf.download.flatten_top_dirs)
        self.assertIsInstance(my_new_provider_conf.auth, config.PluginConfig)
        self.assertEqual(my_new_provider_conf.auth.type, "AwsAuth")
        self.assertEqual(
            my_new_provider_conf.auth.credentials["aws_access_key_id"], "access-key-id"
        )
        self.assertEqual(
            my_new_provider_conf.auth.credentials["aws_secret_access_key"],
            "secret-access-key",
        )

    def test_override_config_from_env(self):
        """Default configuration must be overridden by environment variables"""
        default_config = config.load_default_config()
        os.environ["EODAG__USGS__PRIORITY"] = "5"
        os.environ["EODAG__USGS__API__EXTRACT"] = "false"
        os.environ["EODAG__USGS__API__CREDENTIALS__USERNAME"] = "usr"
        os.environ["EODAG__USGS__API__CREDENTIALS__PASSWORD"] = "pwd"
        os.environ["EODAG__AWS_EOS__SEARCH__PRODUCT_LOCATION_SCHEME"] = "file"
        os.environ["EODAG__AWS_EOS__AUTH__CREDENTIALS__APIKEY"] = "api-key"
        os.environ[
            "EODAG__AWS_EOS__AUTH__CREDENTIALS__AWS_ACCESS_KEY_ID"
        ] = "access-key-id"
        os.environ[
            "EODAG__AWS_EOS__AUTH__CREDENTIALS__AWS_SECRET_ACCESS_KEY"
        ] = "secret-access-key"
        os.environ["EODAG__PEPS__DOWNLOAD__OUTPUTS_PREFIX"] = "/data"
        # check a parameter that has not been set yet
        self.assertFalse(hasattr(default_config["peps"].search, "timeout"))
        self.assertNotIn("start_page", default_config["peps"].search.pagination)
        os.environ["EODAG__PEPS__SEARCH__TIMEOUT"] = "3.1"
        os.environ["EODAG__PEPS__SEARCH__PAGINATION__START_PAGE"] = "2"

        config.override_config_from_env(default_config)
        usgs_conf = default_config["usgs"]
        self.assertEqual(usgs_conf.priority, 5)
        self.assertEqual(usgs_conf.api.extract, False)
        self.assertEqual(usgs_conf.api.credentials["username"], "usr")
        self.assertEqual(usgs_conf.api.credentials["password"], "pwd")

        aws_conf = default_config["aws_eos"]
        self.assertEqual(aws_conf.search.product_location_scheme, "file")
        self.assertEqual(aws_conf.auth.credentials["apikey"], "api-key")
        self.assertEqual(
            aws_conf.auth.credentials["aws_access_key_id"], "access-key-id"
        )
        self.assertEqual(
            aws_conf.auth.credentials["aws_secret_access_key"], "secret-access-key"
        )

        peps_conf = default_config["peps"]
        self.assertEqual(peps_conf.download.outputs_prefix, "/data")
        self.assertEqual(peps_conf.search.timeout, 3.1)
        self.assertEqual(peps_conf.search.pagination["start_page"], 2)

    @mock.patch("requests.get", autospec=True)
    def test_get_ext_product_types_conf(self, mock_get):
        """External product types configuration must be loadable from remote or local file"""
        ext_product_types_path = os.path.join(
            TEST_RESOURCES_PATH, "ext_product_types.json"
        )

        # mock get request response for remote conf file (default value)
        mock_get.return_value = mock.Mock()
        mock_get.return_value.json.return_value = {"some_parameter": "a_value"}

        ext_product_types_conf = get_ext_product_types_conf()
        mock_get.assert_called_once_with(
            EXT_PRODUCT_TYPES_CONF_URI, headers=USER_AGENT, timeout=HTTP_REQ_TIMEOUT
        )
        self.assertEqual(ext_product_types_conf, {"some_parameter": "a_value"})

        # local conf file
        ext_product_types_conf = get_ext_product_types_conf(ext_product_types_path)
        self.assertIsInstance(ext_product_types_conf, dict)
        self.assertIn("foo", ext_product_types_conf["astraea_eod"]["providers_config"])


class TestStacProviderConfig(unittest.TestCase):
    def setUp(self):
        super(TestStacProviderConfig, self).setUp()
        # Mock home and eodag conf directory to tmp dir
        self.tmp_home_dir = TemporaryDirectory()
        self.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, return_value=self.tmp_home_dir.name
        )
        self.expanduser_mock.start()

        self.dag = EODataAccessGateway()

    def tearDown(self):
        super(TestStacProviderConfig, self).tearDown()
        # stop Mock and remove tmp config dir
        self.expanduser_mock.stop()
        self.tmp_home_dir.cleanup()

    def test_existing_stac_provider_conf(self):
        """Existing / pre-configured STAC providers conf should mix providers.yml and  stac_provider.yml infos."""
        with open(resource_filename("eodag", "resources/providers.yml"), "r") as fh:
            providers_configs = {
                p.name: p for p in yaml.load_all(fh, Loader=yaml.Loader)
            }

        raw_provider_search_conf = providers_configs["usgs_satapi_aws"].search.__dict__
        common_stac_provider_search_conf = load_stac_provider_config()["search"]
        provider_search_conf = self.dag.providers_config[
            "usgs_satapi_aws"
        ].search.__dict__

        # conf existing in common (stac_provider.yml) and not in raw_provider (providers.yml)
        self.assertIn(
            "resolution", common_stac_provider_search_conf["metadata_mapping"]
        )
        self.assertNotIn("resolution", raw_provider_search_conf["metadata_mapping"])
        self.assertIn("resolution", provider_search_conf["metadata_mapping"])

        self.assertIn("discover_metadata", common_stac_provider_search_conf)
        self.assertNotIn("discover_metadata", raw_provider_search_conf)
        self.assertIn("discover_metadata", provider_search_conf)

        # raw_provider conf (providers.yml) should overwrite common conf (stac_provider.yml)
        self.assertEqual(
            raw_provider_search_conf["metadata_mapping"]["assets"],
            provider_search_conf["metadata_mapping"]["assets"],
        )
        self.assertNotEqual(
            common_stac_provider_search_conf["metadata_mapping"]["assets"],
            provider_search_conf["metadata_mapping"]["assets"],
        )

        # check if raw_provider_search_conf is a subset of provider_search_conf
        for k, v in raw_provider_search_conf.items():
            if isinstance(v, dict):
                assert (
                    raw_provider_search_conf[k].items()
                    <= provider_search_conf[k].items()
                )
            else:
                self.assertEqual(v, provider_search_conf[k])

    def test_custom_stac_provider_conf(self):
        """Custom STAC providers conf should mix providers.yml and stac_provider.yml infos."""
        custom_stac_provider_conf_yml = """
            foo:
                search:
                    type: StacSearch
                    api_endpoint: https://foo.bar/search
                    metadata_mapping:
                        title: '$.properties."foo:bar_baz"'
                products:
                    GENERIC_PRODUCT_TYPE:
                        productType: '{productType}'
                download:
                    type: HTTPDownload
                    base_uri: https://foo.bar
        """
        self.dag.update_providers_config(custom_stac_provider_conf_yml)
        custom_stac_provider_conf = yaml.safe_load(custom_stac_provider_conf_yml)[
            "foo"
        ]["search"]

        common_stac_provider_search_conf = load_stac_provider_config()["search"]
        provider_search_conf = self.dag.providers_config["foo"].search.__dict__

        # conf existing in common (stac_provider.yml) and not in raw_provider (providers.yml)
        self.assertIn(
            "resolution", common_stac_provider_search_conf["metadata_mapping"]
        )
        self.assertNotIn("resolution", custom_stac_provider_conf["metadata_mapping"])
        self.assertIn("resolution", provider_search_conf["metadata_mapping"])

        self.assertIn("discover_metadata", common_stac_provider_search_conf)
        self.assertNotIn("discover_metadata", custom_stac_provider_conf)
        self.assertIn("discover_metadata", provider_search_conf)

        # raw_provider conf (providers.yml) should overwrite common conf (stac_provider.yml)
        self.assertEqual(
            custom_stac_provider_conf["metadata_mapping"]["title"],
            provider_search_conf["metadata_mapping"]["title"],
        )
        self.assertNotEqual(
            common_stac_provider_search_conf["metadata_mapping"]["title"],
            provider_search_conf["metadata_mapping"]["title"],
        )

        # check if custom_stac_provider_conf is a subset of provider_search_conf
        for k, v in custom_stac_provider_conf.items():
            if isinstance(v, dict):
                assert (
                    custom_stac_provider_conf[k].items()
                    <= provider_search_conf[k].items()
                )
            else:
                self.assertEqual(v, provider_search_conf[k])
