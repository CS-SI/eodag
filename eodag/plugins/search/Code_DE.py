# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

from opensearch import Client
from sphinx.util import requests

from eodag.api.product import EOProduct
from eodag.api.product.representations import properties_from_xml
from eodag.plugins.search.base import Search


class Code_DESearch(Search):

    def __init__(self, config):
        super(Code_DESearch, self).__init__(config)
        self.catalog = None

    def query(self, product_type, **kwargs):

        client = Client(self.config['api_endpoint'])
        params = {}
        footprint = kwargs.pop('geometry', '')
        if footprint:
            params['geo'] = '{lonmin}, {latmin}, {lonmax}, {latmax}'.format(**footprint)
        else:
            params['geo'] = ''
        start_date = kwargs.pop('startTimeFromAscendingNode', '')
        end_date = kwargs.pop('completionTimeFromAscendingNode', '')

        search_result = client.search('', eo__parentIdentifier=self.config['products'][product_type]['product_type'],
                                      geo__box=params['geo'], time__start=start_date, time__end=end_date)
        results = []
        for product in search_result.items:
            xml = requests.get(product['id']).content
            download_url = product['links'][1]['href'].split(',')[0]
            results.append(EOProduct(product_type, self.instance_name, download_url,
                                     properties_from_xml(xml, self.config['metadata_mapping']))) #TODO: make xml parsing work and download work
        print(search_result.list)