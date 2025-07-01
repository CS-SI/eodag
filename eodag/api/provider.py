from typing import Any, Optional, Union
from collections import UserList

from eodag.config import ProviderConfig, credentials_in_auth
from eodag.utils import sort_dict
from attrs import define, field

AUTH_TOPIC_KEYS = ("auth", "search_auth", "download_auth")

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

    # @property    
    # def auth_conf_with_creds(self):
    #     return [
    #         getattr(self.config, auth_key)
    #         for auth_key in AUTH_TOPIC_KEYS
    #         if hasattr(self.config, auth_key) and credentials_in_auth(getattr(self.config, auth_key))
    #     ]

    def product(self, product_type: str) -> Optional[Any]:
        """Return a product type if available from this provider."""
        return self.products.get(product_type)

    def delete_product(self, product_type: str) -> None:
        """Remove a product type from this provider."""
        if self.product(product_type):
            del self.products[product_type]
        else:
            raise KeyError(f"Product type '{product_type}' not found in provider '{self.name}'.")


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

    def __repr__(self) -> str:
        return f"ProvidersList({[p.name for p in self.data]})"
    
    def get(self, name: str) -> Optional[Provider]:
        for p in self.data:
            if p.name == name:
                return p
        return None

    def share_credentials(self) -> None:
        """
        Share credentials between plugins having the same matching criteria
        across all providers in this list.
        """
        auth_confs_with_creds = self._get_auth_confs_with_credentials()
        if not auth_confs_with_creds:
            return

        for provider in self.data:
            for auth_topic_key in AUTH_TOPIC_KEYS:
                provider_auth_config = getattr(provider.config, auth_topic_key, None)
                if provider_auth_config and not credentials_in_auth(provider_auth_config):
                    self._copy_matching_credentials(
                        provider_auth_config, auth_confs_with_creds, provider, auth_topic_key
                    )

    def _get_auth_confs_with_credentials(self) -> list[Any]:
        """
        Collect all auth configs from all providers that already have credentials.
        """
        return [
            getattr(provider.config, auth_key)
            for provider in self.data
            for auth_key in AUTH_TOPIC_KEYS
            if hasattr(provider.config, auth_key) and credentials_in_auth(getattr(provider.config, auth_key))
        ]

    def _copy_matching_credentials(
        self,
        target_auth_config: Any,
        auth_confs_with_creds: list[Any],
        provider: Provider,
        auth_topic_key: str,
    ) -> None:
        """
        Copy credentials from matching auth configs to the target auth config.
        """
        target_matching_conf = getattr(target_auth_config, "matching_conf", {})
        target_matching_url = getattr(target_auth_config, "matching_url", None)

        for conf_with_creds in auth_confs_with_creds:
            if self._is_matching_auth(target_matching_conf, target_matching_url, conf_with_creds):
                # Set credentials from the matching config
                getattr(provider.config, auth_topic_key).credentials = conf_with_creds.credentials

    @staticmethod
    def _is_matching_auth(
        target_matching_conf: dict,
        target_matching_url: Optional[str],
        conf_with_creds: Any,
    ) -> bool:
        """
        Check if the target auth config matches the given config with credentials.
        """
        conf_with_creds_matching_conf = getattr(conf_with_creds, "matching_conf", {})
        conf_with_creds_matching_url = getattr(conf_with_creds, "matching_url", None)

        if target_matching_conf and sort_dict(target_matching_conf) == sort_dict(conf_with_creds_matching_conf):
            return True
        if target_matching_url and target_matching_url == conf_with_creds_matching_url:
            return True
        return False