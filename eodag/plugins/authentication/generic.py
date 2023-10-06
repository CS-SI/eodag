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

from typing import Any, Dict, List, Optional, Union

from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from eodag.plugins.authentication.base import Authentication
from eodag.utils.exceptions import MisconfiguredError


class GenericAuth(Authentication):
    """GenericAuth authentication plugin"""

    def authenticate(self):
        """Authenticate"""
        self.validate_config_credentials()

        method = getattr(self.config, "method", None)
        if not method:
            method = "basic"

        if not method in ["basic", "digest"]:
            raise MisconfiguredError(
                "Generic authentication supports method basic or digest"
            )

        if method == "basic":
            return HTTPBasicAuth(
                self.config.credentials["username"],
                self.config.credentials["password"],
            )
        else:
            return HTTPDigestAuth(
                self.config.credentials["username"],
                self.config.credentials["password"],
            )

    def prepare_authenticated_request(
        self,
        method: str,
        url: str,
        data: Optional[Union[Dict[str, Any], bytes]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        retries: int = 3,
        delay: int = 1,
        timeout: int = 10,
        unquoted_params: Optional[List[str]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        auth = self.authenticate()

        return {
            "method": method,
            "url": url,
            "data": data,
            "json": json,
            "headers": headers,
            "retries": retries,
            "delay": delay,
            "timeout": timeout,
            "unquoted_params": unquoted_params,
            "auth": auth,
            **kwargs,
        }
