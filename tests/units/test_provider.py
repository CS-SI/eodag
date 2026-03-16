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

from tests.context import (
    EODataAccessGateway,
    PluginConfig,
    Provider,
    ProviderConfig,
    ProvidersDict,
    UnsupportedCollection,
    UnsupportedProvider,
    ValidationError,
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

    def tearDown(self):
        super().tearDown()
        # stop Mock and remove tmp config dir
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

    def test_provider_sync_collections_strict(self):
        """Test Provider sync_collections in strict mode."""
        config = self.basic_config.copy()
        config["products"]["UNKNOWN_TYPE"] = {"collection": "UNKNOWN_TYPE"}
        provider = Provider(config)

        dag = EODataAccessGateway()
        with patch.object(provider, "delete_collection") as mock_delete:
            provider.sync_collections(dag, strict_mode=True)
            mock_delete.assert_called_once_with("UNKNOWN_TYPE")

    def test_provider_sync_collections_permissive(self):
        """Test Provider sync_collections in permissive mode."""
        config = self.basic_config.copy()
        config["products"]["UNKNOWN_TYPE"] = {"collection": "UNKNOWN_TYPE"}
        provider = Provider(config)

        dag = EODataAccessGateway()

        with patch.object(provider, "delete_collection") as mock_delete:
            provider.sync_collections(dag, strict_mode=False)
            mock_delete.assert_not_called()
            self.assertIn("UNKNOWN_TYPE", provider.collections_config)


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
    """Test cases for the ProvidersDict class."""

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
        cls.sample_providers = ProvidersDict.from_configs(cls.sample_configs)

    def test_providers_dict_creation(self):
        """Test ProvidersDict creation."""
        providers = ProvidersDict.from_configs(self.sample_configs)
        self.assertEqual(len(providers), 2)
        self.assertIn("provider1", providers)
        self.assertIn("provider2", providers)

    def test_providers_dict_contains(self):
        """Test ProvidersDict contains operation."""
        self.assertIn("provider1", self.sample_providers)
        self.assertNotIn("nonexistent", self.sample_providers)

        # Test with Provider object
        provider = self.sample_providers["provider1"]
        self.assertIn(provider, self.sample_providers)

    def test_providers_dict_attributes(self):
        """Test ProvidersDict provider attributes."""
        self.assertEqual(self.sample_providers["provider1"].title, "First provider")
        self.assertEqual(
            self.sample_providers["provider1"].url, "https://provider1.example.com"
        )
        self.assertEqual(self.sample_providers["provider2"].title, "Second provider")
        self.assertIsNone(self.sample_providers["provider2"].url)

    def test_providers_dict_basic_properties(self):
        """Test ProvidersDict basic properties."""
        self.assertEqual(len(self.sample_providers), 2)
        self.assertEqual(self.sample_providers.names, ["provider1", "provider2"])

        priorities = self.sample_providers.priorities
        self.assertEqual(priorities["provider1"], 1)
        self.assertEqual(priorities["provider2"], 2)

    def test_providers_dict_duplicate_provider(self):
        """Test ProvidersDict prevents duplicate providers."""
        new_provider = Provider({"name": "provider1", "search": {"type": "StacSearch"}})
        with self.assertRaisesRegex(ValueError, "Provider 'provider1' already exists"):
            self.sample_providers["provider1"] = new_provider

    def test_providers_dict_delete_provider(self):
        """Test ProvidersDict provider deletion."""
        # Create a fresh copy to avoid mutating shared state
        providers = ProvidersDict.from_configs(self.sample_configs)
        del providers["provider1"]
        self.assertNotIn("provider1", providers)
        self.assertEqual(len(providers), 1)

        # Test deleting non-existent provider
        with self.assertRaisesRegex(
            UnsupportedProvider, "Provider 'nonexistent' not found"
        ):
            del providers["nonexistent"]

    def test_providers_dict_filter_no_query(self):
        """Test ProvidersDict filter with no query."""
        results = list(self.sample_providers.filter())
        self.assertEqual(len(results), 2)

    def test_providers_dict_filter_with_query(self):
        """Test ProvidersDict filter with query."""
        results = self.sample_providers.filter("First")
        self.assertEqual(len(results), 1)
        self.assertEqual(results.names, ["provider1"])

    def test_providers_dict_filter_by_name_or_group(self):
        """Test ProvidersDict filter_by_name_or_group."""
        # Filter by name
        results = list(self.sample_providers.filter_by_name_or_group("provider1"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "provider1")

        # Filter by group
        results = list(self.sample_providers.filter_by_name_or_group("group_a"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "provider1")

    def test_providers_dict_delete_collection(self):
        """Test ProvidersDict delete_collection method."""
        # Create a fresh copy to avoid mutating shared state
        providers = ProvidersDict.from_configs(self.sample_configs)
        # Add a collection first
        providers["provider1"].config.products = {"TEST": {"collection": "TEST"}}

        providers.delete_collection("provider1", "TEST")
        self.assertNotIn("TEST", providers["provider1"].collections_config)

        # Test with non-existent provider
        with self.assertRaises(UnsupportedProvider):
            providers.delete_collection("nonexistent", "TEST")

    def test_providers_dict_get_config(self):
        """Test ProvidersDict get_config method."""
        config = self.sample_providers.get_config("provider1")
        self.assertIsNotNone(config)
        self.assertEqual(config.name, "provider1")

        config = self.sample_providers.get_config("nonexistent")
        self.assertIsNone(config)

    @patch.dict("os.environ", {"EODAG_PROVIDERS_WHITELIST": "provider1"})
    def test_providers_dict_whitelist(self):
        """Test ProvidersDict whitelist filtering."""
        filtered = ProvidersDict._get_whitelisted_configs(self.sample_configs)
        self.assertEqual(set(filtered.keys()), {"provider1"})

    def test_providers_dict_invalid_config_handling(self):
        """Test ProvidersDict handles invalid configurations."""
        providers_dict = ProvidersDict()
        invalid_configs = {"invalid": {"description": "Missing required fields"}}

        with patch("eodag.api.provider.logger") as mock_logger:
            providers_dict.update_from_configs(invalid_configs)
            mock_logger.warning.assert_called()
            self.assertEqual(len(providers_dict), 0)
