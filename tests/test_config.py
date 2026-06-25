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
from importlib.resources import files as res_files
from tempfile import TemporaryDirectory

import pytest
import yaml

from eodag.config import (
    PluginConfig,
    ProviderConfig,
    _has_matching_external_auth,
    _parse_env_provider_configs,
    build_provider_configs,
    disable_providers,
    merge_provider_configs,
)
from eodag.databases.sqlite import SQLiteDatabase
from eodag.utils import deepcopy
from eodag.utils.yaml import LegacyAwareLoader
from tests.context import (
    EXT_COLLECTIONS_CONF_URI,
    HTTP_REQ_TIMEOUT,
    TEST_RESOURCES_PATH,
    USER_AGENT,
    EODataAccessGateway,
    ValidationError,
    config,
    get_ext_collections_conf,
    load_stac_provider_config,
    mock,
)


def load_provider_config_from_string(yaml_string: str) -> ProviderConfig:
    """Load a provider config from a YAML string using legacy-aware YAML tags."""
    with pytest.warns(
        FutureWarning,
        match=r".*deprecated YAML tag '!(provider|plugin)'.*",
    ):
        data = yaml.load(StringIO(yaml_string), Loader=LegacyAwareLoader)
    mapping = data.__dict__ if isinstance(data, ProviderConfig) else data
    return ProviderConfig.from_mapping(mapping)


def load_plugin_config_from_string(yaml_string: str) -> PluginConfig:
    """Load a plugin config from a YAML string using legacy-aware YAML tags."""
    with pytest.warns(
        FutureWarning,
        match=r".*deprecated YAML tag '!plugin'.*",
    ):
        data = yaml.load(StringIO(yaml_string), Loader=LegacyAwareLoader)
    mapping = data.__dict__ if isinstance(data, PluginConfig) else data
    return PluginConfig.from_mapping(mapping)


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
                EODAG_COLLECTION: provider_collection
            """.format(
                unslugified_provider_name
            )
        )
        provider_config = load_provider_config_from_string(stream.getvalue())
        self.assertEqual(provider_config.name, slugified_provider_name)

    def test_provider_config_valid(self):
        """Provider config must be valid"""
        # Not defining any plugin at all
        invalid_stream = StringIO("""!provider\nname: my_provider""")
        self.assertRaises(
            ValidationError, load_provider_config_from_string, invalid_stream.getvalue()
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
            ValidationError, load_provider_config_from_string, invalid_stream.getvalue()
        )

        # Not giving a name to the provider
        invalid_stream = StringIO(
            """!provider
                api: !plugin
                    type: MyPluginClass
            """
        )
        self.assertRaises(
            ValidationError, load_provider_config_from_string, invalid_stream.getvalue()
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
            ValidationError,
            load_provider_config_from_string,
            invalid_stream1.getvalue(),
        )
        self.assertRaises(
            ValidationError,
            load_provider_config_from_string,
            invalid_stream2.getvalue(),
        )
        self.assertRaises(
            ValidationError,
            load_provider_config_from_string,
            invalid_stream3.getvalue(),
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
        provider_config = load_provider_config_from_string(valid_stream.getvalue())
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
        provider1_config1 = load_provider_config_from_string(config_stream1.getvalue())
        provider1_config2 = load_provider_config_from_string(config_stream2.getvalue())

        provider2_config1 = deepcopy(provider1_config1.__dict__)
        provider2_config1.update({"name": "provider2"})

        provider3_config1 = deepcopy(provider1_config1.__dict__)
        provider3_config1.update({"name": "provider3"})

        providers = build_provider_configs(
            {
                "provider1": provider1_config1,
                "provider2": provider2_config1,
            }
        )

        merge_provider_configs(
            providers,
            {
                "provider1": provider1_config2,
                "provider3": provider3_config1,
            },
        )

        self.assertEqual(len(providers), 3)
        self.assertEqual(providers["provider1"].provider_param, "val1")
        self.assertEqual(providers["provider1"].provider_param2, "val2")
        self.assertEqual(providers["provider1"].provider_param3, "val3")
        self.assertEqual(providers["provider1"].api.plugin_param1, "value1")
        self.assertEqual(providers["provider1"].api.pluginParam2, "value3")


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
            ValidationError, load_plugin_config_from_string, invalid_stream.getvalue()
        )

        valid_stream = StringIO(
            """!plugin
                    type: MySearchPlugin
                    param1: value
        """
        )
        self.assertIsInstance(
            load_plugin_config_from_string(valid_stream.getvalue()), PluginConfig
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
        plugin_config = load_plugin_config_from_string(valid_stream.getvalue())
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
                self.assertEqual(download_plugin.output_dir, tempfile.gettempdir())
            # priority is set to 0 for all providers
            self.assertEqual(value.priority, 0)

    def test_load_config_providers_whitelist(self):
        """Config must be loaded with only the selected whitelist of providers"""
        try:
            os.environ["EODAG_PROVIDERS_WHITELIST"] = "creodias"
            providers = build_provider_configs(config.load_default_config())

            self.assertEqual({"creodias"}, set(providers.keys()))
        finally:
            os.environ.pop("EODAG_PROVIDERS_WHITELIST", None)

    def test_override_config_from_str(self):
        """Default configuration must be overridden from a yaml conf str"""

        providers = build_provider_configs(config.load_default_config())
        merge_provider_configs(
            providers,
            yaml.safe_load(
                """
                my_new_provider:
                    priority: 4
                    search:
                        type: StacSearch
                        api_endpoint: https://api.my_new_provider/search
                    products:
                        S2_MSI_L1C:
                            _collection: sentinel2_l1c
                        GENERIC_COLLECTION:
                            _collection: '{collection}'
                    download:
                        type: AwsDownload
                        s3_endpoint: https://api.my_new_provider
                    auth:
                        type: AwsAuth
                        credentials:
                            aws_access_key_id: access-key-id
                            aws_secret_access_key: secret-access-key
                """
            ),
        )

        my_new_provider_conf = providers["my_new_provider"]
        self.assertEqual(my_new_provider_conf.priority, 4)
        self.assertIsInstance(my_new_provider_conf.search, PluginConfig)
        self.assertEqual(
            my_new_provider_conf.products["S2_MSI_L1C"]["_collection"], "sentinel2_l1c"
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
          search_auth:
              credentials:
                  apikey: api-key
          download_auth:
              credentials:
                  aws_access_key_id: access-key-id
                  aws_secret_access_key: secret-access-key

        cop_dataspace:
          download:
              output_dir: /data

        my_new_provider:
            priority: 4
            search:
                type: StacSearch
                api_endpoint: https://api.my_new_provider/search
            products:
                S2_MSI_L1C:
                  _collection: sentinel2_l1c
                GENERIC_COLLECTION:
                  _collection: '{collection}'
            download:
                type: AwsDownload
                s3_endpoint: https://api.my_new_provider
                flatten_top_dirs: false
            auth:
                type: AwsAuth
                credentials:
                  aws_access_key_id: access-key-id
                  aws_secret_access_key: secret-access-key
        """
        providers = build_provider_configs(config.load_default_config())
        file_path_override = os.path.join(
            os.path.dirname(__file__), "resources", "file_config_override.yml"
        )
        with open(file_path_override) as fh:
            merge_provider_configs(providers, yaml.safe_load(fh))

        usgs_conf = providers["usgs"]
        self.assertEqual(usgs_conf.priority, 5)
        self.assertEqual(usgs_conf.api.extract, False)
        self.assertEqual(usgs_conf.api.credentials["username"], "usr")
        self.assertEqual(usgs_conf.api.credentials["password"], "pwd")

        aws_conf = providers["aws_eos"]
        self.assertEqual(aws_conf.search.product_location_scheme, "file")
        self.assertEqual(aws_conf.search_auth.credentials["apikey"], "api-key")
        self.assertEqual(
            aws_conf.download_auth.credentials["aws_access_key_id"], "access-key-id"
        )
        self.assertEqual(
            aws_conf.download_auth.credentials["aws_secret_access_key"],
            "secret-access-key",
        )

        cop_dataspace_conf = providers["cop_dataspace"]
        self.assertEqual(cop_dataspace_conf.download.output_dir, "/data")

        my_new_provider_conf = providers["my_new_provider"]
        self.assertEqual(my_new_provider_conf.priority, 4)
        self.assertIsInstance(my_new_provider_conf.search, PluginConfig)
        self.assertEqual(my_new_provider_conf.search.type, "StacSearch")
        self.assertEqual(
            my_new_provider_conf.search.api_endpoint,
            "https://api.my_new_provider/search",
        )
        self.assertIsInstance(my_new_provider_conf.products, dict)
        self.assertEqual(
            my_new_provider_conf.products["S2_MSI_L1C"]["_collection"], "sentinel2_l1c"
        )
        self.assertEqual(
            my_new_provider_conf.products["GENERIC_COLLECTION"]["_collection"],
            "{collection}",
        )
        self.assertIsInstance(my_new_provider_conf.download, PluginConfig)
        self.assertEqual(my_new_provider_conf.download.type, "AwsDownload")
        self.assertEqual(
            my_new_provider_conf.download.s3_endpoint, "https://api.my_new_provider"
        )
        self.assertFalse(my_new_provider_conf.download.flatten_top_dirs)
        self.assertIsInstance(my_new_provider_conf.auth, PluginConfig)
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
        providers = build_provider_configs(config.load_default_config())
        os.environ["EODAG__USGS__PRIORITY"] = "5"
        os.environ["EODAG__USGS__API__EXTRACT"] = "false"
        os.environ["EODAG__USGS__API__CREDENTIALS__USERNAME"] = "usr"
        os.environ["EODAG__USGS__API__CREDENTIALS__PASSWORD"] = "pwd"
        os.environ["EODAG__AWS_EOS__SEARCH__PRODUCT_LOCATION_SCHEME"] = "file"
        os.environ["EODAG__AWS_EOS__SEARCH_AUTH__CREDENTIALS__APIKEY"] = "api-key"
        os.environ[
            "EODAG__AWS_EOS__DOWNLOAD_AUTH__CREDENTIALS__AWS_ACCESS_KEY_ID"
        ] = "access-key-id"
        os.environ[
            "EODAG__AWS_EOS__DOWNLOAD_AUTH__CREDENTIALS__AWS_SECRET_ACCESS_KEY"
        ] = "secret-access-key"
        os.environ["EODAG__COP_DATASPACE__DOWNLOAD__OUTPUT_DIR"] = "/data"
        # check a parameter that has not been set yet
        self.assertNotIn("start_page", providers["cop_dataspace"].search.pagination)
        os.environ["EODAG__COP_DATASPACE__SEARCH__PAGINATION__START_PAGE"] = "2"

        merge_provider_configs(providers, _parse_env_provider_configs())
        usgs_conf = providers["usgs"]
        self.assertEqual(usgs_conf.priority, 5)
        self.assertEqual(usgs_conf.api.extract, False)
        self.assertEqual(usgs_conf.api.credentials["username"], "usr")
        self.assertEqual(usgs_conf.api.credentials["password"], "pwd")

        aws_conf = providers["aws_eos"]
        self.assertEqual(aws_conf.search.product_location_scheme, "file")
        self.assertEqual(aws_conf.search_auth.credentials["apikey"], "api-key")
        self.assertEqual(
            aws_conf.download_auth.credentials["aws_access_key_id"], "access-key-id"
        )
        self.assertEqual(
            aws_conf.download_auth.credentials["aws_secret_access_key"],
            "secret-access-key",
        )

        cop_dataspace_conf = providers["cop_dataspace"]
        self.assertEqual(cop_dataspace_conf.download.output_dir, "/data")
        self.assertEqual(cop_dataspace_conf.search.pagination["start_page"], 2)

    @mock.patch("requests.get", autospec=True)
    def test_get_ext_collections_conf(self, mock_get):
        """External collections configuration must be loadable from remote or local file"""
        ext_collections_path = os.path.join(TEST_RESOURCES_PATH, "ext_collections.json")

        # mock get request response for remote conf file (default value)
        mock_get.return_value = mock.Mock()
        mock_get.return_value.json.return_value = {"some_parameter": "a_value"}

        ext_collections_conf = get_ext_collections_conf()
        mock_get.assert_called_once_with(
            EXT_COLLECTIONS_CONF_URI, headers=USER_AGENT, timeout=HTTP_REQ_TIMEOUT
        )
        self.assertEqual(ext_collections_conf, {"some_parameter": "a_value"})

        # local conf file
        ext_collections_conf = get_ext_collections_conf(ext_collections_path)
        self.assertIsInstance(ext_collections_conf, dict)
        self.assertIn("foo", ext_collections_conf["earth_search"]["providers_config"])


class TestStacProviderConfig(unittest.TestCase):
    def setUp(self):
        super().setUp()
        # Mock home and eodag conf directory to tmp dir
        self.tmp_home_dir = TemporaryDirectory()
        self.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, return_value=self.tmp_home_dir.name
        )
        self.expanduser_mock.start()
        # Use in-memory SQLite DB for faster tests
        self.sqlite_mock = mock.patch(
            "eodag.api.core.SQLiteDatabase",
            side_effect=lambda db_path: SQLiteDatabase(":memory:"),
        )
        self.sqlite_mock.start()

        self.dag = EODataAccessGateway()

    def tearDown(self):
        super().tearDown()
        # stop Mock and remove tmp config dir
        self.expanduser_mock.stop()
        self.sqlite_mock.stop()
        self.tmp_home_dir.cleanup()

    def test_existing_stac_provider_conf(self):
        """Existing / pre-configured STAC providers conf should mix providers.yml and  stac_provider.yml infos."""
        # Load raw provider configs (without stac_provider.yml defaults applied).
        with mock.patch(
            "eodag.config.ProviderConfig._finalize",
            lambda self: None,
        ):
            providers_configs = config.load_default_config()

        raw_provider_search_conf = providers_configs["usgs_satapi_aws"].search.__dict__
        common_stac_provider_search_conf = load_stac_provider_config()["search"]
        provider_search_conf = self.dag.db.get_fb_config("usgs_satapi_aws")["search"]

        # conf existing in common (stac_provider.yml) and not in raw_provider (providers.yml)
        self.assertIn("gsd", common_stac_provider_search_conf["metadata_mapping"])
        self.assertNotIn("gsd", raw_provider_search_conf["metadata_mapping"])
        self.assertIn("gsd", provider_search_conf["metadata_mapping"])

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
                    GENERIC_COLLECTION:
                        _collection: '{collection}'
                download:
                    type: HTTPDownload
                    base_uri: https://foo.bar
        """
        self.dag.update_providers_config(custom_stac_provider_conf_yml)
        custom_stac_provider_conf = yaml.safe_load(custom_stac_provider_conf_yml)[
            "foo"
        ]["search"]

        common_stac_provider_search_conf = load_stac_provider_config()["search"]
        provider_search_conf = self.dag.db.get_fb_config("foo")["search"]

        # conf existing in common (stac_provider.yml) and not in raw_provider (providers.yml)
        self.assertIn("gsd", common_stac_provider_search_conf["metadata_mapping"])
        self.assertNotIn("gsd", custom_stac_provider_conf["metadata_mapping"])
        self.assertIn("gsd", provider_search_conf["metadata_mapping"])

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


class TestDisableProviders(unittest.TestCase):
    """Integration tests for :func:`~eodag.config.disable_providers` that verify
    provider disabling behaviour during :class:`EODataAccessGateway` initialisation."""

    def setUp(self):
        super().setUp()
        self.tmp_home_dir = TemporaryDirectory()
        self.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, return_value=self.tmp_home_dir.name
        )
        self.expanduser_mock.start()
        # Use in-memory SQLite DB for faster tests
        self.sqlite_mock = mock.patch(
            "eodag.api.core.SQLiteDatabase",
            side_effect=lambda db_path: SQLiteDatabase(":memory:"),
        )
        self.sqlite_mock.start()
        self.dag = EODataAccessGateway()
        self.mock_os_environ = mock.patch.dict(os.environ, {}, clear=True)
        self.mock_os_environ.start()

    def tearDown(self):
        super().tearDown()
        self.mock_os_environ.stop()
        self.expanduser_mock.stop()
        self.sqlite_mock.stop()
        self.tmp_home_dir.cleanup()

    def test_disable_providers(self):
        """Providers needing auth for search but without credentials must be disabled on init"""
        empty_conf_file = str(
            res_files("eodag") / "resources" / "user_conf_template.yml"
        )
        try:
            # Default conf: no auth needed for search
            dag = EODataAccessGateway(user_conf_file_path=empty_conf_file)
            assert not dag.db.get_fb_config("sara")["search"].get("need_auth", False)

            # auth needed for search without credentials
            os.environ["EODAG__SARA__SEARCH__NEED_AUTH"] = "true"
            dag = EODataAccessGateway(user_conf_file_path=empty_conf_file)
            assert "sara" not in dag.providers.names

            # auth needed for search with credentials
            os.environ["EODAG__SARA__SEARCH__NEED_AUTH"] = "true"
            os.environ["EODAG__SARA__AUTH__CREDENTIALS__USERNAME"] = "foo"
            dag = EODataAccessGateway(user_conf_file_path=empty_conf_file)
            assert "sara" in dag.providers.names
            assert dag.db.get_fb_config("sara")["search"].get("need_auth", False)

        # Teardown
        finally:
            os.environ.pop("EODAG__SARA__SEARCH__NEED_AUTH", None)
            os.environ.pop("EODAG__SARA__AUTH__CREDENTIALS__USERNAME", None)

    @mock.patch("eodag.plugins.manager.importlib_metadata.entry_points", autospec=True)
    def test_disable_providers_skipped_plugin(self, mock_iter_ep):
        """Providers needing skipped plugin must be disabled on init"""
        empty_conf_file = str(
            res_files("eodag") / "resources" / "user_conf_template.yml"
        )

        def skip_qssearch(group):
            ep = mock.MagicMock()
            if group == "eodag.plugins.search":
                ep.name = "QueryStringSearch"
                ep.load = mock.MagicMock(side_effect=ModuleNotFoundError())
            return [ep]

        mock_iter_ep.side_effect = skip_qssearch

        dag = EODataAccessGateway(user_conf_file_path=empty_conf_file)
        self.assertNotIn("sara", dag.providers.names)
        self.assertEqual(dag._plugins_manager.skipped_plugins, ["QueryStringSearch"])
        dag._plugins_manager.skipped_plugins = []

    def test_disable_providers_for_search_without_auth(self):
        """Providers needing auth for search but without auth plugin must be disabled"""
        empty_conf_file = str(
            res_files("eodag") / "resources" / "user_conf_template.yml"
        )
        # Save original sara config from shared instance before modifying shared DB
        original_sara_config = self.dag.db.get_fb_config("sara")
        try:
            # auth needed for search with need_auth but without auth plugin
            os.environ["EODAG__SARA__SEARCH__NEED_AUTH"] = "true"
            os.environ["EODAG__SARA__AUTH__CREDENTIALS__USERNAME"] = "foo"
            dag = EODataAccessGateway(user_conf_file_path=empty_conf_file)
            # Remove auth from the DB record directly
            full_config = dag.db.get_fb_config("sara")
            full_config.pop("auth", None)
            dag.db.upsert_fb_configs([ProviderConfig.from_mapping(full_config)])
            assert "sara" in dag.providers.names
            assert dag.db.get_fb_config("sara")["search"].get("need_auth", False)
            assert "auth" not in dag.db.get_fb_config("sara")

            with self.assertLogs(level="INFO") as cm:
                sara_config = ProviderConfig.from_mapping(dag.db.get_fb_config("sara"))
                disable_providers(
                    {"sara": sara_config}, dag._plugins_manager.skipped_plugins
                )
                dag.db.upsert_fb_configs([sara_config])
                self.assertNotIn("sara", dag.providers)
                self.assertIn(
                    "sara: provider needing auth for search has been disabled because no auth plugin could be found",
                    str(cm.output),
                )

        # Teardown
        finally:
            os.environ.pop("EODAG__SARA__SEARCH__NEED_AUTH", None)
            os.environ.pop("EODAG__SARA__AUTH__CREDENTIALS__USERNAME", None)
            # Restore sara to original state in shared DB to avoid contaminating other tests
            self.dag.db.upsert_fb_configs(
                [ProviderConfig.from_mapping(original_sara_config)]
            )

    def test_disable_providers_without_api_or_search_plugin(self):
        """Providers without api or search plugin must be disabled"""
        empty_conf_file = str(
            res_files("eodag") / "resources" / "user_conf_template.yml"
        )
        dag = EODataAccessGateway(user_conf_file_path=empty_conf_file)
        # Save original sara config to restore after test
        original_sara_config = dag.db.get_fb_config("sara")
        try:
            # Remove search plugin from DB record directly
            full_config = dag.db.get_fb_config("sara")
            full_config.pop("search", None)
            dag.db.upsert_fb_configs([ProviderConfig.from_mapping(full_config)])
            assert "sara" in dag.providers.names
            assert "api" not in dag.db.get_fb_config("sara")
            assert "search" not in dag.db.get_fb_config("sara")

            with self.assertLogs(level="INFO") as cm:
                sara_config = ProviderConfig.from_mapping(dag.db.get_fb_config("sara"))
                disable_providers(
                    {"sara": sara_config}, dag._plugins_manager.skipped_plugins
                )
                dag.db.upsert_fb_configs([sara_config])
                self.assertNotIn("sara", dag.providers)
                self.assertIn(
                    "sara: provider has been disabled because no api or search plugin could be found",
                    str(cm.output),
                )
        finally:
            # Restore sara to original state in shared DB to avoid contaminating other tests
            self.dag.db.upsert_fb_configs(
                [ProviderConfig.from_mapping(original_sara_config)]
            )

    def test_disable_providers_with_plugin_but_no_type(self):
        """Providers with a plugin section but no type (credentials-only stub)
        must be disabled with a specific message"""
        empty_conf_file = str(
            res_files("eodag") / "resources" / "user_conf_template.yml"
        )
        dag = EODataAccessGateway(user_conf_file_path=empty_conf_file)
        # Save original sara config to restore after test
        original_sara_config = dag.db.get_fb_config("sara")
        try:
            # Replace sara search plugin with a credentials-only stub (no type)
            full_config = dag.db.get_fb_config("sara")
            full_config["search"] = {"credentials": {"username": "foo"}}
            dag.db.upsert_fb_configs([ProviderConfig.from_mapping(full_config)])
            assert "sara" in dag.providers.names
            assert "search" in dag.db.get_fb_config("sara")
            assert "type" not in dag.db.get_fb_config("sara")["search"]

            with self.assertLogs(level="INFO") as cm:
                sara_config = ProviderConfig.from_mapping(dag.db.get_fb_config("sara"))
                disable_providers(
                    {"sara": sara_config}, dag._plugins_manager.skipped_plugins
                )
                dag.db.upsert_fb_configs([sara_config])
                self.assertNotIn("sara", dag.providers)
                self.assertIn(
                    "sara: provider has been disabled because its api or search plugin has no type configured",
                    str(cm.output),
                )
        finally:
            # Restore sara to original state in shared DB to avoid contaminating other tests
            self.dag.db.upsert_fb_configs(
                [ProviderConfig.from_mapping(original_sara_config)]
            )


class TestDisableProvidersExternalAuth(unittest.TestCase):
    """Unit tests for cross-provider auth handling in
    :func:`~eodag.config.disable_providers` and
    :func:`~eodag.config._has_matching_external_auth`.

    A provider needing auth but having no usable local credentials must stay
    enabled when another enabled provider exposes a credentialed auth plugin
    whose ``matching_url`` matches its search/api ``api_endpoint`` or whose
    ``matching_conf`` is a subset of its search/api config. This mirrors the
    runtime resolution done by ``PluginManager.get_auth_plugin``.
    """

    @staticmethod
    def _provider(name, mapping):
        return ProviderConfig.from_mapping({"name": name, **mapping})

    @classmethod
    def _credentialed_auth_provider(
        cls,
        name="extauth",
        matching_url=None,
        matching_conf=None,
        with_credentials=True,
    ):
        """Build a provider exposing a search + an auth plugin matching by url/conf."""
        auth = {
            "type": "GenericAuth",
            "credentials": (
                {"username": "foo", "password": "bar"} if with_credentials else {}
            ),
        }
        if matching_url is not None:
            auth["matching_url"] = matching_url
        if matching_conf is not None:
            auth["matching_conf"] = matching_conf
        return cls._provider(
            name,
            {
                "search": {
                    "type": "QueryStringSearch",
                    "api_endpoint": "https://ext.example.com/search",
                },
                "auth": auth,
            },
        )

    # --- api plugin branch ------------------------------------------------------

    def test_api_need_auth_with_credentials_stays_enabled(self):
        """An api provider with need_auth and embedded credentials stays enabled."""
        provider = self._provider(
            "myapi",
            {
                "api": {
                    "type": "EcmwfApi",
                    "need_auth": True,
                    "api_endpoint": "https://api.example.com",
                    "credentials": {"username": "x"},
                }
            },
        )
        disable_providers({"myapi": provider}, [])
        self.assertTrue(provider.enabled)

    def test_api_need_auth_no_credentials_no_external_auth_disabled(self):
        """An api provider with need_auth, no credentials and no matching external
        auth must be disabled."""
        provider = self._provider(
            "myapi",
            {
                "api": {
                    "type": "EcmwfApi",
                    "need_auth": True,
                    "api_endpoint": "https://api.example.com",
                    "credentials": {},
                }
            },
        )
        disable_providers({"myapi": provider}, [])
        self.assertFalse(provider.enabled)

    def test_api_need_auth_external_auth_url_match_stays_enabled(self):
        """An api provider with need_auth and no credentials stays enabled when
        another provider exposes a credentialed auth matching its api_endpoint."""
        provider = self._provider(
            "myapi",
            {
                "api": {
                    "type": "EcmwfApi",
                    "need_auth": True,
                    "api_endpoint": "https://api.example.com/v1",
                    "credentials": {},
                }
            },
        )
        ext = self._credentialed_auth_provider(matching_url="https://api.example.com")
        disable_providers({"myapi": provider, "extauth": ext}, [])
        self.assertTrue(provider.enabled)
        self.assertTrue(ext.enabled)

    def test_api_need_auth_external_auth_conf_match_stays_enabled(self):
        """Same as above but the external auth matches by ``matching_conf``."""
        provider = self._provider(
            "myapi",
            {
                "api": {
                    "type": "EcmwfApi",
                    "need_auth": True,
                    "api_endpoint": "https://api.example.com",
                    "result_type": "json",
                    "credentials": {},
                }
            },
        )
        ext = self._credentialed_auth_provider(matching_conf={"result_type": "json"})
        disable_providers({"myapi": provider, "extauth": ext}, [])
        self.assertTrue(provider.enabled)

    def test_api_need_auth_external_auth_without_credentials_disabled(self):
        """A matching external auth plugin without credentials does not rescue the
        provider."""
        provider = self._provider(
            "myapi",
            {
                "api": {
                    "type": "EcmwfApi",
                    "need_auth": True,
                    "api_endpoint": "https://api.example.com",
                    "credentials": {},
                }
            },
        )
        ext = self._credentialed_auth_provider(
            matching_url="https://api.example.com", with_credentials=False
        )
        disable_providers({"myapi": provider, "extauth": ext}, [])
        self.assertFalse(provider.enabled)

    # --- search plugin branch (no local auth plugin) ----------------------------

    def test_search_no_auth_plugin_external_url_match_stays_enabled(self):
        """A search provider with need_auth and no auth plugin stays enabled when
        another provider exposes a credentialed auth matching its api_endpoint."""
        provider = self._provider(
            "mysearch",
            {
                "search": {
                    "type": "QueryStringSearch",
                    "need_auth": True,
                    "api_endpoint": "https://search.example.com/api",
                }
            },
        )
        ext = self._credentialed_auth_provider(
            matching_url="https://search.example.com"
        )
        disable_providers({"mysearch": provider, "extauth": ext}, [])
        self.assertTrue(provider.enabled)

    def test_search_no_auth_plugin_external_conf_match_stays_enabled(self):
        """Same as above but the external auth matches by ``matching_conf``."""
        provider = self._provider(
            "mysearch",
            {
                "search": {
                    "type": "QueryStringSearch",
                    "need_auth": True,
                    "api_endpoint": "https://search.example.com/api",
                    "result_type": "json",
                }
            },
        )
        ext = self._credentialed_auth_provider(matching_conf={"result_type": "json"})
        disable_providers({"mysearch": provider, "extauth": ext}, [])
        self.assertTrue(provider.enabled)

    def test_search_no_auth_plugin_no_external_match_disabled(self):
        """A search provider with need_auth, no auth plugin and no matching external
        auth must be disabled."""
        provider = self._provider(
            "mysearch",
            {
                "search": {
                    "type": "QueryStringSearch",
                    "need_auth": True,
                    "api_endpoint": "https://search.example.com/api",
                }
            },
        )
        disable_providers({"mysearch": provider}, [])
        self.assertFalse(provider.enabled)

    # --- _has_matching_external_auth direct unit tests --------------------------

    def test_has_matching_external_auth_ignores_self(self):
        """A provider's own auth plugin must not be considered an external match."""
        provider = self._provider(
            "mysearch",
            {
                "search": {
                    "type": "QueryStringSearch",
                    "need_auth": True,
                    "api_endpoint": "https://search.example.com/api",
                },
                "auth": {
                    "type": "GenericAuth",
                    "matching_url": "https://search.example.com",
                    "credentials": {"username": "foo"},
                },
            },
        )
        self.assertFalse(
            _has_matching_external_auth("mysearch", provider, {"mysearch": provider})
        )

    def test_has_matching_external_auth_ignores_disabled_providers(self):
        """A disabled provider's auth plugin must not be considered."""
        provider = self._provider(
            "mysearch",
            {
                "search": {
                    "type": "QueryStringSearch",
                    "need_auth": True,
                    "api_endpoint": "https://search.example.com/api",
                }
            },
        )
        ext = self._credentialed_auth_provider(
            matching_url="https://search.example.com"
        )
        ext.enabled = False
        self.assertFalse(
            _has_matching_external_auth(
                "mysearch", provider, {"mysearch": provider, "extauth": ext}
            )
        )

    def test_has_matching_external_auth_no_search_or_api_returns_false(self):
        """A provider with neither search nor api config has nothing to match."""
        provider = self._provider("dlonly", {"download": {"type": "HTTPDownload"}})
        ext = self._credentialed_auth_provider(
            matching_url="https://anything.example.com"
        )
        self.assertFalse(
            _has_matching_external_auth(
                "dlonly", provider, {"dlonly": provider, "extauth": ext}
            )
        )
