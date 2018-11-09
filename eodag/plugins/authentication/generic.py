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
from __future__ import absolute_import, print_function, unicode_literals

from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from eodag.plugins.authentication.base import Authentication
from eodag.utils.exceptions import MisconfiguredError


class GenericAuth(Authentication):

    def authenticate(self):
        method = getattr(self.config, 'method', None)
        try:
            if not method:
                method = 'basic'
            if method == 'basic':
                return HTTPBasicAuth(
                    self.config.credentials['username'],
                    self.config.credentials['password']
                )
            if method == 'digest':
                return HTTPDigestAuth(
                    self.config.credentials['username'],
                    self.config.credentials['password']
                )
        except AttributeError as err:
            if 'credentials' in err:
                raise MisconfiguredError('Missing Credentials for provider: %s', self.provider)
