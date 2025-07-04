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
from __future__ import annotations

from typing import TYPE_CHECKING

from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from eodag.plugins.authentication.base import Authentication
from eodag.utils.exceptions import MisconfiguredError

if TYPE_CHECKING:
    from requests.auth import AuthBase


class GenericAuth(Authentication):
    """GenericAuth authentication plugin (authentication using ``username`` and ``password``)

    The mandatory parameters that have to be added in the eodag config are username and password.

    :param provider: provider name
    :param config: Authentication plugin configuration:

        * :attr:`~eodag.config.PluginConfig.type` (``str``) (**mandatory**): GenericAuth
        * :attr:`~eodag.config.PluginConfig.method` (``str``): specifies if digest authentication
          (``digest``) or basic authentication (``basic``) should be used; default: ``basic``

    """

    def authenticate(self) -> AuthBase:
        """Authenticate"""
        self.validate_config_credentials()
        method = getattr(self.config, "method", "basic")
        if not all(x in self.config.credentials for x in ["username", "password"]):
            raise MisconfiguredError(
                f"Missing credentials for provider {self.provider}",
                "You must provide 'username' and 'password' in the configuration.",
            )
        if method == "digest":
            return HTTPDigestAuth(
                self.config.credentials["username"],
                self.config.credentials["password"],
            )
        elif method == "basic":
            return HTTPBasicAuth(
                self.config.credentials["username"],
                self.config.credentials["password"],
            )
        else:
            raise MisconfiguredError(
                f"Cannot authenticate with {self.provider}",
                f"Method {method} is not supported; it must be one of 'digest' or 'basic'.",
            )
