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
from typing import Any

from botocore.exceptions import BotoCoreError

from eodag.api.product import EOProduct  # type: ignore
from eodag.api.search_result import RawSearchResult
from eodag.utils.exceptions import MisconfiguredError, RequestError
from eodag.utils.s3 import update_assets_from_s3

from .qssearch import ODataV4Search

logger = logging.getLogger("eodag.search.creodias_s3")


class CreodiasS3Search(ODataV4Search):
    """
    ``CreodiasS3Search`` is an extension of :class:`~eodag.plugins.search.qssearch.ODataV4Search`,
    it executes a Search on creodias and adapts results so that the assets contain links to s3.
    It has the same configuration parameters as :class:`~eodag.plugins.search.qssearch.ODataV4Search` and
    one additional parameter:

    :param provider: provider name
    :param config: Search plugin configuration:

        * :attr:`~eodag.config.PluginConfig.s3_endpoint` (``str``) (**mandatory**): base url of the s3
    """

    def __init__(self, provider, config):
        super(CreodiasS3Search, self).__init__(provider, config)

    def normalize_results(
        self, results: RawSearchResult, **kwargs: Any
    ) -> list[EOProduct]:
        """Build EOProducts from provider results"""
        products = super(CreodiasS3Search, self).normalize_results(results, **kwargs)
        for product in products:
            # Update asset from s3 when product has registered plugin_manager
            if product.plugins_manager is not None:
                self._update_product_assets(product)
            else:
                product.on("register_plugin_manager", self._update_product_assets)

        return products

    def _update_product_assets(self, product: EOProduct):
        """Add the download information to the product.
        :param product: product to which information should be added
        """
        if product.plugins_manager is not None:
            downloader = product.plugins_manager.get_download_plugin(product.provider)
            authenticator = product.plugins_manager.get_auth_plugin(downloader, None)  # type: ignore
            if downloader is not None and authenticator is not None:

                # verify credentials
                required_creds = ["aws_access_key_id", "aws_secret_access_key"]
                credentials = getattr(authenticator.config, "credentials", {}) or {}
                if not all(x in credentials and credentials[x] for x in required_creds):
                    raise MisconfiguredError(
                        f"Incomplete credentials for {product.provider}, missing "
                        f"{[x for x in required_creds if x not in credentials or not credentials[x]]}"
                    )

                product.off("register_plugin_manager")

                # and also update assets
                try:
                    update_assets_from_s3(
                        product,
                        authenticator,  # type: ignore
                        getattr(downloader.config, "s3_endpoint", None),
                    )
                except BotoCoreError as e:
                    raise RequestError.from_error(e, "could not update assets") from e


__all__ = ["CreodiasS3Search"]
