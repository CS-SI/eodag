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

import logging

from eodag.api.product import EOProduct
from eodag.api.product.representations import properties_from_json
from eodag.plugins.search.resto import RestoSearch


logger = logging.getLogger('eodag.plugins.search.aws')


class AwsSearch(RestoSearch):

    def normalize_results(self, product_type, results, search_bbox):
        normalized = []
        if results['features']:
            logger.debug('Adapting plugin results to eodag product representation')
            for result in results['features']:
                ref = result['properties']['title'].split('_')[5]
                year = result['properties']['completionDate'][0:4]
                month = str(int(result['properties']['completionDate'][5:7]))
                day = str(int(result['properties']['completionDate'][8:10]))

                download_url = ('{proto}://tiles/{ref[1]}{ref[2]}/{ref[3]}/{ref[4]}{ref[5]}/{year}/'
                                '{month}/{day}/0/').format(proto=self.config.product_location_scheme, **locals())

                product = EOProduct(
                    product_type,
                    self.provider,
                    download_url,
                    properties_from_json(result, self.config.metadata_mapping),
                    searched_bbox=search_bbox,
                )
                normalized.append(product)
            logger.debug('Normalized products : %s', normalized)
        return normalized
