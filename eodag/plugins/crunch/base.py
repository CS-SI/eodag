# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

from eodag.plugins.base import PluginTopic


class Crunch(PluginTopic):

    def proceed(self, product_list, **search_params):
        """Implementation of how the results must be crunched"""
        raise NotImplementedError
