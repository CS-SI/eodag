# -*- coding: utf-8 -*-
# Copyright 2018, CS Systemes d'Information, http://www.c-s.fr
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
from __future__ import unicode_literals

import string
from random import SystemRandom

import requests
from lxml import etree
from requests.auth import AuthBase

from eodag.plugins.authentication import Authentication
from eodag.utils import parse_qs, repeatfunc, urlencode, urlparse, urlunparse
from eodag.utils.exceptions import AuthenticationError, MisconfiguredError


class OIDCAuthorizationCodeFlowAuth(Authentication):
    """Implement the authorization code flow of the OpenIDConnect authorization specification.

    The `OpenID Connect <http://openid.net/specs/openid-connect-core-1_0.html>`_ specification
    adds an authentication layer on top of oauth 2.0. This plugin implements the
    `authorization code flow <http://openid.net/specs/openid-connect-core-1_0.html#Authentication>`_
    option of this specification.
    The particularity of this plugin is that it proceeds to a headless (not involving the user)
    interaction with the `Theia <https://sso.theia-land.fr/>`_ OpenID provider to authenticate a
    registered user with its username and password on the server and then granting to eodag the
    necessary rights. It does that using the client ID of the eodag provider that use it.

    The configuration keys of this plugin are as follows (they have no defaults)::

        # The authorization url of the server (where to query for grants)
        authorization_uri:

        # The callback url that will handle the code given by the OIDC provider
        redirect_uri:

        # The url of the authentication backend of the OIDC provider
        authentication_uri:

        # The url to query to exchange the authorization code obtained from the OIDC provider
        # for an authorized token
        token_uri:

        # The OIDC provider's client ID of the eodag provider
        client_id:

        # An optional mapping between OIDC url query string and token handler query string
        # params (only necessary if they are not the same as for OIDC). This is eodag provider
        # dependant
        token_exchange_params:
          redirect_uri: redirectUri
          client_id: clientId

        # One of: json, data or params. This is the way to pass the data to the POST request
        # that is made to the token server. They correspond to the recognised keywords arguments
        # of the Python `requests <http://docs.python-requests.org/>`_ library
        token_exchange_post_data_method:

        # One of qs or header. This is how the token obtained will be used to authenticate the user
        # on protected requests. if 'qs' is chosen, then 'token_qs_key' is mandatory
        token_provision:

        # Only necessary when 'token_provision' is 'qs'. Refers to the name of the query param to be
        # used in the query request
        token_qs_key:

    """
    SCOPE = 'openid'
    RESPONSE_TYPE = 'code'

    def __init__(self, config):
        super(OIDCAuthorizationCodeFlowAuth, self).__init__(config)
        self.session = requests.Session()

    def authenticate(self):
        state = self.compute_state()
        params = {
            'client_id': self.config['client_id'],
            'response_type': self.RESPONSE_TYPE,
            'scope': self.SCOPE,
            'state': state,
            'redirect_uri': self.config['redirect_uri'],
        }
        authentication_response = self.authenticate_user(self.session.get(
            self.config['authorization_uri'],
            params=params
        ))
        user_consent_response = self.grant_user_consent(authentication_response)
        try:
            token = self.exchange_code_for_token(user_consent_response.url, state)
        except Exception:
            import traceback as tb
            raise AuthenticationError(
                'Something went wrong while trying to get authorization token:\n{}'.format(tb.format_exc())
            )
        if self.config['token_provision'] not in ('qs', 'headers'):
            raise MisconfiguredError('Provider config parameter "token_provision" must be one of "qs" or "headers"')
        if self.config['token_provision'] == 'qs' and not self.config.get('token_qs_key', ''):
            raise MisconfiguredError('Provider config parameter "token_provision" with value "qs" must have '
                                     '"token_qs_key" config parameter as well')
        return CodeAuthorizedAuth(token, self.config['token_provision'], key=self.config.get('token_qs_key'))

    def authenticate_user(self, authorization_response):
        login_document = etree.HTML(authorization_response.text)
        login_form = login_document.xpath('//form[@id="loginForm"]')[0]
        try:
            login_data = self.config['credentials']
            login_data['sessionDataKey'] = login_form.xpath('//input[@name="sessionDataKey"]')[0].attrib['value']
            return self.session.post(self.config['authentication_uri'], data=login_data)
        except KeyError as err:
            if 'credentials' in err:
                raise MisconfiguredError('Missing Credentials for provider: %s', self.instance_name)

    def grant_user_consent(self, authentication_response):
        user_consent_document = etree.HTML(authentication_response.text)
        user_consent_form = user_consent_document.xpath('//form[@id="profile"]')[0]
        user_consent_data = {
            'consent': 'approve',
            'sessionDataKeyConsent': user_consent_form.xpath(
                '//input[@name="sessionDataKeyConsent"]'
            )[0].attrib['value']
        }
        return self.session.post(self.config['authorization_uri'], data=user_consent_data)

    def exchange_code_for_token(self, authorized_url, state):
        qs = parse_qs(urlparse(authorized_url).query)
        if qs['state'][0] != state:
            raise AuthenticationError(
                'The state received in the authorized url does not match initially computed state')
        code = qs['code'][0]
        token_exchange_data = {
            'redirect_uri': self.config['redirect_uri'],
            'client_id': self.config['client_id'],
            'code': code,
            'state': state,
        }
        custom_token_exchange_params = self.config['token_exchange_params']
        if custom_token_exchange_params:
            token_exchange_data[custom_token_exchange_params['redirect_uri']] = token_exchange_data.pop('redirect_uri')
            token_exchange_data[custom_token_exchange_params['client_id']] = token_exchange_data.pop('client_id')
        post_request_kwargs = {self.config['token_exchange_post_data_method']: token_exchange_data}
        r = self.session.post(self.config['token_uri'], **post_request_kwargs)
        return r.json()['token']

    @staticmethod
    def compute_state():
        rand = SystemRandom()
        return ''.join(repeatfunc(rand.choice, 22, string.digits + string.ascii_lowercase + string.ascii_uppercase))


class CodeAuthorizedAuth(AuthBase):

    def __init__(self, token, where, key=None):
        self.token = token
        self.where = where
        self.key = key

    def __call__(self, request):
        if self.where == 'qs':
            parts = urlparse(request.url)
            qs = parse_qs(parts.query)
            qs[self.key] = self.token
            request.url = urlunparse((
                parts.scheme,
                parts.netloc,
                parts.path,
                parts.params,
                urlencode(qs),
                parts.fragment
            ))
        elif self.where == 'header':
            request.headers['Authorization'] = "Bearer {}".format(self.token)
        return request
