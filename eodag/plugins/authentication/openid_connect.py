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

import re
import string
from random import SystemRandom
from typing import TYPE_CHECKING, Any, Dict, Optional

import requests
from lxml import etree
from requests.auth import AuthBase

from eodag.plugins.authentication import Authentication
from eodag.utils import HTTP_REQ_TIMEOUT, USER_AGENT, parse_qs, repeatfunc, urlparse
from eodag.utils.exceptions import AuthenticationError, MisconfiguredError

if TYPE_CHECKING:
    from requests import PreparedRequest, Response

    from eodag.config import PluginConfig


class OIDCAuthorizationCodeFlowAuth(Authentication):
    """Implement the authorization code flow of the OpenIDConnect authorization specification.

    The `OpenID Connect <http://openid.net/specs/openid-connect-core-1_0.html>`_ specification
    adds an authentication layer on top of oauth 2.0. This plugin implements the
    `authorization code flow <http://openid.net/specs/openid-connect-core-1_0.html#Authentication>`_
    option of this specification.
    The particularity of this plugin is that it proceeds to a headless (not involving the user)
    interaction with the OpenID provider (if necessary) to authenticate a
    registered user with its username and password on the server and then granting to eodag the
    necessary rights. It does that using the client ID of the eodag provider that use it.
    If the client secret of the eodag provider using this plugin is known, it is used in conjunction
    with the client ID to do a BASIC Auth during the token exchange request.
    The headless interaction is fully configurable, and rely on XPATH to retrieve all the necessary
    information.

    The configuration keys of this plugin are as follows (they have no defaults)::

        # (mandatory) The authorization url of the server (where to query for grants)
        authorization_uri:

        # (mandatory) The callback url that will handle the code given by the OIDC provider
        redirect_uri:

        # (mandatory) The url to query to exchange the authorization code obtained from the OIDC provider
        # for an authorized token
        token_uri:

        # (mandatory) The OIDC provider's client ID of the eodag provider
        client_id:

        # (mandatory) Wether a user consent is needed during the authentication
        user_consent_needed:

        # (mandatory) One of: json, data or params. This is the way to pass the data to the POST request
        # that is made to the token server. They correspond to the recognised keywords arguments
        # of the Python `requests <http://docs.python-requests.org/>`_ library
        token_exchange_post_data_method:

        # (mandatory) The key pointing to the token in the json response to the POST request to the token server
        token_key:

        # (mandatory) One of qs or header. This is how the token obtained will be used to authenticate the user
        # on protected requests. If 'qs' is chosen, then 'token_qs_key' is mandatory
        token_provision:

        # (mandatory) The xpath to the HTML form element representing the user login form
        login_form_xpath:

        # (mandatory) Where to look for the authentication_uri. One of 'config' (in the configuration) or 'login-form'
        # (use the 'action' URL found in the login form retrieved with login_form_xpath). If the value is 'config',
        # authentication_uri config param is mandatory
        authentication_uri_source:

        # (optional) The URL of the authentication backend of the OIDC provider
        authentication_uri:

        # (optional) The xpath to the user consent form. The form is searched in the content of the response
        # to the authorization request
        user_consent_form_xpath:

        # (optional) The data that will be passed with the POST request on the form 'action' URL. The data are
        # given as a key value pairs, the keys representing the data key and the value being either
        # a 'constant' string value, or a string of the form 'xpath(<path-to-a-value-to-be-retrieved>)'
        # and representing a value to be retrieved in the user consent form. The xpath must resolve
        # directly to a string value, not to an HTML element. Example:
        # `xpath(//input[@name="sessionDataKeyConsent"]/@value)`
        user_consent_form_data:

        # (optional) A mapping giving additional data to be passed to the login POST request. The value follows the
        # same rules as with user_consent_form_data
        additional_login_form_data:

        # (optional) The OIDC provider's client secret of the eodag provider
        client_secret:

        # (optional) A mapping between OIDC url query string and token handler query string
        # params (only necessary if they are not the same as for OIDC). This is eodag provider
        # dependant
        token_exchange_params:
          redirect_uri:
          client_id:

        # (optional) Only necessary when 'token_provision' is 'qs'. Refers to the name of the query param to be
        # used in the query request
        token_qs_key:

    """

    SCOPE = "openid"
    RESPONSE_TYPE = "code"
    CONFIG_XPATH_REGEX = re.compile(r"^xpath\((?P<xpath_value>.+)\)$")

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(OIDCAuthorizationCodeFlowAuth, self).__init__(provider, config)
        if getattr(self.config, "token_provision", None) not in ("qs", "header"):
            raise MisconfiguredError(
                'Provider config parameter "token_provision" must be one of "qs" or "header"'
            )
        if self.config.token_provision == "qs" and not getattr(
            self.config, "token_qs_key", ""
        ):
            raise MisconfiguredError(
                'Provider config parameter "token_provision" with value "qs" must have '
                '"token_qs_key" config parameter as well'
            )
        self.session = requests.Session()

    def authenticate(self) -> AuthBase:
        """Authenticate"""
        state = self.compute_state()
        authentication_response = self.authenticate_user(state)
        exchange_url = authentication_response.url
        if self.config.user_consent_needed:
            user_consent_response = self.grant_user_consent(authentication_response)
            exchange_url = user_consent_response.url
        try:
            token = self.exchange_code_for_token(exchange_url, state)
        except Exception:
            import traceback as tb

            raise AuthenticationError(
                "Something went wrong while trying to get authorization token:\n{}".format(
                    tb.format_exc()
                )
            )
        return CodeAuthorizedAuth(
            token,
            self.config.token_provision,
            key=getattr(self.config, "token_qs_key", None),
        )

    def authenticate_user(self, state: str) -> Response:
        """Authenticate user"""
        self.validate_config_credentials()
        params = {
            "client_id": self.config.client_id,
            "response_type": self.RESPONSE_TYPE,
            "scope": self.SCOPE,
            "state": state,
            "redirect_uri": self.config.redirect_uri,
        }
        authorization_response = self.session.get(
            self.config.authorization_uri,
            params=params,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
        )

        login_document = etree.HTML(authorization_response.text)
        login_form = login_document.xpath(self.config.login_form_xpath)[0]
        # Get the form data to pass to the login form from config or from the login form
        login_data = {
            key: self._constant_or_xpath_extracted(value, login_form)
            for key, value in getattr(
                self.config, "additional_login_form_data", {}
            ).items()
        }
        # Add the credentials
        login_data.update(self.config.credentials)
        auth_uri = getattr(self.config, "authentication_uri", None)
        # Retrieve the authentication_uri from the login form if so configured
        if self.config.authentication_uri_source == "login-form":
            # Given that the login_form_xpath resolves to an HTML element, if suffices to add '/@action' to get
            # the value of its action attribute to this xpath
            auth_uri = login_form.xpath(
                self.config.login_form_xpath.rstrip("/") + "/@action"
            )[0]
        return self.session.post(
            auth_uri, data=login_data, headers=USER_AGENT, timeout=HTTP_REQ_TIMEOUT
        )

    def grant_user_consent(self, authentication_response: Response) -> Response:
        """Grant user consent"""
        user_consent_document = etree.HTML(authentication_response.text)
        user_consent_form = user_consent_document.xpath(
            self.config.user_consent_form_xpath
        )[0]
        # Get the form data to pass to the consent form from config or from the consent form
        user_consent_data = {
            key: self._constant_or_xpath_extracted(value, user_consent_form)
            for key, value in self.config.user_consent_form_data.items()
        }
        return self.session.post(
            self.config.authorization_uri,
            data=user_consent_data,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
        )

    def exchange_code_for_token(self, authorized_url: str, state: str) -> str:
        """Get exchange code for token"""
        qs = parse_qs(urlparse(authorized_url).query)
        if qs["state"][0] != state:
            raise AuthenticationError(
                "The state received in the authorized url does not match initially computed state"
            )
        code = qs["code"][0]
        token_exchange_data: Dict[str, Any] = {
            "redirect_uri": self.config.redirect_uri,
            "client_id": self.config.client_id,
            "code": code,
            "state": state,
        }
        # If necessary, change the keys of the form data that will be passed to the token exchange POST request
        custom_token_exchange_params = getattr(self.config, "token_exchange_params", {})
        if custom_token_exchange_params:
            token_exchange_data[
                custom_token_exchange_params["redirect_uri"]
            ] = token_exchange_data.pop("redirect_uri")
            token_exchange_data[
                custom_token_exchange_params["client_id"]
            ] = token_exchange_data.pop("client_id")
        # If the client_secret is known, the token exchange request must be authenticated with a BASIC Auth, using the
        # client_id and client_secret as username and password respectively
        if getattr(self.config, "client_secret", None):
            token_exchange_data.update(
                {
                    "auth": (self.config.client_id, self.config.client_secret),
                    "grant_type": "authorization_code",
                    "client_secret": self.config.client_secret,
                }
            )
        post_request_kwargs = {
            self.config.token_exchange_post_data_method: token_exchange_data
        }
        r = self.session.post(
            self.config.token_uri,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            **post_request_kwargs,
        )
        return r.json()[self.config.token_key]

    def _constant_or_xpath_extracted(
        self, value: str, form_element: Any
    ) -> Optional[str]:
        match = self.CONFIG_XPATH_REGEX.match(value)
        if not match:
            return value
        value_from_xpath = form_element.xpath(
            self.CONFIG_XPATH_REGEX.match(value).groupdict("xpath_value")
        )
        if len(value_from_xpath) == 1:
            return value_from_xpath[0]
        return None

    @staticmethod
    def compute_state() -> str:
        """Compute state"""
        rand = SystemRandom()
        return "".join(
            repeatfunc(
                rand.choice,
                22,
                string.digits + string.ascii_lowercase + string.ascii_uppercase,
            )
        )


class CodeAuthorizedAuth(AuthBase):
    """CodeAuthorizedAuth custom authentication class to be used with requests module"""

    def __init__(self, token: str, where: str, key: Optional[str] = None) -> None:
        self.token = token
        self.where = where
        self.key = key

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        """Perform the actual authentication"""
        if self.where == "qs":
            parts = urlparse(request.url)
            query_dict = parse_qs(parts.query)
            query_dict.update({self.key: self.token})
            url_without_args = parts._replace(query=None).geturl()

            request.prepare_url(url_without_args, query_dict)

        elif self.where == "header":
            request.headers["Authorization"] = "Bearer {}".format(self.token)
        return request
