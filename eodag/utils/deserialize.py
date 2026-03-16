# -*- coding: utf-8 -*-
# Copyright 2026, CS GROUP - France, https://www.csgroup.eu/
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
from typing import TYPE_CHECKING, Any, Optional

from eodag.utils import GENERIC_STAC_PROVIDER, STAC_SEARCH_PLUGINS
from eodag.utils.exceptions import MisconfiguredError

if TYPE_CHECKING:
    from eodag.api.product import EOProduct
    from eodag.plugins.manager import PluginManager


logger = logging.getLogger("eodag.utils.deserialize")


def unregistered_product_from_item(
    feature: dict[str, Any], provider: str, plugins_manager: "PluginManager"
) -> Optional[EOProduct]:
    """Create an EOProduct from a STAC item, map its metadata, but without registering its plugins.

    :param feature: The STAC item to convert into an EOProduct.
    :param provider: The associated provider from which configuration should be used for mapping.
    :param plugins_manager: The plugins manager instance to use for retrieving search plugins.
    :returns: An EOProduct instance if the item can be normalized, otherwise None.
    """
    for search_plugin in plugins_manager.get_search_plugins(provider=provider):
        if hasattr(search_plugin, "normalize_results"):
            products = search_plugin.normalize_results([feature])
            if len(products) > 0:
                # properties cleanup
                for prop in ("start_datetime", "end_datetime"):
                    products[0].properties.pop(prop, None)
                # set collection if not already set
                if products[0].collection is None:
                    products[0].collection = products[0].properties.get("collection")
                return products[0]
    return None


def _import_stac_item_from_eodag_server(
    feature: dict[str, Any], plugins_manager: PluginManager
) -> Optional[EOProduct]:
    """Import a STAC item from EODAG Server.

    :param feature: A STAC item as a dictionary
    :param plugins_manager: The EODAG plugin manager instance
    :returns: An EOProduct created from the STAC item
    """
    provider = None
    if backends := feature["properties"].get("federation:backends"):
        provider = backends[0]
    elif providers := feature["properties"].get("providers"):
        provider = providers[0].get("name")
    if provider is not None:
        logger.debug("Trying to import STAC item from EODAG Server")
        # assets coming from a STAC provider
        assets = {
            k: v["alternate"]["origin"]
            for k, v in feature.get("assets", {}).items()
            if k not in ("thumbnail", "downloadLink", "eodag:download_link")
            and "origin" in v.get("alternate", {})
        }
        if assets:
            updated_item = {**feature, **{"assets": assets}}
        else:
            # item coming from a non-STAC provider
            updated_item = {**feature}
            download_link = (
                feature.get("assets", {})
                .get("downloadLink", {})
                .get("alternate", {})
                .get("origin", {})
                .get("href")
            ) or (
                feature.get("assets", {})
                .get("eodag:download_link", {})
                .get("alternate", {})
                .get("origin", {})
                .get("href")
            )
            if download_link:
                updated_item["assets"] = {}
                updated_item["links"] = [{"rel": "self", "href": download_link}]
            else:
                updated_item = {}
        try:
            eo_product = unregistered_product_from_item(
                updated_item, GENERIC_STAC_PROVIDER, plugins_manager
            )
        except MisconfiguredError:
            eo_product = None
        if eo_product is not None:
            eo_product.provider = provider
            eo_product._register_downloader_from_manager(plugins_manager)
            return eo_product
    return None


def _import_stac_item_from_known_provider(
    feature: dict[str, Any],
    plugins_manager: PluginManager,
    provider: Optional[str] = None,
) -> Optional[EOProduct]:
    """Import a STAC item from an already-configured STAC provider.

    :param feature: A STAC item as a dictionary
    :param plugins_manager: The EODAG plugin manager instance
    :returns: An EOProduct created from the STAC item
    """
    item_hrefs = [f for f in feature.get("links", []) if f.get("rel") == "self"]
    item_href = item_hrefs[0]["href"] if len(item_hrefs) > 0 else None
    for search_plugin in plugins_manager.get_search_plugins(provider=provider):
        # only try STAC search plugins
        if (
            search_plugin.config.type in STAC_SEARCH_PLUGINS
            and search_plugin.provider != GENERIC_STAC_PROVIDER
            and hasattr(search_plugin, "normalize_results")
        ):
            provider_base_url = search_plugin.config.api_endpoint.removesuffix(
                "/search"
            )
            # compare the item href with the provider base URL
            if item_href and item_href.startswith(provider_base_url):
                products = search_plugin.normalize_results([feature])
                if len(products) == 0 or len(products[0].assets) == 0:
                    continue
                logger.debug(
                    "Trying to import STAC item from %s", search_plugin.provider
                )
                eo_product = products[0]

                configured_cols = [
                    k
                    for k, v in search_plugin.config.products.items()
                    if v.get("_collection") == feature.get("collection")
                ]
                if len(configured_cols) > 0:
                    eo_product.collection = configured_cols[0]
                else:
                    eo_product.collection = feature.get("collection")

                eo_product._register_downloader_from_manager(plugins_manager)
                return eo_product

    return None


def _import_stac_item_from_unknown_provider(
    feature: dict[str, Any], plugins_manager: PluginManager
) -> Optional[EOProduct]:
    """Import a STAC item from an unknown STAC provider.

    :param feature: A STAC item as a dictionary
    :param plugins_manager: The EODAG plugin manager instance
    :returns: An EOProduct created from the STAC item
    """
    try:
        logger.debug("Trying to import STAC item from unknown provider")
        eo_product = unregistered_product_from_item(
            feature, GENERIC_STAC_PROVIDER, plugins_manager
        )
    except MisconfiguredError:
        pass
    if eo_product is not None:
        eo_product.collection = feature.get("collection")
        eo_product._register_downloader_from_manager(plugins_manager)
        return eo_product
    else:
        return None
