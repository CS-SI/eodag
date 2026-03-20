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
from typing import TYPE_CHECKING, Any, Iterator, Optional

import importlib_metadata

from eodag.config import AUTH_TOPIC_KEYS, PLUGINS_TOPICS_KEYS, PluginConfig, load_config
from eodag.plugins.crunch.base import Crunch
from eodag.utils import GENERIC_COLLECTION
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
    from eodag.plugins.apis.base import Api
    from eodag.plugins.authentication.base import Authentication
    from eodag.plugins.base import PluginTopic
    from eodag.plugins.download.base import Download
    from eodag.plugins.search.base import Search

logger = logging.getLogger("eodag.plugins.manager")


class PluginManager:
    """Entry-point loader for eodag plugins.

    Loads all plugin classes via setuptools entry points so that they are
    registered in the metaclass registry
    (:class:`~eodag.plugins.base.EODAGPluginMount`).  After initialisation
    every plugin class is available through
    ``TopicBase.get_plugin_by_class_name(name)``.

    External packages that ship their own ``providers.yml`` are detected and
    their raw configuration dicts are exposed via
    :attr:`external_providers_config` so that the caller can merge them into
    the database.
    """

    supported_topics = set(PLUGINS_TOPICS_KEYS)

    skipped_plugins: list[str]
    external_providers_config: dict[str, dict[str, Any]]

    def __init__(
        self,
        providers: Optional[dict[str, Any]] = None,
    ) -> None:
        self.skipped_plugins: list[str] = []
        self.external_providers_config: dict[str, dict[str, Any]] = {}
        self._db: Optional[Database] = None
        self._credentials: dict[str, Any] = {}

        for topic in self.supported_topics:
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

        # Optional convenience: set up an in-memory DB from providers (for tests)
        if providers is not None:
            from eodag.api.provider import Provider
            from eodag.config import (
                extract_credentials,
                get_collections_providers_config,
                get_federation_backends_config,
            )
            from eodag.databases.sqlite import SQLiteDatabase

            db = SQLiteDatabase(":memory:")
            configs = [
                p.config if isinstance(p, Provider) else p
                for p in providers.values()
            ]
            credentials = extract_credentials(configs)
            fb_configs = get_federation_backends_config(configs)
            db.upsert_federation_backends(fb_configs)
            coll_p_configs = get_collections_providers_config(configs)
            db.upsert_collections_federation_backends(coll_p_configs)
            self.set_db(db, credentials)

    @property
    def providers(self) -> list[str]:
        """Return the list of provider names from the DB."""
        return list(self.db.get_federation_backend_priorities().keys())

    def add_provider(self, name: str, provider: Any) -> None:
        """Add a single provider to the DB (convenience for tests)."""
        from eodag.config import (
            extract_credentials,
            get_collections_providers_config,
            get_federation_backends_config,
        )

        config = provider.config if hasattr(provider, "config") else provider
        creds = extract_credentials([config])
        self._credentials.update(creds)
        fb = get_federation_backends_config([config])
        self.db.upsert_federation_backends(fb)
        cp = get_collections_providers_config([config])
        self.db.upsert_collections_federation_backends(cp)

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

    def set_db(self, db: Database, credentials: dict[str, Any]) -> None:
        """Bind the plugin manager to a database and credentials store.

        Must be called before any ``get_*_plugin`` method.

        :param db: A :class:`~eodag.databases.sqlite.SQLiteDatabase` instance.
        :param credentials: In-memory credentials dict (provider → topic → creds).
        """
        self._db = db
        self._credentials = credentials

    @property
    def db(self) -> Database:
        """Return the bound database, raising if not set."""
        if self._db is None:
            raise MisconfiguredError("PluginManager has no database bound; call set_db() first")
        return self._db

    @staticmethod
    def build_plugin(
        provider: str,
        plugin_conf_dict: dict[str, Any],
        topic_class: type,
        priority: int = 0,
    ) -> Search | Api | Download | Authentication:
        """Build a single plugin from a config dict.

        :param provider: Provider name
        :param plugin_conf_dict: Config dict (must contain ``type``)
        :param topic_class: Base class to look up the concrete class
        :param priority: Priority to set on the plugin config
        :returns: An instantiated plugin
        """
        conf = PluginConfig.from_mapping(plugin_conf_dict)
        conf.priority = priority
        klass = topic_class.get_plugin_by_class_name(conf.type)
        return klass(provider, conf)

    def get_search_plugins(
        self,
        collection: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> Iterator[Search | Api]:
        """Build and yield search plugins for the given collection/provider.

        :param collection: The collection to search for
        :param provider: Optional provider or group filter
        :returns: Iterator of search or api plugins, ordered by priority DESC
        """
        from eodag.plugins.apis.base import Api
        from eodag.plugins.search.base import Search

        if collection:
            fb_filter = (
                self.db.filter_federation_backends(provider) if provider else None
            )
            rows = self.db.get_search_configs_for_collection(
                collection, providers=fb_filter
            )
            if not rows:
                logger.info(
                    "UnsupportedCollection: %s, using generic settings", collection
                )
                rows = self.db.get_search_configs_for_collection(
                    GENERIC_COLLECTION, providers=fb_filter
                )
        else:
            # All enabled backends
            fb_names = (
                self.db.filter_federation_backends(provider)
                if provider
                else self.db.list_federation_backend_names()
            )
            fbs = self.db.get_federation_backends(fb_names)
            rows = [
                {
                    "provider": name,
                    "plugins_config": fb["plugins_config"],
                    "priority": fb["priority"],
                    "collection_plugins_config": None,
                }
                for name, fb in sorted(
                    fbs.items(), key=lambda x: x[1]["priority"], reverse=True
                )
            ]

        if not rows and collection:
            raise UnsupportedProvider(
                f"{provider} is not (yet) supported for {collection}"
            )
        if not rows:
            raise UnsupportedProvider(f"{provider} is not (yet) supported")

        for row in rows:
            pc = row["plugins_config"]
            priority = row["priority"]
            coll_pc = row["collection_plugins_config"]
            provider_name = row["provider"]

            if "search" in pc:
                search_conf = dict(pc["search"])
                raw = self.db.get_collection_configs_for_backend(provider_name)
                search_conf["products"] = {
                    cid: cfg.get("search", cfg) for cid, cfg in raw.items()
                }
                yield self.build_plugin(provider_name, search_conf, Search, priority)
            elif "api" in pc:
                api_conf = dict(pc["api"])
                raw = self.db.get_collection_configs_for_backend(provider_name)
                api_conf["products"] = {
                    cid: cfg.get("api", cfg) for cid, cfg in raw.items()
                }
                yield self.build_plugin(provider_name, api_conf, Api, priority)

    def get_download_plugin(self, product: EOProduct) -> Download | Api:
        """Build and return the download plugin for the given product.

        :param product: The product to download
        :returns: A download or api plugin
        """
        from eodag.plugins.apis.base import Api
        from eodag.plugins.download.base import Download

        fb = self.db.get_federation_backends([product.provider])
        if not fb:
            raise UnsupportedProvider(f"Provider {product.provider} not found")
        fb_conf = fb[product.provider]
        pc = fb_conf["plugins_config"]
        priority = fb_conf["priority"]

        if "download" in pc:
            return self.build_plugin(product.provider, pc["download"], Download, priority)
        elif "api" in pc:
            api_conf = dict(pc["api"])
            return self.build_plugin(product.provider, api_conf, Api, priority)
        raise MisconfiguredError(
            f"No download plugin configured for provider {product.provider}."
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

    def get_auth_plugins(
        self,
        provider: str,
        matching_url: Optional[str] = None,
        matching_conf: Optional[PluginConfig] = None,
    ) -> Iterator[Authentication]:
        """Build and yield auth plugins matching the given criteria.

        :param provider: The provider for which to authenticate
        :param matching_url: URL to compare with plugin matching_url pattern
        :param matching_conf: Config to compare with plugin matching_conf
        :returns: Iterator of matching authentication plugins
        """
        from eodag.plugins.authentication.base import Authentication

        all_auth = self.db.get_all_auth_configs()
        sorted_providers = [provider] + [p for p in all_auth if p != provider]

        for plugin_provider in sorted_providers:
            if plugin_provider not in all_auth:
                continue
            auth_entries = all_auth[plugin_provider]

            priorities = self.db.get_federation_backend_priorities()
            priority = priorities.get(plugin_provider, 0)

            for key in AUTH_TOPIC_KEYS:
                if key not in auth_entries:
                    continue
                auth_dict = dict(auth_entries[key])

                provider_creds = self._credentials.get(plugin_provider, {})
                if key in provider_creds:
                    auth_dict["credentials"] = provider_creds[key]

                plugin_matching_conf = auth_dict.get("matching_conf", {})
                plugin_matching_url = auth_dict.get("matching_url")

                unconfigured_match = (
                    not plugin_matching_conf
                    and not plugin_matching_url
                    and provider == plugin_provider
                )

                conf_matches = False
                if matching_conf and plugin_matching_conf:
                    if matching_conf.__dict__.items() >= plugin_matching_conf.items():
                        conf_matches = True

                url_matches = False
                if matching_url and plugin_matching_url:
                    if re.match(rf"{plugin_matching_url}", matching_url):
                        url_matches = True

                if unconfigured_match or conf_matches or url_matches:
                    yield self.build_plugin(
                        plugin_provider, auth_dict, Authentication, priority
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
