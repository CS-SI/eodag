# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
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
