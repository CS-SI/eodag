# -*- coding: utf-8 -*-
# Copyright 2022, CS GROUP - France, https://www.csgroup.eu/
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

import requests.auth

from eodag.plugins.authentication import Authentication


class HTTPHeaderAuth(Authentication):
    """A Generic Authentication plugin.

    This plugin enables implementation of custom HTTP authentication scheme (other than Basic, Digest, Token
    negotiation et al.) using HTTP headers.

    The plugin is configured as follows in the providers config file::

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

    As you can see in the sample above, the maintainer of `provider` define the headers that will be used in the
    authentication process as-is, by giving their names (e.g. `Authorization`) and their value (e.g
    `"Something {userinput}"`) as regular Python string templates that enable passing in the user input necessary to
    compute its identity. The user input awaited in the header value string must be present in the user config file.
    In the sample above, the plugin await for user credentials to be specified as::

        provider:
            credentials:
                userinput: XXX
                oh-my-another-user-input: YYY

    Expect an undefined behaviour if you use empty braces in header value strings.
    """

    def authenticate(self):
        """Authenticate"""
        self.validate_config_credentials()
        headers = {
            header: value.format(**self.config.credentials)
            for header, value in self.config.headers.items()
        }
        return HeaderAuth(headers)


class HeaderAuth(requests.auth.AuthBase):
    """HeaderAuth authentication plugin"""

    def __init__(self, authentication_headers):
        self.auth_headers = authentication_headers

    def __call__(self, request):
        """Perform the actual authentication"""
        request.headers.update(self.auth_headers)
        return request
