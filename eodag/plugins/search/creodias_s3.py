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
from types import MethodType
from typing import Any

from botocore.exceptions import BotoCoreError

from eodag.api.product import EOProduct  # type: ignore
from eodag.api.search_result import RawSearchResult
from eodag.plugins.search.qssearch import ODataV4Search
from eodag.utils.exceptions import RequestError
from eodag.utils.s3 import update_assets_from_s3

logger = logging.getLogger("eodag.search.creodiass3")


def patched_register_downloader(self, downloader, authenticator):
    """Add the download information to the product.

    :param self: product to which information should be added
    :param downloader: The download method that it can use
                      :class:`~eodag.plugins.download.base.Download` or
                      :class:`~eodag.plugins.api.base.Api`
    :param authenticator: The authentication method needed to perform the download
                         :class:`~eodag.plugins.authentication.base.Authentication`
    """
    # register downloader
    self.register_downloader_only(downloader, authenticator)
    # and also update assets
    try:
        update_assets_from_s3(
            self, authenticator, getattr(downloader.config, "s3_endpoint", None)
        )
    except BotoCoreError as e:
        raise RequestError.from_error(e, "could not update assets") from e


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
            # backup original register_downloader to register_downloader_only
            product.register_downloader_only = product.register_downloader
            # patched register_downloader that will also update assets
            product.register_downloader = MethodType(
                patched_register_downloader, product
            )

        return products
