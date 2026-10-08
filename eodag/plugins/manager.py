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
import pathlib
import re
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, Optional, TypeVar, Union

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

    from eodag.api.product._product import EOProduct
    from eodag.api.provider import DisabledProviderReason
    from eodag.config import ProviderConfig
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

    skipped_plugins: dict[str, str]
    external_providers_config: dict[str, ProviderConfig]
    _db: Database
    _creds_store: Optional[dict[str, dict[str, Any]]] = None

    def __init__(self, db: Database) -> None:
        self.skipped_plugins: dict[str, str] = {}
        self.external_providers_config: dict[str, ProviderConfig] = {}
        self.disabled_providers_reasons: dict[str, DisabledProviderReason] = {}
        self._auth_plugins_cache: dict[AuthCacheKey, Authentication] = {}
        self._db = db

        for topic in PLUGINS_TOPIC_KEYS:
            for entry_point in importlib_metadata.entry_points(
                group=f"eodag.plugins.{topic}"
            ):
                try:
                    entry_point.load()
                except ModuleNotFoundError:
                    msg = (
                        f"{entry_point.name} plugin skipped, "
                        f"eodag[{','.join(entry_point.extras)}] or eodag[all] needed"
                    )
                    logger.debug(msg)
                    self.skipped_plugins[entry_point.name] = msg
                except ImportError:
                    import traceback as tb

                    logger.warning("Unable to load plugin: %s.", entry_point.name)
                    logger.warning("Reason:\n%s", tb.format_exc())
                    logger.warning(
                        "Check that the plugin module (%s) is importable",
                        entry_point.name,
                    )
                plugin_config_paths = self._get_external_provider_config_paths(
                    entry_point
                )
                if plugin_config_paths:
                    plugin_configs: dict[str, ProviderConfig] = {}
                    for path in plugin_config_paths:
                        plugin_configs.update(load_config(path.as_posix()))
                    self.external_providers_config.update(plugin_configs)

    def _get_external_provider_config_paths(
        self,
        entry_point: importlib_metadata.EntryPoint,
    ) -> list[pathlib.Path]:
        """Return provider config paths exposed by an external plugin distribution."""
        config_paths: list[pathlib.Path] = []
        dist = entry_point.dist
        dist_name = getattr(dist, "name", None)

        if not dist or not isinstance(dist_name, str) or dist_name == "eodag":
            return config_paths

        providers_dir = pathlib.Path(
            str(dist.locate_file(pathlib.Path("eodag/providers")))
        )
        if providers_dir.exists() and providers_dir.is_dir():
            config_paths.extend(
                path for path in providers_dir.iterdir() if path.is_file()
            )

        module_name = getattr(entry_point, "module", None)
        if isinstance(module_name, str) and module_name:
            module_path = pathlib.Path(module_name.replace(".", "/"))

            # Check providers/ subdirectory within the module
            module_providers_dir = pathlib.Path(
                str(dist.locate_file(module_path / "providers"))
            )
            if module_providers_dir.exists() and module_providers_dir.is_dir():
                config_paths.extend(
                    path for path in module_providers_dir.iterdir() if path.is_file()
                )

            # Legacy: single providers.yml file at the module root
            providers_yml = pathlib.Path(
                str(dist.locate_file(module_path / "providers.yml"))
            )
            if providers_yml.exists() and providers_yml.is_file():
                config_paths.append(providers_yml)

        return config_paths

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
        """Instantiate a eodag Crunch plugin whose class name is ``name``, and configure it with ``options``.

        :param name: The name of the Crunch plugin to instantiate
        :param options: The configuration parameters of the cruncher
        :returns: The cruncher named ``name``
        """
        klass = Crunch.get_plugin_by_class_name(name)
        return klass(options)

    def get_skipped_plugin_messages(self, provider_config: ProviderConfig) -> list[str]:
        """Return skipped plugin messages for plugins used by a provider config."""
        return [
            self.skipped_plugins[plugin_conf.type]
            for plugin_conf in provider_config.__dict__.values()
            if isinstance(plugin_conf, PluginConfig)
            and getattr(plugin_conf, "type", None) in self.skipped_plugins
        ]

    def check_provider_available(self, provider: str) -> None:
        """Check whether a provider can be used by plugins.

        Plugin availability is reflected in the provider disabled reasons recorded during
        gateway initialization.

        :param provider: The name of the provider (or group, if ``include_groups``) to check.
        :raises MisconfiguredError: If the provider has been disabled for a configuration reason.
        :raises UnsupportedProvider: If the provider/group is unknown, or if the provider
                                     has been disabled because a required plugin was skipped.
        """
        if provider in self._db.get_federation_backends(enabled=False):
            if reason_dict := self.disabled_providers_reasons.get(provider):
                reason = reason_dict["reason"]
                if reason_dict["reason_type"] == "skipped_plugin":
                    msg = f"{provider}: provider is not available because {reason}"
                    raise UnsupportedProvider(msg)
                msg = f"{provider}: {reason}"
                raise MisconfiguredError(msg)
            # Fallback for legacy/manual disabled entries missing an explicit reason.
            msg = f"{provider}: provider has been disabled and is not available"
            raise UnsupportedProvider(msg)
        known = provider in self._db.get_federation_backends(enabled=True)
        if not known:
            msg = f"{provider}: provider is not recognised by eodag"
            raise UnsupportedProvider(msg)

    def get_search_plugins(
        self,
        collection: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> Iterator[Union[Search, Api]]:
        """Build and return all the search plugins supporting the given collection,
        ordered by highest priority, or the search plugin of the given provider.

        :param collection: (optional) The collection that the constructed plugins
                             must support
        :param provider: (optional) The provider or the provider group on which to get
            the search plugins
        :returns: All the plugins supporting the collection, one by one (a generator
                  object)
            or :class:`~eodag.plugins.download.Api`)
        :raises: :class:`~eodag.utils.exceptions.UnsupportedProvider`
        """
        if provider:
            self.check_provider_available(provider)

        generic_collection_used = False
        providers = self._db.get_federation_backends(
            enabled=True, collection=collection
        )
        if not providers and collection:
            logger.info("UnsupportedCollection: %s, using generic settings", collection)
            providers = self._db.get_federation_backends(
                enabled=True, collection=GENERIC_COLLECTION
            )
            generic_collection_used = True

        if provider:
            prov = providers.get(provider)
            if prov is None and collection:
                raise UnsupportedProvider(
                    f"{provider} is not (yet) supported for {collection}"
                )

            providers = {provider: prov} if prov else {}

        for p_name in providers:
            # get config of one collection if given, otherwise get config of all collections of the provider
            # to be able to have a mapping for metadata from any of them
            if collection and generic_collection_used:
                collections = {GENERIC_COLLECTION}
            elif collection:
                collections = {collection}
            else:
                p_name_collections, _ = self._db.collections_search(
                    federation_backends=[p_name]
                )
                collections_id: set[str] = set(c["id"] for c in p_name_collections)
                collections = {GENERIC_COLLECTION} | collections_id

            p_c = self._db.get_fb_config(p_name, collections)

            # add configuration for another collection if needed to have a mapping for metadata from it
            other_product_for_mapping: Optional[str] = (
                p_c["products"]
                .get(collection, {})
                .get("metadata_mapping_from_product", None)
            )
            if other_product_for_mapping:
                op_c = self._db.get_fb_config(p_name, {other_product_for_mapping})
                p_c["products"].update(op_c["products"])

            if "search" in p_c:
                mode, topic_class = "search", Search
            elif "api" in p_c:
                mode, topic_class = "api", Api
            else:
                raise MisconfiguredError(
                    f"No search or api plugin configured for provider {p_name}."
                )

            plugin_conf = p_c[mode] | {
                "priority": p_c["priority"],
                "products": p_c["products"],
            }

            yield topic_class.get_plugin_by_class_name(plugin_conf["type"])(
                p_name, PluginConfig.from_mapping(plugin_conf)
            )

    def get_download_plugin(self, product: EOProduct) -> Union[Download, Api]:
        """Build and return the download plugin for the given product."""
        self.check_provider_available(product.provider)

        pc = self._db.get_fb_config(
            product.provider, {product.collection} if product.collection else None
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

        auth_conf["credentials"] = self.creds_store.get(provider, {}).get(auth_key, {})
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
        """Build and yield authentication plugins matching the given criteria.

        An auth plugin matches when either its ``matching_url`` pattern matches
        ``matching_url`` or its ``matching_conf`` is a subset of ``matching_conf``.
        The requested provider is considered first, followed by other providers.

        :param provider: The provider for which to get the authentication plugin
        :param matching_url: url to compare with plugin matching_url pattern
        :param matching_conf: configuration to compare with plugin matching_conf
        :returns: Iterator of authentication plugins matching the given criteria
        """
        auth_conf: Optional[dict[str, Any]] = None

        def _is_auth_plugin_matching(
            auth_conf: dict[str, Any],
            matching_url: Optional[str],
            matching_conf: Optional[PluginConfig],
        ) -> bool:
            plugin_matching_conf = auth_conf.get("matching_conf", {})
            if matching_conf:
                if (
                    plugin_matching_conf
                    and matching_conf.__dict__.items() >= plugin_matching_conf.items()
                ):
                    # conf matches
                    return True
            plugin_matching_url = auth_conf.get("matching_url", None)
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
                    logger.debug(f"Could not authenticate on {provider}: {e!s}")
                    continue
            else:
                logger.debug(
                    f"Could not authenticate on {provider} using {auth_plugin} plugin"
                )
                continue
        return None

    # TODO: add tests for all the methods of this class
