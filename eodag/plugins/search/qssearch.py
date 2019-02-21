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

import jsonpath_rw as jsonpath
import requests
from lxml import etree

from eodag.api.product import EOProduct
from eodag.api.product.metadata_mapping import (
    format_metadata, get_search_param, properties_from_json,
    properties_from_xml,
)
from eodag.plugins.search.base import Search
from eodag.utils import urlencode
from eodag.utils.exceptions import RequestError


logger = logging.getLogger('eodag.plugins.search.qssearch')


class QueryStringSearch(Search):
    """A plugin that helps implementing any kind of search protocol that relies on query strings (e.g: opensearch).

    The available configuration parameters for this kind of plugin are:

        - **result_type**: (optional) One of "json" or "xml", depending on the representation of the provider's search
          results. The default is "json"

        - **results_entry**: (mandatory) The name of the key in the provider search result that gives access to the
          result entries

        - **api_endpoint**: (mandatory) The endpoint of the provider's search interface

        - **literal_search_param**: (optional) A mapping of (search_param => search_value) pairs giving search
          parameters to be passed as is in the search url query string

        - **pagination**: (mandatory) The configuration of how the pagination is done on the provider. It is a tree
          with the following nodes:

          - *next_page_url_tpl*: The template for pagination requests. This is a simple Python format string which
            will be resolved using the following keywords: ``url`` (the base url of the search endpoint), ``search``
            (the query string corresponding to the search request), ``items_per_page`` (the number of items to return
            per page), ``skip`` (the number of items to skip) and ``page`` (which page to return).

          - *total_items_nb_key_path*: (optional) An XPath or JsonPath leading to the total number of results
            satisfying a request. This is used for providers which provides the total results metadata along with the
            result of the query and don't have an endpoint for querying the number of items satisfying a request, or
            for providers for which the count endpoint returns a json or xml document

          - *count_endpoint*: (optional) The endpoint for counting the number of items satisfying a request

          - *items_per_page*: (optional) The maximum number of items a page can have (default: 10)

        - **free_text_search_operations**: (optional) A tree structure of the form::

            <search-param>:     # e.g: $search
                union: # how to join the operations below (e.g: ' AND ' --> '(op1 AND op2) AND (op3 OR op4)')
                wrapper: # a pattern for how each operation will be wrapped (e.g: '({})' --> '(op1 AND op2)')
                operations:     # The operations to build
                  <opname>:     # e.g: AND
                    - <op1>    # e.g: 'sensingStartDate:[{startTimeFromAscendingNode}Z TO *]'
                    - <op2>    # e.g: 'sensingStopDate:[* TO {completionTimeFromAscendingNode}Z]'
                    ...
                  ...
            ...

          With the structure above, each operation will become a string of the form: '(<op1> <opname> <op2>)', then
          the operations will be joined together using the union string and finally if the number of operations is
          greater than 1, they will be wrapped as specified by the wrapper config key.

    The search plugins of this kind can detect when a metadata mapping is "query-able", and get the semantics of how
    to format the query string parameter that enables to make a query on the corresponding metadata. To make a
    metadata query-able, just configure it in the metadata mapping to be a list of 2 items, the first one being the
    specification of the query string search formatting. The later is a string following the specification of Python
    string formatting, with a special behaviour added to it. For example, an entry in the metadata mapping of this
    kind::

        completionTimeFromAscendingNode:
            - 'f=acquisition.endViewingDate:lte:{completionTimeFromAscendingNode#timestamp}'
            - '$.properties.acquisition.endViewingDate'

    means that the search url will have a query string parameter named *"f"* with a value of
    *"acquisition.endViewingDate:lte:1543922280.0"* if the search was done with the value of
    ``completionTimeFromAscendingNode`` being ``2018-12-04T12:18:00``. What happened is that
    ``{completionTimeFromAscendingNode#timestamp}`` was replaced with the timestamp of the value of
    ``completionTimeFromAscendingNode``. This example shows all there is to know about the semantics of the query
    string formatting introduced by this plugin: any eodag search parameter can be referenced in the query string
    with an additional optional conversion function that is separated from it by a ``#`` (see
    :func:`~eodag.utils.format_metadata` for further details on the available converters). Note that for the values
    in the ``free_text_search_operations`` configuration parameter follow the same rule.
    """
    COMPLEX_QS_REGEX = re.compile(r'^(.+=)?([^=]*)({.+})+([^=&]*)$')
    DEFAULT_ITEMS_PER_PAGE = 10
    extract_properties = {
        'xml': properties_from_xml,
        'json': properties_from_json
    }

    def __init__(self, provider, config):
        super(QueryStringSearch, self).__init__(provider, config)
        self.config.__dict__.setdefault('result_type', 'json')
        self.config.__dict__.setdefault('results_entry', 'features')
        self.config.__dict__.setdefault('pagination', {})
        self.config.__dict__.setdefault('free_text_search_operations', {})
        self.config.pagination.setdefault('items_per_page', self.DEFAULT_ITEMS_PER_PAGE)
        if self.config.pagination['items_per_page'] == 0:
            self.config['items_per_page'] = self.DEFAULT_ITEMS_PER_PAGE
        self.search_urls = []
        self.query_params = dict()
        self.query_string = ''

    def query(self, product_type, cached=False, start=0, stop=1, max_count=False, *args, **kwargs):
        if not cached:
            self.rollback()
        provider_product_type = self.map_product_type(product_type, *args, **kwargs)
        keywords = {k: v for k, v in kwargs.items() if k != 'auth'}
        qp, qs = self.build_query_string(product_type, productType=provider_product_type, *args, **keywords)
        self.query_params = qp
        self.query_string = qs
        self.search_urls, total_items = self.collect_search_urls(productType=product_type, *args, **kwargs)
        provider_results = self.do_search(start=start, stop=stop, *args, **kwargs)
        eo_products = self.normalize_results(provider_results, product_type, provider_product_type, *args, **kwargs)
        if max_count:
            return eo_products, total_items
        return eo_products

    def build_query_string(self, *args, **kwargs):
        """Build The query string using the search parameters"""
        logger.debug('Building the query string that will be used for search')
        queryables = self.get_queryables()
        query_params = {}
        # Get all the search parameters that are recognised as queryables by the provider (they appear in the
        # queryables dictionary)
        for search_param, query in kwargs.items():
            try:
                queryable = queryables[search_param]
                if kwargs.get(search_param) is not None:
                    if self.COMPLEX_QS_REGEX.match(queryable):
                        parts = queryable.split('=')
                        if len(parts) == 1:
                            query_params[search_param] = format_metadata(queryable)
                        else:
                            param, value = parts
                            query_params[param] = format_metadata(value, *args, **kwargs)
                    else:
                        query_params[queryable] = query
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
        query_params.update(literal_search_params)

        # Build the final query string, in one go without quoting it (some providers do not operate well with
        # urlencoded and quoted query strings...
        return query_params, urlencode(query_params, quote_via=lambda x, *_args, **_kwargs: x)

    def format_free_text_search(self, **kwargs):
        """Build the free text search parameter using the search parameters"""
        query_params = {}
        for param, operations_config in self.config.free_text_search_operations.items():
            union = operations_config['union']
            wrapper = operations_config.get('wrapper', '{}')
            formatted_query = []
            for operator, operands in operations_config['operations'].items():
                # The Operator string is the operator wrapped with spaces
                operator = ' {} '.format(operator)
                # Build the operation string by joining the formatted operands together using the operation string
                operation_string = operator.join(
                    format_metadata(operand, **kwargs)
                    for operand in operands
                    if any(kw in operand and val is not None for kw, val in kwargs.items())
                )
                # Finally wrap the operation string as specified by the wrapper and add it to the list of queries (only
                # if the operation string is not empty)
                if operation_string:
                    query = wrapper.format(operation_string)
                    formatted_query.append(query)
            # Join the formatted query using the "union" config parameter, and then wrap it with the Python format
            # string specified in the "wrapper" config parameter
            final_query = union.join(formatted_query)
            if len(operations_config['operations']) > 1 and len(formatted_query) > 1:
                final_query = wrapper.format(query_params[param])
            if final_query:
                query_params[param] = final_query
        return query_params

    def get_queryables(self):
        """Retrieve the metadata mappings that are query-able"""
        logger.debug('Retrieving queryable metadata from metadata_mapping')
        return {
            key: get_search_param(val)
            for key, val in self.config.metadata_mapping.items()
            if len(val) == 2
        }

    def collect_search_urls(self, *args, **kwargs):
        urls = []
        total_results = 0
        for collection in self.get_collections(*args, **kwargs):
            search_endpoint = self.config.api_endpoint.rstrip('/').format(collection=collection)
            count_endpoint = self.config.pagination.get('count_endpoint', '').format(collection=collection)
            if count_endpoint:
                count_url = '{}?{}'.format(count_endpoint, self.query_string)
                max_page, items_per_page, total_results = self.count_hits(count_url,
                                                                          result_type=self.config.result_type)
            else:  # First do one request querying only one element (lightweight request to schedule the pagination)
                next_url_tpl = self.config.pagination['next_page_url_tpl']
                count_url = next_url_tpl.format(url=search_endpoint, search=self.query_string,
                                                items_per_page=1, page=1, skip=0)
                max_page, items_per_page, total_results = self.count_hits(count_url,
                                                                          result_type=self.config.result_type)
            for page in range(1, max_page + 1):
                next_url = self.config.pagination['next_page_url_tpl'].format(
                    url=search_endpoint,
                    search=self.query_string,
                    items_per_page=items_per_page,
                    page=page,
                    skip=(page - 1) * items_per_page
                )
                urls.append(next_url)
        return urls, total_results

    def do_search(self, start=0, stop=1, *args, **kwargs):
        """Perform the actual search request

        :param int start: The page where to query, specified as list index (i.e starting at 0) (default: 0)
        :param int stop: The page where to stop query (default: 1, i.e only fetch the first page by default)
        """
        # Get all the pages
        if stop == -1:
            urls = self.search_urls[start:]
        # Only get the specified number of pages
        else:
            urls = self.search_urls[start:stop]
        for search_url in urls:
            try:
                response = self._request(
                    search_url,
                    info_message='Sending search request: {}'.format(search_url),
                    exception_message='Skipping error while searching for {} {} instance:'.format(
                        self.provider, self.__class__.__name__)
                )
            except RequestError:
                raise StopIteration
            else:
                if self.config.result_type == 'xml':
                    root_node = etree.fromstring(response.content)
                    namespaces = {k or 'ns': v for k, v in root_node.nsmap.items()}
                    for entry in root_node.xpath(self.config.results_entry, namespaces=namespaces):
                        yield etree.tostring(entry)
                else:
                    results = response.json()
                    for entry in results[self.config.results_entry]:
                        yield entry

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

    def count_hits(self, count_url, result_type='json'):
        # Handle a very annoying special case :'(
        url = count_url.replace('$format=json&', '')
        response = self._request(
            url,
            info_message='Sending count request: {}'.format(url),
            exception_message='Skipping error while counting results for {} {} instance:'.format(
                self.provider, self.__class__.__name__)
        )
        if result_type == 'xml':
            root_node = etree.fromstring(response.content)
            total_nb_results = root_node.xpath(
                self.config.pagination['total_items_nb_key_path'],
                namespaces={k or 'ns': v for k, v in root_node.nsmap.items()}
            )[0]
            total_results = int(total_nb_results)
        else:
            count_results = response.json()
            if isinstance(count_results, dict):
                path_parsed = jsonpath.parse(self.config.pagination['total_items_nb_key_path'])
                total_results = path_parsed.find(count_results)[0].value
            else:  # interpret the result as a raw int
                total_results = int(count_results)
        items_per_page = self.config.pagination['items_per_page']
        if total_results == 0:
            return -1, 0, 0
        max_page, rest = divmod(total_results, items_per_page)
        if rest != 0:
            max_page += 1
        return max_page, items_per_page, total_results

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
                collections = (self.config.products[product_type].get('collection', ''),)
        else:
            collection = getattr(self.config, 'collection', None)
            if collection is None:
                product_type = kwargs.get('productType') or args[0]
                collection = self.config.products[product_type].get('collection', '')
            collections = (collection,)
        return collections

    def map_product_type(self, product_type, *args, **kwargs):
        """Map the eodag product type to the provider product type"""
        logger.debug('Mapping eodag product type to provider product type')
        return self.config.products[product_type]['product_type']

    def rollback(self):
        """Do not rely on any cached and prepared searches"""
        self.search_urls = []
        self.query_params = {}
        self.query_string = ''

    def _request(self, url, info_message=None, exception_message=None):
        try:
            if info_message:
                logger.info(info_message)
            response = requests.get(url)
            response.raise_for_status()
        except requests.HTTPError:
            if exception_message:
                logger.exception(exception_message)
            else:
                logger.exception('Skipping error while requesting: %s (provider:%s, plugin:%s):', url, self.provider,
                                 self.__class__.__name__)
            raise RequestError
        return response


class AwsSearch(QueryStringSearch):
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

    def do_search(self, start=0, stop=1, *args, **kwargs):
        """Do a two step search, as the metadata are not given into the search result"""
        # TODO: This plugin is still very specific to the ONDA provider. Be careful to generalize
        #       it if needed when the chance to do so arrives
        final_result = []
        # Query the products entity set for basic metadata about the product
        for entity in super(ODataV4Search, self).do_search(start=start, stop=stop, *args, **kwargs):
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
