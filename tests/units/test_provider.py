# -*- coding: utf-8 -*-
# Copyright 2025, CS GROUP - France, https://www.csgroup.eu/
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

import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

from eodag.databases.sqlite import SQLiteDatabase
from tests.context import (
    PluginConfig,
    Provider,
    ProviderConfig,
    ProvidersDict,
    UnsupportedProvider,
    ValidationError,
    build_provider_configs,
)


class TestProvider(unittest.TestCase):
    """Test cases for the Provider class."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures for the class."""
        super().setUpClass()
        cls.basic_config = {
            "name": "test_provider",
            "priority": 0,
            "enabled": True,
            "metadata": {
                "description": "Test provider for unit tests",
                "url": "https://test.example.com",
            },
        }

    def setUp(self):
        super().setUp()
        # Mock home and eodag conf directory to tmp dir
        self.tmp_home_dir = TemporaryDirectory()
        self.expanduser_mock = patch(
            "os.path.expanduser", autospec=True, return_value=self.tmp_home_dir.name
        )
        self.expanduser_mock.start()
        # Use in-memory SQLite DB for faster tests
        self.sqlite_mock = patch(
            "eodag.api.core.SQLiteDatabase",
            side_effect=lambda db_path: SQLiteDatabase(":memory:"),
        )
        self.sqlite_mock.start()

    def tearDown(self):
        super().tearDown()
        # stop Mock and remove tmp config dir
        self.sqlite_mock.stop()
        self.expanduser_mock.stop()
        self.tmp_home_dir.cleanup()

    def test_provider_creation_from_dict(self):
        """Test Provider creation from dict config."""
        provider = Provider(**self.basic_config)
        self.assertEqual(provider.name, "test_provider")
        self.assertIsInstance(provider.metadata, dict)

    def test_provider_creation_from_provider_config(self):
        """Test Provider creation from ProviderConfig object."""
        config_dict = {
            "name": "test_provider",
            "search": {"type": "StacSearch"},
        }
        config_obj = ProviderConfig.from_mapping(config_dict)
        provider = Provider(
            name=config_obj.name,
            priority=getattr(config_obj, "priority", 0),
            enabled=getattr(config_obj, "enabled", True),
            metadata={},
        )
        self.assertEqual(provider.name, "test_provider")

    def test_provider_creation_invalid_config(self):
        """Test Provider creation with invalid config raises TypeError."""
        with self.assertRaises(TypeError):
            Provider()  # missing required args

        with self.assertRaises(TypeError):
            Provider(priority=0, enabled=True, metadata={})  # missing name

    def test_provider_string_representations(self):
        """Test Provider string representations."""
        provider = Provider(**self.basic_config)
        self.assertEqual(str(provider), "test_provider")
        self.assertEqual(repr(provider), "Provider('test_provider')")

    def test_provider_equality(self):
        """Test Provider equality."""
        provider1 = Provider(**self.basic_config)
        provider2 = Provider(**self.basic_config)

        # Equal providers
        self.assertEqual(provider1, provider2)
        self.assertEqual(provider1, "test_provider")
        self.assertEqual(hash(provider1), hash(provider2))

        # Different providers
        config2 = {**self.basic_config, "name": "different_provider"}
        provider3 = Provider(**config2)
        self.assertNotEqual(provider1, provider3)
        self.assertNotEqual(provider1, "different_provider")
        self.assertNotEqual(provider1, 123)

    def test_provider_basic_properties(self):
        """Test Provider basic properties."""
        provider = Provider(**self.basic_config)
        self.assertEqual(provider.priority, 0)
        self.assertTrue(provider.enabled)
        self.assertEqual(
            provider.metadata["description"], "Test provider for unit tests"
        )
        self.assertEqual(provider.metadata["url"], "https://test.example.com")
        self.assertIsNone(provider.metadata.get("group"))

    def test_provider_custom_properties(self):
        """Test Provider properties with custom values."""
        config = {
            **self.basic_config,
            "priority": 5,
            "metadata": {**self.basic_config["metadata"], "group": "test_group"},
        }
        provider = Provider(**config)

        self.assertEqual(provider.priority, 5)
        self.assertEqual(provider.metadata.get("group"), "test_group")

    def test_provider_fetchable(self):
        """Test Provider fetchable key from metadata."""
        provider = Provider(**self.basic_config)
        self.assertIsNone(provider.metadata.get("fetchable"))  # not set in basic_config

        fetchable = Provider(
            name="test_provider",
            priority=0,
            enabled=True,
            metadata={"fetchable": True},
        )
        self.assertTrue(fetchable.metadata["fetchable"])

        not_fetchable = Provider(
            name="test_provider",
            priority=0,
            enabled=True,
            metadata={"fetchable": False},
        )
        self.assertFalse(not_fetchable.metadata["fetchable"])


# TODO: move TestProviderConfig to test_config.py.
class TestProviderConfig(unittest.TestCase):
    """Test cases for the ProviderConfig class."""

    def test_provider_config_creation(self):
        """Test ProviderConfig creation from mapping."""
        config_dict = {
            "name": "test_provider",
            "search": {"type": "StacSearch"},
        }
        config = ProviderConfig.from_mapping(config_dict)
        self.assertEqual(config.name, "test_provider")
        self.assertIsInstance(config.search, PluginConfig)

    def test_provider_config_validation_missing_name(self):
        """Test ProviderConfig validation with missing name."""
        with self.assertRaisesRegex(
            ValidationError, "Provider config must have name key"
        ):
            ProviderConfig.from_mapping({"search": {"type": "StacSearch"}})

    def test_provider_config_validation_missing_plugins(self):
        """Test ProviderConfig validation with missing plugins."""
        with self.assertRaisesRegex(
            ValidationError, "A provider must implement at least one plugin"
        ):
            ProviderConfig.from_mapping({"name": "test_provider"})

    def test_provider_config_validation_api_exclusivity(self):
        """Test that API plugin cannot coexist with other plugin types."""
        config = {
            "name": "test_provider",
            "api": {"type": "SomeApi"},
            "search": {"type": "StacSearch"},
        }
        with self.assertRaisesRegex(
            ValidationError, "Api plugin must not implement any other type"
        ):
            ProviderConfig.from_mapping(config)

    def test_provider_config_update(self):
        """Test ProviderConfig update operation."""
        config = ProviderConfig.from_mapping(
            {"name": "test_provider", "search": {"type": "StacSearch"}}
        )

        config.update({"description": "Updated description"})
        self.assertEqual(config.description, "Updated description")


class TestProvidersDict(unittest.TestCase):
    """Test cases for the ProvidersDict class."""

    def setUp(self):
        super().setUp()
        # Build a ProvidersDict with two Provider objects directly
        self.providers_dict = ProvidersDict()
        self.providers_dict["provider1"] = Provider(
            name="provider1",
            priority=1,
            enabled=True,
            metadata={
                "description": "First provider",
                "url": "https://provider1.example.com",
                "group": "group_a",
            },
        )
        self.providers_dict["provider2"] = Provider(
            name="provider2",
            priority=2,
            enabled=True,
            metadata={"description": "Second provider", "group": "group_b"},
        )

    def test_providers_dict_creation(self):
        """Test ProvidersDict creation."""
        self.assertEqual(len(self.providers_dict), 2)
        self.assertIn("provider1", self.providers_dict)
        self.assertIn("provider2", self.providers_dict)

    def test_providers_dict_contains(self):
        """Test ProvidersDict contains operation."""
        self.assertIn("provider1", self.providers_dict)
        self.assertNotIn("nonexistent", self.providers_dict)

        # Test with Provider object
        provider = self.providers_dict["provider1"]
        self.assertIn(provider, self.providers_dict)

    def test_providers_dict_attributes(self):
        """Test ProvidersDict provider attributes via metadata."""
        self.assertEqual(
            self.providers_dict["provider1"].metadata.get("description"),
            "First provider",
        )
        self.assertEqual(
            self.providers_dict["provider1"].metadata.get("url"),
            "https://provider1.example.com",
        )
        self.assertEqual(
            self.providers_dict["provider2"].metadata.get("description"),
            "Second provider",
        )
        self.assertIsNone(self.providers_dict["provider2"].metadata.get("url"))

    def test_providers_dict_basic_properties(self):
        """Test ProvidersDict basic properties."""
        self.assertEqual(len(self.providers_dict), 2)
        self.assertCountEqual(self.providers_dict.names, ["provider1", "provider2"])

        priorities = self.providers_dict.priorities
        self.assertEqual(priorities["provider1"], 1)
        self.assertEqual(priorities["provider2"], 2)

    def test_providers_dict_del(self):
        """Test ProvidersDict __delitem__ raises UnsupportedProvider."""
        with self.assertRaises(UnsupportedProvider):
            del self.providers_dict["nonexistent"]

    def test_providers_dict_groups(self):
        """Test ProvidersDict groups property."""
        self.assertCountEqual(self.providers_dict.groups, ["group_a", "group_b"])

    # TODO: move this test to test_config.py.
    @patch.dict("os.environ", {"EODAG_PROVIDERS_WHITELIST": "provider1"})
    def test_providers_dict_whitelist(self):
        """Test whitelist filtering via standalone function."""
        from eodag.config import _get_whitelisted_configs

        sample = {
            "provider1": {"name": "provider1", "search": {"type": "StacSearch"}},
            "provider2": {"name": "provider2", "search": {"type": "StacSearch"}},
        }
        filtered = _get_whitelisted_configs(sample)
        self.assertEqual(set(filtered.keys()), {"provider1"})

    # TODO: move this test to test_config.py.
    def test_providers_dict_invalid_config_handling(self):
        """Test build_provider_configs handles invalid configurations."""
        invalid_configs = {"invalid": {"description": "Missing required fields"}}

        with patch("eodag.config.logger") as mock_logger:
            providers = build_provider_configs(invalid_configs)
            mock_logger.warning.assert_called()
            self.assertEqual(len(providers), 0)
