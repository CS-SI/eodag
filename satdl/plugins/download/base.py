# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from satdl.plugins.base import GeoProductDownloaderPluginMount


class Download(metaclass=GeoProductDownloaderPluginMount):
    def __init__(self, config):
        self.config = config
        self.authenticate = bool(self.config.setdefault('authenticate', False))

    def download(self, product, auth=None):
        raise NotImplementedError('A Download plugin must implement a method named download')
