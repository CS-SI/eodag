# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

import logging
import re

from requests import HTTPError

from eodag.api.product.representations import properties_from_json
from eodag.utils.metadata_mapping import get_search_param


try:  # PY3
    from urllib.parse import urljoin, urlparse
except ImportError:  # PY2
    from urlparse import urljoin, urlparse

import requests
import shapely

from eodag.api.product import EOProduct
from .base import Search


logger = logging.getLogger('eodag.plugins.search.resto')


class AsfSearch(Search):
    SEARCH_PATH = '/collections/{collection}/search.json'

    def __init__(self, config):
        super(AsfSearch, self).__init__(config)


    def query(self, product_type, auth=None, **kwargs):
        """Query method on Alaska Satellite Facility

        :param product_type: The eodag specific product type code name
        :type product_type: str or unicode
        :param auth: Authentication mode for the download plugin
        :type auth: authentication class
        :return: The search result
        :rtype: list
        """
        logger.info('New search for product type : *%s* on %s interface', product_type, self.name)
        results = []
        add_to_results = results.extend

        params = {
            'start': kwargs.pop('startTimeFromAscendingNode', None),
            'output': 'json',
        }
        cloud_cover = kwargs.pop('cloudCover', None)
        if cloud_cover is not None:
            if not 0 <= cloud_cover <= 100:
                raise RuntimeError("Invalid cloud cover criterium: '{}'. Should be a percentage (bounded in [0-100])")
            params['cloudcover'] = '[0,{}]'.format(cloud_cover)
        end_date = kwargs.pop('completionTimeFromAscendingNode', None)
        if end_date:
            params['end'] = end_date
        footprint = kwargs.pop('geometry', None)
        if footprint:
            params['bbox'] = '{lonmin},{latmin},{lonmax},{latmax}'.format(**footprint)

        product_type_query = self.config['products'][product_type]['product_type']
        if 'level' in self.config['products'][product_type].keys():
            params['processingLevel'] = self.config['products'][product_type]['level']
        # len(collections) == 2 If and Only if the product type is S2-L1C, provider is PEPS and there is no search
        # constraint on date. Otherwise, it's equal to 1

        params['platform'] = product_type_query

        url = self.config['api_endpoint']
        logger.debug('Making request to %s with params : %s', url, params)
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
        except HTTPError as e:
            logger.debug('Skipping error while searching for %s RestoSearch instance product type %s: %s',
                         self.instance_name, product_type, e)
        else:
            add_to_results(self.normalize_results(product_type, response.json(), footprint))
        return results


    def normalize_results(self, product_type, results, search_bbox):
        normalized = []
        if len(results[0]) != 0:
            logger.info('Found %s products', len(results[0]))
            logger.debug('Adapting plugin results to eodag product representation')
            for result in results[0]:
                download_url = result['downloadUrl']
                product = EOProduct(
                    product_type,
                    self.instance_name,
                    download_url,
                    properties_from_json(result, self.config['metadata_mapping']),
                    searched_bbox=search_bbox
                )
                normalized.append(product)
            logger.debug('Normalized products : %s', normalized)
        else:
            logger.info('Nothing found !')
        return normalized
