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
from typing import TYPE_CHECKING, Any, Dict

import requests

from eodag.plugins.authentication.openid_connect import (
    CodeAuthorizedAuth,
    OIDCRefreshTokenBase,
)
from eodag.utils import HTTP_REQ_TIMEOUT, USER_AGENT
from eodag.utils.exceptions import MisconfiguredError, TimeOutError

if TYPE_CHECKING:
    from requests.auth import AuthBase

    from eodag.config import PluginConfig


logger = logging.getLogger("eodag.auth.keycloak")


class KeycloakOIDCPasswordAuth(OIDCRefreshTokenBase):
    """Authentication plugin using Keycloak and OpenId Connect.

    This plugin request a token and use it through a query-string or a header.

    Using :class:`~eodag.plugins.download.http.HTTPDownload` a download link
    `http://example.com?foo=bar` will become
    `http://example.com?foo=bar&my-token=obtained-token` if associated to the following
    configuration::

        provider:
            ...
            auth:
                plugin: KeycloakOIDCPasswordAuth
                auth_base_uri: 'https://somewhere/auth'
                realm: 'the-realm'
                client_id: 'SOME_ID'
                client_secret: '01234-56789'
                token_provision: qs
                token_qs_key: 'my-token'
                ...
            ...

    If configured to send the token through the header, the download request header will
    be updated with `Authorization: "Bearer obtained-token"` if associated to the
    following configuration::

        provider:
            ...
            auth:
                plugin: KeycloakOIDCPasswordAuth
                auth_base_uri: 'https://somewhere/auth'
                realm: 'the-realm'
                client_id: 'SOME_ID'
                client_secret: '01234-56789'
                token_provision: header
                ...
            ...
    """

    GRANT_TYPE = "password"
    TOKEN_URL_TEMPLATE = "{auth_base_uri}/realms/{realm}/protocol/openid-connect/token"
    REQUIRED_PARAMS = ["auth_base_uri", "client_id", "client_secret", "token_provision"]

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(KeycloakOIDCPasswordAuth, self).__init__(provider, config)

    def validate_config_credentials(self) -> None:
        """Validate configured credentials"""
        super(KeycloakOIDCPasswordAuth, self).validate_config_credentials()

        for param in self.REQUIRED_PARAMS:
            if not hasattr(self.config, param):
                raise MisconfiguredError(
                    "The following authentication configuration is missing for provider ",
                    f"{self.provider}: {param}",
                )

    def authenticate(self) -> AuthBase:
        """
        Makes authentication request
        """
        self.validate_config_credentials()
        access_token = self._get_access_token()
        self.token_info["access_token"] = access_token
        return CodeAuthorizedAuth(
            self.token_info["access_token"],
            self.config.token_provision,
            key=getattr(self.config, "token_qs_key", None),
        )

    def _request_new_token(self) -> Dict[str, Any]:
        logger.debug("fetching new access token")
        req_data = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "grant_type": self.GRANT_TYPE,
        }
        credentials = {k: v for k, v in self.config.credentials.items()}
        try:
            response = self.session.post(
                self.TOKEN_URL_TEMPLATE.format(
                    auth_base_uri=self.config.auth_base_uri.rstrip("/"),
                    realm=self.config.realm,
                ),
                data=dict(req_data, **credentials),
                headers=USER_AGENT,
                timeout=HTTP_REQ_TIMEOUT,
            )
            response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(exc, timeout=HTTP_REQ_TIMEOUT) from exc
        except requests.RequestException as e:
            return self._request_new_token_error(e)
        return response.json()

    def _get_token_with_refresh_token(self) -> Dict[str, str]:
        logger.debug("fetching access token with refresh token")
        req_data = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self.token_info["refresh_token"],
        }
        try:
            response = self.session.post(
                self.TOKEN_URL_TEMPLATE.format(
                    auth_base_uri=self.config.auth_base_uri.rstrip("/"),
                    realm=self.config.realm,
                ),
                data=req_data,
                headers=USER_AGENT,
                timeout=HTTP_REQ_TIMEOUT,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(
                "could not fetch access token with refresh token, executing new token request, error: %s",
                getattr(e.response, "text", ""),
            )
            return self._request_new_token()
        return response.json()
