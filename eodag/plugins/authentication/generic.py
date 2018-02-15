# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from eodag.plugins.authentication.base import Authentication


class GenericAuth(Authentication):

    def authenticate(self):
        method = self.config.get('method')
        if not method:
            method = 'basic'
        if method == 'basic':
            return HTTPBasicAuth(*tuple(self.config['credentials'].values()))
        if method == 'digest':
            return HTTPDigestAuth(*tuple(self.config['credentials'].values()))

