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

from requests.auth import AuthBase

from eodag.plugins.authentication import Authentication
from eodag.utils.exceptions import MisconfiguredError

if TYPE_CHECKING:
    from requests import PreparedRequest


class HTTPHeaderAuth(Authentication):
    """HTTPHeaderAuth Authentication plugin.

    This plugin enables implementation of custom HTTP authentication scheme (other than Basic, Digest, Token
    negotiation et al.) using HTTP headers.

    :param provider: provider name
    :param config: Authentication plugin configuration:

        * :attr:`~eodag.config.PluginConfig.type` (``str``) (**mandatory**): HTTPHeaderAuth
        * :attr:`~eodag.config.PluginConfig.headers` (``dict[str, str]``): dictionary containing
          all keys/value pairs that should be added to the headers

    Below an example for the configuration in the providers config file is shown::

        provider:
            ...
            auth:
                plugin: HTTPHeaderAuth
                headers:
                    Authorization: "Something {userinput}"
                    X-Special-Header: "Fixed value"
                    X-Another-Special-Header: "{oh-my-another-user-input}"
                ...
            ...

    As you can see in the sample above, the maintainer of ``provider`` define the headers that will be used in the
    authentication process as-is, by giving their names (e.g. ``Authorization``) and their value (e.g
    ``"Something {userinput}"``) as regular Python string templates that enable passing in the user input necessary to
    compute its identity. The user input awaited in the header value string must be present in the user config file.
    In the sample above, the plugin await for user credentials to be specified as::

        provider:
            credentials:
                userinput: XXX
                oh-my-another-user-input: YYY

    Expect an undefined behaviour if you use empty braces in header value strings.

    The plugin also accepts headers to be passed directly through credentials::

        provider:
            ...
            auth:
                plugin: HTTPHeaderAuth
                credentials:
                    Authorization: "Something XXX"
                    X-Special-Header: "Fixed value"
                    X-Another-Special-Header: "YYY"
                ...
            ...

    """

    def authenticate(self) -> HeaderAuth:
        """Authenticate"""
        self.validate_config_credentials()
        try:
            headers = (
                {
                    header: value.format(**self.config.credentials)
                    for header, value in self.config.headers.items()
                }
                if getattr(self.config, "headers", None)
                else self.config.credentials
            )
            return HeaderAuth(headers)
        except KeyError as e:
            raise MisconfiguredError(
                "The following credentials are missing for provider {}: {}".format(
                    self.provider, ", ".join(e.args)
                )
            )


class HeaderAuth(AuthBase):
    """HeaderAuth custom authentication class to be used with requests module"""

    def __init__(self, authentication_headers: dict[str, str]) -> None:
        self.auth_headers = authentication_headers

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        """Perform the actual authentication"""
        request.headers.update(self.auth_headers)
        return request
