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
from eodag.utils import HTTP_REQ_TIMEOUT, USER_AGENT
from eodag.utils.exceptions import AuthenticationError, MisconfiguredError, TimeOutError

if TYPE_CHECKING:
    from requests import PreparedRequest

    from eodag.config import PluginConfig


logger = logging.getLogger("eodag.authentication.token")


class TokenAuth(Authentication):
    """TokenAuth authentication plugin - fetches a token which is added to search/download requests

    The configuration parameters for this plugin are:

    * **type** [str] (mandatory): TokenAuth
    * **auth_uri** [str] (mandatory): url used to fetch the access token with user/password
    * **refresh_uri** [str] : url used to fetch the access token with a refresh token
    * **token_type** [str]: type of the token (json or text); default: text
    * **token_key** [str] (mandatory if token_type=json): key to get the access token in the
      response to the token request
    * **refresh_token_key** [str]: key to get the refresh token in the response to the token request
    * **ssl_verify** [bool]: if the ssl certificates should be verified in the requests; default: True
    * **auth_error_code** [int]: which error code is returned in case of an authentication error
    * **req_data** [Dict[str, Any]]: if the credentials should be sent as data in the post request,
      the json structure can be given in this parameter
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
            # format headers if needed (and accepts {token} to be formatted later)
            self.config.headers = {
                header: value.format(**{"token": "{token}", **self.config.credentials})
                for header, value in getattr(self.config, "headers", {}).items()
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
        retries = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[401, 429, 500, 502, 503, 504],
        )

        # append headers to req if some are specified in config
        req_kwargs: Dict[str, Any] = {
            "headers": dict(self.config.headers, **USER_AGENT)
        }
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
