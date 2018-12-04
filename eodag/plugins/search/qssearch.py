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
from lxml import etree

from eodag.api.product import EOProduct
from eodag.api.product.representations import properties_from_json, properties_from_xml
from eodag.plugins.search.base import Search
from eodag.utils import format_search_param
from eodag.utils.metadata_mapping import get_search_param


logger = logging.getLogger('eodag.plugins.search.qssearch')


class QueryStringSearch(Search):
    """A plugin that helps implementing any kind of search protocol that relies on query strings (e.g: opensearch).

    The available configuration parameters for this kind of plugin are:
        - result_type: (optional) One of "json" or "xml", depending on the representation of the provider's search
                       results. The default is "json"
        - results_entry: (mandatory) The name of the key in the provider search result that gives access to the
                         result entries
        - api_endpoint: (mandatory) The endpoint of the provider's search interface
        - literal_search_param: (optional) A mapping of (search_param => search_value) pairs giving search parameters
                                to be passed as is in the search url
        - free_text_search_param: (optional) The name of a search parameter that will have the value obtained from the
                                  application of the operations configured in the free_text_search_operations below
        - free_text_search_operations: (optional) A mapping of (operation => list of operands), that defines all the
                                       free text search operations to be applied to form the value of the
                                       free_text_search_param above. The operands are joined together using the
                                       operator.

    The search plugins of this kind can detect when a metadata mapping is "query-able", and get the semantics of how
    to format the query string parameter that enables to make a query on the corresponding metadata. To make a
    metadata query-able, just configure it in the metadata mapping to be a list of 2 items, the first one being the
    specification of the query string search formatting. The later is a string following the specification of Python
    string formatting, with a special behaviour added to it. For example, an entry in the metadata mapping of this
    kind::
        completionTimeFromAscendingNode:
            - 'f=acquisition.endViewingDate:lte:{completionTimeFromAscendingNode$timestamp}'
            - '$.properties.acquisition.endViewingDate'
    means that the search url will have a query string parameter named "f" with a value of
    "acquisition.endViewingDate:lte:1543922280.0" if the search was done with a value of
    `completionTimeFromAscendingNode` being `2018-12-04T12:18:00`. What happened is that
    `{completionTimeFromAscendingNode$timestamp}` was replaced with the timestamp of the value of
    `completionTimeFromAscendingNode`. This example shows all there is to know about the semantics of the query string
    formatting introduced by this plugin: any eodag search parameter can be referenced in the query string
    with an additional optional conversion function that is separated from it by a `$` (see
    :func:`~eodag.utils.format_search_param` for further details on the available converters). Note that for the values
    in the `free_text_search_operations` configuration parameter follow the same rule.
    """
    COMPLEX_QS_REGEX = re.compile(r'^(.+=)?([^=]*)({.+})+([^=&]*)$')
    extract_properties = {
        'xml': properties_from_xml,
        'json': properties_from_json
    }

    def __init__(self, provider, config):
        super(QueryStringSearch, self).__init__(provider, config)
        self.config.__dict__.setdefault('result_type', 'json')

    def query(self, product_type, *args, **kwargs):
        provider_product_type = self.map_product_type(product_type, *args, **kwargs)
        qs = self.build_query_string(
            product_type,
            productType=provider_product_type,
            *args,
            **{k: v for k, v in kwargs.items() if k != 'auth'}
        )
        search_url = '{}?{}'.format(self.config.api_endpoint.rstrip('/'), qs)
        provider_results = self.do_request(search_url, product_type, provider_product_type, *args, **kwargs)
        eo_products = self.normalize_results(provider_results, product_type, provider_product_type, *args, **kwargs)
        return eo_products

    def build_query_string(self, *args, **kwargs):
        """Build The query string using the search parameters"""
        logger.debug('Building the query string that will be used for search')
        queryables = self.get_queryables()
        qs_participants = []
        # Get all the search parameters that are recognised as queryables by the provider (they appear in the
        # queryables dictionary)
        for search_param, query in kwargs.items():
            try:
                queryable = queryables[search_param]
                self.add_to_qs_participants(qs_participants, query, queryable, args, kwargs)
            except KeyError:
                continue

        # Now get all the literal search params (i.e params to be passed "as is" in the search request)
        # ignore additional_params if it isn't a dictionary
        literal_search_params = getattr(self.config, 'literal_search_params', {})
        if not isinstance(literal_search_params, dict):
            literal_search_params = {}

        # Now add formatted free text search parameters (this is for cases where a complex query through a free text
        # search parameter is available for the provider and needed for the consumer)
        literal_search_params.update(self.format_free_text_search(**kwargs))
        qs_participants.extend('{}={}'.format(param, value) for param, value in literal_search_params.items())

        # Build the final query string
        return '&'.join(qs_participants)

    def add_to_qs_participants(self, qs_participants, query, queryable, args, kwargs):
        if query is not None:
            if self.COMPLEX_QS_REGEX.match(queryable):
                qs_participants.append(format_search_param(queryable, *args, **kwargs))
            else:
                qs_participants.append('{}={}'.format(queryable, query))

    def format_free_text_search(self, **kwargs):
        """Build the free text search parameter using the search parameters"""
        free_text_search_param = getattr(self.config, 'free_text_search_param', '')
        if not free_text_search_param:
            return {}
        formatted_query = []
        for operator, operands in self.config.free_text_search_operations.items():
            # The Operator string is the operator surrounded with spaces
            operator_string = ' {} '.format(operator)
            # Build the operation string by joining the formatted operands together using the operation string
            operation_string = operator_string.join(
                format_search_param(operand, **kwargs)
                for operand in operands
            )
            # Finally wrap the operation string in parentheses and add it to the list of queries
            formatted_query.append('({})'.format(operation_string))
        # Return the formatted queries joined together using a default 'AND' operator and wrap the overall operation
        # in parentheses
        return {
            free_text_search_param: '({})'.format(' AND '.join(formatted_query))
        }

    def get_queryables(self):
        """Retrieve the metadata mappings that are query-able"""
        logger.debug('Retrieving queryable metadata from metadata_mapping')
        return {
            key: get_search_param(val)
            for key, val in self.config.metadata_mapping.items()
            if len(val) == 2
        }

    def map_product_type(self, product_type, *args, **kwargs):
        """Map the eodag product type to the provider product type"""
        logger.debug('Mapping eodag product type to provider product type')
        return self.config.products[product_type]['product_type']

    def normalize_results(self, results, *args, **kwargs):
        """Build EOProducts from provider results"""
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
        """Perform the actual search request"""
        try:
            logger.info('Sending search request: %s', search_url)
            response = requests.get(search_url)
            response.raise_for_status()
        except requests.HTTPError:
            logger.exception('Skipping error while searching for %s %s instance:', self.provider,
                             self.__class__.__name__)
            raise StopIteration
        else:
            if self.config.result_type == 'xml':
                root_node = etree.fromstring(response.content)
                for entry in root_node.xpath(
                    self.config.results_entry,
                    namespaces={k or 'ns': v for k, v in root_node.nsmap.items()}
                ):
                    yield etree.tostring(entry)
            else:
                for entry in response.json()[self.config.results_entry]:
                    yield entry


class RestoSearch(QueryStringSearch):
    """A specialisation of a QueryStringSearch that adds the notion of a collection to the api_endpoint parameter"""

    def __init__(self, provider, config):
        super(RestoSearch, self).__init__(provider, config)
        self.config.results_entry = 'features'

    def do_request(self, search_url, *args, **kwargs):
        collections = self.get_collections(*args, **kwargs)
        results = []
        # len(collections) == 2 If and Only if the product type is S2-L1C, provider is PEPS and there is no search
        # constraint on date. Otherwise, it's equal to 1
        for collection in collections:
            logger.debug('Collection found for product type %s: %s', args[0], collection)
            logger.debug('Corresponding Resto product_type found for product type %s: %s', args[0], args[1])
            for result in super(RestoSearch, self).do_request(
                search_url.format(collection=collection),
                *args, **kwargs
            ):
                results.append(result)
        return results

    def get_collections(self, *args, **kwargs):
        """Get the collection to which the product belongs"""
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


class AwsSearch(RestoSearch):
    """A specialisation of RestoSearch that modifies the way the EOProducts are built from the search results"""

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


class ODataV4Search(QueryStringSearch):
    """A specialisation of a QueryStringSearch that does a two step search to retrieve all products metadata"""

    def build_query_string(self, *args, **kwargs):
        logger.debug('Building the query string that will be used for search')
        queryables = self.get_queryables()
        qs_participants = []
        for search_param, query in kwargs.items():
            try:
                queryable = queryables[search_param]
                self.add_to_qs_participants(qs_participants, query, queryable, args, kwargs)
            except KeyError:
                continue
        return '$search="{}"&$format={}'.format(' AND '.join(qs_participants), self.config.result_type)

    def do_request(self, search_url, *args, **kwargs):
        """Do a two step search, as the metadata are not given into the search result"""
        # TODO: This plugin is still very specific to the ONDA provider. Be careful to generalize
        #       it if needed when the chance to do so arrives
        final_result = []
        # Query the products entity set for basic metadata about the product
        for entity in super(ODataV4Search, self).do_request(search_url, *args, **kwargs):
            if entity['downloadable']:
                entity_metadata = {
                    'quicklook': entity['quicklook'],
                    'id': entity['id'],
                    'footprint': entity['footprint'],
                }
                metadata_url = self.get_metadata_search_url(entity)
                try:
                    response = requests.get(metadata_url)
                    response.raise_for_status()
                except requests.HTTPError:
                    logger.exception('Skipping error while searching for %s %s instance:', self.provider,
                                     self.__class__.__name__)
                else:
                    entity_metadata.update({
                        item['id']: item['value']
                        for item in response.json()['value']
                    })
                    final_result.append(entity_metadata)
        return final_result

    def get_metadata_search_url(self, entity):
        """Build the metadata link for the given entity"""
        return '{}({})/Metadata'.format(self.config.api_endpoint.rstrip('/'), entity['id'])
