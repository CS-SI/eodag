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

import logging
import re
import string
from datetime import datetime, timedelta, timezone
from random import SystemRandom
from typing import TYPE_CHECKING, Any, Optional

import jwt
import requests
from lxml import etree
from requests.auth import AuthBase

from eodag.plugins.authentication import Authentication
from eodag.utils import HTTP_REQ_TIMEOUT, USER_AGENT, parse_qs, repeatfunc, urlparse
from eodag.utils.exceptions import AuthenticationError, MisconfiguredError, TimeOutError

if TYPE_CHECKING:
    from requests import PreparedRequest, Response

    from eodag.config import PluginConfig


logger = logging.getLogger("eodag.auth.openid_connect")


class OIDCRefreshTokenBase(Authentication):
    """OIDC refresh token base class, to be used through specific OIDC flows plugins;
    Common mechanism to handle refresh token from all OIDC auth plugins;

    Plugins inheriting from this base class must implement the methods ``_request_new_token()`` and
    ``_get_token_with_refresh_token()``. Depending on the implementation of these methods they can have
    different configuration parameters.

    """

    jwks_client: jwt.PyJWKClient

    access_token: str
    access_token_expiration: datetime

    refresh_token: str
    refresh_token_expiration: datetime

    token_endpoint: str
    authorization_endpoint: str

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(OIDCRefreshTokenBase, self).__init__(provider, config)
        self.session = requests.Session()

        self.access_token = ""
        self.access_token_expiration = datetime.min.replace(tzinfo=timezone.utc)

        self.refresh_token = ""
        self.refresh_token_expiration = datetime.min.replace(tzinfo=timezone.utc)

        try:
            response = requests.get(self.config.oidc_config_url)
            response.raise_for_status()
            auth_config = response.json()
        except requests.HTTPError as e:
            raise MisconfiguredError(
                f"Cannot obtain OIDC endpoints from {self.config.oidc_config_url}"
                f"Request returned {e.response.text}."
            )

        self.jwks_client = jwt.PyJWKClient(auth_config["jwks_uri"])
        self.token_endpoint = auth_config["token_endpoint"]
        self.authorization_endpoint = auth_config["authorization_endpoint"]
        self.algorithms = auth_config["id_token_signing_alg_values_supported"]

    def decode_jwt_token(self, token: str) -> dict[str, Any]:
        """Decode JWT token."""
        try:
            key = self.jwks_client.get_signing_key_from_jwt(token).key
            if getattr(self.config, "allowed_audiences", None):
                return jwt.decode(
                    token,
                    key,
                    algorithms=self.algorithms,
                    # NOTE: Audience validation MUST match audience claim if set in token
                    # (https://pyjwt.readthedocs.io/en/stable/changelog.html?highlight=audience#id40)
                    audience=self.config.allowed_audiences,
                )
            else:
                return jwt.decode(
                    token,
                    key,
                    algorithms=self.algorithms,
                )
        except (jwt.exceptions.InvalidTokenError, jwt.exceptions.DecodeError) as e:
            raise AuthenticationError(e)

    def _get_access_token(self) -> str:
        now = datetime.now(timezone.utc)
        if self.access_token and now < self.access_token_expiration:
            logger.debug(
                f"Existing access_token is still valid until {self.access_token_expiration.isoformat()}."
            )
            return self.access_token

        elif self.refresh_token and now < self.refresh_token_expiration:
            response = self._get_token_with_refresh_token()
            logger.debug(
                "access_token expired, fetching new access_token using refresh_token"
            )
        else:
            logger.debug("access_token expired or not available yet, new token request")
            response = self._request_new_token()

        self.access_token = response[getattr(self.config, "token_key", "access_token")]
        self.access_token_expiration = datetime.fromtimestamp(
            self.decode_jwt_token(self.access_token)["exp"], timezone.utc
        )
        self.refresh_token = response.get(
            getattr(self.config, "refresh_token_key", "refresh_token"), ""
        )
        if self.refresh_token and response.get("refresh_expires_in", "0"):
            self.refresh_token_expiration = now + timedelta(
                seconds=int(response["refresh_expires_in"])
            )
        else:
            # refresh token does not expire but will be changed at each request
            self.refresh_token_expiration = now + timedelta(days=1000)

        return self.access_token

    def _request_new_token(self) -> dict[str, str]:
        """Fetch the access token with a new authentication"""
        raise NotImplementedError(
            "Incomplete OIDC refresh token retrieval mechanism implementation"
        )

    def _request_new_token_error(self, e: requests.RequestException) -> dict[str, str]:
        """Handle RequestException raised by `self._request_new_token()`"""
        if self.access_token:
            # try using already retrieved token if authenticate() fails (OTP use-case)
            return {
                "access_token": self.access_token,
                "expires_in": self.access_token_expiration.isoformat(),
            }
        response_text = getattr(e.response, "text", "").strip()
        # check if error is identified as auth_error in provider conf
        auth_errors = getattr(self.config, "auth_error_code", [None])
        if not isinstance(auth_errors, list):
            auth_errors = [auth_errors]
        if (
            e.response
            and hasattr(e.response, "status_code")
            and e.response.status_code in auth_errors
        ):
            raise AuthenticationError(
                f"Please check your credentials for {self.provider}.",
                f"HTTP Error {e.response.status_code} returned.",
                response_text,
            )
        # other error
        else:
            import traceback as tb

            logger.error(
                f"Provider {self.provider} returned {getattr(e.response, 'status_code', '')}: {response_text}"
            )
            raise AuthenticationError(
                "Something went wrong while trying to get access token:\n{}".format(
                    tb.format_exc()
                )
            )

    def _get_token_with_refresh_token(self) -> dict[str, str]:
        """Fetch the access token with the refresh token"""
        raise NotImplementedError(
            "Incomplete OIDC refresh token retrieval mechanism implementation"
        )


class OIDCAuthorizationCodeFlowAuth(OIDCRefreshTokenBase):
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

    :param provider: provider name
    :param config: Authentication plugin configuration:

        * :attr:`~eodag.config.PluginConfig.type` (``str``) (**mandatory**): OIDCAuthorizationCodeFlowAuth
        * :attr:`~eodag.config.PluginConfig.redirect_uri` (``str``) (**mandatory**):  The callback
          url that will handle the code given by the OIDC provider
        * :attr:`~eodag.config.PluginConfig.oidc_config_url` (``str``) (**mandatory**):
          The url to get the OIDC Provider's endpoints
        * :attr:`~eodag.config.PluginConfig.client_id` (``str``) (**mandatory**): The OIDC provider's
          client ID of the eodag provider
        * :attr:`~eodag.config.PluginConfig.user_consent_needed` (``bool``) (mandatory): Whether
          a user consent is needed during the authentication
        * :attr:`~eodag.config.PluginConfig.token_exchange_post_data_method` (``str``) (**mandatory**):
          One of: ``json``, ``data`` or ``params``. This is the way to pass the data to the
          POST request that is made to the token server. They correspond to the recognised keywords
          arguments of the Python `requests <http://docs.python-requests.org/>`_ library
        * :attr:`~eodag.config.PluginConfig.token_key` (``str``): The key pointing
          to the token in the json response to the POST request to the token server
        * :attr:`~eodag.config.PluginConfig.token_provision` (``str``) (**mandatory**): One of
          ``qs`` or ``header``. This is how the token obtained will be used to authenticate the
          user on protected requests. If ``qs`` is chosen, then ``token_qs_key`` is mandatory
        * :attr:`~eodag.config.PluginConfig.login_form_xpath` (``str``) (**mandatory**): The
          xpath to the HTML form element representing the user login form
        * :attr:`~eodag.config.PluginConfig.authentication_uri_source` (``str``) (**mandatory**): Where
          to look for the authentication_uri. One of ``config`` (in the configuration) or ``login-form``
          (use the 'action' URL found in the login form retrieved with login_form_xpath). If the
          value is ``config``, authentication_uri config param is mandatory
        * :attr:`~eodag.config.PluginConfig.authentication_uri` (``str``): (**mandatory if
          authentication_uri_source=config**) The URL of the authentication backend of the OIDC provider
        * :attr:`~eodag.config.PluginConfig.user_consent_form_xpath` (``str``): The xpath to
          the user consent form. The form is searched in the content of the response to the authorization request
        * :attr:`~eodag.config.PluginConfig.user_consent_form_data` (``dict[str, str]``): The data that
          will be passed with the POST request on the form 'action' URL. The data are given as
          key value pairs, the keys representing the data key and the value being either a 'constant'
          string value, or a string of the form 'xpath(<path-to-a-value-to-be-retrieved>)' and representing a
          value to be retrieved in the user consent form. The xpath must resolve directly to a
          string value, not to an HTML element. Example: ``xpath(//input[@name="sessionDataKeyConsent"]/@value)``
        * :attr:`~eodag.config.PluginConfig.additional_login_form_data` (``dict[str, str]``): A mapping
          giving additional data to be passed to the login POST request. The value follows
          the same rules as with user_consent_form_data
        * :attr:`~eodag.config.PluginConfig.exchange_url_error_pattern` (``dict[str, str]``): Key/value
          pairs of patterns/messages. If exchange_url contains the given pattern, the associated
          message will be sent in an AuthenticationError
        * :attr:`~eodag.config.PluginConfig.client_secret` (``str``): The OIDC provider's client
          secret of the eodag provider
        * :attr:`~eodag.config.PluginConfig.token_exchange_params` (``dict[str, str]``): mandatory
          keys for the dict: redirect_uri, client_id; A mapping between OIDC url query string
          and token handler query string params (only necessary if they are not the same as for OIDC).
          This is eodag provider dependant
        * :attr:`~eodag.config.PluginConfig.token_qs_key` (``str``): (mandatory when token_provision=qs)
          Refers to the name of the query param to be used in the query request
        * :attr:`~eodag.config.PluginConfig.refresh_token_key` (``str``): The key pointing to
          the refresh_token in the json response to the POST request to the token server

    """

    SCOPE = "openid"
    RESPONSE_TYPE = "code"
    CONFIG_XPATH_REGEX = re.compile(r"^xpath\((?P<xpath_value>.+)\)$")

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(OIDCAuthorizationCodeFlowAuth, self).__init__(provider, config)

    def validate_config_credentials(self) -> None:
        """Validate configured credentials"""
        super(OIDCAuthorizationCodeFlowAuth, self).validate_config_credentials()
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

    def authenticate(self) -> CodeAuthorizedAuth:
        """Authenticate"""
        self._get_access_token()

        return CodeAuthorizedAuth(
            self.access_token,
            self.config.token_provision,
            key=getattr(self.config, "token_qs_key", None),
        )

    def _request_new_token(self) -> dict[str, str]:
        """Fetch the access token with a new authentication"""
        logger.debug("Fetching access token from %s", self.token_endpoint)
        state = self.compute_state()
        authentication_response = self.authenticate_user(state)
        exchange_url = authentication_response.url
        for err_pattern, err_message in getattr(
            self.config, "exchange_url_error_pattern", {}
        ).items():
            if err_pattern in exchange_url:
                raise AuthenticationError(err_message)
        if not exchange_url.startswith(self.config.redirect_uri):
            raise AuthenticationError(
                f"Could not authenticate user with provider {self.provider}.",
                "Please verify your credentials",
            )
        if self.config.user_consent_needed:
            user_consent_response = self.grant_user_consent(authentication_response)
            exchange_url = user_consent_response.url
        try:
            token_response = self.exchange_code_for_token(exchange_url, state)
            token_response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(exc, timeout=HTTP_REQ_TIMEOUT) from exc
        except requests.RequestException as e:
            return self._request_new_token_error(e)
        return token_response.json()

    def _get_token_with_refresh_token(self) -> dict[str, str]:
        """Fetch the access token with the refresh token"""
        logger.debug(
            "Fetching access token with refresh token from %s.", self.token_endpoint
        )
        token_data: dict[str, Any] = {
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }
        token_data = self._prepare_token_post_data(token_data)
        post_request_kwargs: Any = {
            self.config.token_exchange_post_data_method: token_data
        }
        ssl_verify = getattr(self.config, "ssl_verify", True)
        try:
            token_response = self.session.post(
                self.token_endpoint,
                timeout=HTTP_REQ_TIMEOUT,
                verify=ssl_verify,
                **post_request_kwargs,
            )
            token_response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(exc, timeout=HTTP_REQ_TIMEOUT) from exc
        except requests.RequestException as exc:
            logger.error(
                "Could not fetch access token with refresh token, executing new token request, error: %s",
                getattr(exc.response, "text", ""),
            )
            return self._request_new_token()
        return token_response.json()

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
        ssl_verify = getattr(self.config, "ssl_verify", True)
        authorization_response = self.session.get(
            self.authorization_endpoint,
            params=params,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            verify=ssl_verify,
        )

        login_document = etree.HTML(authorization_response.text)
        login_forms = login_document.xpath(self.config.login_form_xpath)

        if not login_forms:
            # we assume user is already logged in
            # no form found because we got redirected to the redirect_uri
            return authorization_response

        login_form = login_forms[0]

        # Get the form data to pass to the login form from config or from the login form
        login_data = {
            key: self._constant_or_xpath_extracted(value, login_form)
            for key, value in getattr(
                self.config, "additional_login_form_data", {}
            ).items()
        }
        # Add the credentials
        login_data.update(self.config.credentials)

        # Retrieve the authentication_uri from the login form if so configured
        if self.config.authentication_uri_source == "login-form":
            # Given that the login_form_xpath resolves to an HTML element, if suffices to add '/@action' to get
            # the value of its action attribute to this xpath
            auth_uri = login_form.xpath(
                self.config.login_form_xpath.rstrip("/") + "/@action"
            )
            if not auth_uri or not auth_uri[0]:
                raise MisconfiguredError(
                    f"Could not get auth_uri from {self.config.login_form_xpath}"
                )
            auth_uri = auth_uri[0]
        else:
            auth_uri = getattr(self.config, "authentication_uri", None)
            if not auth_uri:
                raise MisconfiguredError("authentication_uri is missing")
        return self.session.post(
            auth_uri,
            data=login_data,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            verify=ssl_verify,
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
        ssl_verify = getattr(self.config, "ssl_verify", True)
        return self.session.post(
            self.authorization_endpoint,
            data=user_consent_data,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            verify=ssl_verify,
        )

    def _prepare_token_post_data(self, token_data: dict[str, Any]) -> dict[str, Any]:
        """Prepare the common data to post to the token URI"""
        token_data.update(
            {
                "redirect_uri": self.config.redirect_uri,
                "client_id": self.config.client_id,
            }
        )
        # If necessary, change the keys of the form data that will be passed to the token exchange POST request
        custom_token_exchange_params = getattr(self.config, "token_exchange_params", {})
        if custom_token_exchange_params:
            token_data[custom_token_exchange_params["redirect_uri"]] = token_data.pop(
                "redirect_uri"
            )
            token_data[custom_token_exchange_params["client_id"]] = token_data.pop(
                "client_id"
            )
        # If the client_secret is known, the token exchange request must be authenticated with a BASIC Auth, using the
        # client_id and client_secret as username and password respectively
        if getattr(self.config, "client_secret", None):
            token_data.update(
                {
                    "auth": (self.config.client_id, self.config.client_secret),
                    "client_secret": self.config.client_secret,
                }
            )
        return token_data

    def exchange_code_for_token(self, authorized_url: str, state: str) -> Response:
        """Get exchange code for token"""
        qs = parse_qs(urlparse(authorized_url).query)
        if qs["state"][0] != state:
            raise AuthenticationError(
                "The state received in the authorized url does not match initially computed state"
            )
        code = qs["code"][0]
        token_exchange_data: dict[str, Any] = {
            "code": code,
            "state": state,
            "grant_type": "authorization_code",
        }
        token_exchange_data = self._prepare_token_post_data(token_exchange_data)
        post_request_kwargs: Any = {
            self.config.token_exchange_post_data_method: token_exchange_data
        }
        ssl_verify = getattr(self.config, "ssl_verify", True)
        r = self.session.post(
            self.token_endpoint,
            headers=USER_AGENT,
            timeout=HTTP_REQ_TIMEOUT,
            verify=ssl_verify,
            **post_request_kwargs,
        )
        return r

    def _constant_or_xpath_extracted(
        self, value: str, form_element: Any
    ) -> Optional[str]:
        match = self.CONFIG_XPATH_REGEX.match(value)
        if not match:
            return value
        value_from_xpath = form_element.xpath(
            match.groupdict("xpath_value")["xpath_value"]
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
            parts = urlparse(str(request.url))
            query_dict = parse_qs(parts.query)
            if self.key is not None:
                query_dict.update({self.key: [self.token]})
            url_without_args = parts._replace(query="").geturl()

            request.prepare_url(url_without_args, query_dict)

        elif self.where == "header":
            request.headers["Authorization"] = "Bearer {}".format(self.token)
        logger.debug(
            re.sub(
                r"'Bearer [^']+'",
                r"'Bearer ***'",
                f"PreparedRequest: {request.__dict__}",
            )
        )
        return request
