# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from urllib.parse import urljoin, urlparse

import requests
from dateutil.parser import parse as dateparse

from satdl.api.product import EOProduct
from .base import Search


class RestoSearch(Search):
    SEARCH_PATH = '/collections/{collection}/search.json'
    DEFAULT_MAX_CLOUD_COVER = 20

    def __init__(self, config=None):
        super(RestoSearch, self).__init__(config=config)
        self.query_url_tpl = urljoin(
            self.config['api_endpoint'],
            urlparse(self.config['api_endpoint']).path.rstrip('/') + self.SEARCH_PATH
        )

    def query(self, product_type, **kwargs):
        collection = None
        for key, value in self.config['products'].items():
            if product_type in value['product_types']:
                collection = key
        if not collection:
            raise RuntimeError('Unknown product type')

        cloud_cover = kwargs.pop('cloudCover', self.config.get('maxCloudCover', self.DEFAULT_MAX_CLOUD_COVER))
        if cloud_cover and not 0 <= cloud_cover <= 100:
            raise RuntimeError("Invalid cloud cover criterium: '{}'. Should be a percentage (bounded in [0-100])")
        if cloud_cover > self.config.get('maxCloudCover', self.DEFAULT_MAX_CLOUD_COVER):
            cloud_cover = self.config.get('maxCloudCover', self.DEFAULT_MAX_CLOUD_COVER)

        collection_config = self.config['products'][collection]
        params = {
            'sortOrder': 'descending',
            'sortParam': 'startDate',
            'startDate': collection_config['min_start_date'],
            'cloudCover': '[0,{}]'.format(cloud_cover),
            'productType': product_type,
        }

        start_date = kwargs.pop('startDate', None)
        if start_date:
            parsed_query_start_date = dateparse(start_date)
            parsed_collection_min_start_date = dateparse(collection_config['min_start_date'])
            if parsed_query_start_date > parsed_collection_min_start_date:
                params['startDate'] = start_date

        end_date = kwargs.pop('endDate', None)
        if end_date:
            params['completionDate'] = end_date

        bbox = kwargs.pop('bbox', None)
        if bbox:
            params['box'] = str(bbox.reproject())

        params.update(kwargs)
        response = requests.get(
            self.query_url_tpl.format(collection=collection),
            params=params
        )
        response.raise_for_status()
        return self.normalize_results(response.json())

    @staticmethod
    def normalize_results(results):
        normalized = []
        for result in results['features']:
            product = EOProduct(result)
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
        return normalized
