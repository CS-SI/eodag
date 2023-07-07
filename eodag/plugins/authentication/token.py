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

import requests
from requests import RequestException

from eodag.plugins.authentication.base import Authentication
from eodag.utils import USER_AGENT, RequestsTokenAuth
from eodag.utils.exceptions import AuthenticationError, MisconfiguredError
from eodag.utils.stac_reader import HTTP_REQ_TIMEOUT


class TokenAuth(Authentication):
    """TokenAuth authentication plugin"""

    def validate_config_credentials(self):
        """Validate configured credentials"""
        super(TokenAuth, self).validate_config_credentials()
        try:
            # format auth_uri using credentials if needed
            self.config.auth_uri = self.config.auth_uri.format(
                **self.config.credentials
            )
            # format headers if needed
            self.config.headers = {
                header: value.format(**self.config.credentials)
                for header, value in getattr(self.config, "headers", {}).items()
            }
        except KeyError as e:
            raise MisconfiguredError(
                f"Missing credentials inputs for provider {self.provider}: {e}"
            )

    def authenticate(self):
        """Authenticate"""
        self.validate_config_credentials()

        # append headers to req if some are specified in config
        req_kwargs = (
            {"headers": dict(self.config.headers, **USER_AGENT)}
            if hasattr(self.config, "headers")
            else {"headers": USER_AGENT}
        )
        try:
            # First get the token
            if getattr(self.config, "request_method", "POST") == "POST":
                response = requests.post(
                    self.config.auth_uri,
                    data=self.config.credentials,
                    timeout=HTTP_REQ_TIMEOUT,
                    **req_kwargs,
                )
            else:
                cred = self.config.credentials
                response = requests.get(
                    self.config.auth_uri,
                    auth=(cred["username"], cred["password"]),
                    timeout=HTTP_REQ_TIMEOUT,
                    **req_kwargs,
                )
            response.raise_for_status()
        except RequestException as e:
            raise AuthenticationError(f"Could no get authentication token: {str(e)}")
        else:
            if getattr(self.config, "token_type", "text") == "json":
                token = response.json()[self.config.token_key]
            else:
                token = response.text
            # Return auth class set with obtained token
            return RequestsTokenAuth(token, "header", headers=self.config.headers)
