# -*- coding: utf-8 -*-
# Copyright 2026, CS GROUP - France, https://www.csgroup.eu/
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
"""EODAG authentication package"""
from .aws_auth import AwsAuth, create_s3_session, raise_if_auth_error
from .base import Authentication
from .dummy import DummyAuth
from .eoiam import EOIAMAuth, EOIAMSessionAuth
from .generic import GenericAuth
from .header import HeaderAuth, HTTPHeaderAuth
from .keycloak import KeycloakOIDCPasswordAuth
from .openid_connect import (
    CodeAuthorizedAuth,
    OIDCAuthorizationCodeFlowAuth,
    OIDCRefreshTokenBase,
)
from .qsauth import HttpQueryStringAuth, QueryStringAuth
from .sas_auth import RequestsSASAuth, SASAuth
from .token import RequestsTokenAuth, TokenAuth
from .token_exchange import OIDCTokenExchangeAuth

__all__ = [
    "Authentication",
    "DummyAuth",
    "AwsAuth",
    "create_s3_session",
    "raise_if_auth_error",
    "GenericAuth",
    "HTTPHeaderAuth",
    "HeaderAuth",
    "KeycloakOIDCPasswordAuth",
    "CodeAuthorizedAuth",
    "OIDCRefreshTokenBase",
    "OIDCAuthorizationCodeFlowAuth",
    "HttpQueryStringAuth",
    "QueryStringAuth",
    "RequestsSASAuth",
    "SASAuth",
    "RequestsTokenAuth",
    "TokenAuth",
    "OIDCTokenExchangeAuth",
    "EOIAMSessionAuth",
    "EOIAMAuth",
]
