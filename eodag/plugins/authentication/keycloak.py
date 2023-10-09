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
from typing import Any

from eodag.plugins.authentication import Authentication
from eodag.utils.exceptions import AuthenticationError, MisconfiguredError, RequestError
from eodag.utils.http import HttpRequestParams, add_qs_params

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
    # token store, to be used if authenticate() fails (OTP use-case)
    token: str = ""
    key: str = ""

    def validate_config_credentials(self):
        """Validate configured credentials"""
        super(KeycloakOIDCPasswordAuth, self).validate_config_credentials()

        for param in self.REQUIRED_PARAMS:
            if not hasattr(self.config, param):
                raise MisconfiguredError(
                    "The following authentication configuration is missing for provider "
                    f"{self.provider}: {param}"
                )

        if self.config.token_provision == "qs" and not getattr(
            self.config, "token_qs_key", ""
        ):
            raise MisconfiguredError(
                'Provider config parameter "token_provision" with value "qs" must have '
                '"token_qs_key" config parameter as well'
            )

        self.where = self.config.token_provision
        self.key = getattr(self.config, "token_qs_key", "")

    def authenticate(self, **kwargs: Any) -> Any:
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
            response = self.http.post(
                url=self.TOKEN_URL_TEMPLATE.format(
                    auth_base_uri=self.config.auth_base_uri.rstrip("/"),
                    realm=self.config.realm,
                ),
                data=dict(req_data, **credentials),
            )
            self.token = response.json()["access_token"]
        except RequestError as e:
            # try using already retrieved token if authenticate() fails (OTP use-case)
            if not self.token:
                import traceback as tb

                logger.error(f"Provider {self.provider} returned {e}")
                raise AuthenticationError(
                    "Something went wrong while trying to get access token:\n{}".format(
                        tb.format_exc()
                    )
                )

    def prepare_authenticated_http_request(
        self, params: HttpRequestParams
    ) -> HttpRequestParams:
        """
        Prepare an authenticated HTTP request.

        :param HttpRequestParams params: The parameters for the HTTP request.

        :return: The parameters for the authenticated HTTP request.
        :rtype: HttpRequestParams

        :note: This function modifies the `params` instance directly and also returns it. The returned value is the same
            instance that was passed in, not a new one.
        """
        # generate a new access token
        self.authenticate()

        # Add token to headers or query parameters based on self.where
        if self.where == "qs":
            params.url = add_qs_params(params.url, {self.key: [self.token]})
        else:
            params.headers["Authorization"] = f"Bearer {self.token}"

        return params
