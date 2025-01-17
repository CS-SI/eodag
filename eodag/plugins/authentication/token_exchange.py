# -*- coding: utf-8 -*-
# Copyright 2024, CS GROUP - France, https://www.csgroup.eu/
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

import requests
from requests import RequestException

from eodag.config import PluginConfig
from eodag.plugins.authentication import Authentication
from eodag.plugins.authentication.openid_connect import (
    CodeAuthorizedAuth,
    OIDCAuthorizationCodeFlowAuth,
)
from eodag.utils import HTTP_REQ_TIMEOUT, USER_AGENT
from eodag.utils.exceptions import AuthenticationError, MisconfiguredError, TimeOutError

logger = logging.getLogger("eodag.auth.token_exchange")


class OIDCTokenExchangeAuth(Authentication):
    """Token exchange implementation using
        :class:`~eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth` token as subject.

    :param provider: provider name
    :param config: Authentication plugin configuration:

        * :attr:`~eodag.config.PluginConfig.subject` (``dict[str, Any]``) (**mandatory**):
          The full :class:`~eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth` plugin
          configuration used to retrieve subject token
        * :attr:`~eodag.config.PluginConfig.subject_issuer` (``str``) (**mandatory**): Identifies
          the issuer of the subject_token
        * :attr:`~eodag.config.PluginConfig.token_uri` (``str``) (**mandatory**): The url to
          query to get the authorized token
        * :attr:`~eodag.config.PluginConfig.client_id` (``str``) (**mandatory**): The OIDC
          provider's client ID of the eodag provider
        * :attr:`~eodag.config.PluginConfig.audience` (``str``) (**mandatory**): This parameter
          specifies the target client you want the new token minted for.
        * :attr:`~eodag.config.PluginConfig.token_key` (``str``) (**mandatory**): The key
          pointing to the token in the json response to the POST request to the token server

    """

    GRANT_TYPE = "urn:ietf:params:oauth:grant-type:token-exchange"
    SUBJECT_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"
    REQUIRED_KEYS = [
        "subject",
        "subject_issuer",
        "token_uri",
        "client_id",
        "audience",
        "token_key",
    ]

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super().__init__(provider, config)
        for required_key in self.REQUIRED_KEYS:
            if getattr(self.config, required_key, None) is None:
                raise MisconfiguredError(
                    f"Missing required entry for OIDCTokenExchangeAuth configuration: {required_key}"
                )
        self.subject = OIDCAuthorizationCodeFlowAuth(
            provider,
            PluginConfig.from_mapping(
                {
                    "credentials": getattr(self.config, "credentials", {}),
                    **self.config.subject,
                }
            ),
        )

    def authenticate(self) -> CodeAuthorizedAuth:
        """Authenticate"""
        logger.debug("Getting subject auth token")
        subject_auth = self.subject.authenticate()
        auth_data = {
            "grant_type": self.GRANT_TYPE,
            "subject_token": subject_auth.token,
            "subject_issuer": self.config.subject_issuer,
            "subject_token_type": self.SUBJECT_TOKEN_TYPE,
            "client_id": self.config.client_id,
            "audience": self.config.audience,
        }
        logger.debug("Getting target auth token")
        ssl_verify = getattr(self.config, "ssl_verify", True)
        try:
            auth_response = self.subject.session.post(
                self.config.token_uri,
                data=auth_data,
                headers=USER_AGENT,
                timeout=HTTP_REQ_TIMEOUT,
                verify=ssl_verify,
            )
            auth_response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(exc, timeout=HTTP_REQ_TIMEOUT) from exc
        except RequestException as exc:
            raise AuthenticationError("Could no get authentication token") from exc
        finally:
            self.subject.session.close()

        token = auth_response.json()[self.config.token_key]

        return CodeAuthorizedAuth(token, where="header")
