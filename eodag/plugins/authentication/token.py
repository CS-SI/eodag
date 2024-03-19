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
    """TokenAuth authentication plugin"""

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

        # append headers to req if some are specified in config
        req_kwargs: Dict[str, Any] = (
            {"headers": dict(self.config.headers, **USER_AGENT)}
            if hasattr(self.config, "headers")
            else {"headers": USER_AGENT}
        )
        req_kwargs["headers"].pop("Authorization", None)
        s = requests.Session()
        try:
            # First get the token
            response = self._token_request(session=s, req_kwargs=req_kwargs)
            response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(exc, timeout=HTTP_REQ_TIMEOUT) from exc
        except RequestException as e:
            response_text = getattr(e.response, "text", "").strip()
            raise AuthenticationError(
                f"Could no get authentication token: {str(e)}, {response_text}"
            )
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
        self, session: requests.Session, req_kwargs: Dict[str, Any]
    ) -> requests.Response:
        retries = Retry(
            total=3, backoff_factor=2, status_forcelist=[401, 429, 500, 502, 503, 504]
        )
        if self.refresh_token:
            logger.debug("fetching access token with refresh token")
            session.mount(self.config.refresh_uri, HTTPAdapter(max_retries=retries))
            req_data = {"refresh_token": self.refresh_token}
            return session.post(
                self.config.refresh_uri,
                data=req_data,
                timeout=HTTP_REQ_TIMEOUT,
                **req_kwargs,
            )
        else:
            logger.debug("fetching access token from %s", self.config.auth_uri)
            # append headers to req if some are specified in config
            session.mount(self.config.auth_uri, HTTPAdapter(max_retries=retries))
            if getattr(self.config, "request_method", "POST") == "POST":
                return session.post(
                    self.config.auth_uri,
                    data=self.config.credentials,
                    timeout=HTTP_REQ_TIMEOUT,
                    **req_kwargs,
                )
            else:
                cred = self.config.credentials
                return session.get(
                    self.config.auth_uri,
                    auth=(cred["username"], cred["password"]),
                    timeout=HTTP_REQ_TIMEOUT,
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
            qs[self.qs_key] = self.token  # type: ignore
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
