# -*- coding: utf-8 -*-
# Copyright 2024, CS GROUP - France, https://www.csgroup.eu/
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
import logging
from typing import Any, List

from botocore.exceptions import BotoCoreError

from eodag.api.product import EOProduct  # type: ignore
from eodag.api.search_result import RawSearchResult
from eodag.utils.exceptions import RequestError
from eodag.utils.s3 import update_assets_from_s3

from .qssearch import StacSearch

logger = logging.getLogger("eodag.search.stac_list_assets")


class StacListAssets(StacSearch):
    """``StacListAssets`` is an extension of :class:`~eodag.plugins.search.qssearch.StacSearch`.

    It executes a Search on given STAC API endpoint and updates assets with content listed by the plugin using
    ``eodag:download_link`` :class:`~eodag.api.product._product.EOProduct` property.

    :param provider: provider name
    :param config: It has the same Search plugin configuration as :class:`~eodag.plugins.search.qssearch.StacSearch` and
                   one additional parameter:

        * :attr:`~eodag.config.PluginConfig.s3_endpoint` (``str``): s3 endpoint if not hosted on AWS
    """

    def __init__(self, provider, config):
        super(StacSearch, self).__init__(provider, config)

    def normalize_results(
        self, results: RawSearchResult, **kwargs: Any
    ) -> List[EOProduct]:
        """Build EOProducts from provider results"""

        products = super(StacSearch, self).normalize_results(results, **kwargs)
        for product in products:
            # Update asset from s3 when product has registered plugin_manager
            if product.plugins_manager is not None:
                self._update_product_assets(product)
            else:
                product.on("register_plugin_manager", self._update_product_assets)

        return products

    def _update_product_assets(self, product: EOProduct):
        if product.plugins_manager is not None:
            downloader = product.plugins_manager.get_download_plugin(product.provider)
            authenticator = product.plugins_manager.get_auth_plugin(downloader, None)  # type: ignore
            if downloader is not None and authenticator is not None:
                try:
                    update_assets_from_s3(
                        product,
                        authenticator,  # type: ignore
                        getattr(downloader.config, "s3_endpoint", None),
                    )
                except BotoCoreError as e:
                    raise RequestError.from_error(e, "could not update assets") from e


__all__ = ["StacListAssets"]
