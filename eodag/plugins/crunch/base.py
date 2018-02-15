# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from eodag.plugins.base import GeoProductDownloaderPluginMount


class Crunch(object):
    __metaclass__ = GeoProductDownloaderPluginMount

    def __init__(self, config):
        self.config = config

    def proceed(self, product_list):
        """Implementation of how the results must be crunched"""
        raise NotImplementedError
