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
from __future__ import annotations

import logging
import re
from operator import attrgetter
from typing import TYPE_CHECKING, Any, Iterator, Optional, Union, cast

import importlib_metadata

from eodag.config import (
    AUTH_TOPIC_KEYS,
    PLUGINS_TOPICS_KEYS,
    load_config,
    merge_configs,
)
from eodag.plugins.apis.base import Api
from eodag.plugins.authentication.base import Authentication
from eodag.plugins.base import EODAGPluginMount
from eodag.plugins.crunch.base import Crunch
from eodag.plugins.download.base import Download
from eodag.plugins.search.base import Search
from eodag.utils import GENERIC_PRODUCT_TYPE, deepcopy, dict_md5sum
from eodag.utils.exceptions import (
    AuthenticationError,
    MisconfiguredError,
    UnsupportedProvider,
)

if TYPE_CHECKING:
    from requests.auth import AuthBase

    from eodag.api.product import EOProduct
    from eodag.config import PluginConfig, ProviderConfig
    from eodag.plugins.base import PluginTopic
    from eodag.types import S3SessionKwargs


logger = logging.getLogger("eodag.plugins.manager")


class PluginManager:
    """A manager for the plugins.

    The role of instances of this class (normally only one instance exists,
    created during instantiation of :class:`~eodag.api.core.EODataAccessGateway`.
    But nothing is done to enforce this) is to instantiate the plugins
    according to the providers configuration, keep track of them in memory, and
    manage a cache of plugins already constructed. The providers configuration contains
    information such as the name of the provider, the internet endpoint for accessing
    it, and the plugins to use to perform defined actions (search, download,
    authenticate, crunch).

    :param providers_config: The configuration with all information about the providers
                             supported by ``eodag``
    """

    supported_topics = set(PLUGINS_TOPICS_KEYS)

    product_type_to_provider_config_map: dict[str, list[ProviderConfig]]

    skipped_plugins: list[str]

    def __init__(self, providers_config: dict[str, ProviderConfig]) -> None:
        self.skipped_plugins = []
        self.providers_config = providers_config
        # Load all the plugins. This will make all plugin classes of a particular
        # type to be available in the base plugin class's 'plugins' attribute.
        # For example, by importing module 'eodag.plugins.search.resto', the plugin
        # 'RestoSearch' will be available in self.supported_topics['search'].plugins
        for topic in self.supported_topics:
            # This way of discovering plugins means that anyone can create eodag
            # plugins as a separate python package (though it must require eodag), and
            # have it discovered as long as they declare an entry point of the type
            # 'eodag.plugins.search' for example in its setup script. See the setup
            # script of eodag for an example of how to do this.
            for entry_point in importlib_metadata.entry_points(
                group="eodag.plugins.{}".format(topic)
            ):
                try:
                    entry_point.load()
                except ModuleNotFoundError:
                    logger.debug(
                        "%s plugin skipped, eodag[%s] or eodag[all] needed",
                        entry_point.name,
                        ",".join(entry_point.extras),
                    )
                    self.skipped_plugins.append(entry_point.name)
                except ImportError:
                    import traceback as tb

                    logger.warning("Unable to load plugin: %s.", entry_point.name)
                    logger.warning("Reason:\n%s", tb.format_exc())
                    logger.warning(
                        "Check that the plugin module (%s) is importable",
                        entry_point.module_name,
                    )
                if entry_point.dist and entry_point.dist.name != "eodag":
                    # use plugin providers if any
                    name = entry_point.dist.name
                    dist = entry_point.dist
                    plugin_providers_config_path = [
                        str(x) for x in dist.locate_file(name).rglob("providers.yml")
                    ]
                    if plugin_providers_config_path:
                        plugin_providers_config = load_config(
                            plugin_providers_config_path[0]
                        )
                        merge_configs(plugin_providers_config, self.providers_config)
                        self.providers_config = plugin_providers_config
        self.rebuild()

    def rebuild(
        self, providers_config: Optional[dict[str, ProviderConfig]] = None
    ) -> None:
        """(Re)Build plugin manager mapping and cache"""
        if providers_config is not None:
            self.providers_config = providers_config

        self.build_product_type_to_provider_config_map()
        self._built_plugins_cache: dict[tuple[str, str, str], Any] = {}

    def build_product_type_to_provider_config_map(self) -> None:
        """Build mapping conf between product types and providers"""
        self.product_type_to_provider_config_map = {}
        for provider in list(self.providers_config):
            provider_config = self.providers_config[provider]
            if not hasattr(provider_config, "products") or not provider_config.products:
                logger.info(
                    "%s: provider has no product configured and will be skipped",
                    provider,
                )
                self.providers_config.pop(provider)
                continue

            # provider priority set to lowest if not set
            if getattr(provider_config, "priority", None) is None:
                self.providers_config[provider].priority = provider_config.priority = 0

            for product_type in provider_config.products:
                product_type_providers = (
                    self.product_type_to_provider_config_map.setdefault(  # noqa
                        product_type, []
                    )
                )
                product_type_providers.append(provider_config)
                product_type_providers.sort(key=attrgetter("priority"), reverse=True)

    def get_search_plugins(
        self, product_type: Optional[str] = None, provider: Optional[str] = None
    ) -> Iterator[Union[Search, Api]]:
        """Build and return all the search plugins supporting the given product type,
        ordered by highest priority, or the search plugin of the given provider

        :param product_type: (optional) The product type that the constructed plugins
                             must support
        :param provider: (optional) The provider or the provider group on which to get
            the search plugins
        :returns: All the plugins supporting the product type, one by one (a generator
                  object)
            or :class:`~eodag.plugins.download.Api`)
        :raises: :class:`~eodag.utils.exceptions.UnsupportedProvider`
        """

        def get_plugin() -> Union[Search, Api]:
            plugin: Union[Search, Api]
            if search := getattr(config, "search", None):
                config.search.products = config.products
                config.search.priority = config.priority
                plugin = cast(Search, self._build_plugin(config.name, search, Search))
            elif api := getattr(config, "api", None):
                config.api.products = config.products
                config.api.priority = config.priority
                plugin = cast(Api, self._build_plugin(config.name, api, Api))
            else:
                raise MisconfiguredError(
                    f"No search plugin configureed for {config.name}."
                )
            return plugin

        configs: Optional[list[ProviderConfig]]
        if product_type:
            configs = self.product_type_to_provider_config_map.get(product_type)
            if not configs:
                logger.info(
                    "UnsupportedProductType: %s, using generic settings", product_type
                )
                configs = self.product_type_to_provider_config_map[GENERIC_PRODUCT_TYPE]
        else:
            configs = list(self.providers_config.values())

        if provider:
            configs = [
                c for c in configs if provider in [getattr(c, "group", None), c.name]
            ]

        if not configs and product_type:
            raise UnsupportedProvider(
                f"{provider} is not (yet) supported for {product_type}"
            )
        if not configs:
            raise UnsupportedProvider(f"{provider} is not (yet) supported")

        for config in sorted(configs, key=attrgetter("priority"), reverse=True):
            yield get_plugin()

    def get_download_plugin(self, product: EOProduct) -> Union[Download, Api]:
        """Build and return the download plugin capable of downloading the given
        product.

        :param product: The product to get a download plugin for
        :returns: The download plugin capable of downloading the product
        """
        plugin_conf = self.providers_config[product.provider]
        if download := getattr(plugin_conf, "download", None):
            plugin_conf.download.priority = plugin_conf.priority
            plugin = cast(
                Download,
                self._build_plugin(product.provider, download, Download),
            )
        elif api := getattr(plugin_conf, "api", None):
            plugin_conf.api.products = plugin_conf.products
            plugin_conf.api.priority = plugin_conf.priority
            plugin = cast(Api, self._build_plugin(product.provider, api, Api))
        else:
            raise MisconfiguredError(
                f"No download plugin configured for provider {plugin_conf.name}."
            )
        return plugin

    def get_auth_plugin(
        self, associated_plugin: PluginTopic, product: Optional[EOProduct] = None
    ) -> Optional[Authentication]:
        """Build and return the authentication plugin associated to the given
        search/download plugin

        .. versionchanged:: v3.0.0
            ``get_auth_plugin()`` now needs ``associated_plugin`` instead of ``provider``
            as argument.

        :param associated_plugin: The search/download plugin to which the authentication
                                  plugin is linked
        :param product: The product to download. ``None`` for search authentication
        :returns: The Authentication plugin
        """
        # matching url from product to download
        if product is not None and len(product.assets) > 0:
            matching_url = next(iter(product.assets.values()))["href"]
        elif product is not None:
            matching_url = product.properties.get(
                "downloadLink"
            ) or product.properties.get("orderLink")
        else:
            # search auth
            matching_url = getattr(associated_plugin.config, "api_endpoint", None)

        try:
            auth_plugin = next(
                self.get_auth_plugins(
                    associated_plugin.provider,
                    matching_url=matching_url,
                    matching_conf=associated_plugin.config,
                )
            )
        except StopIteration:
            auth_plugin = None
        return auth_plugin

    def get_auth_plugins(
        self,
        provider: str,
        matching_url: Optional[str] = None,
        matching_conf: Optional[PluginConfig] = None,
    ) -> Iterator[Authentication]:
        """Build and return the authentication plugin for the given product_type and
        provider

        :param provider: The provider for which to get the authentication plugin
        :param matching_url: url to compare with plugin matching_url pattern
        :param matching_conf: configuration to compare with plugin matching_conf
        :returns: All the Authentication plugins for the given criteria
        """
        auth_conf: Optional[PluginConfig] = None

        def _is_auth_plugin_matching(
            auth_conf: PluginConfig,
            matching_url: Optional[str],
            matching_conf: Optional[PluginConfig],
        ) -> bool:
            plugin_matching_conf = getattr(auth_conf, "matching_conf", {})
            if matching_conf:
                if (
                    plugin_matching_conf
                    and matching_conf.__dict__.items() >= plugin_matching_conf.items()
                ):
                    # conf matches
                    return True
            plugin_matching_url = getattr(auth_conf, "matching_url", None)
            if matching_url:
                if plugin_matching_url and re.match(
                    rf"{plugin_matching_url}", matching_url
                ):
                    # url matches
                    return True
            # no match
            return False

        # providers configs with given provider at first
        sorted_providers_config = deepcopy(self.providers_config)
        sorted_providers_config = {
            provider: sorted_providers_config.pop(provider),
            **sorted_providers_config,
        }

        for plugin_provider, provider_conf in sorted_providers_config.items():
            for key in AUTH_TOPIC_KEYS:
                auth_conf = getattr(provider_conf, key, None)
                if auth_conf is None:
                    continue
                # plugin without configured match criteria: only works for given provider
                unconfigured_match = (
                    True
                    if (
                        not getattr(auth_conf, "matching_conf", {})
                        and not getattr(auth_conf, "matching_url", None)
                        and provider == plugin_provider
                    )
                    else False
                )

                if unconfigured_match or _is_auth_plugin_matching(
                    auth_conf, matching_url, matching_conf
                ):
                    auth_conf.priority = provider_conf.priority
                    plugin = cast(
                        Authentication,
                        self._build_plugin(plugin_provider, auth_conf, Authentication),
                    )
                    yield plugin
                else:
                    continue

    def get_auth(
        self,
        provider: str,
        matching_url: Optional[str] = None,
        matching_conf: Optional[PluginConfig] = None,
    ) -> Optional[Union[AuthBase, S3SessionKwargs]]:
        """Authenticate and return the authenticated object for the first matching
        authentication plugin

        :param provider: The provider for which to get the authentication plugin
        :param matching_url: url to compare with plugin matching_url pattern
        :param matching_conf: configuration to compare with plugin matching_conf
        :returns: All the Authentication plugins for the given criteria
        """
        for auth_plugin in self.get_auth_plugins(provider, matching_url, matching_conf):
            if auth_plugin and callable(getattr(auth_plugin, "authenticate", None)):
                try:
                    auth = auth_plugin.authenticate()
                    return auth
                except (AuthenticationError, MisconfiguredError) as e:
                    logger.debug(f"Could not authenticate on {provider}: {str(e)}")
                    continue
            else:
                logger.debug(
                    f"Could not authenticate on {provider} using {auth_plugin} plugin"
                )
                continue
        return None

    @staticmethod
    def get_crunch_plugin(name: str, **options: Any) -> Crunch:
        """Instantiate a eodag Crunch plugin whom class name is `name`, and configure
        it with the `options`

        :param name: The name of the Crunch plugin to instantiate
        :param options: The configuration parameters of the cruncher
        :returns: The cruncher named `name`
        """
        klass = Crunch.get_plugin_by_class_name(name)
        return klass(options)

    def sort_providers(self) -> None:
        """Sort providers taking into account current priority order"""
        for provider_configs in self.product_type_to_provider_config_map.values():
            provider_configs.sort(key=attrgetter("priority"), reverse=True)

    def set_priority(self, provider: str, priority: int) -> None:
        """Set the priority of the given provider

        :param provider: The provider which is assigned the priority
        :param priority: The priority to assign to the provider
        """
        # Update the priority in the configurations so that it is taken into account
        # when a plugin of this provider is latterly built
        for (
            _,
            provider_configs,
        ) in self.product_type_to_provider_config_map.items():
            for config in provider_configs:
                if config.name == provider:
                    config.priority = priority
            # Sort the provider configs, taking into account the new priority order
            provider_configs.sort(key=attrgetter("priority"), reverse=True)
        # Update the priority of already built plugins of the given provider
        for provider_name, topic_class, auth_match_md5 in self._built_plugins_cache:
            if provider_name == provider:
                self._built_plugins_cache[
                    (provider, topic_class, auth_match_md5)
                ].priority = priority

    def _build_plugin(
        self,
        provider: str,
        plugin_conf: PluginConfig,
        topic_class: type[PluginTopic],
    ) -> Union[Api, Search, Download, Authentication, Crunch]:
        """Build the plugin of the given topic with the given plugin configuration and
        registered as the given provider

        :param provider: The provider for which to build the plugin
        :param plugin_conf: The configuration of the plugin to be built
        :param topic_class: The type of plugin to build
        :returns: The built plugin
                :class:`~eodag.plugin.download.Download` or
                :class:`~eodag.plugin.authentication.Authentication` or
                :class:`~eodag.plugin.crunch.Crunch`
        """
        # md5 hash to helps identifying an auth plugin within several for a given provider
        # (each has distinct matching settings)
        auth_match_md5 = dict_md5sum(
            {
                "matching_url": getattr(plugin_conf, "matching_url", None),
                "matching_conf": getattr(plugin_conf, "matching_conf", None),
            }
        )
        cached_instance = self._built_plugins_cache.setdefault(
            (provider, topic_class.__name__, auth_match_md5), None
        )
        if cached_instance is not None:
            return cached_instance
        plugin_class = EODAGPluginMount.get_plugin_by_class_name(
            topic_class, getattr(plugin_conf, "type")
        )
        plugin: Union[Api, Search, Download, Authentication, Crunch] = plugin_class(
            provider, plugin_conf
        )
        self._built_plugins_cache[
            (provider, topic_class.__name__, auth_match_md5)
        ] = plugin
        return plugin
