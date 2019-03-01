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
from __future__ import absolute_import, print_function, unicode_literals

import jsonpath_rw as jsonpath

from eodag.api.product.metadata_mapping import DEFAULT_METADATA_MAPPING, NOT_MAPPED, get_metadata_path
from eodag.plugins.base import PluginTopic


class Search(PluginTopic):

    def __init__(self, provider, config):
        super(Search, self).__init__(provider, config)
        # Prepare the metadata mapping
        # Do a shallow copy, the structure is flat enough for this to be sufficient
        metas = DEFAULT_METADATA_MAPPING.copy()
        # Update the defaults with the mapping value. This will add any new key
        # added by the provider mapping that is not in the default metadata
        metas.update(self.config.metadata_mapping)
        for metadata in metas:
            if metadata not in self.config.metadata_mapping:
                self.config.metadata_mapping[metadata] = (None, NOT_MAPPED)
            else:
                conversion, path = get_metadata_path(self.config.metadata_mapping[metadata])
                try:
                    # If the metadata is queryable (i.e a list of 2 elements), replace the value of the last item
                    if len(self.config.metadata_mapping[metadata]) == 2:
                        self.config.metadata_mapping[metadata][1] = (conversion, jsonpath.parse(path))
                    else:
                        self.config.metadata_mapping[metadata] = (conversion, jsonpath.parse(path))
                except Exception:  # jsonpath_rw does not provide a proper exception
                    # Assume the mapping is to be passed as is.
                    # Ignore any transformation specified. If a value is to be passed as is, we don't want to transform
                    # it further
                    _, text = get_metadata_path(self.config.metadata_mapping[metadata])
                    if len(self.config.metadata_mapping[metadata]) == 2:
                        self.config.metadata_mapping[metadata][1] = (None, text)
                    else:
                        self.config.metadata_mapping[metadata] = (None, text)

    def query(self, *args, **kwargs):
        """Implementation of how the products must be searched goes here.

        This method must return a list of EOProduct instances (see eodag.api.product module) which will
        be processed by a Download plugin.
        """
        raise NotImplementedError('A Search plugin must implement a method named query')
