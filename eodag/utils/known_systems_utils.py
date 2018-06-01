# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

import getpass

import requests


def get_eocloud_product_types():
    """Function based on analysis of source code of https://finder.eocloud.eu/www/.

    The endpoint is called on page load to get a list of supported collections that helps create search
    fields. We assume if a collection has an empty list of supported product types, it means the collection
    only have one product type, and this product type is manually guessed by doing a search on the UI with
    this collection as the unique criteria (by time of first writing of this function, this may be true for
    Sentinel2 and Envisat collections). Note that even if the list of product types is not empty, there may
    be more supported product types. This way of finding the eocloud product types is not standard !
    """
    url = 'https://finder.eocloud.eu/www/eox_attributes.json'
    eox_attributes = requests.get(url).json()
    for coll_props in eox_attributes['collections']:
        collection_name = coll_props['id']
        product_types = [
            sp['id']
            for p in coll_props['properties'] if p['id'] == 'productType'
            for sp in p['values']
        ]
        yield collection_name, product_types


def get_airbus_ds_dias_product_types():
    """Get all the collections and product types that are supported by airbus dias provider (an
    `ARLAS server <http://arlas.io/arlas-tech/current/>`_ implemented with a collection named `catalog`, located at
    https://testing.dias.datastore.multisat.space/sdk/resolver/api/v1/services/explore/explore/catalog/
    """
    base = 'https://testing.dias.datastore.multisat.space/sdk10/lobby/api/v1/services/explore/explore/catalog/_search'
    query = 'f=identification.collection:like:Sentinel&include=identification.collection,identification.type'
    url = '?'.join(['{base}', '{query}']).format(**locals())
    try:
        user = raw_input('Airbus DIAS user: ')
    except NameError:
        user = input('Airbus DIAS user: ')
    password = getpass.getpass("Airbus DIAS password for user '{}':".format(user))
    result = requests.get(url, auth=(user, password)).json()
    if result['nbhits'] < result['totalnb']:
        rest = requests.get(
            url + '&from={r[nbhits]}&size={r[totalnb]}'.format(r=result),
            auth=(user, password)
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
