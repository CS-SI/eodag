# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

from eodag.plugins.base import PluginTopic
from eodag.utils.exceptions import MisconfiguredError


class Search(PluginTopic):

    def __init__(self, config):
        # Defining a products key in the config is made optional
        if not isinstance(config.get('products', {}), dict):
            raise MisconfiguredError("'products' must be a dictionary of values")
            # TODO: an instance without products should have minimum possible priority => it should be lower bounded
        if not config.get('api_endpoint'):
            raise MisconfiguredError("'api_endpoint' must be a valid url")
        self.config = config

    def query(self, *args, **kwargs):
        """Implementation of how the products must be searched goes here.

        This method must return a list of EOProduct instances (see eodag.api.product module) which will
        be processed by a Download plugin.
        """
        raise NotImplementedError('A Search plugin must implement a method named query')
