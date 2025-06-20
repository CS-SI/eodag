# -*- coding: utf-8 -*-
# Copyright 2023, CS GROUP - France, https://www.csgroup.eu/
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
from json import JSONDecodeError
from typing import TYPE_CHECKING, Optional

import requests
from requests.auth import AuthBase

from eodag.plugins.authentication.base import Authentication
from eodag.utils import HTTP_REQ_TIMEOUT, USER_AGENT, deepcopy, format_dict_items
from eodag.utils.exceptions import AuthenticationError, TimeOutError

if TYPE_CHECKING:
    from requests import PreparedRequest


logger = logging.getLogger("eodag.auth.sas_auth")


class RequestsSASAuth(AuthBase):
    """A custom authentication class to be used with requests module"""

    def __init__(
        self,
        auth_uri: str,
        signed_url_key: str,
        headers: Optional[dict[str, str]] = None,
        ssl_verify: bool = True,
    ) -> None:
        self.auth_uri = auth_uri
        self.signed_url_key = signed_url_key
        self.headers = headers
        self.signed_urls: dict[str, str] = {}
        self.ssl_verify = ssl_verify

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        """Perform the actual authentication"""

        # update headers
        if self.headers and isinstance(self.headers, dict):
            for k, v in self.headers.items():
                request.headers[k] = v

        # request the signed_url
        req_signed_url = self.auth_uri.format(url=request.url)
        if req_signed_url not in self.signed_urls.keys():
            logger.debug(f"Signed URL request: {req_signed_url}")
            try:
                response = requests.get(
                    req_signed_url,
                    headers=self.headers,
                    timeout=HTTP_REQ_TIMEOUT,
                    verify=self.ssl_verify,
                )
                response.raise_for_status()
                signed_url = response.json().get(self.signed_url_key)
            except requests.exceptions.Timeout as exc:
                raise TimeOutError(exc, timeout=HTTP_REQ_TIMEOUT) from exc
            except (requests.RequestException, JSONDecodeError, KeyError) as e:
                raise AuthenticationError("Could no get signed url", str(e)) from e
            else:
                self.signed_urls[req_signed_url] = signed_url

        request.url = self.signed_urls[req_signed_url]

        return request


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
        if apikey:
            headers_update = format_dict_items(self.config.headers, apikey=apikey)
            headers.update(headers_update)

        return RequestsSASAuth(
            auth_uri=self.config.auth_uri,
            signed_url_key=self.config.signed_url_key,
            headers=headers,
            ssl_verify=ssl_verify,
        )
