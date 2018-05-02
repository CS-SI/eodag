# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os

import shapely.geometry
from requests import HTTPError


try:  # PY3
    from urllib.parse import urljoin, urlparse
except ImportError:  # PY2
    from urlparse import urljoin, urlparse

import requests

from eodag.api.product import EOProduct, EOPRODUCT_PROPERTIES
from .base import Search


logger = logging.getLogger(b'eodag.plugins.search.resto')


class RestoSearch(Search):
    SEARCH_PATH = '/collections/{collection}/search.json'
    DEFAULT_MAX_CLOUD_COVER = 20

    def __init__(self, config):
        super(RestoSearch, self).__init__(config)
        self.query_url_tpl = urljoin(
            self.config['api_endpoint'],
            urlparse(self.config['api_endpoint']).path.rstrip('/') + self.SEARCH_PATH
        )
        # What scheme is used to locate the products that will be discovered during search
        self.product_location_scheme = self.config.get('product_location_scheme', 'https')

    def query(self, product_type, **kwargs):
        logger.info('New search for product type : *%s* on %s interface', product_type, self.name)
        results = []
        add_to_results = results.extend
        configured_max_cloud_cover = self.config.get('maxCloudCover', self.DEFAULT_MAX_CLOUD_COVER)
        cloud_cover = kwargs.pop('maxCloudCover', configured_max_cloud_cover) or configured_max_cloud_cover
        if not 0 <= cloud_cover <= 100:
            raise RuntimeError("Invalid cloud cover criterium: '{}'. Should be a percentage (bounded in [0-100])")
        elif cloud_cover > configured_max_cloud_cover:
            logger.info('The requested max cloud cover (%s) is too high, capping it to %s', cloud_cover,
                        self.DEFAULT_MAX_CLOUD_COVER)
            cloud_cover = self.config.get('maxCloudCover', self.DEFAULT_MAX_CLOUD_COVER)
        params = {
            'sortOrder': 'descending',
            'sortParam': 'startDate',
            'startDate': kwargs.pop('startDate', None),
            'cloudCover': '[0,{}]'.format(cloud_cover),
        }
        end_date = kwargs.pop('endDate', None)
        if end_date:
            params['completionDate'] = end_date
        footprint = kwargs.pop('footprint', None)
        if footprint:
            if len(footprint.keys()) == 2:  # a point
                # footprint will be a dict with {'lat': ..., 'lon': ...} => simply update the param dict
                params.update(footprint)
            elif len(footprint.keys()) == 4:  # a rectangle (or bbox)
                params['box'] = '{lonmin},{latmin},{lonmax},{latmax}'.format(**footprint)
        params.update({key: value for key, value in kwargs.items() if value is not None})

        collection, resto_product_type = self.map_product_type(product_type)
        logger.debug('Collection found for product type %s: %s', product_type, collection)
        logger.debug('Corresponding Resto product_type found for product type %s: %s', product_type, resto_product_type)
        params['productType'] = resto_product_type

        url = self.query_url_tpl.format(collection=collection)
        logger.debug('Making request to %s with params : %s', url, params)
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
        except HTTPError as e:
            logger.debug('Skipping error while searching for %s RestoSearch instance product type %s: %s',
                         self.instance_name, resto_product_type, e)
        else:
            add_to_results(self.normalize_results(response.json(), footprint))
        return results

    def map_product_type(self, product_type):
        """Maps the eodag's specific product type code to Resto specific product type (which is a collection id and a
        product type id)

        :param product_type: The eodag specific product type code name
        :return: The corresponding collection and product type ids on this instance of Resto
        :rtype: tuple(str, str)
        """
        mapping = self.config['products'][product_type]
        return mapping['collection'], mapping['product_type']

    def normalize_results(self, results, search_bbox):
        normalized = []
        if results['features']:
            logger.info('Found %s products', len(results['features']))
            logger.debug('Adapting plugin results to eodag product representation')
            for result in results['features']:
                if self.product_location_scheme == 'file':
                    # TODO: This behaviour maybe very specific to eocloud provider (having the path to the local
                    # TODO: resource being stored on result['properties']['productIdentifier']). It may therefore need
                    # TODO: to be better handled in the future
                    download_url = '{}://{}'.format(
                        self.product_location_scheme,
                        result['properties']['productIdentifier'])
                    local_filename = os.path.basename(download_url)
                else:
                    if result['properties']['organisationName'] in ('ESA',):
                        # TODO: See the above todo about that productIdentifier thing
                        download_url = '{base}' + '/{prodId}.zip'.format(
                            prodId=result['properties']['productIdentifier'].replace('/eodata/', '')
                        )
                        local_filename = result['properties']['title'] + '.zip'
                    else:
                        if result['properties']['services']['download']['url']:
                            download_url = result['properties']['services']['download']['url']
                        else:
                            download_url = '{base}' + '/collections/{collection}/{feature_id}/download'.format(
                                collection=result['properties']['collection'],
                                feature_id=result['id'],
                            )
                        local_filename = result['id'] + '.zip'
                product = EOProduct(
                    self.instance_name,
                    download_url,
                    local_filename,
                    shapely.geometry.shape(result['geometry']),
                    search_bbox,
                    result['properties']['productType'],
                    result['properties']['platform'],
                    result['properties']['instrument'],
                    provider_id=result['id'],
                    # EOPRODUCT_PROPERTIES are based on resto representation of Earth observation products properties
                    **{prop_key: (result['properties'][prop_key] if prop_key != 'endDate' else result['properties'][
                        'completionDate']) for prop_key in EOPRODUCT_PROPERTIES}
                )
                normalized.append(product)
            logger.debug('Normalized products : %s', normalized)
        else:
            logger.info('Nothing found !')
        return normalized
