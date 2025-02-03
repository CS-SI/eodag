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

from typing import TYPE_CHECKING, Optional, cast

from eodag.plugins.authentication.base import Authentication
from eodag.types import S3SessionKwargs

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client

    from eodag.config import PluginConfig


class AwsAuth(Authentication):
    """AWS authentication plugin

    Authentication will use the first valid method within the following ones depending on which
    parameters are available in the configuration:

    * auth anonymously using no-sign-request
    * auth using ``aws_profile``
    * auth using ``aws_access_key_id`` and ``aws_secret_access_key``
      (optionally ``aws_session_token``)
    * auth using current environment (AWS environment variables and/or ``~/aws/*``),
      will be skipped if AWS credentials are filled in eodag conf

    :param provider: provider name
    :param config: Authentication plugin configuration:

        * :attr:`~eodag.config.PluginConfig.type` (``str``) (**mandatory**): AwsAuth
        * :attr:`~eodag.config.PluginConfig.auth_error_code` (``int``) (mandatory for ``creodias_s3``):
          which error code is returned in case of an authentication error

    """

    s3_client: S3Client

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(AwsAuth, self).__init__(provider, config)
        self.aws_access_key_id: Optional[str] = None
        self.aws_secret_access_key: Optional[str] = None
        self.aws_session_token: Optional[str] = None
        self.profile_name: Optional[str] = None

    def authenticate(self) -> S3SessionKwargs:
        """Authenticate

        :returns: dict containing AWS/boto3 non-empty credentials
        """
        credentials = getattr(self.config, "credentials", {}) or {}
        self.aws_access_key_id = credentials.get(
            "aws_access_key_id", self.aws_access_key_id
        )
        self.aws_secret_access_key = credentials.get(
            "aws_secret_access_key", self.aws_secret_access_key
        )
        self.aws_session_token = credentials.get(
            "aws_session_token", self.aws_session_token
        )
        self.profile_name = credentials.get("aws_profile", self.profile_name)

        auth_dict = cast(
            S3SessionKwargs,
            {
                k: getattr(self, k)
                for k in S3SessionKwargs.__annotations__
                if getattr(self, k, None)
            },
        )
        return auth_dict
