# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

import logging

from eodag.plugins.base import PluginTopic


logger = logging.getLogger('eodag.plugins.apis.base')


class Api(PluginTopic):

    def __init__(self, config):
        self.config = config
        self.config.setdefault('outputs_prefix', '/tmp')
        self.config.setdefault('on_site', False)
        self.config.setdefault('extract', True)
        logger.debug('Images will be downloaded to directory %s', self.config['outputs_prefix'])

    def query(self, *args, **kwargs):
        """Implementation of how the products must be searched goes here.

        This method must return a list of EOProduct instances (see eodag.api.product module) which will
        be processed by a Download plugin.
        """
        raise NotImplementedError('A Api plugin must implement a method named query')

    def download(self, *args, **kwargs):
        """Implementation of how the products must be downloaded."""
        raise NotImplementedError('A Api plugin must implement a method named download')
