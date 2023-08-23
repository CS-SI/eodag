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
from requests import RequestException
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from eodag.plugins.authentication.base import Authentication
from eodag.utils import USER_AGENT, RequestsTokenAuth
from eodag.utils.exceptions import AuthenticationError, MisconfiguredError
from eodag.utils.stac_reader import HTTP_REQ_TIMEOUT

logger = logging.getLogger("eodag.authentication.token")


class TokenAuth(Authentication):
    """TokenAuth authentication plugin"""

    def __init__(self, provider, config):
        super(TokenAuth, self).__init__(provider, config)
        self.token = ""

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
        s = requests.Session()
        retries = Retry(
            total=3, backoff_factor=2, status_forcelist=[401, 429, 500, 502, 503, 504]
        )
        s.mount(self.config.auth_uri, HTTPAdapter(max_retries=retries))
        try:
            # First get the token
            if getattr(self.config, "request_method", "POST") == "POST":
                response = s.post(
                    self.config.auth_uri,
                    data=self.config.credentials,
                    timeout=HTTP_REQ_TIMEOUT,
                    **req_kwargs,
                )
            else:
                cred = self.config.credentials
                response = s.get(
                    self.config.auth_uri,
                    auth=(cred["username"], cred["password"]),
                    timeout=HTTP_REQ_TIMEOUT,
                    **req_kwargs,
                )
            response.raise_for_status()
        except RequestException as e:
            response_text = getattr(e.response, "text", "").strip()
            logger.error(
                f"Could no get authentication token: {str(e)}, {response_text}"
            )
            if e.response and e.response.status_code == 401:
                raise Exception  # do not forward unauthorized from provider to user
            raise AuthenticationError(
                f"Could no get authentication token: {str(e)}, {response_text}"
            )
        else:
            if getattr(self.config, "token_type", "text") == "json":
                token = response.json()[self.config.token_key]
            else:
                token = response.text
            headers = self._get_headers(token)
            self.token = token
            # Return auth class set with obtained token
            return RequestsTokenAuth(token, "header", headers=headers)

    def _get_headers(self, token):
        headers = self.config.headers
        if "Authorization" in headers and "$" in headers["Authorization"]:
            headers["Authorization"] = headers["Authorization"].replace("$token", token)
        if (
            self.token
            and token != self.token
            and self.token in headers["Authorization"]
        ):
            headers["Authorization"] = headers["Authorization"].replace(
                self.token, token
            )
        return headers
