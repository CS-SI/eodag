# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
import requests
from requests import HTTPError

from eodag.plugins.authentication.base import Authentication
from eodag.utils import RequestsTokenAuth


class TokenAuth(Authentication):

    def authenticate(self):
        # First get the token
        response = requests.post(
            self.config['auth_uri'],
            data=self.config['credentials']
        )
        try:
            response.raise_for_status()
        except HTTPError as e:
            raise e
        else:
            if self.config.get('token_type', 'text') == 'json':
                token = response.json()
            else:
                token = response.text
            return RequestsTokenAuth(token)

