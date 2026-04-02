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
from typing import TYPE_CHECKING, Any, Iterator, Optional, TypeVar, Union

import importlib_metadata

from eodag.config import PluginConfig, load_config
from eodag.plugins.apis.base import Api
from eodag.plugins.authentication.base import Authentication
from eodag.plugins.base import PluginTopic
from eodag.plugins.crunch.base import Crunch
from eodag.plugins.download.base import Download
from eodag.plugins.search.base import Search
from eodag.utils import (
    AUTH_TOPIC_KEYS,
    GENERIC_COLLECTION,
    PLUGINS_TOPIC_KEYS,
    dict_md5sum,
)
from eodag.utils.exceptions import (
    AuthenticationError,
    MisconfiguredError,
    UnsupportedProvider,
)

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3ServiceResource
    from requests.auth import AuthBase

    from eodag.api.product import EOProduct
    from eodag.databases.base import Database

logger = logging.getLogger("eodag.plugins.manager")

T = TypeVar("T", bound=PluginTopic)

AuthCacheKey = tuple[str, str, str]  # (provider, auth_type, conf_hash)


class PluginManager:
    """Entry-point loader for eodag plugins.


    The role of instances of this class (normally only one instance exists,
    created during instantiation of :class:`~eodag.api.core.EODataAccessGateway`.
    But nothing is done to enforce this) is to instantiate the plugins
    according to the providers configuration, keep track of them in memory, and
    manage a cache of plugins already constructed. The providers configuration contains
    information such as the name of the provider, the internet endpoint for accessing
    it, and the plugins to use to perform defined actions (search, download,
    authenticate, crunch).

    :param providers: The ProvidersDict instance with all information about the providers
                      supported by ``eodag``
    """

    skipped_plugins: list[str]
    external_providers_config: dict[str, dict[str, Any]]
    _db: Database
    _creds_store: Optional[dict[str, dict[str, Any]]] = None

    def __init__(self, db: Database) -> None:
        self.skipped_plugins: list[str] = []
        self.external_providers_config: dict[str, dict[str, Any]] = {}
        self._auth_plugins_cache: dict[AuthCacheKey, Authentication] = {}
        self._db = db

        for topic in PLUGINS_TOPIC_KEYS:
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
                        entry_point.name,
                    )
                if entry_point.dist and entry_point.dist.name != "eodag":
                    name = entry_point.dist.name
                    dist = entry_point.dist
                    plugin_providers_config_path = [
                        str(x) for x in dist.locate_file(name).rglob("providers.yml")
                    ]
                    if plugin_providers_config_path:
                        plugin_configs = load_config(plugin_providers_config_path[0])
                        self.external_providers_config.update(plugin_configs)

    # creds_store handling
    @property
    def creds_store(self) -> dict[str, dict[str, Any]]:
        """Get creds_store for the auth plugin.

        :returns: creds_store, or None if not set
        """
        if self._creds_store is None:
            raise ValueError("creds_store can not be null")
        return self._creds_store

    @creds_store.setter
    def creds_store(self, value: dict[str, dict[str, Any]]) -> None:
        """Set creds_store.

        :param value: The value of creds_store to set
        """
        self._creds_store = value

    @staticmethod
    def get_crunch_plugin(name: str, **options: Any) -> Crunch:
        """Instantiate a eodag Crunch plugin whose class name is ``name``,
        and configure it with ``options``.

        :param name: The name of the Crunch plugin to instantiate
        :param options: The configuration parameters of the cruncher
        :returns: The cruncher named ``name``
        """
        klass = Crunch.get_plugin_by_class_name(name)
        return klass(options)

    def get_search_plugins(
        self,
        collection: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> Iterator[Union[Search, Api]]:
        """Build and return all the search plugins supporting the given collection,
        ordered by highest priority, or the search plugin of the given provider

        :param collection: (optional) The collection that the constructed plugins
                             must support
        :param provider: (optional) The provider or the provider group on which to get
            the search plugins
        :returns: All the plugins supporting the collection, one by one (a generator
                  object)
            or :class:`~eodag.plugins.download.Api`)
        :raises: :class:`~eodag.utils.exceptions.UnsupportedProvider`
        """

        # raise an error if a provider is given but is not found
        if provider is not None:
            providers = self._db.get_federation_backends(names={provider}, enabled=True)
            if not providers:
                msg = f"Provider {provider} unknown or not enabled"
                raise UnsupportedProvider(msg)

        providers = self._db.get_federation_backends(
            names={provider} if provider else None, enabled=True, collection=collection
        )
        if not providers:
            logger.info("UnsupportedCollection: %s, using generic settings", collection)
            collection = GENERIC_COLLECTION
            providers = self._db.get_federation_backends(
                enabled=True, collection=collection
            )

        for p_name in providers:
            pc = self._db.get_fb_config(p_name, {collection} if collection else None)

            if "search" in pc:
                mode, topic_class = "search", Search
            elif "api" in pc:
                mode, topic_class = "api", Api
            else:
                raise MisconfiguredError(
                    f"No search or api plugin configured for provider {p_name}."
                )

            plugin_conf = pc[mode] | {
                "priority": pc["priority"],
                "products": pc["products"],
            }

            yield topic_class.get_plugin_by_class_name(plugin_conf["type"])(
                p_name, PluginConfig.from_mapping(plugin_conf)
            )

    def get_download_plugin(self, product: EOProduct) -> Union[Download, Api]:
        """Build and return the download plugin for the given product."""
        from eodag.plugins.apis.base import Api
        from eodag.plugins.download.base import Download

        pc = self._db.get_fb_config(product.provider, {product.collection})
        if not pc:
            raise UnsupportedProvider(
                f"Provider {product.provider} not found with collection {product.collection}"
            )

        if "download" in pc:
            mode, topic_class = "download", Download
        elif "api" in pc:
            mode, topic_class = "api", Api
        else:
            raise MisconfiguredError(
                f"No download plugin configured for provider {product.provider}."
            )
        plugin_conf = pc[mode] | {"priority": pc["priority"]}

        return topic_class.get_plugin_by_class_name(plugin_conf["type"])(
            product.provider, PluginConfig.from_mapping(plugin_conf)
        )

    def get_auth_plugin(
        self,
        associated_plugin: PluginTopic,
        product: Optional[EOProduct] = None,
    ) -> Authentication | None:
        """Build and return the auth plugin for the given search/download plugin.

        :param associated_plugin: The plugin that needs authentication
        :param product: The product to download (None for search auth)
        :returns: An authentication plugin or None
        """
        if product is not None and len(product.assets) > 0:
            matching_url = next(iter(product.assets.values()))["href"]
        elif product is not None:
            matching_url = product.properties.get(
                "eodag:download_link"
            ) or product.properties.get("eodag:order_link")
        else:
            matching_url = getattr(associated_plugin.config, "api_endpoint", None)

        try:
            return next(
                self.get_auth_plugins(
                    associated_plugin.provider,
                    matching_url=matching_url,
                    matching_conf=associated_plugin.config,
                )
            )
        except StopIteration:
            return None

    def _get_or_create_auth_plugin(
        self,
        provider: str,
        auth_conf: dict[str, Any],
        auth_key: str,
        priority: int,
    ) -> Authentication:
        conf_hash = dict_md5sum(auth_conf)

        cache_key = (provider, auth_conf["type"], conf_hash)
        cached = self._auth_plugins_cache.get(cache_key)
        if cached is not None:
            return cached

        auth_conf["credentials"] = self._creds_store.get(provider, {}).get(auth_key, {})
        plugin_conf = PluginConfig.from_mapping(auth_conf | {"priority": priority})
        plugin = Authentication.get_plugin_by_class_name(auth_conf["type"])(
            provider, plugin_conf
        )
        self._auth_plugins_cache[cache_key] = plugin
        return plugin

    def get_auth_plugins(
        self,
        provider: str,
        matching_url: Optional[str] = None,
        matching_conf: Optional[PluginConfig] = None,
    ) -> Iterator[Authentication]:
        """Build and return the authentication plugin for the given collection and
        provider

        :param provider: The provider for which to get the authentication plugin
        :param matching_url: url to compare with plugin matching_url pattern
        :param matching_conf: configuration to compare with plugin matching_conf
        :returns: All the Authentication plugins for the given criteria
        """
        auth_conf: Optional[dict[str, Any]] = None

        def _is_auth_plugin_matching(
            auth_conf: dict[str, Any],
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

        all_providers = [provider] + [
            p for p in self._db.get_federation_backends(enabled=True) if p != provider
        ]

        for p in all_providers:
            provider_conf = self._db.get_fb_config(p, collections=None)

            for key in AUTH_TOPIC_KEYS:
                auth_conf = provider_conf.get(key, None) if provider_conf else None
                if auth_conf is None:
                    continue

                # plugin without configured match criteria: only works for given provider
                unconfigured_match = (
                    True
                    if (
                        not auth_conf.get("matching_conf", {})
                        and not auth_conf.get("matching_url", None)
                        and provider == p
                    )
                    else False
                )

                if unconfigured_match or _is_auth_plugin_matching(
                    auth_conf, matching_url, matching_conf
                ):
                    yield self._get_or_create_auth_plugin(
                        p, auth_conf, key, provider_conf["priority"]
                    )

    def get_auth(
        self,
        provider: str,
        matching_url: Optional[str] = None,
        matching_conf: Optional[PluginConfig] = None,
    ) -> AuthBase | S3ServiceResource | None:
        """Authenticate and return the auth object for the first matching plugin.

        :param provider: The provider for which to authenticate
        :param matching_url: URL to compare with plugin matching_url pattern
        :param matching_conf: Config to compare with plugin matching_conf
        :returns: The authenticated object or None
        """
        for auth_plugin in self.get_auth_plugins(provider, matching_url, matching_conf):
            if auth_plugin and callable(getattr(auth_plugin, "authenticate", None)):
                try:
                    return auth_plugin.authenticate()
                except (AuthenticationError, MisconfiguredError) as e:
                    logger.debug(f"Could not authenticate on {provider}: {str(e)}")
                    continue
            else:
                logger.debug(
                    f"Could not authenticate on {provider} using {auth_plugin} plugin"
                )
                continue
        return None
