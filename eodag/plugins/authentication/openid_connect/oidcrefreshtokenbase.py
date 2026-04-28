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
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import jwt
import requests

from eodag.utils import DEFAULT_TOKEN_EXPIRATION_MARGIN
from eodag.utils.exceptions import AuthenticationError, MisconfiguredError

from ..base import Authentication

if TYPE_CHECKING:
    from eodag.config import PluginConfig

logger = logging.getLogger("eodag.auth.openid_connect")


class OIDCRefreshTokenBase(Authentication):
    """OIDC refresh token base class, to be used through specific OIDC flows plugins;
    Common mechanism to handle refresh token from all OIDC auth plugins;

    Plugins inheriting from this base class must implement the methods ``_request_new_token()`` and
    ``_get_token_with_refresh_token()``. Depending on the implementation of these methods they can have
    different configuration parameters.

    """

    jwks_client: jwt.PyJWKClient

    access_token: str
    access_token_expiration: datetime

    refresh_token: str
    refresh_token_expiration: datetime

    token_endpoint: str
    authorization_endpoint: str

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(OIDCRefreshTokenBase, self).__init__(provider, config)

        self.access_token = ""
        self.access_token_expiration = datetime.min.replace(tzinfo=timezone.utc)
        self.refresh_token = ""
        self.refresh_token_expiration = datetime.min.replace(tzinfo=timezone.utc)
        self.session = requests.Session()

        auth_config = self._get_oidc_endpoints()

        self.jwks_client = jwt.PyJWKClient(auth_config["jwks_uri"])
        self.token_endpoint = auth_config["token_endpoint"]
        self.authorization_endpoint = auth_config["authorization_endpoint"]
        self.algorithms = auth_config["id_token_signing_alg_values_supported"]

    def _get_oidc_endpoints(self):
        try:
            response = requests.get(self.config.oidc_config_url)
            response.raise_for_status()
            auth_config = response.json()
        except requests.HTTPError as e:
            raise MisconfiguredError(
                f"Cannot obtain OIDC endpoints from {self.config.oidc_config_url}"
                f"Request returned {e.response.text}."
            )
        return auth_config

    def decode_jwt_token(self, token: str) -> dict[str, Any]:
        """Decode JWT token."""
        try:
            key = self.jwks_client.get_signing_key_from_jwt(token).key
            if getattr(self.config, "allowed_audiences", None):
                return jwt.decode(
                    token,
                    key,
                    algorithms=self.algorithms,
                    # NOTE: Audience validation MUST match audience claim if set in token
                    # (https://pyjwt.readthedocs.io/en/stable/changelog.html?highlight=audience#id40)
                    audience=self.config.allowed_audiences,
                )
            else:
                return jwt.decode(
                    token,
                    key,
                    algorithms=self.algorithms,
                )
        except (jwt.exceptions.InvalidTokenError, jwt.exceptions.DecodeError) as e:
            raise AuthenticationError(e)

    def _get_access_token(self) -> str:
        now = datetime.now(timezone.utc)
        expiration_margin = timedelta(
            seconds=getattr(
                self.config, "token_expiration_margin", DEFAULT_TOKEN_EXPIRATION_MARGIN
            )
        )

        if self.access_token and self.access_token_expiration - now > expiration_margin:
            logger.debug(
                f"Existing access_token is still valid until {self.access_token_expiration.isoformat()}."
            )
            return self.access_token

        elif (
            self.refresh_token
            and self.refresh_token_expiration - now > expiration_margin
        ):
            response = self._get_token_with_refresh_token()
            logger.debug(
                "access_token expired, fetching new access_token using refresh_token"
            )
        else:
            logger.debug("access_token expired or not available yet, new token request")
            response = self._request_new_token()

        self.access_token = response[getattr(self.config, "token_key", "access_token")]
        self.access_token_expiration = datetime.fromtimestamp(
            self.decode_jwt_token(self.access_token)["exp"], timezone.utc
        )
        self.refresh_token = response.get(
            getattr(self.config, "refresh_token_key", "refresh_token"), ""
        )
        if self.refresh_token and response.get("refresh_expires_in", "0"):
            self.refresh_token_expiration = now + timedelta(
                seconds=int(response["refresh_expires_in"])
            )
        else:
            # refresh token does not expire but will be changed at each request
            self.refresh_token_expiration = now + timedelta(days=1000)

        return self.access_token

    def _request_new_token(self) -> dict[str, str]:
        """Fetch the access token with a new authentication"""
        raise NotImplementedError(
            "Incomplete OIDC refresh token retrieval mechanism implementation"
        )

    def _request_new_token_error(self, e: requests.RequestException) -> dict[str, str]:
        """Handle RequestException raised by `self._request_new_token()`"""
        if self.access_token:
            # try using already retrieved token if authenticate() fails (OTP use-case)
            return {
                "access_token": self.access_token,
                "expires_in": self.access_token_expiration.isoformat(),
            }
        response_text = getattr(e.response, "text", "").strip()
        # check if error is identified as auth_error in provider conf
        auth_errors = getattr(self.config, "auth_error_code", [None])
        if not isinstance(auth_errors, list):
            auth_errors = [auth_errors]
        if (
            e.response
            and hasattr(e.response, "status_code")
            and e.response.status_code in auth_errors
        ):
            raise AuthenticationError(
                f"Please check your credentials for {self.provider}.",
                f"HTTP Error {e.response.status_code} returned.",
                response_text,
            )
        # other error
        else:
            import traceback as tb

            logger.error(
                f"Provider {self.provider} returned {getattr(e.response, 'status_code', '')}: {response_text}"
            )
            raise AuthenticationError(
                "Something went wrong while trying to get access token:\n{}".format(
                    tb.format_exc()
                )
            )

    def _get_token_with_refresh_token(self) -> dict[str, str]:
        """Fetch the access token with the refresh token"""
        raise NotImplementedError(
            "Incomplete OIDC refresh token retrieval mechanism implementation"
        )


__all__ = ["OIDCRefreshTokenBase"]
