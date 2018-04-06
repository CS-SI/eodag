# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

import logging

import shapely.geometry

try:  # PY3
    from urllib.parse import urljoin, urlparse
except ImportError:  # PY2
    from urlparse import urljoin, urlparse

from eodag.api.product import EOProduct, EOPRODUCT_PROPERTIES
from eodag.plugins.search.resto import RestoSearch

logger = logging.getLogger('eodag.plugins.search.resto')


class AwsSearch(RestoSearch):

    def __init__(self, config):
        super(AwsSearch, self).__init__(config)
        # self.query_url_tpl = self.config['api_endpoint']
        self.dl_base = config.get('amazon_dl_endpoint')



    def normalize_results(self, results, search_bbox):
        normalized = []
        if results['features']:
            logger.info('Found %s products', len(results['features']))
            logger.debug('Adapting plugin results to eodag product representation')
            for result in results['features']:
                local_filename = result['id']
                ref = result['properties']['title'].split('_')[5]
                year = result['properties']['completionDate'][0:4]
                month = str(int(result['properties']['completionDate'][5:7]))
                day = str(int(result['properties']['completionDate'][8:10]))

                download_url = 'tiles' + '/' + ref[1:3] + '/' + ref[3] + '/' + ref[4:6] + '/' + year + '/' + month + '/' + day + '/' + '0' + '/'

                product = EOProduct(
                    result['id'],
                    self.instance_name,
                    download_url,
                    local_filename,
                    shapely.geometry.shape(result['geometry']),
                    search_bbox,
                    # EOPRODUCT_PROPERTIES are based on resto representation of Earth observation products properties
                    **{prop_key: (result['properties'][prop_key] if prop_key != 'endDate' else result['properties'][
                        'completionDate']) for prop_key in EOPRODUCT_PROPERTIES}
                )
                normalized.append(product)
            logger.debug('Normalized products : %s', normalized)
        else:
            logger.info('Nothing found !')
        return normalized
