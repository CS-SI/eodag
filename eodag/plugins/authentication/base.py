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
from eodag.plugins.base import PluginTopic
from eodag.utils.exceptions import MisconfiguredError


class Authentication(PluginTopic):
    """Plugins authentication Base plugin"""

    def authenticate(self):
        """Authenticate"""
        raise NotImplementedError

    def validate_config_credentials(self):
        """Validate configured credentials"""
        # No credentials dict in the config
        try:
            credentials = self.config.credentials
        except AttributeError:
            raise MisconfiguredError(
                f"Missing credentials configuration for provider {self.provider}"
            )
        # Empty credentials dict
        if not credentials:
            raise MisconfiguredError(
                f"Missing credentials for provider {self.provider}"
            )
        # Credentials keys but values are None.
        missing_credentials = [
            cred_name
            for cred_name, cred_value in credentials.items()
            if cred_value is None
        ]
        if missing_credentials:
            raise MisconfiguredError(
                "The following credentials are missing for provider {}: {}".format(
                    self.provider, ", ".join(missing_credentials)
                )
            )
