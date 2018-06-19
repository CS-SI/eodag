# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

import getpass

import requests


def get_airbus_ds_dias_product_types(url_base):
    """Get all the collections and product types that are supported by airbus dias provider (an
    `ARLAS server <http://arlas.io/arlas-tech/current/>`_ implemented with a collection named `catalog`, located at
    https://testing.dias.datastore.multisat.space/sdk/resolver/api/v1/services/explore/explore/catalog/
    """
    base = '{}/explore/catalog/_search'.format(url_base.rstrip('/'))
    query = 'f=identification.collection:like:Sentinel&include=identification.collection,identification.type'
    url = '?'.join(['{base}', '{query}']).format(**locals())
    apikey = getpass.getpass('Airbus DIAS apikey:')
    print(url)
    response = requests.get(url, headers={'Authorization': 'Apikey {}'.format(apikey)})
    response.raise_for_status()
    result = response.json()
    if result['nbhits'] < result['totalnb']:
        rest = requests.get(
            url + '&from={r[nbhits]}&size={r[totalnb]}'.format(r=result),
            headers={'Authorization': 'Apikey {}'.format(apikey)}
        ).json()
        result['hits'].extend(rest['hits'])
    aggregated_result = {}
    for product_identification in (hit['data']['identification'] for hit in result['hits']):
        aggregated_result.setdefault(
            product_identification['collection'],
            set()
        ).add(product_identification['type'])
    for collection, product_types in aggregated_result.items():
        yield collection, product_types
