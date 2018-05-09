# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

import os
import unittest

from shapely import wkt

try:
    from unittest import mock  # PY3
except ImportError:
    import mock  # PY2


jp = os.path.join
dirn = os.path.dirname

TEST_RESOURCES_PATH = jp(dirn(__file__), 'resources')
RESOURCES_PATH = jp(dirn(__file__), '..', 'eodag', 'resources')


class EODagTestCase(unittest.TestCase):

    def setUp(self):
        self.provider = 'eocloud'
        self.download_url = ('https://static.eocloud.eu/v1/AUTH_8f07679eeb0a43b19b33669a4c888c45/eorepo/Sentinel-2/MSI/'
                             'L1C/2018/01/01/S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911.SAFE.zip')
        self.local_filename = 'S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911.SAFE'
        # A good valid geometry of a sentinel 2 product around Toulouse
        self.geometry = wkt.loads('POLYGON((0.495928592903789 44.22596415476343, 1.870237286761489 44.24783068396879, '
                                  '1.888683014192297 43.25939191053712, 0.536772323136669 43.23826255332707, '
                                  '0.495928592903789 44.22596415476343))')
        # The footprint requested
        self.footprint = {
            'lonmin': 1.3128662109375002, 'latmin': 43.65197548731186,
            'lonmax': 1.6754150390625007, 'latmax': 43.699651229671446
        }
        self.product_type = 'L1C'
        self.platform = 'S2A'
        self.instrument = 'MSI'
        self.provider_id = '9deb7e78-9341-5530-8fe8-f81fd99c9f0f'

        self.patcher = mock.patch('requests.get', autospec=True)
        self.requests_http_get = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def override_properties(self, **kwargs):
        """Overrides the properties with the values specified in the input parameters"""
        self.__dict__.update({
            prop: new_value
            for prop, new_value in kwargs.items()
            if prop in self.__dict__ and new_value != self.__dict__[prop]
        })

    def assertHttpGetCalledOnceWith(self, expected_url, expected_params=None):
        """Helper method for doing assertions on requests http get method mock"""
        self.assertEqual(self.requests_http_get.call_count, 1)
        actual_url = self.requests_http_get.call_args[0][0]
        self.assertEqual(actual_url, expected_url)
        if expected_params:
            actual_params = self.requests_http_get.call_args[1]['params']
            self.assertDictEqual(actual_params, expected_params)

    @staticmethod
    def _tuples_to_lists(shapely_mapping):
        """Transforms all tuples in shapely mapping to lists.

        When doing for example::
            shapely_mapping = geometry.mapping(geom)

        ``shapely_mapping['coordinates']`` will contain only tuples.

        When doing for example::
            geojson_load = geojson.loads(geojson.dumps(obj_with_geo_interface))

        ``geojson_load['coordinates']`` will contain only lists.

        Then this helper exists to transform all tuples in  ``shapely_mapping['coordinates']`` to lists in-place, so
        that ``shapely_mapping['coordinates']`` can be compared to ``geojson_load['coordinates']``
        """
        shapely_mapping['coordinates'] = list(shapely_mapping['coordinates'])
        for i, coords in enumerate(shapely_mapping['coordinates']):
            shapely_mapping['coordinates'][i] = list(coords)
            coords = shapely_mapping['coordinates'][i]
            for j, pair in enumerate(coords):
                coords[j] = list(pair)
        return shapely_mapping
