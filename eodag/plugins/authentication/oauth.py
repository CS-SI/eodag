# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from eodag.plugins.authentication.base import Authentication


class OAuth(Authentication):

    def __init__(self, config):
        super(OAuth, self).__init__(config)
        self.access_key = None
        self.secret_key = None

    def authenticate(self):
        self.access_key = self.config['credentials']['aws_access_key_id']
        self.secret_key = self.config['credentials']['aws_secret_access_key']
        return self.access_key, self.secret_key

