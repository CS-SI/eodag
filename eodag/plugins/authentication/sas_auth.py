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
import threading
from copy import copy
from datetime import datetime, timedelta, timezone
from json import JSONDecodeError
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlsplit, urlunsplit

import requests
from requests.adapters import HTTPAdapter
from requests.auth import AuthBase
from urllib3 import Retry

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

# Tokens are shared by all RequestsSASAuth instances to avoid one token request per asset/product.
_SAS_TOKENS: dict[str, tuple[str, Optional[datetime]]] = {}
_SAS_TOKENS_LOCK = threading.Lock()
_SAS_FETCH_LOCKS: dict[str, threading.Lock] = {}
_SAS_EXPIRY_MARGIN = timedelta(seconds=60)


def _parse_expiry(value: object) -> Optional[datetime]:
    """Parse a token expiry date, return ``None`` if missing or invalid"""
    try:
        expiry = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return expiry if expiry.tzinfo else expiry.replace(tzinfo=timezone.utc)


def _get_cached_token(keys: list[str]) -> Optional[str]:
    """Return the first non-expired cached token found for the given keys"""
    now = datetime.now(timezone.utc)
    with _SAS_TOKENS_LOCK:
        for key in keys:
            entry = _SAS_TOKENS.get(key)
            if entry and (entry[1] is None or entry[1] - _SAS_EXPIRY_MARGIN > now):
                return entry[0]
    return None


class RequestsSASAuth(AuthBase):
    """A custom authentication class to be used with requests module"""

    def __init__(
        self,
        auth_uri: str,
        signed_url_key: str,
        headers: Optional[dict[str, str]] = None,
        ssl_verify: bool = True,
        matching_url: Optional[Pattern[str]] = None,
        provider_collection: Optional[str] = None,
        retry_total: int = REQ_RETRY_TOTAL,
        retry_backoff_factor: int = REQ_RETRY_BACKOFF_FACTOR,
        retry_status_forcelist: Optional[list[int]] = None,
    ) -> None:
        self.auth_uri = auth_uri
        self.signed_url_key = signed_url_key
        self.headers = headers
        self.ssl_verify = ssl_verify
        self.matching_url = matching_url
        self.provider_collection = provider_collection
        self.retry_total = retry_total
        self.retry_backoff_factor = retry_backoff_factor
        self.retry_status_forcelist = (
            REQ_RETRY_STATUS_FORCELIST
            if retry_status_forcelist is None
            else retry_status_forcelist
        )

    @staticmethod
    def _get_container_url(url: str) -> Optional[str]:
        """Return the Azure blob container URL, or None for other URLs."""
        parsed_url = urlsplit(url)
        path_parts = parsed_url.path.strip("/").split("/", 1)
        if (
            parsed_url.hostname
            and parsed_url.hostname.endswith(".blob.core.windows.net")
            and path_parts[0]
        ):
            return f"{parsed_url.scheme}://{parsed_url.netloc}/{path_parts[0]}"
        return None

    @staticmethod
    def _apply_sas_token(url: str, signed_url: str) -> Optional[str]:
        """Apply a cached SAS token to another blob URL in the same container."""
        parsed_url = urlsplit(url)
        parsed_signed_url = urlsplit(signed_url)
        container_key = RequestsSASAuth._get_container_url(url)
        if not container_key:
            return None

        if parsed_signed_url.scheme and parsed_signed_url.netloc:
            if RequestsSASAuth._get_container_url(signed_url) != container_key:
                return None
            token = parsed_signed_url.query
        else:
            token = signed_url.lstrip("?")

        if not token:
            return None

        return urlunsplit(
            (
                parsed_url.scheme,
                parsed_url.netloc,
                parsed_url.path,
                token,
                parsed_url.fragment,
            )
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

        request.url = self.sign_url(request.url or "")

        return request

    def sign_url(self, url: str) -> str:
        """Return ``url`` signed with a (cached or freshly requested) SAS token"""
        # Azure SAS tokens are scoped to a container, not an individual blob.
        container_key = self._get_container_url(url)
        if "{_collection}" in self.auth_uri and not self.provider_collection:
            raise AuthenticationError(
                "A provider collection is required to request a SAS token"
            )
        req_signed_url = self.auth_uri.format(
            url=url, _collection=self.provider_collection or ""
        )

        cache_keys = [k for k in (container_key, req_signed_url) if k]
        signed_url = _get_cached_token(cache_keys)
        if signed_url is None:
            # one fetch at a time per container, other threads then reuse its result
            with _SAS_TOKENS_LOCK:
                fetch_lock = _SAS_FETCH_LOCKS.setdefault(
                    cache_keys[0], threading.Lock()
                )
            with fetch_lock:
                signed_url = _get_cached_token(cache_keys)
                if signed_url is None:
                    signed_url = self._fetch_signed_url(
                        url, req_signed_url, container_key
                    )

        return self._apply_sas_token(url, signed_url) or signed_url

    def _fetch_signed_url(
        self, url: str, req_signed_url: str, container_key: Optional[str]
    ) -> str:
        """Request a signed url / token and store it in the shared cache"""
        logger.debug(f"Signed URL request: {req_signed_url}")
        try:
            session = requests.Session()
            retries = Retry(
                total=self.retry_total,
                backoff_factor=self.retry_backoff_factor,
                status_forcelist=self.retry_status_forcelist,
            )
            session.mount(req_signed_url, HTTPAdapter(max_retries=retries))
            response = session.get(
                req_signed_url,
                headers=self.headers,
                timeout=HTTP_REQ_TIMEOUT,
                verify=self.ssl_verify,
            )
            response.raise_for_status()
            body = response.json()
            signed_url = body[self.signed_url_key]
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(exc, timeout=HTTP_REQ_TIMEOUT) from exc
        except (requests.RequestException, JSONDecodeError, KeyError) as e:
            raise AuthenticationError("Could no get signed url", str(e)) from e

        cache_key = (
            container_key
            if container_key and self._apply_sas_token(url, signed_url)
            else req_signed_url
        )
        expiry = _parse_expiry(body.get("msft:expiry"))
        with _SAS_TOKENS_LOCK:
            _SAS_TOKENS[cache_key] = (signed_url, expiry)
        return signed_url


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
        * :attr:`~eodag.config.PluginConfig.retry_total` (``int``): total number of retries; default: ``3``
        * :attr:`~eodag.config.PluginConfig.retry_backoff_factor` (``int``): retry backoff factor; default: ``2``
        * :attr:`~eodag.config.PluginConfig.retry_status_forcelist` (``list[int]``): HTTP status codes to retry;
          default: ``[401, 429, 500, 502, 503, 504]``

    """

    provider_collection: Optional[str] = None

    def validate_config_credentials(self) -> None:
        """Validate configured credentials"""
        # credentials are optionnal
        pass

    def bind_collection(self, provider_collection: str) -> SASAuth:
        """Return a product-specific auth plugin using its provider collection ID."""
        auth_plugin = copy(self)
        auth_plugin.provider_collection = provider_collection
        return auth_plugin

    def authenticate(self) -> RequestsSASAuth:
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

        provider_collection = getattr(self, "provider_collection", None)
        return RequestsSASAuth(
            auth_uri=self.config.auth_uri,
            signed_url_key=self.config.signed_url_key,
            headers=headers,
            ssl_verify=ssl_verify,
            matching_url=matching_url,
            provider_collection=provider_collection,
            retry_total=getattr(self.config, "retry_total", REQ_RETRY_TOTAL),
            retry_backoff_factor=getattr(
                self.config, "retry_backoff_factor", REQ_RETRY_BACKOFF_FACTOR
            ),
            retry_status_forcelist=getattr(
                self.config,
                "retry_status_forcelist",
                REQ_RETRY_STATUS_FORCELIST,
            ),
        )

    def presign_url(
        self,
        asset: Asset,
        expires_in: int = 3600,
    ) -> str:
        """This method is used to presign a url to download an asset.

        :param asset: asset for which the url shall be presigned
        :param expires_in: ignored, the token lifetime is set by the provider
        :returns: presigned url
        """
        return self.authenticate().sign_url(asset["href"])
