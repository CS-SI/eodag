# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import logging
try:    #PY3
    from urllib.parse import urljoin, urlparse
except ImportError:     #PY2
    from urlparse import urljoin, urlparse

import requests
from dateutil.parser import parse as dateparse

from eodag.api.product import EOProduct
from .base import Search


logger = logging.getLogger('eodag.plugins.search.resto')


class RestoSearch(Search):
    SEARCH_PATH = '/collections/{collection}/search.json'
    DEFAULT_MAX_CLOUD_COVER = 20

    def __init__(self, config):
        super(RestoSearch, self).__init__(config)
        self.query_url_tpl = urljoin(
            self.config['api_endpoint'],
            urlparse(self.config['api_endpoint']).path.rstrip('/') + self.SEARCH_PATH
        )

    def query(self, product_type, **kwargs):
        logger.info('New search for product type : *%s* on %s interface', product_type, self.name)
        collection = None
        resto_product_type = None
        pt_config = self.config['products'].setdefault(product_type, {})
        if pt_config:
            collection = pt_config['collection']
            resto_product_type = pt_config['product_type']
        if not collection:
            raise RuntimeError('Unknown product type')

        logger.debug('Collection found for product type %s: %s', product_type, collection)
        logger.debug('Corresponding Resto product_type found for product type %s: %s', product_type, resto_product_type)

        cloud_cover = kwargs.pop('maxCloudCover', self.config.get('maxCloudCover', self.DEFAULT_MAX_CLOUD_COVER))
        if not cloud_cover:
            cloud_cover = self.config.get('maxCloudCover', self.DEFAULT_MAX_CLOUD_COVER)
        if cloud_cover and not 0 <= cloud_cover <= 100:
            raise RuntimeError("Invalid cloud cover criterium: '{}'. Should be a percentage (bounded in [0-100])")
        if cloud_cover > self.config.get('maxCloudCover', self.DEFAULT_MAX_CLOUD_COVER):
            logger.info('The requested max cloud cover (%s) is too high, capping it to %s', cloud_cover,
                        self.DEFAULT_MAX_CLOUD_COVER)
            cloud_cover = self.config.get('maxCloudCover', self.DEFAULT_MAX_CLOUD_COVER)

        product_config = self.config['products'][product_type]
        params = {
            'sortOrder': 'descending',
            'sortParam': 'startDate',
            'cloudCover': '[0,{}]'.format(cloud_cover),
            'productType': resto_product_type,
        }

        start_date = kwargs.pop('startDate', None)
        config_start_date = product_config.get('min_start_date', '1970-01-01')
        if any(isinstance(config_start_date, klass) for klass in (datetime.date, datetime.datetime)):
            config_start_date = config_start_date.isoformat()
        if start_date:
            if dateparse(start_date) > dateparse(config_start_date):
                params['startDate'] = start_date
            else:
                logger.info('The requested start date (%s) is too old, capping it to %s', start_date, config_start_date)
                params['startDate'] = config_start_date

        end_date = kwargs.pop('endDate', None)
        if end_date:
            params['completionDate'] = end_date

        footprint = kwargs.pop('footprint')
        if footprint:
            if len(footprint.keys()) == 2:  # a point
                # footprint will be a dict with {'lat': ..., 'lon': ...} => simply update the param dict
                params.update(footprint)
            elif len(footprint.keys()) == 4:  # a rectangle (or bbox)
                params['box'] = '{lonmin},{latmin},{lonmax},{latmax}'.format(**footprint)

        params.update({key: value for key, value in kwargs.items() if value is not None})
        url = self.query_url_tpl.format(collection=collection)
        logger.debug('Making request to %s with params : %s', url, params)
        response = requests.get(url, params=params)
        response.raise_for_status()
        return self.normalize_results(response.json())

    @staticmethod
    def normalize_results(results):
        normalized = []
        if results['features']:
            logger.info('Found %s products', len(results['features']))
            logger.debug('Adapting plugin results to eodag product representation')
            for result in results['features']:
                product = EOProduct(result)
                product.id = result['id']
                if result['properties']['organisationName'] in ('ESA',):
                    product.location_url_tpl = '{base}' + '/{prodId}.zip'.format(
                        prodId=result['properties']['productIdentifier'].replace('/eodata/', '')
                    )
                    product.local_filename = result['properties']['title'] + '.zip'
                else:
                    if result['properties']['services']['download']['url']:
                        product.location_url_tpl = result['properties']['services']['download']['url']
                    else:
                        product.location_url_tpl = '{base}' + '/collections/{collection}/{feature_id}/download'.format(
                            collection=result['properties']['collection'],
                            feature_id=result['id'],
                        )
                    product.local_filename = result['id'] + '.zip'
                normalized.append(product)
            logger.debug('Normalized products : %s', normalized)
        else:
            logger.info('Nothing found !')
        return normalized
