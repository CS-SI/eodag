# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

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
        headers = {
            header: value.format(**self.config['credentials'])
            for header, value in self.config['headers'].items()
        }
        return HeaderAuth(headers)


class HeaderAuth(requests.auth.AuthBase):

    def __init__(self, authentication_headers):
        self.auth_headers = authentication_headers

    def __call__(self, request):
        request.headers.update(self.auth_headers)
        return request
