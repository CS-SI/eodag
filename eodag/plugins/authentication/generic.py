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
from typing import Any

from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from eodag.plugins.authentication.base import Authentication
from eodag.utils.exceptions import MisconfiguredError
from eodag.utils.http import HttpRequestParams


class GenericAuth(Authentication):
    """GenericAuth authentication plugin"""

    method: str = ""

    def validate_config_credentials(self):
        """
        Validate configured credentials.

        :raises MisconfiguredError: If the authentication method is not supported.
        """
        super().validate_config_credentials()
        self.method = getattr(self.config, "method", "")
        if not self.method:
            self.method = "basic"

        if self.method not in ["basic", "digest"]:
            raise MisconfiguredError(
                "Generic authentication supports method basic or digest"
            )

    def authenticate(self, **kwargs: Any) -> Any:
        """Authenticate"""
        self.validate_config_credentials()

        if self.method == "basic":
            return HTTPBasicAuth(
                self.config.credentials["username"],
                self.config.credentials["password"],
            )
        else:
            return HTTPDigestAuth(
                self.config.credentials["username"],
                self.config.credentials["password"],
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
        params.extra_params["auth"] = self.authenticate()

        return params
