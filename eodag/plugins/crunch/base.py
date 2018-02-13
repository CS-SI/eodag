# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from eodag.plugins.base import GeoProductDownloaderPluginMount


class Crunch(metaclass=GeoProductDownloaderPluginMount):

    def __init__(self, config):
        self.config = config

    def proceed(self, product_list):
        """Implementation of how the results must be crunched"""
        raise NotImplementedError
