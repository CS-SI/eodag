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
from typing import TYPE_CHECKING, Any, Dict, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
from requests import RequestException
from requests.adapters import HTTPAdapter
from requests.auth import AuthBase
from urllib3 import Retry

from eodag.plugins.authentication.base import Authentication
from eodag.utils import (
    HTTP_REQ_TIMEOUT,
    REQ_RETRY_BACKOFF_FACTOR,
    REQ_RETRY_STATUS_FORCELIST,
    REQ_RETRY_TOTAL,
    USER_AGENT,
)
from eodag.utils.exceptions import AuthenticationError, MisconfiguredError, TimeOutError

if TYPE_CHECKING:
    from requests import PreparedRequest

    from eodag.config import PluginConfig


logger = logging.getLogger("eodag.authentication.token")


class TokenAuth(Authentication):
    """TokenAuth authentication plugin - fetches a token which is added to search/download requests.

    When using headers, if only :attr:`~eodag.config.PluginConfig.headers` is given, it will be used for both token
    retrieve and authentication. If :attr:`~eodag.config.PluginConfig.retrieve_headers` is given, it will be used for
    token retrieve only. If both are given, :attr:`~eodag.config.PluginConfig.retrieve_headers` will be used for token
    retrieve and :attr:`~eodag.config.PluginConfig.headers` for authentication.

    :param provider: provider name
    :param config: Authentication plugin configuration:

        * :attr:`~eodag.config.PluginConfig.type` (``str``) (**mandatory**): TokenAuth
        * :attr:`~eodag.config.PluginConfig.auth_uri` (``str``) (**mandatory**): url used to fetch
          the access token with user/password
        * :attr:`~eodag.config.PluginConfig.headers` (``Dict[str, str]``): Dictionary containing all
          keys/value pairs that should be added to the headers
        * :attr:`~eodag.config.PluginConfig.retrieve_headers` (``Dict[str, str]``): Dictionary containing all
          keys/value pairs that should be added to the headers for token retrieve only
        * :attr:`~eodag.config.PluginConfig.refresh_uri` (``str``) : url used to fetch the
          access token with a refresh token
        * :attr:`~eodag.config.PluginConfig.token_type` (``str``): type of the token (``json``
          or ``text``); default: ``text``
        * :attr:`~eodag.config.PluginConfig.token_key` (``str``): (mandatory if token_type=json)
          key to get the access token in the response to the token request
        * :attr:`~eodag.config.PluginConfig.refresh_token_key` (``str``): key to get the refresh
          token in the response to the token request
        * :attr:`~eodag.config.PluginConfig.ssl_verify` (``bool``): if the ssl certificates
          should be verified in the requests; default: ``True``
        * :attr:`~eodag.config.PluginConfig.auth_error_code` (``int``): which error code is
          returned in case of an authentication error
        * :attr:`~eodag.config.PluginConfig.req_data` (``Dict[str, Any]``): if the credentials
          should be sent as data in the post request, the json structure can be given in this parameter
        * :attr:`~eodag.config.PluginConfig.retry_total` (``int``): :class:`urllib3.util.Retry` ``total`` parameter,
          total number of retries to allow; default: ``3``
        * :attr:`~eodag.config.PluginConfig.retry_backoff_factor` (``int``): :class:`urllib3.util.Retry`
          ``backoff_factor`` parameter, backoff factor to apply between attempts after the second try; default: ``2``
        * :attr:`~eodag.config.PluginConfig.retry_status_forcelist` (``List[int]``): :class:`urllib3.util.Retry`
          ``status_forcelist`` parameter, list of integer HTTP status codes that we should force a retry on; default:
          ``[401, 429, 500, 502, 503, 504]``
    """

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(TokenAuth, self).__init__(provider, config)
        self.token = ""
        self.refresh_token = ""

    def validate_config_credentials(self) -> None:
        """Validate configured credentials"""
        super(TokenAuth, self).validate_config_credentials()
        try:
            # format auth_uri using credentials if needed
            self.config.auth_uri = self.config.auth_uri.format(
                **self.config.credentials
            )

            # Format headers if needed with values from the credentials. Note:
            # if only 'headers' is given, it will be used for both token retrieve and authentication.
            # if 'retrieve_headers' is given, it will be used for token retrieve only.
            # if both are given, 'retrieve_headers' will be used for token retrieve and 'headers' for authentication.

            # If the authentication headers are undefined or None: use an empty dict.
            # And don't format '{token}' now, it will be done later.
            raw_headers = getattr(self.config, "headers", None) or {}
            self.config.headers = {
                header: value.format(**{"token": "{token}", **self.config.credentials})
                for header, value in raw_headers.items()
            }

            # If the retrieve headers are undefined, their attribute must not be set in self.config.
            # If they are defined but empty, use an empty dict instead of None.
            if hasattr(self.config, "retrieve_headers"):
                raw_retrieve_headers = self.config.retrieve_headers or {}
                self.config.retrieve_headers = {
                    header: value.format(**self.config.credentials)
                    for header, value in raw_retrieve_headers.items()
                }

        except KeyError as e:
            raise MisconfiguredError(
                f"Missing credentials inputs for provider {self.provider}: {e}"
            )

    def authenticate(self) -> AuthBase:
        """Authenticate"""
        self.validate_config_credentials()

        s = requests.Session()
        try:
            # First get the token
            response = self._token_request(session=s)
            response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(exc, timeout=HTTP_REQ_TIMEOUT) from exc
        except RequestException as e:
            response_text = getattr(e.response, "text", "").strip()
            # check if error is identified as auth_error in provider conf
            auth_errors = getattr(self.config, "auth_error_code", [None])
            if not isinstance(auth_errors, list):
                auth_errors = [auth_errors]
            if (
                e.response is not None
                and getattr(e.response, "status_code", None)
                and e.response.status_code in auth_errors
            ):
                raise AuthenticationError(
                    f"Please check your credentials for {self.provider}.",
                    f"HTTP Error {e.response.status_code} returned.",
                    response_text,
                ) from e
            # other error
            else:
                raise AuthenticationError(
                    "Could no get authentication token", str(e), response_text
                ) from e
        else:
            if getattr(self.config, "token_type", "text") == "json":
                token = response.json()[self.config.token_key]
            else:
                token = response.text
            self.token = token
            if getattr(self.config, "refresh_token_key", None):
                self.refresh_token = response.json()[self.config.refresh_token_key]
            if not hasattr(self.config, "headers"):
                raise MisconfiguredError(f"Missing headers configuration for {self}")
            # Return auth class set with obtained token
            return RequestsTokenAuth(
                token, "header", headers=getattr(self.config, "headers", {})
            )

    def _token_request(
        self,
        session: requests.Session,
    ) -> requests.Response:
        retry_total = getattr(self.config, "retry_total", REQ_RETRY_TOTAL)
        retry_backoff_factor = getattr(
            self.config, "retry_backoff_factor", REQ_RETRY_BACKOFF_FACTOR
        )
        retry_status_forcelist = getattr(
            self.config, "retry_status_forcelist", REQ_RETRY_STATUS_FORCELIST
        )

        retries = Retry(
            total=retry_total,
            backoff_factor=retry_backoff_factor,
            status_forcelist=retry_status_forcelist,
        )

        # Use the headers for retrieval if defined, else the headers for authentication
        try:
            headers = self.config.retrieve_headers
        except AttributeError:
            headers = self.config.headers

        # append headers to req if some are specified in config
        req_kwargs: Dict[str, Any] = {"headers": dict(headers, **USER_AGENT)}
        ssl_verify = getattr(self.config, "ssl_verify", True)

        if self.refresh_token:
            logger.debug("fetching access token with refresh token")
            session.mount(self.config.refresh_uri, HTTPAdapter(max_retries=retries))
            try:
                response = session.post(
                    self.config.refresh_uri,
                    data={"refresh_token": self.refresh_token},
                    timeout=HTTP_REQ_TIMEOUT,
                    verify=ssl_verify,
                    **req_kwargs,
                )
                response.raise_for_status()
                return response
            except requests.exceptions.HTTPError as e:
                logger.debug(getattr(e.response, "text", "").strip())

        logger.debug("fetching access token from %s", self.config.auth_uri)
        # append headers to req if some are specified in config
        session.mount(self.config.auth_uri, HTTPAdapter(max_retries=retries))
        method = getattr(self.config, "request_method", "POST")

        # send credentials also as data in POST requests
        if method == "POST":
            # append req_data to credentials if specified in config
            req_kwargs["data"] = dict(
                getattr(self.config, "req_data", {}), **self.config.credentials
            )

        # credentials as auth tuple if possible
        req_kwargs["auth"] = (
            (
                self.config.credentials["username"],
                self.config.credentials["password"],
            )
            if all(
                k in self.config.credentials.keys() for k in ["username", "password"]
            )
            else None
        )

        return session.request(
            method=method,
            url=self.config.auth_uri,
            timeout=HTTP_REQ_TIMEOUT,
            verify=ssl_verify,
            **req_kwargs,
        )


class RequestsTokenAuth(AuthBase):
    """A custom authentication class to be used with requests module"""

    def __init__(
        self,
        token: str,
        where: str,
        qs_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.token = token
        self.where = where
        self.qs_key = qs_key
        self.headers = headers

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        """Perform the actual authentication"""
        if self.headers and isinstance(self.headers, dict):
            for k, v in self.headers.items():
                request.headers[k] = v
        if self.where == "qs":
            parts = urlparse(str(request.url))
            qs = parse_qs(parts.query)
            if self.qs_key is not None:
                qs[self.qs_key] = [self.token]
            request.url = urlunparse(
                (
                    parts.scheme,
                    parts.netloc,
                    parts.path,
                    parts.params,
                    urlencode(qs),
                    parts.fragment,
                )
            )
        elif self.where == "header":
            request.headers["Authorization"] = request.headers.get(
                "Authorization", "Bearer {token}"
            ).format(token=self.token)
        return request
