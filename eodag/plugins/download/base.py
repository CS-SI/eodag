# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

from eodag.plugins.base import PluginTopic


class Download(PluginTopic):

    def __init__(self, config):
        self.config = config
        self.authenticate = bool(self.config.setdefault('authenticate', False))

    def download(self, product, auth=None, progress_callback=None):
        raise NotImplementedError('A Download plugin must implement a method named download')
