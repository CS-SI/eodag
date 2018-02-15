# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from eodag.plugins.base import GeoProductDownloaderPluginMount


class Download(object):
    __metaclass__ = GeoProductDownloaderPluginMount

    def __init__(self, config):
        self.config = config
        self.authenticate = bool(self.config.setdefault('authenticate', False))

    def download(self, product, auth=None):
        raise NotImplementedError('A Download plugin must implement a method named download')
