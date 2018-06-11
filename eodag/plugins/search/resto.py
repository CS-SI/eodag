# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

import logging
import re

from requests import HTTPError

from eodag.api.product.representations import properties_from_json


try:  # PY3
    from urllib.parse import urljoin, urlparse
except ImportError:  # PY2
    from urlparse import urljoin, urlparse

import requests

from eodag.api.product import EOProduct
from .base import Search


logger = logging.getLogger('eodag.plugins.search.resto')


class RestoSearch(Search):
    SEARCH_PATH = '/collections/{collection}/search.json'

    def __init__(self, config):
        super(RestoSearch, self).__init__(config)
        self.query_url_tpl = urljoin(
            self.config['api_endpoint'],
            urlparse(self.config['api_endpoint']).path.rstrip('/') + self.SEARCH_PATH
        )
        # What scheme is used to locate the products that will be discovered during search
        self.product_location_scheme = self.config.get('product_location_scheme', 'https')

    def query(self, product_type, auth=None, **kwargs):
        logger.info('New search for product type : *%s* on %s interface', product_type, self.name)
        results = []
        add_to_results = results.extend
        params = {
            'sortOrder': 'descending',
            'sortParam': 'startDate',
            'startDate': kwargs.pop('startDate', None),
        }
        cloud_cover = kwargs.pop('maxCloudCover', None)
        if cloud_cover is not None:
            if not 0 <= cloud_cover <= 100:
                raise RuntimeError("Invalid cloud cover criterium: '{}'. Should be a percentage (bounded in [0-100])")
            params['cloudCover'] = '[0,{}]'.format(cloud_cover)
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

        collections, resto_product_type = self.map_product_type(product_type, params['startDate'])
        # len(collections) == 2 If and Only if the product type is S2-L1C, provider is PEPS and there is no search
        # constraint on date. Otherwise, it's equal to 1
        for collection in collections:
            logger.debug('Collection found for product type %s: %s', product_type, collection)
            logger.debug('Corresponding Resto product_type found for product type %s: %s',
                         product_type, resto_product_type)
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

    def map_product_type(self, product_type, date):
        """Maps the eodag's specific product type code to Resto specific product type (which is a collection id and a
        product type id)

        :param product_type: The eodag specific product type code name
        :type product_type: str or unicode
        :param date: The date search constraint (used only for peps provider)
        :type date: str or unicode
        :return: The corresponding collection and product type ids on this instance of Resto
        :rtype: tuple(tuple, str)
        """
        mapping = self.config['products'][product_type]
        # See https://earth.esa.int/web/sentinel/missions/sentinel-2/news/-/asset_publisher/Ac0d/content/change-of
        # -format-for-new-sentinel-2-level-1c-products-starting-on-6-december
        if product_type == 'S2_MSI_L1C':
            if self.instance_name == 'peps':
                # If there is no criteria on date, we want to query all the collections known for providing L1C products
                if date is None:
                    collection = ('S2', 'S2ST')
                else:
                    match = re.match(r'(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})', date).groupdict()
                    year, month, day = int(match['year']), int(match['month']), int(match['day'])
                    if year == 2016 and month <= 12 and day <= 5:
                        collection = ('S2',)
                    else:
                        collection = ('S2ST',)
            else:
                collection = (mapping['collection'],)
        else:
            collection = (mapping['collection'],)
        return collection, mapping['product_type']

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
                else:
                    if result['properties']['organisationName'] in ('ESA',):
                        # TODO: See the above todo about that productIdentifier thing
                        download_url = '{base}' + '/{prodId}.zip'.format(
                            prodId=result['properties']['productIdentifier'].replace('/eodata/', '')
                        )
                    else:
                        if result['properties'].get('services', {}).get('download', {}).get('url'):
                            download_url = result['properties']['services']['download']['url']
                        else:
                            download_url = '{base}' + '/collections/{collection}/{feature_id}/download'.format(
                                collection=result['properties']['collection'],
                                feature_id=result['id'],
                            )
                product = EOProduct(
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
