# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from satdl.plugins.authentication.base import Authentication


class GenericAuth(Authentication):

    def __init__(self, config):
        super(GenericAuth, self).__init__(config)

    def authenticate(self):
        method = self.config.get('method')
        if not method:
            method = 'basic'
        if method == 'basic':
            return HTTPBasicAuth(*tuple(self.config['credentials'].values()))
        if method == 'digest':
            return HTTPDigestAuth(*tuple(self.config['credentials'].values()))

