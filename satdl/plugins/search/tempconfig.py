# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
"""A temporary config file to illustrate how we want to configure the search plugins"""

PLUGIN_INSTANCES_CONF = {
    'eocloud': {
        'plugin': 'RestoSearch',
        'priority': 1,
        'api_endpoint': 'http://finder.eocloud.eu/resto/api/',
        'products': {
            'Sentinel2': {
                'min_start_date': '2016-12-10',  # new S2 products specification
                'product_type': 'L1C',
                'instrument': None,
                'band2_pattern': '*B02.tif',
                'lms': '40',
            },
            'Landsat8': {
                'min_start_date': '2013-05-26',
                'product_type': 'L1T',
                'instrument': 'OLI',
                'band2_pattern': '*_B2.tif',
                'lms': '120',
            },
            'Envisat': {
                'min_start_date': '2002-05-17',
                'product_type': 'FRS',
                'instrument': None,
                'band2_pattern': '*_band_02.tif',
                'lms': '1200',
            },
        },
    },
    'thiea': {
        'plugin': 'RestoSearch',
        'priority': 1,
        'api_endpoint': '',
        'products': {},
    },
    'scihub': {
        'plugin': 'SentinelSearch',
        'priority': 1,
        'api_endpoint': 'https://scihub.copernicus.eu/apihub/',
        'products': {},
    },
}

