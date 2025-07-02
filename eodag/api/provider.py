from typing import Any, Optional, Union, Self
from collections import UserDict
from dataclasses import dataclass, field

from eodag.config import ProviderConfig, credentials_in_auth, PluginConfig

AUTH_TOPIC_KEYS = ("auth", "search_auth", "download_auth")

@dataclass
class Provider:
    """
    Represents a data provider with its configuration and utility methods.
    """
    name: str
    config: ProviderConfig

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"Provider('{self.name}')"

    @property
    def products(self) -> dict[str, Any]:
        """Return the products dictionary for this provider."""
        return self.config.products

    @property
    def priority(self) -> int:
        """Return the provider's priority (default: 0)."""
        return self.config.priority

    @property
    def group(self) -> Optional[str]:
        """Return the provider's group, if any."""
        return getattr(self.config, "group", None)

    @property
    def search_config(self) -> Optional[PluginConfig]:
        """Return the search plugin config, if any."""
        return getattr(self.config, "search", None) or getattr(self.config, "api", None)

    @property
    def discoverable(self) -> bool:
        if self.search_config is None:
            return False
        
        if not hasattr(self.search_config, "discover_product_types"):
            return False
        
        if not hasattr(self.search_config.discover_product_types, "fetch_url"):
            return False
        
        return True

    @property
    def unparsable_properties(self) -> Optional[set[str]]:
        if self.discoverable:
            return getattr(self.search_config.discover_product_types, "generic_product_type_unparsable_properties", {}).keys()
        
        return None

    @property
    def api_config(self) -> Optional[PluginConfig]:
        """Return the api plugin config, if any."""
        return getattr(self.config, "api", None)

    @property
    def download_config(self) -> Optional[PluginConfig]:
        """Return the download plugin config, if any."""
        return getattr(self.config, "download", None)

    def product(self, product_type: str) -> Optional[Any]:
        """Return a product type if available from this provider."""
        return self.products.get(product_type)

    def delete_product(self, product_type: str) -> None:
        """Remove a product type from this provider."""
        if self.product(product_type):
            del self.products[product_type]
        else:
            raise KeyError(f"Product type '{product_type}' not found in provider '{self.name}'.")

    def _get_auth_confs_with_credentials(self) -> list[PluginConfig]:
        """
        Collect all auth configs from the provider.
        """
        return [
            getattr(self.config, auth_key)
            for auth_key in AUTH_TOPIC_KEYS
            if hasattr(self.config, auth_key) and credentials_in_auth(getattr(self.config, auth_key))
        ]
        
    def _copy_matching_credentials(
        self,
        auth_confs_with_creds: list[PluginConfig],
    ) -> None:
        """
        Copy credentials from matching auth configs to the target auth config.
        """
        for key in AUTH_TOPIC_KEYS:
            provider_auth_config = getattr(self.config, key, None)
            if provider_auth_config and not credentials_in_auth(provider_auth_config):
                for conf_with_creds in auth_confs_with_creds:
                    if conf_with_creds.matches_target_auth(self.config):
                        getattr(self.config, key).credentials = conf_with_creds.credentials

@dataclass
class ProvidersDict(UserDict[str, Provider]):
    """
    A dictionary-like collection of Provider objects, keyed by provider name.
    """
    def __init__(
        self,
        providers: Union[list[Provider], list[str], list[dict], dict[str, Any]],
        plugins_manager=None,
    ):
        super().__init__()

        if isinstance(providers, dict):
            self.data = {name: Provider(name, conf) for name, conf in providers.items()}
        else:
            self.data = {
                p.name if isinstance(p, Provider) else p: p if isinstance(p, Provider) else Provider(p, {})
                for p in providers
            }

    def __contains__(self, item: str | Provider) -> bool:
        if isinstance(item, Provider):
            return item.name in self.data
        return item in self.data

    def __getitem__(self, key: str) -> Provider:
        return self.data[key]

    def __repr__(self) -> str:
        return f"ProvidersDict({list(self.data.keys())})"

    def get(self, name: str) -> Optional[Provider]:
        return self.data.get(name)
    
    def get_config(self, name: str) -> Optional[ProviderConfig]:
        return self.data.get(name).config

    def add(self, provider: Provider) -> None:
        if provider.name in self.data:
            raise ValueError(f"Provider '{provider.name}' already exists.")
        self.data[provider.name] = provider

    def delete(self, name: str) -> None:
        if name in self.data:
            del self.data[name]
        else:
            raise KeyError(f"Provider '{name}' not found.")

    def share_credentials(self) -> None:
        """
        Share credentials between plugins having the same matching criteria
        across all providers in this list.
        """
        auth_confs_with_creds: list[PluginConfig] = []
        for provider in self.values():
            auth_confs_with_creds.extend(provider._get_auth_confs_with_credentials())
            
        if not auth_confs_with_creds:
            return

        for provider in self.values():
            provider._copy_matching_credentials(auth_confs_with_creds)
            
    def merge(self, other: Self) -> None:
        """
        Override the current providers' configuration with the values of another ProvidersDict.

        :param other: Another ProvidersDict instance whose configs will override the current ones.
        """
        for name, other_provider in other.items():
            if name in self:
                current_provider = self[name]
                old_conf = current_provider.config
                new_conf = other_provider.config

                merged_dict = dict(old_conf.__dict__)
                merged_dict.update(new_conf.__dict__)

                for key, value in merged_dict.items():
                    old_val = getattr(old_conf, key, None)
                    if isinstance(value, PluginConfig) and isinstance(old_val, PluginConfig):
                        old_val.update(value.__dict__)
                        merged_dict[key] = old_val
                    elif isinstance(old_val, PluginConfig):
                        merged_dict[key] = old_val

                    setattr(old_conf, key, merged_dict[key])
            else:
                self.data[name] = other_provider