# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from eodag.plugins.base import GeoProductDownloaderPluginMount


class Authentication(metaclass=GeoProductDownloaderPluginMount):

    def __init__(self, config):
        self.config = {
            'uri': '',
            'credentials': {}
        }
        self.config.update(config)

    def authenticate(self):
        raise NotImplementedError

