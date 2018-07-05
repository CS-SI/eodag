# -*- coding: utf-8 -*-
# Copyright 2018, CS Systemes d'Information, http://www.c-s.fr
#
# This file is part of EODAG project
#     https://www.github.com/CS-SI/EODAG
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import os

import yaml
import yaml.parser

from eodag.utils import utf8_everywhere


class SimpleYamlProxyConfig(object):
    """A simple configuration class acting as a proxy to an underlying dict object as returned by yaml.load"""

    def __init__(self, conf_file_path):
        with open(os.path.abspath(os.path.realpath(conf_file_path)), 'r') as fh:
            try:
                self.source = yaml.load(fh)
                utf8_everywhere(self.source)
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
