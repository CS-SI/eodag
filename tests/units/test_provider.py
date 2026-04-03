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
    UnsupportedCollection,
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
            "description": "Test provider for unit tests",
            "url": "https://test.example.com",
            "search": {"type": "StacSearch"},
            "products": {"S2_MSI_L1C": {"collection": "S2_MSI_L1C"}},
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
        provider = Provider(self.basic_config)
        self.assertEqual(provider.name, "test_provider")
        self.assertIsInstance(provider.config, ProviderConfig)

    def test_provider_creation_from_provider_config(self):
        """Test Provider creation from ProviderConfig object."""
        config_obj = ProviderConfig.from_mapping(self.basic_config)
        provider = Provider(config_obj)
        self.assertEqual(provider.name, "test_provider")
        self.assertIsInstance(provider.config, ProviderConfig)

    def test_provider_creation_invalid_config(self):
        """Test Provider creation with invalid config."""
        with self.assertRaises(ValidationError):
            Provider("invalid_string")

        with self.assertRaises(ValidationError):
            Provider({"search": {"type": "StacSearch"}})  # missing name

    def test_provider_string_representations(self):
        """Test Provider string representations."""
        provider = Provider(self.basic_config)
        self.assertEqual(str(provider), "test_provider")
        self.assertEqual(repr(provider), "Provider('test_provider')")

    def test_provider_equality(self):
        """Test Provider equality."""
        provider1 = Provider(self.basic_config)
        provider2 = Provider(self.basic_config.copy())

        # Equal providers
        self.assertEqual(provider1, provider2)
        self.assertEqual(provider1, "test_provider")
        self.assertEqual(hash(provider1), hash(provider2))

        # Different providers
        config2 = self.basic_config.copy()
        config2["name"] = "different_provider"
        provider3 = Provider(config2)
        self.assertNotEqual(provider1, provider3)
        self.assertNotEqual(provider1, "different_provider")
        self.assertNotEqual(provider1, 123)

    def test_provider_basic_properties(self):
        """Test Provider basic properties."""
        provider = Provider(self.basic_config)
        self.assertEqual(provider.priority, 0)
        self.assertIsNone(provider.group)
        self.assertEqual(
            provider.collections_config, {"S2_MSI_L1C": {"collection": "S2_MSI_L1C"}}
        )
        self.assertEqual(provider.search_config.type, "StacSearch")
        self.assertIsNone(provider.api_config)
        self.assertIsNone(provider.download_config)

    def test_provider_custom_properties(self):
        """Test Provider properties with custom values."""
        config = self.basic_config.copy()
        config.update({"priority": 5, "group": "test_group"})
        provider = Provider(config)

        self.assertEqual(provider.priority, 5)
        self.assertEqual(provider.group, "test_group")

    def test_provider_fetchable(self):
        """Test Provider fetchable property."""
        provider = Provider(self.basic_config)
        self.assertTrue(provider.fetchable)

    def test_provider_delete_collection(self):
        """Test Provider delete_collection method."""
        provider = Provider(self.basic_config)

        # Successful deletion
        provider.delete_collection("S2_MSI_L1C")
        self.assertNotIn("S2_MSI_L1C", provider.collections_config)

        # Non-existent collection
        with self.assertRaises(UnsupportedCollection):
            provider.delete_collection("NONEXISTENT")


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

    def test_provider_config_with_name(self):
        """Test ProviderConfig with_name method."""
        original_config = ProviderConfig.from_mapping(
            {
                "name": "original_provider",
                "description": "Original description",
                "priority": 5,
                "search": {"type": "StacSearch", "url": "https://example.com"},
                "products": {"S2_MSI_L1C": {"collection": "S2_MSI_L1C"}},
            }
        )

        # Create a copy with a new name
        new_config = original_config.with_name("new_provider")

        # Verify the new config has the updated name
        self.assertEqual(new_config.name, "new_provider")

        # Verify all other properties are preserved
        self.assertEqual(new_config.description, "Original description")
        self.assertEqual(new_config.priority, 5)
        self.assertIsInstance(new_config.search, PluginConfig)
        self.assertEqual(new_config.search.type, "StacSearch")
        self.assertEqual(new_config.search.url, "https://example.com")
        self.assertEqual(
            new_config.products, {"S2_MSI_L1C": {"collection": "S2_MSI_L1C"}}
        )

        # Verify the original config is unchanged
        self.assertEqual(original_config.name, "original_provider")

        # Verify they are separate objects (deep copy)
        self.assertIsNot(new_config, original_config)
        self.assertIsNot(new_config.search, original_config.search)


class TestProvidersDict(unittest.TestCase):
    """Test cases for the ProvidersDict class (DB-backed)."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures for the class."""
        super().setUpClass()
        cls.sample_configs = {
            "provider1": {
                "name": "provider1",
                "description": "First provider",
                "url": "https://provider1.example.com",
                "group": "group_a",
                "priority": 1,
                "search": {"type": "StacSearch"},
            },
            "provider2": {
                "name": "provider2",
                "description": "Second provider",
                "group": "group_b",
                "priority": 2,
                "search": {"type": "StacSearch"},
            },
        }

    def setUp(self):
        super().setUp()
        from eodag.config import (
            get_collections_providers_config,
            get_federation_backends_config,
        )

        self.db = SQLiteDatabase(":memory:")
        providers = build_provider_configs(self.sample_configs)
        fb_configs = get_federation_backends_config(
            [p.config for p in providers.values()]
        )
        self.db.upsert_federation_backends(fb_configs)
        coll_configs = get_collections_providers_config(
            [p.config for p in providers.values()]
        )
        self.db.upsert_collections_federation_backends(coll_configs)
        self.providers_dict = ProvidersDict(self.db)

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
        """Test ProvidersDict provider attributes."""
        self.assertEqual(self.providers_dict["provider1"].title, "First provider")
        self.assertEqual(
            self.providers_dict["provider1"].url, "https://provider1.example.com"
        )
        self.assertEqual(self.providers_dict["provider2"].title, "Second provider")
        self.assertIsNone(self.providers_dict["provider2"].url)

    def test_providers_dict_basic_properties(self):
        """Test ProvidersDict basic properties."""
        self.assertEqual(len(self.providers_dict), 2)
        self.assertCountEqual(self.providers_dict.names, ["provider1", "provider2"])

        priorities = self.providers_dict.priorities
        self.assertEqual(priorities["provider1"], 1)
        self.assertEqual(priorities["provider2"], 2)

    def test_providers_dict_pop(self):
        """Test ProvidersDict pop disables provider in DB."""
        provider = self.providers_dict.pop("provider1")
        self.assertEqual(provider.name, "provider1")
        # After pop, provider1 should be disabled
        self.assertNotIn("provider1", self.providers_dict)
        self.assertEqual(len(self.providers_dict), 1)

        # Pop non-existent with default
        result = self.providers_dict.pop("nonexistent", None)
        self.assertIsNone(result)

        # Pop non-existent without default
        with self.assertRaises(UnsupportedProvider):
            self.providers_dict.pop("nonexistent")

    def test_providers_dict_get_config(self):
        """Test ProvidersDict get_config method."""
        config = self.providers_dict.get_config("provider1")
        self.assertIsNotNone(config)
        self.assertEqual(config.name, "provider1")

        config = self.providers_dict.get_config("nonexistent")
        self.assertIsNone(config)

    @patch.dict("os.environ", {"EODAG_PROVIDERS_WHITELIST": "provider1"})
    def test_providers_dict_whitelist(self):
        """Test whitelist filtering via standalone function."""
        from eodag.api.provider import _get_whitelisted_configs

        filtered = _get_whitelisted_configs(self.sample_configs)
        self.assertEqual(set(filtered.keys()), {"provider1"})

    def test_providers_dict_invalid_config_handling(self):
        """Test build_provider_configs handles invalid configurations."""
        invalid_configs = {"invalid": {"description": "Missing required fields"}}

        with patch("eodag.api.provider.logger") as mock_logger:
            providers = build_provider_configs(invalid_configs)
            mock_logger.warning.assert_called()
            self.assertEqual(len(providers), 0)
