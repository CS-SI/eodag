# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import six

from eodag.plugins.base import GeoProductDownloaderPluginMount


class Authentication(six.with_metaclass(GeoProductDownloaderPluginMount)):

    def __init__(self, config):
        self.config = config

    def authenticate(self):
        raise NotImplementedError

