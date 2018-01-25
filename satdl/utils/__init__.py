# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from requests.auth import AuthBase


class RequestsTokenAuth(AuthBase):
    def __init__(self, token):
        if isinstance(token, str):
            self.token = token
        elif isinstance(token, dict):
            self.token = token.get('tokenIdentity', '')
        self.bearer_str = "Bearer {}".format(self.token)

    def __call__(self, req):
        req.headers['Authorization'] = self.bearer_str
        return req

