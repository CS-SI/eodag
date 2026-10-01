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
import re
from json import JSONDecodeError
from typing import TYPE_CHECKING, Optional

import requests
from requests.adapters import HTTPAdapter
from requests.auth import AuthBase
from urllib3.exceptions import MaxRetryError, ReadTimeoutError
from urllib3.util.retry import Retry

from eodag.api.product._assets import Asset
from eodag.plugins.authentication.base import Authentication
from eodag.utils import (
    HTTP_REQ_TIMEOUT,
    REQ_RETRY_BACKOFF_FACTOR,
    REQ_RETRY_STATUS_FORCELIST,
    REQ_RETRY_TOTAL,
    USER_AGENT,
    deepcopy,
    format_dict_items,
)
from eodag.utils.exceptions import AuthenticationError, TimeOutError

if TYPE_CHECKING:
    from typing import Pattern

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
        matching_url: Optional[Pattern[str]] = None,
        retry_total: int = REQ_RETRY_TOTAL,
        retry_backoff_factor: int = REQ_RETRY_BACKOFF_FACTOR,
        retry_status_forcelist: Optional[list[int]] = None,
    ) -> None:
        self.auth_uri = auth_uri
        self.signed_url_key = signed_url_key
        self.headers = headers
        self.signed_urls: dict[str, str] = {}
        self.ssl_verify = ssl_verify
        self.matching_url = matching_url
        self.retries = Retry(
            total=retry_total,
            backoff_factor=retry_backoff_factor,
            status_forcelist=(
                REQ_RETRY_STATUS_FORCELIST
                if retry_status_forcelist is None
                else retry_status_forcelist
            ),
            respect_retry_after_header=True,
        )

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        """Perform the actual authentication"""
        # if matching_url is set, check if request.url matches
        if (
            self.matching_url
            and request.url
            and not self.matching_url.match(request.url)
        ):
            return request

        # update headers
        if self.headers and isinstance(self.headers, dict):
            for k, v in self.headers.items():
                request.headers[k] = v

        # request the signed_url
        req_signed_url = self.auth_uri.format(url=request.url)
        if req_signed_url not in self.signed_urls.keys():
            logger.debug(f"Signed URL request: {req_signed_url}")
            try:
                with requests.Session() as session:
                    adapter = HTTPAdapter(max_retries=self.retries)
                    session.mount("http://", adapter)
                    session.mount("https://", adapter)
                    response = session.get(
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
                # Requests wraps exhausted read timeouts in ConnectionError.
                if (
                    isinstance(e, requests.exceptions.ConnectionError)
                    and e.args
                    and isinstance(e.args[0], MaxRetryError)
                    and isinstance(e.args[0].reason, ReadTimeoutError)
                ):
                    raise TimeOutError(e, timeout=HTTP_REQ_TIMEOUT) from e
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
        * :attr:`~eodag.config.PluginConfig.retry_total` (``int``): maximum number of retries
          for signing requests; default: ``3``
        * :attr:`~eodag.config.PluginConfig.retry_backoff_factor` (``int``): exponential
          backoff factor for signing requests; default: ``2``. The server's ``Retry-After``
          header is respected when present.
        * :attr:`~eodag.config.PluginConfig.retry_status_forcelist` (``list[int]``): HTTP
          status codes to retry; default: ``[401, 429, 500, 502, 503, 504]``

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
        credentials = getattr(self.config, "credentials", {})
        ssl_verify = getattr(self.config, "ssl_verify", True)
        if matching_url := getattr(self.config, "matching_url", None):
            matching_url = re.compile(matching_url)
        if any(credentials.values()):
            not_empty_credentials = {k: v for k, v in credentials.items() if v}
            headers_update = format_dict_items(
                self.config.headers, **not_empty_credentials
            )
            headers.update(headers_update)

        return RequestsSASAuth(
            auth_uri=self.config.auth_uri,
            signed_url_key=self.config.signed_url_key,
            headers=headers,
            ssl_verify=ssl_verify,
            matching_url=matching_url,
            retry_total=getattr(self.config, "retry_total", REQ_RETRY_TOTAL),
            retry_backoff_factor=getattr(
                self.config, "retry_backoff_factor", REQ_RETRY_BACKOFF_FACTOR
            ),
            retry_status_forcelist=getattr(
                self.config, "retry_status_forcelist", REQ_RETRY_STATUS_FORCELIST
            ),
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
