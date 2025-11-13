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

from unittest.mock import patch

import pytest

from eodag.api.core import EODataAccessGateway
from eodag.api.provider import Provider, ProviderConfig, ProvidersDict
from eodag.config import PluginConfig
from eodag.utils.exceptions import (
    UnsupportedCollection,
    UnsupportedProvider,
    ValidationError,
)


class TestProvider:
    """Test cases for the Provider class."""

    @pytest.fixture
    def basic_config(self):
        """Basic valid provider configuration."""
        return {
            "name": "test_provider",
            "description": "Test provider for unit tests",
            "url": "https://test.example.com",
            "search": {"type": "StacSearch"},
            "products": {"S2_MSI_L1C": {"collection": "S2_MSI_L1C"}},
        }

    def test_provider_creation_from_dict(self, basic_config):
        """Test Provider creation from dict config."""
        provider = Provider(basic_config)
        assert provider.name == "test_provider"
        assert isinstance(provider.config, ProviderConfig)

    def test_provider_creation_from_provider_config(self, basic_config):
        """Test Provider creation from ProviderConfig object."""
        config_obj = ProviderConfig.from_mapping(basic_config)
        provider = Provider(config_obj)
        assert provider.name == "test_provider"
        assert isinstance(provider.config, ProviderConfig)

    def test_provider_creation_invalid_config(self):
        """Test Provider creation with invalid config."""
        with pytest.raises(ValidationError):
            Provider("invalid_string")

        with pytest.raises(ValidationError):
            Provider({"search": {"type": "StacSearch"}})  # missing name

    def test_provider_string_representations(self, basic_config):
        """Test Provider string representations."""
        provider = Provider(basic_config)
        assert str(provider) == "test_provider"
        assert repr(provider) == "Provider('test_provider')"

    def test_provider_equality(self, basic_config):
        """Test Provider equality."""
        provider1 = Provider(basic_config)
        provider2 = Provider(basic_config.copy())

        # Equal providers
        assert provider1 == provider2
        assert provider1 == "test_provider"
        assert hash(provider1) == hash(provider2)

        # Different providers
        config2 = basic_config.copy()
        config2["name"] = "different_provider"
        provider3 = Provider(config2)
        assert provider1 != provider3
        assert provider1 != "different_provider"
        assert provider1 != 123

    def test_provider_basic_properties(self, basic_config):
        """Test Provider basic properties."""
        provider = Provider(basic_config)
        assert provider.priority == 0
        assert provider.group is None
        assert provider.collections == {"S2_MSI_L1C": {"collection": "S2_MSI_L1C"}}
        assert provider.search_config.type == "StacSearch"
        assert provider.api_config is None
        assert provider.download_config is None

    def test_provider_custom_properties(self, basic_config):
        """Test Provider properties with custom values."""
        config = basic_config.copy()
        config.update({"priority": 5, "group": "test_group"})
        provider = Provider(config)

        assert provider.priority == 5
        assert provider.group == "test_group"

    def test_provider_fetchable(self, basic_config):
        """Test Provider fetchable property."""
        provider = Provider(basic_config)
        assert provider.fetchable is True

    def test_provider_delete_collection(self, basic_config):
        """Test Provider delete_collection method."""
        provider = Provider(basic_config)

        # Successful deletion
        provider.delete_collection("S2_MSI_L1C")
        assert "S2_MSI_L1C" not in provider.collections

        # Non-existent collection
        with pytest.raises(UnsupportedCollection):
            provider.delete_collection("NONEXISTENT")

    def test_provider_sync_collections_strict(self, basic_config):
        """Test Provider sync_collections in strict mode."""
        config = basic_config.copy()
        config["products"]["UNKNOWN_TYPE"] = {"collection": "UNKNOWN_TYPE"}
        provider = Provider(config)

        dag = EODataAccessGateway()
        with patch.object(provider, "delete_collection") as mock_delete:
            provider.sync_collections(dag, strict_mode=True)
            mock_delete.assert_called_once_with("UNKNOWN_TYPE")

    def test_provider_sync_collections_permissive(self, basic_config):
        """Test Provider sync_collections in permissive mode."""
        config = basic_config.copy()
        config["products"]["UNKNOWN_TYPE"] = {"collection": "UNKNOWN_TYPE"}
        provider = Provider(config)

        dag = EODataAccessGateway()

        with patch.object(provider, "delete_collection") as mock_delete:
            provider.sync_collections(dag, strict_mode=False)
            mock_delete.assert_not_called()
            assert "UNKNOWN_TYPE" in provider.collections


class TestProviderConfig:
    """Test cases for the ProviderConfig class."""

    def test_provider_config_creation(self):
        """Test ProviderConfig creation from mapping."""
        config_dict = {
            "name": "test_provider",
            "search": {"type": "StacSearch"},
        }
        config = ProviderConfig.from_mapping(config_dict)
        assert config.name == "test_provider"
        assert isinstance(config.search, PluginConfig)

    def test_provider_config_validation_missing_name(self):
        """Test ProviderConfig validation with missing name."""
        with pytest.raises(ValidationError, match="Provider config must have name key"):
            ProviderConfig.from_mapping({"search": {"type": "StacSearch"}})

    def test_provider_config_validation_missing_plugins(self):
        """Test ProviderConfig validation with missing plugins."""
        with pytest.raises(
            ValidationError, match="A provider must implement at least one plugin"
        ):
            ProviderConfig.from_mapping({"name": "test_provider"})

    def test_provider_config_validation_api_exclusivity(self):
        """Test that API plugin cannot coexist with other plugin types."""
        config = {
            "name": "test_provider",
            "api": {"type": "SomeApi"},
            "search": {"type": "StacSearch"},
        }
        with pytest.raises(
            ValidationError, match="Api plugin must not implement any other type"
        ):
            ProviderConfig.from_mapping(config)

    def test_provider_config_update(self):
        """Test ProviderConfig update operation."""
        config = ProviderConfig.from_mapping(
            {"name": "test_provider", "search": {"type": "StacSearch"}}
        )

        config.update({"description": "Updated description"})
        assert config.description == "Updated description"

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
        assert new_config.name == "new_provider"

        # Verify all other properties are preserved
        assert new_config.description == "Original description"
        assert new_config.priority == 5
        assert isinstance(new_config.search, PluginConfig)
        assert new_config.search.type == "StacSearch"
        assert new_config.search.url == "https://example.com"
        assert new_config.products == {"S2_MSI_L1C": {"collection": "S2_MSI_L1C"}}

        # Verify the original config is unchanged
        assert original_config.name == "original_provider"

        # Verify they are separate objects (deep copy)
        assert new_config is not original_config
        assert new_config.search is not original_config.search


class TestProvidersDict:
    """Test cases for the ProvidersDict class."""

    @pytest.fixture
    def sample_configs(self):
        """Sample provider configurations."""
        return {
            "provider1": {
                "name": "provider1",
                "description": "First provider",
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

    @pytest.fixture
    def sample_providers(self, sample_configs):
        """Sample ProvidersDict for testing."""
        return ProvidersDict.from_configs(sample_configs)

    def test_providers_dict_creation(self, sample_configs):
        """Test ProvidersDict creation."""
        providers = ProvidersDict.from_configs(sample_configs)
        assert len(providers) == 2
        assert "provider1" in providers
        assert "provider2" in providers

    def test_providers_dict_contains(self, sample_providers):
        """Test ProvidersDict contains operation."""
        assert "provider1" in sample_providers
        assert "nonexistent" not in sample_providers

        # Test with Provider object
        provider = sample_providers["provider1"]
        assert provider in sample_providers

    def test_providers_dict_basic_properties(self, sample_providers):
        """Test ProvidersDict basic properties."""
        assert len(sample_providers) == 2
        assert sample_providers.names == ["provider1", "provider2"]

        priorities = sample_providers.priorities
        assert priorities["provider1"] == 1
        assert priorities["provider2"] == 2

    def test_providers_dict_duplicate_provider(self, sample_providers):
        """Test ProvidersDict prevents duplicate providers."""
        new_provider = Provider({"name": "provider1", "search": {"type": "StacSearch"}})
        with pytest.raises(ValueError, match="Provider 'provider1' already exists"):
            sample_providers["provider1"] = new_provider

    def test_providers_dict_delete_provider(self, sample_providers):
        """Test ProvidersDict provider deletion."""
        del sample_providers["provider1"]
        assert "provider1" not in sample_providers
        assert len(sample_providers) == 1

        # Test deleting non-existent provider
        with pytest.raises(
            UnsupportedProvider, match="Provider 'nonexistent' not found"
        ):
            del sample_providers["nonexistent"]

    def test_providers_dict_filter_no_query(self, sample_providers):
        """Test ProvidersDict filter with no query."""
        results = list(sample_providers.filter())
        assert len(results) == 2

    def test_providers_dict_filter_with_query(self, sample_providers):
        """Test ProvidersDict filter with query."""
        results = list(sample_providers.filter("First"))
        assert len(results) == 1
        assert results[0].name == "provider1"

    def test_providers_dict_filter_by_name_or_group(self, sample_providers):
        """Test ProvidersDict filter_by_name_or_group."""
        # Filter by name
        results = list(sample_providers.filter_by_name_or_group("provider1"))
        assert len(results) == 1
        assert results[0].name == "provider1"

        # Filter by group
        results = list(sample_providers.filter_by_name_or_group("group_a"))
        assert len(results) == 1
        assert results[0].name == "provider1"

    def test_providers_dict_delete_collection(self, sample_providers):
        """Test ProvidersDict delete_collection method."""
        # Add a collection first
        sample_providers["provider1"].config.products = {"TEST": {"collection": "TEST"}}

        sample_providers.delete_collection("provider1", "TEST")
        assert "TEST" not in sample_providers["provider1"].collections

        # Test with non-existent provider
        with pytest.raises(UnsupportedProvider):
            sample_providers.delete_collection("nonexistent", "TEST")

    def test_providers_dict_get_config(self, sample_providers):
        """Test ProvidersDict get_config method."""
        config = sample_providers.get_config("provider1")
        assert config is not None
        assert config.name == "provider1"

        config = sample_providers.get_config("nonexistent")
        assert config is None

    @patch.dict("os.environ", {"EODAG_PROVIDERS_WHITELIST": "provider1"})
    def test_providers_dict_whitelist(self, sample_configs):
        """Test ProvidersDict whitelist filtering."""
        filtered = ProvidersDict._get_whitelisted_configs(sample_configs)
        assert set(filtered.keys()) == {"provider1"}

    def test_providers_dict_invalid_config_handling(self):
        """Test ProvidersDict handles invalid configurations."""
        providers_dict = ProvidersDict()
        invalid_configs = {"invalid": {"description": "Missing required fields"}}

        with patch("eodag.api.provider.logger") as mock_logger:
            providers_dict.update_from_configs(invalid_configs)
            mock_logger.warning.assert_called()
            assert len(providers_dict) == 0


if __name__ == "__main__":
    pytest.main([__file__])
