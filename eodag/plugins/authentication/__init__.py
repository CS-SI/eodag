# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from eodag.plugins.authentication.base import Authentication


class DummyAuth(Authentication):

    def authenticate(self):
        return self
