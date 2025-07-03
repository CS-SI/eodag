from typing import Any, Optional, Union, Self, Iterator
from collections import UserDict
from dataclasses import dataclass
import yaml
import logging

from eodag.api.plugin import credentials_in_auth, PluginConfig
from eodag.utils import slugify, merge_mappings

from eodag.utils.exceptions import ValidationError

logger = logging.getLogger("eodag.provider")

AUTH_TOPIC_KEYS = ("auth", "search_auth", "download_auth")
PLUGINS_TOPICS_KEYS = ("api", "search", "download") + AUTH_TOPIC_KEYS


class ProviderConfig(yaml.YAMLObject):
    """Representation of eodag configuration.

    :param name: The name of the provider
    :param priority: (optional) The priority of the provider while searching a product.
                     Lower value means lower priority. (Default: 0)
    :param api: (optional) The configuration of a plugin of type Api
    :param search: (optional) The configuration of a plugin of type Search
    :param products: (optional) The products types supported by the provider
    :param download: (optional) The configuration of a plugin of type Download
    :param auth: (optional) The configuration of a plugin of type Authentication
    :param search_auth: (optional) The configuration of a plugin of type Authentication for search
    :param download_auth: (optional) The configuration of a plugin of type Authentication for download
    :param kwargs: Additional configuration variables for this provider
    """

    name: str
    group: str
    priority: int = 0  # Set default priority to 0
    roles: list[str]
    description: str
    url: str
    api: PluginConfig
    search: PluginConfig
    products: dict[str, Any]
    download: PluginConfig
    auth: PluginConfig
    search_auth: PluginConfig
    download_auth: PluginConfig
    product_types_fetched: bool  # set in core.update_product_types_list

    yaml_loader = yaml.Loader
    yaml_dumper = yaml.SafeDumper
    yaml_tag = "!provider"

    @classmethod
    def from_yaml(cls, loader: yaml.Loader, node: Any) -> Self:
        """Build a :class:`~eodag.config.ProviderConfig` from Yaml"""
        cls.validate(tuple(node_key.value for node_key, _ in node.value))
        for node_key, node_value in node.value:
            if node_key.value == "name":
                node_value.value = slugify(node_value.value).replace("-", "_")
                break
        return loader.construct_yaml_object(node, cls)

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> Self:
        """Build a :class:`~eodag.config.ProviderConfig` from a mapping"""
        cls.validate(mapping)
        for key in PLUGINS_TOPICS_KEYS:
            if key in mapping:
                mapping[key] = PluginConfig.from_mapping(mapping[key])
        c = cls()
        c.__dict__.update(mapping)
        return c

    @staticmethod
    def validate(config_keys: Union[tuple[str, ...], dict[str, Any]]) -> None:
        """Validate a :class:`~eodag.config.ProviderConfig`

        :param config_keys: The configurations keys to validate
        """
        if "name" not in config_keys:
            raise ValidationError("Provider config must have name key")
        if not any(k in config_keys for k in PLUGINS_TOPICS_KEYS):
            raise ValidationError("A provider must implement at least one plugin")
        non_api_keys = [k for k in PLUGINS_TOPICS_KEYS if k != "api"]
        if "api" in config_keys and any(k in config_keys for k in non_api_keys):
            raise ValidationError(
                "A provider implementing an Api plugin must not implement any other "
                "type of plugin"
            )

    def update(self, mapping: Optional[dict[str, Any]]) -> None:
        """Update the configuration parameters with values from `mapping`

        :param mapping: The mapping from which to override configuration parameters
        """
        if mapping is None:
            mapping = {}
        merge_mappings(
            self.__dict__,
            {
                key: value
                for key, value in mapping.items()
                if key not in PLUGINS_TOPICS_KEYS and value is not None
            },
        )
        for key in PLUGINS_TOPICS_KEYS:
            current_value: Optional[PluginConfig] = getattr(self, key, None)
            mapping_value = mapping.get(key, {})
            if current_value is not None:
                current_value.update(mapping_value)
            elif mapping_value:
                try:
                    setattr(self, key, PluginConfig.from_mapping(mapping_value))
                except ValidationError as e:
                    logger.warning(
                        (
                            "Could not add %s Plugin config to %s configuration: %s. "
                            "Try updating existing %s Plugin configs instead."
                        ),
                        key,
                        self.name,
                        str(e),
                        ", ".join([k for k in PLUGINS_TOPICS_KEYS if hasattr(self, k)]),
                    )

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
        providers: list[Provider] | dict[str, PluginConfig] | None,
    ):
        super().__init__()
        
        if providers is None:
            self.data = {}
            
        elif isinstance(providers, dict):
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