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

from typing import Dict, Union

from requests.auth import AuthBase

from eodag.config import PluginConfig
from eodag.plugins.authentication.base import Authentication


class OAuth(Authentication):
    """OAuth authentication plugin"""

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(OAuth, self).__init__(provider, config)
        self.access_key = None
        self.secret_key = None

    def authenticate(self) -> Union[AuthBase, Dict[str, str]]:
        """Authenticate"""
        self.validate_config_credentials()
        self.access_key = self.config.credentials["aws_access_key_id"]
        self.secret_key = self.config.credentials["aws_secret_access_key"]
        return {"access_key": self.access_key, "secret_key": self.secret_key}
