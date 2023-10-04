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
import logging

import requests

from eodag.plugins.authentication import Authentication
from eodag.plugins.authentication.openid_connect import CodeAuthorizedAuth
from eodag.utils import HTTP_REQ_TIMEOUT, USER_AGENT
from eodag.utils.exceptions import AuthenticationError, MisconfiguredError

logger = logging.getLogger("eodag.plugins.auth.keycloak")


class KeycloakOIDCPasswordAuth(Authentication):
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
    # already retrieved token store, to be used if authenticate() fails (OTP use-case)
    retrieved_token = None

    def __init__(self, provider, config):
        super(KeycloakOIDCPasswordAuth, self).__init__(provider, config)
        self.session = requests.Session()

    def validate_config_credentials(self):
        """Validate configured credentials"""
        super(KeycloakOIDCPasswordAuth, self).validate_config_credentials()

        for param in self.REQUIRED_PARAMS:
            if not hasattr(self.config, param):
                raise MisconfiguredError(
                    "The following authentication configuration is missing for provider ",
                    f"{self.provider}: {param}",
                )

    def authenticate(self):
        """
        Makes authentication request
        """
        self.validate_config_credentials()
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
        except requests.RequestException as e:
            if self.retrieved_token:
                # try using already retrieved token if authenticate() fails (OTP use-case)
                return CodeAuthorizedAuth(
                    self.retrieved_token,
                    self.config.token_provision,
                    key=getattr(self.config, "token_qs_key", None),
                )
            response_text = getattr(e.response, "text", "").strip()
            # check if error is identified as auth_error in provider conf
            auth_errors = getattr(self.config, "auth_error_code", [None])
            if not isinstance(auth_errors, list):
                auth_errors = [auth_errors]
            if (
                hasattr(e.response, "status_code")
                and e.response.status_code in auth_errors
            ):
                raise AuthenticationError(
                    "HTTP Error %s returned, %s\nPlease check your credentials for %s"
                    % (e.response.status_code, response_text, self.provider)
                )
            # other error
            else:
                import traceback as tb

                logger.error(
                    f"Provider {self.provider} returned {e.response.status_code}: {response_text}"
                )
                raise AuthenticationError(
                    "Something went wrong while trying to get access token:\n{}".format(
                        tb.format_exc()
                    )
                )

        self.retrieved_token = response.json()["access_token"]
        return CodeAuthorizedAuth(
            self.retrieved_token,
            self.config.token_provision,
            key=getattr(self.config, "token_qs_key", None),
        )
