# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

import logging

from eodag.api.product.representations import properties_from_json


try:  # PY3
    from urllib.parse import urljoin, urlparse
except ImportError:  # PY2
    from urlparse import urljoin, urlparse

from eodag.api.product import EOProduct
from eodag.plugins.search.resto import RestoSearch


logger = logging.getLogger('eodag.plugins.search.aws')


class AwsSearch(RestoSearch):

    def __init__(self, config):
        super(AwsSearch, self).__init__(config)
        self.dl_base = config.get('amazon_dl_endpoint')

    def normalize_results(self, product_type, results, search_bbox):
        normalized = []
        if results['features']:
            logger.info('Found %s products', len(results['features']))
            logger.debug('Adapting plugin results to eodag product representation')
            for result in results['features']:
                ref = result['properties']['title'].split('_')[5]
                year = result['properties']['completionDate'][0:4]
                month = str(int(result['properties']['completionDate'][5:7]))
                day = str(int(result['properties']['completionDate'][8:10]))

                download_url = ('{proto}://tiles/{ref[1]}{ref[2]}/{ref[3]}/{ref[4]}{ref[5]}/{year}/'
                                '{month}/{day}/0/').format(proto=self.config['product_location_scheme'], **locals())

                product = EOProduct(
                    product_type,
                    self.instance_name,
                    download_url,
                    properties_from_json(result, self.config['metadata_mapping']),
                    searched_bbox=search_bbox,
                )
                normalized.append(product)
            logger.debug('Normalized products : %s', normalized)
        else:
            logger.info('Nothing found !')
        return normalized
