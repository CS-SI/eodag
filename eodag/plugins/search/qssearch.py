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
from __future__ import unicode_literals

import logging
import re

import requests

from eodag.api.product import EOProduct
from eodag.api.product.representations import properties_from_json, properties_from_xml
from eodag.plugins.search.base import Search
from eodag.utils import format_search_param
from eodag.utils.metadata_mapping import get_search_param


logger = logging.getLogger('eodag.plugins.search.qssearch')


class QueryStringSearch(Search):
    COMPLEX_QS_REGEX = re.compile(r'^(.+=)?([^=]*)({.+})+([^=]*)$')
    extract_properties = {
        'xml': properties_from_xml,
        'json': properties_from_json
    }

    def __init__(self, provider, config):
        super(QueryStringSearch, self).__init__(provider, config)
        self.config.result_type = 'json'

    def query(self, product_type, *args, **kwargs):
        provider_product_type = self.map_product_type(product_type, *args, **kwargs)
        qs = self.build_query_string(
            product_type,
            provider_product_type,
            *args,
            **{k: v for k, v in kwargs.items() if k != 'auth'}
        )
        search_url = '{}?{}'.format(self.config.api_endpoint.rstrip('/'), qs)
        provider_results = self.do_request(search_url, product_type, provider_product_type, *args, **kwargs)
        eo_products = self.normalize_results(provider_results, product_type, provider_product_type, *args, **kwargs)
        return eo_products

    def build_query_string(self, *args, **kwargs):
        logger.debug('Building the query string that will be used for search')
        queryables = self.get_queryables()
        qs_participants = []
        # Get all the search parameters that are recognised as queryables by the provider (they appear in the
        # queryables dictionary)
        for search_param, query in kwargs.items():
            try:
                if query is not None:
                    queryable = queryables[search_param]
                    if self.COMPLEX_QS_REGEX.match(queryable):
                        qs_participants.append(format_search_param(queryable, *args, **kwargs))
                    else:
                        qs_participants.append('{}={}'.format(queryable, query))
            except KeyError:
                continue
        return '&'.join(qs_participants)

    def get_queryables(self):
        logger.debug('Retrieving queryable metadata from metadata_mapping')
        return {
            key: get_search_param(val)
            for key, val in self.config.metadata_mapping.items()
            if len(val) == 2
        }

    def map_product_type(self, product_type, *args, **kwargs):
        logger.debug('Mapping eodag product type to provider product type')
        return self.config.products[product_type]['product_type']

    def normalize_results(self, results, *args, **kwargs):
        logger.debug('Adapting plugin results to eodag product representation')
        return [
            EOProduct(
                self.provider,
                QueryStringSearch.extract_properties[self.config.result_type](result, self.config.metadata_mapping),
                *args,
                **kwargs
            )
            for result in results
        ]

    def do_request(self, search_url, *args, **kwargs):
        try:
            logger.info('Sending search request: %s', search_url)
            response = requests.get(search_url)
            response.raise_for_status()
        except requests.HTTPError:
            logger.exception('Skipping error while searching for %s %s instance:', self.provider,
                             self.__class__.__name__)
        else:
            return response.json()
        return []


class RestoSearch(QueryStringSearch):

    def do_request(self, search_url, *args, **kwargs):
        collections = self.get_collections(*args, **kwargs)
        results = []
        # len(collections) == 2 If and Only if the product type is S2-L1C, provider is PEPS and there is no search
        # constraint on date. Otherwise, it's equal to 1
        for collection in collections:
            logger.debug('Collection found for product type %s: %s', args[0], collection)
            logger.debug('Corresponding Resto product_type found for product type %s: %s', args[0], args[1])
            json_response = super(RestoSearch, self).do_request(
                search_url.format(collection=collection),
                *args, **kwargs
            )
            if isinstance(json_response, dict):
                results.extend(json_response['features'])
        return results

    def get_collections(self, *args, **kwargs):
        # See https://earth.esa.int/web/sentinel/missions/sentinel-2/news/-/asset_publisher/Ac0d/content/change-of
        # -format-for-new-sentinel-2-level-1c-products-starting-on-6-december
        if self.provider == 'peps':
            product_type = kwargs.get('productType') or args[0]
            if product_type == 'S2_MSI_L1C':
                date = kwargs.get('startTimeFromAscendingNode')
                # If there is no criteria on date, we want to query all the collections known for providing L1C
                # products
                if date is None:
                    collections = ('S2', 'S2ST')
                else:
                    match = re.match(r'(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})', date).groupdict()
                    year, month, day = int(match['year']), int(match['month']), int(match['day'])
                    if year == 2016 and month <= 12 and day <= 5:
                        collections = ('S2',)
                    else:
                        collections = ('S2ST',)
            else:
                collections = (self.config.products[product_type]['collection'],)
        else:
            collection = getattr(self.config, 'collection', None)
            if collection is None:
                product_type = kwargs.get('productType') or args[0]
                collection = self.config.products[product_type]['collection']
            collections = (collection,)
        return collections


class ArlasSearch(RestoSearch):

    def build_query_string(self, *args, **kwargs):
        qs_participants = ['{}'.format(super(ArlasSearch, self).build_query_string(*args, **kwargs)).lstrip('&')]
        queryables = self.get_queryables()
        start_date = kwargs.pop('startTimeFromAscendingNode', None)
        end_date = kwargs.pop('completionTimeFromAscendingNode', None)
        if start_date:
            if end_date:
                logger.debug('Adding filter for sensing date range: %s - %s', start_date, end_date)
                qs_participants.append(format_search_param(
                    'f=%(startTimeFromAscendingNode)s:range:[{min$timestamp}<{max$timestamp}]' % queryables,
                    min=start_date, max=end_date
                ))
            else:
                logger.debug('Adding filter for minimum sensing date: %s', start_date)
                qs_participants.append(format_search_param(
                    'f=%(startTimeFromAscendingNode)s:gte:{min$timestamp}' % queryables,
                    min=start_date
                ))
        elif end_date:
            logger.debug('Adding filter for maximum sensing date: %s', end_date)
            qs_participants.append(format_search_param(
                'f=%(startTimeFromAscendingNode)s:lte:{max$timestamp}' % queryables,
                max=end_date
            ))
        return '&'.join(qs_participants)

    def normalize_results(self, results, *args, **kwargs):
        logger.debug('Adapting plugin results to eodag product representation')
        normalized = []
        for result in results:
            properties = QueryStringSearch.extract_properties[self.config.result_type](
                result, self.config.metadata_mapping
            )
            if properties['quicklook']:
                properties['quicklook'] = '{}/{}'.format(self.config.quicklook_endpoint, properties['id'])
            normalized.append(
                EOProduct(
                    self.provider,
                    QueryStringSearch.extract_properties[self.config.result_type](result,
                                                                                  self.config.metadata_mapping),
                    *args,
                    **kwargs
                )
            )
        return normalized


class AwsSearch(RestoSearch):

    def normalize_results(self, results, *args, **kwargs):
        normalized = []
        logger.debug('Adapting plugin results to eodag product representation')
        for result in results:
            ref = result['properties']['title'].split('_')[5]
            year = result['properties']['completionDate'][0:4]
            month = str(int(result['properties']['completionDate'][5:7]))
            day = str(int(result['properties']['completionDate'][8:10]))

            properties = QueryStringSearch.extract_properties[self.config.result_type](
                result, self.config.metadata_mapping
            )

            properties['downloadLink'] = (
                's3://tiles/{ref[1]}{ref[2]}/{ref[3]}/{ref[4]}{ref[5]}/{year}/'
                '{month}/{day}/0/'
            ).format(**locals())
            normalized.append(EOProduct(
                self.provider,
                properties,
                *args,
                **kwargs
            ))
        return normalized
