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
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Optional

from eodag.plugins.authentication.base import Authentication
from eodag.utils.exceptions import EODAGError, MisconfiguredError
from eodag.utils.http import HttpRequestParams, http

logger = logging.getLogger("eodag.authentication.token")


class TokenAuth(Authentication):
    """TokenAuth authentication plugin"""

    validity_period: Optional[timedelta]
    expiration_time: Optional[datetime]

    def __init__(self, provider: str, config):
        super(TokenAuth, self).__init__(provider, config)
        self.token: str = ""
        self.validate_config_credentials()

    @staticmethod
    def str_to_timedelta(duration_str: str) -> timedelta:
        """
        This static method converts a duration string into a timedelta object.

        Parameters:
            duration_str (str): A string representing the duration. The string should be in the format
            of "<value><unit>",
                                where <value> is an integer and <unit> is one of the following:
                                - 'h' for hours
                                - 'm' for minutes
                                - 'd' for days

        Returns:
            timedelta: A timedelta object representing the duration.

        Raises:
            ValueError: If the unit is not 'h', 'm', or 'd'.
        """
        unit = duration_str[-1]
        value = int(duration_str[:-1])

        if unit == "h":
            delta = timedelta(hours=value)
        elif unit == "m":
            delta = timedelta(minutes=value)
        elif unit == "d":
            delta = timedelta(days=value)
        else:
            raise ValueError(f"Invalid unit: {unit}")

        return delta

    def validate_config_credentials(self):
        """Validate configured credentials"""
        try:
            super(TokenAuth, self).validate_config_credentials()
            # format auth_uri using credentials if needed
            self.config.auth_uri = self.config.auth_uri.format(
                **self.config.credentials
            )
            # format headers if needed
            self.config.headers = {
                header: value.format(**self.config.credentials)
                for header, value in getattr(self.config, "headers", {}).items()
            }

            if getattr(self.config, "validity_period", None):
                self.validity_period = TokenAuth.str_to_timedelta(
                    self.config.validity_period
                )

        except (KeyError, ValueError) as e:
            raise MisconfiguredError(
                f"Invalid configuration for provider {self.provider}: {e}"
            )

        if "$token" not in self.config.headers.get("Authorization", ""):
            raise MisconfiguredError(
                "Cannot generate headers: Authorization header is missing from auth configuration."
            )

    def authenticate(self, **kwargs: Any) -> Any:
        """Authenticate"""

        # authenticate only if required
        if self.is_authenticated():
            return

        try:
            response = http.request(
                method=getattr(self.config, "request_method", "POST"),
                url=self.config.auth_uri,
                data=self.config.credentials,
                headers=getattr(self.config, "headers", None),
            )
        except EODAGError as e:
            logger.error(f"Could no get authentication token: {str(e)}")
            raise e

        if getattr(self.config, "token_type", "text") == "json":
            self.token = response.json()[self.config.token_key]
        else:
            self.token = response.text

        self.headers = deepcopy(self.config.headers)
        self.headers["Authorization"] = self.headers["Authorization"].replace(
            "$token", self.token
        )

        if self.validity_period:
            self.expiration_time = datetime.now() + self.validity_period

    def is_authenticated(self) -> bool:
        """
        Checks if the user is authenticated and if the token is still valid.

        :return: True if the user has a valid token that has not expired, False otherwise.
        """
        if not self.token:
            return False
        if self.expiration_time and datetime.now() > self.expiration_time:
            return False
        return True

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
        self.authenticate()

        params.headers.update(self.headers)

        return params
