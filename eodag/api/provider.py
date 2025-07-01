from typing import Any, Optional, Union
from collections import UserList

from eodag.config import ProviderConfig

from attrs import define, field

@define
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
    def search_config(self) -> Optional[Any]:
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
    def unparsable_properties(self) -> set[str]:
        if self.discoverable:
            return getattr(self.search_config.discover_product_types, "generic_product_type_unparsable_properties", {}).keys()

            
            
    @property
    def api_config(self) -> Optional[Any]:
        """Return the api plugin config, if any."""
        return getattr(self.config, "api", None)

    @property
    def download_config(self) -> Optional[Any]:
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

    def is_auth_needed(self) -> bool:
        """Check if authentication is needed for this provider."""
        search = self.search_config
        api = self.api_config
        return (
            (search and getattr(search, "need_auth", False))
            or (api and getattr(api, "need_auth", False))
        )

@define
class ProvidersList(UserList):
    """
    A list of Provider objects, compatible with string-based access.
    """
    data: list[Provider] = field(default_factory=list)

    def __init__(self, providers: Union[list[Provider], list[str], list[dict], dict[str, Any]], plugins_manager=None):
        if isinstance(providers, dict):
            self.data = [Provider(name=name, config=conf) for name, conf in providers.items()]
        else:
            self.data = [p if isinstance(p, Provider) else Provider(name=p, config={}) for p in providers]

    def __contains__(self, item) -> bool:
        if isinstance(item, Provider):
            return any(p.name == item.name for p in self.data)
        return any(p.name == item for p in self.data)

    def __getitem__(self, key) -> Provider:
        if isinstance(key, int):
            return self.data[key]
        # Allow access by provider name
        for p in self.data:
            if p.name == key:
                return p
        raise KeyError(key)

    def get(self, name: str) -> Optional[Provider]:
        for p in self.data:
            if p.name == name:
                return p
        return None

    def __repr__(self) -> str:
        return f"ProvidersList({[p.name for p in self.data]})"