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
import re

import requests
from requests import HTTPError

from eodag.api.product import EOProduct
from eodag.api.product.representations import properties_from_json
from eodag.utils import urljoin, urlparse
from eodag.utils.metadata_mapping import get_search_param
from .base import Search


logger = logging.getLogger('eodag.plugins.search.resto')


class RestoSearch(Search):
    SEARCH_PATH = '/collections/{collection}/search.json'

    def __init__(self, provider, config):
        super(RestoSearch, self).__init__(provider, config)
        self.query_url_tpl = urljoin(
            self.config.api_endpoint,
            urlparse(self.config.api_endpoint).path.rstrip('/') + self.SEARCH_PATH
        )
        # What scheme is used to locate the products that will be discovered during search
        self.product_location_scheme = getattr(self.config, 'product_location_scheme', 'https')

    def query(self, product_type, auth=None, **kwargs):
        results = []
        add_to_results = results.extend
        start_date_param = get_search_param(self.config.metadata_mapping['startTimeFromAscendingNode'])
        end_date_param = get_search_param(self.config.metadata_mapping['completionTimeFromAscendingNode'])
        product_type_param = get_search_param(self.config.metadata_mapping['productType'])
        cloud_cover_param = get_search_param(self.config.metadata_mapping['cloudCover'])
        geometry_param = get_search_param(self.config.metadata_mapping['geometry'])
        params = {
            'sortOrder': 'descending',
            'sortParam': start_date_param,
            start_date_param: kwargs.pop('startTimeFromAscendingNode', None),
        }
        cloud_cover = kwargs.pop('cloudCover', None)
        if cloud_cover is not None:
            if not 0 <= cloud_cover <= 100:
                raise RuntimeError("Invalid cloud cover criterium: '{}'. Should be a percentage (bounded in [0-100])")
            params[cloud_cover_param] = '[0,{}]'.format(cloud_cover)
        end_date = kwargs.pop('completionTimeFromAscendingNode', None)
        if end_date:
            params[end_date_param] = end_date
        footprint = kwargs.pop('geometry', None)
        if footprint:
            params[geometry_param] = '{lonmin},{latmin},{lonmax},{latmax}'.format(**footprint)

        collections, resto_product_type = self.map_product_type(product_type, params[start_date_param])
        # len(collections) == 2 If and Only if the product type is S2-L1C, provider is PEPS and there is no search
        # constraint on date. Otherwise, it's equal to 1
        for collection in collections:
            logger.debug('Collection found for product type %s: %s', product_type, collection)
            logger.debug('Corresponding Resto product_type found for product type %s: %s',
                         product_type, resto_product_type)
            params[product_type_param] = resto_product_type

            url = self.query_url_tpl.format(collection=collection)
            logger.info('Making request to %s with params : %s', url, params)
            try:
                response = requests.get(url, params=params)
                response.raise_for_status()
            except HTTPError:
                import traceback as tb
                logger.debug('Skipping error while searching for %s RestoSearch instance product type %s:\n%s',
                             self.provider, resto_product_type, tb.format_exc())
            else:
                add_to_results(self.normalize_results(product_type, response.json(), footprint))
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
        mapping = self.config.products[product_type]
        # See https://earth.esa.int/web/sentinel/missions/sentinel-2/news/-/asset_publisher/Ac0d/content/change-of
        # -format-for-new-sentinel-2-level-1c-products-starting-on-6-december
        if product_type == 'S2_MSI_L1C':
            if self.provider == 'peps':
                # If there is no criteria on date, we want to query all the collections known for providing L1C
                # products
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

    def normalize_results(self, product_type, results, search_bbox):
        normalized = []
        if results['features']:
            logger.debug('Adapting plugin results to eodag product representation')
            for result in results['features']:
                if self.product_location_scheme == 'file':
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
                    product_type,
                    self.provider,
                    download_url,
                    properties_from_json(result, self.config.metadata_mapping),
                    searched_bbox=search_bbox
                )
                normalized.append(product)
            logger.debug('Normalized products : %s', normalized)
        return normalized
