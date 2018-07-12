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

import getpass

import requests


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
