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

from typing import TYPE_CHECKING, Union

from eodag.plugins.base import PluginTopic
from eodag.utils import deepcopy
from eodag.utils.exceptions import MisconfiguredError

if TYPE_CHECKING:
    from requests.auth import AuthBase

    from eodag.types import S3SessionKwargs


class Authentication(PluginTopic):
    """Plugins authentication Base plugin

    :param provider: provider name
    :param config: Authentication plugin configuration:

        * :attr:`~eodag.config.PluginConfig.match` (``dict[str, str]``): dict of parameters to
          be matched with a product or a search/download plugin to find the correct auth plugin
    """

    def authenticate(self) -> Union[AuthBase, S3SessionKwargs]:
        """Authenticate"""
        raise NotImplementedError

    def get_required_credentials(self) -> dict[str, str]:
        """checks if only a subset of the credentials is required for the plugin object
        and returns this subset; returns all credentials if not required credentials are given
        :returns: dict of credentials
        """
        credentials = deepcopy(self.config.credentials)
        required_credentials = getattr(self.config, "required_credentials", None)
        if required_credentials:
            credentials = {
                k: credentials[k] for k in credentials if k in required_credentials
            }
        return credentials

    def validate_config_credentials(self) -> None:
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
        # check if only specific credentials are required for the plugin
        credentials = self.get_required_credentials()
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
