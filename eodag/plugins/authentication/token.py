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
from eodag.utils import RequestsTokenAuth
from eodag.utils.exceptions import MisconfiguredError


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
        except KeyError as e:
            raise MisconfiguredError(
                f"Missing credentials inputs for provider {self.provider}: {e}"
            )

    def authenticate(self):
        """Authenticate"""
        self.validate_config_credentials()

        # append headers to req if some are specified in config
        req_kwargs = (
            {"headers": self.config.headers} if hasattr(self.config, "headers") else {}
        )

        # First get the token
        response = requests.post(
            self.config.auth_uri, data=self.config.credentials, **req_kwargs
        )
        try:
            response.raise_for_status()
        except RequestException as e:
            raise e
        else:
            if getattr(self.config, "token_type", "text") == "json":
                token = response.json()[self.config.token_key]
            else:
                token = response.text
            # Return auth class set with obtained token
            return RequestsTokenAuth(token, "header")
