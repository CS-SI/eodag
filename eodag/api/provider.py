import logging
from typing import Any, Dict, Iterator, List, Optional, Union

from pydantic import validator

from eodag.config import ProviderConfig
from eodag.plugins.apis.base import Api
from eodag.plugins.authentication.base import Authentication
from eodag.plugins.download.base import Download
from eodag.plugins.manager import PluginManager
from eodag.plugins.search.base import Search
from eodag.utils.exceptions import ValidationError
from eodag.utils.pydantic import BaseModel

logger = logging.getLogger("eodag.api.provider")


class Provider(BaseModel):
    """Represent a provider in EODAG"""

    class Config:
        """
        Configuration class for the Provider class.
        """

        arbitrary_types_allowed = True

    #     extra = Extra.allow

    name: str
    priority: int
    search: Union[Search, Api]
    download: Union[Download, Api]
    auth: Optional[Authentication]
    product_types: Dict[str, Any]

    @validator("search", pre=True)
    def check_search(cls, v, values):
        """
        Validate the search attribute.

        :param v: The value of the search attribute.
        :param values: The values of the other attributes.
        :return: The validated value of the search attribute.
        :raises ValidationError: If the search attribute is not valid.
        """
        assert isinstance(v, (Search, Api)), "search must be of type Search or Api"
        if hasattr(v, "need_auth") and v.need_auth:
            if not values.get("auth"):
                raise ValidationError(f"auth missing for provider {values.get('name')}")
        return v

    @validator("download", pre=True)
    def check_download(cls, v):
        """
        Validate the download attribute.

        :param v: The value of the download attribute.
        :return: The validated value of the download attribute.
        :raises ValidationError: If the download attribute is not valid.
        """
        assert isinstance(
            v, (Download, Api)
        ), "download must be of type Download or Api"
        return v

    @validator("auth", pre=True)
    def check_auth(cls, v):
        """
        Validate the auth attribute.

        :param v: The value of the auth attribute.
        :return: The validated value of the auth attribute.
        :raises ValidationError: If the auth attribute is not valid.
        """
        assert (
            isinstance(v, Authentication) or v is None
        ), "auth must be of type Authentication or None"
        return v

    def __init__(
        self,
        config: ProviderConfig,
        manager: PluginManager,
    ):
        """
        Initialize a new Provider instance.

        :param config: The configuration for this provider.
        :type config: ProviderConfig
        :param manager: The plugin manager for this provider.
        :type manager: PluginManager
        """

        super().__init__(
            name=config.name,
            priority=config.priority,
            auth=manager.get_auth_plugin(config.name)
            if hasattr(config, "auth") and config.auth
            else None,
            search=list(manager.get_search_plugins(provider=config.name))[0],
            download=manager.get_download_plugin(config.name),
            product_types=config.products,
            config=config,
        )

        if self.auth:
            self.download.http = self.auth.http_requests()

            if getattr(self.search.config, "need_auth", False):
                self.search.http = self.auth.http_requests()

    def __str__(self):
        """
        Return a string representation of this Provider instance.

        :return: A string representation of this Provider instance.
        """
        return self.name


class ProviderList:
    """
    A class that represents a list of providers and allows you to access them using the syntax
    providers[provider_name] or providers.provider_name. It also sorts the providers by priority
    (highest to lowest) and then by name (alphabetically) when you iterate over them.
    """

    def __init__(self):
        """Initialize an empty list of providers."""
        self.providers: Dict[str, Provider] = {}

    def __getitem__(self, provider_name: str) -> Provider:
        """Get a provider by its name using the syntax providers[provider_name]."""
        return self.providers[provider_name]

    def __setitem__(self, provider_name: str, provider: Provider) -> None:
        """Add a provider to the list using the syntax providers[provider_name] = provider."""
        self.providers[provider_name] = provider

    def __delitem__(self, provider_name: str) -> None:
        """Remove a provider from the list using the syntax del providers[provider_name]."""
        del self.providers[provider_name]

    def __getattr__(self, provider_name: str) -> Provider:
        """Get a provider by its name using the syntax providers.provider_name."""
        return self.providers[provider_name]

    def __setattr__(
        self, provider_name: str, provider: Union[Dict[str, Provider], Provider]
    ) -> None:
        """Add a provider to the list using the syntax providers.provider_name = provider."""
        if provider_name in ("providers",):
            super().__setattr__(provider_name, provider)
        else:
            self.providers[provider_name] = provider

    def __delattr__(self, provider_name: str) -> None:
        """Remove a provider from the list using the syntax del providers.provider_name."""
        del self.providers[provider_name]

    def __iter__(self) -> Iterator[Provider]:
        """
        Iterate over the providers in the list, sorted by priority (highest to lowest)
        and then by name (alphabetically).
        """
        sorted_providers = sorted(
            self.providers.values(), key=lambda p: (-p.priority, p.name)
        )
        for provider in sorted_providers:
            yield provider

    def keys(self) -> List[str]:
        """
        Return a list of the names of all providers in this list, sorted by priority (highest to lowest)
        and then by name (alphabetically).
        """
        sorted_providers = sorted(
            self.providers.values(), key=lambda p: (-p.priority, p.name)
        )
        return [provider.name for provider in sorted_providers]

    def __contains__(self, provider_name: str) -> bool:
        """Check if a provider with the given name exists in this list using the syntax 'provider_name' in providers."""
        return provider_name in self.providers

    def get_providers_with_product_type(self, product_type: str) -> "ProviderList":
        """
        Return a new ProviderList instance that contains only the providers that have the given product type
        in their product_types dictionary.
        """
        filtered_providers = ProviderList()
        for provider in self.providers.values():
            if product_type in provider.product_types:
                filtered_providers[provider.name] = provider
        return filtered_providers

    def get_preferred(self) -> Provider:
        """Return the provider with the highest priority in this list."""
        return max(self.providers.values(), key=lambda p: p.priority).name

    def set_preferred(self, provider_name: str) -> None:
        """Set the preferred provider by making its priority higher by 1 point from the current highest priority."""
        preferred_provider = self.get_preferred()
        self.providers[provider_name].priority = preferred_provider.priority + 1

    def __len__(self):
        # return the length of the object
        return len(self.providers)
