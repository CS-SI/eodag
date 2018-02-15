# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import os

import yaml
import yaml.parser


class SimpleYamlProxyConfig(object):
    """A simple configuration class acting as a proxy to an underlying dict object as returned by yaml.load"""

    def __init__(self, conf_file_path):
        with open(os.path.abspath(os.path.realpath(conf_file_path)), 'r') as fh:
            try:
                self.source = yaml.load(fh)
            except yaml.parser.ParserError as e:
                print('Unable to load user configuration file')
                raise e

    def __getitem__(self, item):
        return self.source[item]

    def __contains__(self, item):
        return item in self.source

    def __iter__(self):
        return iter(self.source)

    def items(self):
        return self.source.items()

    def values(self):
        return self.source.values()

    def update(self, other):
        if not isinstance(other, self.__class__):
            raise ValueError("'{}' must be of type {}".format(other, self.__class__))
        self.source.update(other.source)
