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
from typing import TYPE_CHECKING

from requests.auth import AuthBase

from eodag.utils import USER_AGENT, deepcopy, format_dict_items

from ..base import Authentication
from .requestssasauth import RequestsSASAuth

if TYPE_CHECKING:
    from eodag.api.product import Asset

logger = logging.getLogger("eodag.auth.sas_auth")


class SASAuth(Authentication):
    """SASAuth authentication plugin

    An apiKey that is added in the headers can be given in the credentials in the config file.

    :param provider: provider name
    :param config: Authentication plugin configuration:

        * :attr:`~eodag.config.PluginConfig.type` (``str``) (**mandatory**): SASAuth
        * :attr:`~eodag.config.PluginConfig.auth_uri` (``str``) (**mandatory**): url used to
          get the signed url
        * :attr:`~eodag.config.PluginConfig.signed_url_key` (``str``) (**mandatory**): key to
          get the signed url
        * :attr:`~eodag.config.PluginConfig.headers` (``dict[str, str]``) (**mandatory if
          apiKey is used**): headers to be added to the requests
        * :attr:`~eodag.config.PluginConfig.ssl_verify` (``bool``): if the ssl certificates should be
          verified in the requests; default: ``True``

    """

    def validate_config_credentials(self) -> None:
        """Validate configured credentials"""
        # credentials are optionnal
        pass

    def authenticate(self) -> AuthBase:
        """Authenticate"""
        self.validate_config_credentials()

        headers = deepcopy(USER_AGENT)

        # update headers with subscription key if exists
        apikey = getattr(self.config, "credentials", {}).get("apikey")
        ssl_verify = getattr(self.config, "ssl_verify", True)
        if matching_url := getattr(self.config, "matching_url", None):
            matching_url = re.compile(matching_url)
        if apikey:
            headers_update = format_dict_items(self.config.headers, apikey=apikey)
            headers.update(headers_update)

        return RequestsSASAuth(
            auth_uri=self.config.auth_uri,
            signed_url_key=self.config.signed_url_key,
            headers=headers,
            ssl_verify=ssl_verify,
            matching_url=matching_url,
        )

    def presign_url(
        self,
        asset: Asset,
        expires_in: int = 3600,
    ) -> str:
        """This method is used to presign a url to download an asset.

        :param asset: asset for which the url shall be presigned
        :param expires_in: expiration time of the presigned url in seconds
        :returns: presigned url
        """
        url = asset["href"]
        return self.config.auth_uri.format(url=url)


__all__ = ["SASAuth"]
