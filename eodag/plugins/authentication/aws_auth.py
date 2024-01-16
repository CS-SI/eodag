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

from typing import TYPE_CHECKING, Dict, Union

from eodag.plugins.authentication.base import Authentication

if TYPE_CHECKING:
    from botocore.client import S3
    from requests.auth import AuthBase

    from eodag.config import PluginConfig


class AwsAuth(Authentication):
    """AWS authentication plugin

    Authentication will use the first valid method within the following ones:

    - auth anonymously using no-sign-request
    - auth using ``aws_profile``
    - auth using ``aws_access_key_id`` and ``aws_secret_access_key``
    - auth using current environment (AWS environment variables and/or ``~/aws/*``),
      will be skipped if AWS credentials are filled in eodag conf
    """

    s3_client: S3

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(AwsAuth, self).__init__(provider, config)
        self.aws_access_key_id = None
        self.aws_secret_access_key = None
        self.profile_name = None

    def authenticate(self) -> Union[AuthBase, Dict[str, str]]:
        """Authenticate

        :returns: dict containing AWS/boto3 non-empty credentials
        :rtype: dict
        """
        credentials = getattr(self.config, "credentials", {}) or {}
        self.aws_access_key_id = credentials.get(
            "aws_access_key_id", self.aws_access_key_id
        )
        self.aws_secret_access_key = credentials.get(
            "aws_secret_access_key", self.aws_secret_access_key
        )
        self.profile_name = credentials.get("aws_profile", self.profile_name)

        auth_keys = ["aws_access_key_id", "aws_secret_access_key", "profile_name"]
        return {k: getattr(self, k) for k in auth_keys if getattr(self, k)}
