# -*- coding: utf-8 -*-
# Copyright 2021, CS GROUP - France, http://www.c-s.fr
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
from requests import HTTPError

from eodag.plugins.authentication.base import Authentication
from eodag.utils import RequestsTokenAuth


class TokenAuth(Authentication):
    """TokenAuth authentication plugin"""

    def authenticate(self):
        """Authenticate"""
        # First get the token
        self.validate_config_credentials()
        response = requests.post(self.config.auth_uri, data=self.config.credentials)
        try:
            response.raise_for_status()
        except HTTPError as e:
            raise e
        else:
            if getattr(self.config, "token_type", "text") == "json":
                token = response.json()[self.config.token_key]
            else:
                token = response.text
            return RequestsTokenAuth(token, "header")
