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
from typing import TYPE_CHECKING, Any

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

    This plugin requests a token which is added to a query-string or a header for authentication.

    :param provider: provider name
    :param config: Authentication plugin configuration:

        * :attr:`~eodag.config.PluginConfig.type` (``str``) (**mandatory**): KeycloakOIDCPasswordAuth
        * :attr:`~eodag.config.PluginConfig.oidc_config_url` (``str``) (**mandatory**):
          The url to get the OIDC Provider's endpoints
        * :attr:`~eodag.config.PluginConfig.client_id` (``str``) (**mandatory**): keycloak client id
        * :attr:`~eodag.config.PluginConfig.client_secret` (``str``) (**mandatory**): keycloak
          client secret, set to null if no secret is used
        * :attr:`~eodag.config.PluginConfig.token_provision` (``str``) (**mandatory**): if the
          token should be added to the query string (``qs``) or to the header (``header``)
        * :attr:`~eodag.config.PluginConfig.token_qs_key` (``str``): (**mandatory if token_provision=qs**)
          key of the param added to the query string
        * :attr:`~eodag.config.PluginConfig.allowed_audiences` (``list[str]``) (**mandatory**):
          The allowed audiences that have to be present in the user token.
        * :attr:`~eodag.config.PluginConfig.auth_error_code` (``int``): which error code is
          returned in case of an authentication error
        * :attr:`~eodag.config.PluginConfig.ssl_verify` (``bool``): if the ssl certificates
          should be verified in the token request; default: ``True``

    Using :class:`~eodag.plugins.download.http.HTTPDownload` a download link
    ``http://example.com?foo=bar`` will become
    ``http://example.com?foo=bar&my-token=obtained-token`` if associated to the following
    configuration::

        provider:
            ...
            auth:
                plugin: KeycloakOIDCPasswordAuth
                oidc_config_url: 'https://somewhere/auth/realms/realm/.well-known/openid-configuration'
                client_id: 'SOME_ID'
                client_secret: '01234-56789'
                token_provision: qs
                token_qs_key: 'my-token'
                ...
            ...

    If configured to send the token through the header, the download request header will
    be updated with ``Authorization: "Bearer obtained-token"`` if associated to the
    following configuration::

        provider:
            ...
            auth:
                plugin: KeycloakOIDCPasswordAuth
                oidc_config_url: 'https://somewhere/auth/realms/realm/.well-known/openid-configuration'
                client_id: 'SOME_ID'
                client_secret: '01234-56789'
                token_provision: header
                ...
            ...
    """

    GRANT_TYPE = "password"
    REQUIRED_PARAMS = [
        "oidc_config_url",
        "client_id",
        "client_secret",
        "token_provision",
    ]

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
        self._get_access_token()
        return CodeAuthorizedAuth(
            self.access_token,
            self.config.token_provision,
            key=getattr(self.config, "token_qs_key", None),
        )

    def _request_new_token(self) -> dict[str, Any]:
        logger.debug("fetching new access token")
        req_data = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "grant_type": self.GRANT_TYPE,
        }
        credentials = {k: v for k, v in self.config.credentials.items()}
        ssl_verify = getattr(self.config, "ssl_verify", True)
        try:
            response = self.session.post(
                self.token_endpoint,
                data=dict(req_data, **credentials),
                headers=USER_AGENT,
                timeout=HTTP_REQ_TIMEOUT,
                verify=ssl_verify,
            )
            response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(exc, timeout=HTTP_REQ_TIMEOUT) from exc
        except requests.RequestException as e:
            return self._request_new_token_error(e)
        return response.json()

    def _get_token_with_refresh_token(self) -> dict[str, str]:
        logger.debug("fetching access token with refresh token")
        req_data = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }
        ssl_verify = getattr(self.config, "ssl_verify", True)
        try:
            response = self.session.post(
                self.token_endpoint,
                data=req_data,
                headers=USER_AGENT,
                timeout=HTTP_REQ_TIMEOUT,
                verify=ssl_verify,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(
                "could not fetch access token with refresh token, executing new token request, error: %s",
                getattr(e.response, "text", ""),
            )
            return self._request_new_token()
        return response.json()
