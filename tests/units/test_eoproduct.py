# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

import random
import unittest

import geojson
import numpy as np
from shapely import geometry, wkt

from .context import DRIVERS, EOProduct, NoDriver, Sentinel2


class TestEOProduct(unittest.TestCase):
    __nominal_search_url_on_eocloud = (
        'https://finder.eocloud.eu/resto/api/collections/Sentinel2/search.json?&maxRecords=10&cloudCover=%5B0%2C20%5D&'
        'processingLevel=LEVELL1C&sortParam=startDate&sortOrder=descending&geometry=POLYGON%28%281.3128662109375002%204'
        '3.65197548731186%2C1.6754150390625007%2043.699651229671446%2C1.6204833984375002%2043.48481212891605%2C1.389770'
        '5078125002%2043.47684039777894%2C1.3128662109375002%2043.65197548731186%29%29&dataset=ESA-DATASET&page=1')

    def setUp(self):
        self.provider = 'eocloud'
        self.download_url = ('https://static.eocloud.eu/v1/AUTH_8f07679eeb0a43b19b33669a4c888c45/eorepo/Sentinel-2/MSI/'
                             'L1C/2018/04/06/S2B_MSIL1C_20180406T105029_N0206_R051_T31TCJ_20180406T125448.SAFE.zip')
        self.local_filename = 'S2B_MSIL1C_20180406T105029_N0206_R051_T31TCJ_20180406T125448.SAFE'
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
        self.platform = 'S2B'
        self.instrument = 'MSI'
        self.provider_id = '9deb7e78-9341-5530-8fe8-f81fd99c9f0f'
        self.raster = np.arange(25).reshape(5, 5)

    def test_eoproduct_id_format(self):
        """EOProduct id attribute must be a string formatted as the result of uuid.uuid4().get_urn()"""

    def test_eoproduct_search_intersection_geom(self):
        """EOProduct search_intersection attr must be it's geom when no bbox_or_intersect param given"""
        product = EOProduct(
            self.provider,
            self.download_url,
            self.local_filename,
            self.geometry,
            bbox_or_intersect={},
            product_type=self.product_type
        )
        self.assertEqual(product.geometry, product.search_intersection)

    def test_eoproduct_search_intersection_none(self):
        """EOProduct search_intersection attr must be None if shapely.errors.TopologicalError when intersecting"""
        invalid_geom = wkt.loads('POLYGON((10.469970703124998 3.9957805129630373,12.227783203124998 4.740675384778385,'
                                 '12.095947265625 4.061535597066097,10.491943359375 4.412136788910175,'
                                 '10.469970703124998 3.9957805129630373))')
        product = EOProduct(
            self.provider,
            self.download_url,
            self.local_filename,
            invalid_geom,
            {
                'lonmin': 10.469970703124998, 'latmin': 3.9957805129630373,
                'lonmax': 12.227783203124998, 'latmax': 4.740675384778385
            },
            self.product_type
        )
        self.assertIsNone(product.search_intersection)

    def test_eoproduct_register_product_id_on_provider(self):
        """EOProduct must have a provider_id property if instantiated with this keyword argument"""
        # First check that without giving the keyword, we don't have the property
        product = EOProduct(
            self.provider,
            self.download_url,
            self.local_filename,
            self.geometry,
            self.footprint,
            self.product_type,
        )
        self.assertNotIn('provider_id', product.properties)
        product = EOProduct(
            self.provider,
            self.download_url,
            self.local_filename,
            self.geometry,
            self.footprint,
            self.product_type,
            provider_id=self.provider_id
        )
        self.assertIn('provider_id', product.properties)
        self.assertEqual(product.properties['provider_id'], self.provider_id)

    def test_eoproduct_default_driver_noplatform_noinstrument(self):
        """EOProduct driver attr must be NoDriver if no platform and instrument names"""
        product = EOProduct(
            self.provider,
            self.download_url,
            self.local_filename,
            self.geometry,
            self.footprint,
            self.product_type,
        )
        self.assertIsInstance(product.driver, NoDriver)

    def test_eoproduct_default_driver_unregistered_platform_unregistered_instrument(self):
        """EOProduct driver attr must be NoDriver if platform and instrument given are not registered in DRIVERS"""
        platform = 'Unregistered_platform'
        instrument = 'Unregistered_instrument'
        self.assertNotIn((platform, instrument), DRIVERS)
        product = EOProduct(
            self.provider,
            self.download_url,
            self.local_filename,
            self.geometry,
            self.footprint,
            self.product_type,
            platform=platform,
            instrument=instrument
        )
        self.assertIsInstance(product.driver, NoDriver)

    def test_eoproduct_driver_ok(self):
        """EOProduct driver attr must be the one registered for valid platform and instrument in DRIVERS"""
        platform = random.choice(['S2A', 'S2B'])
        instrument = 'MSI'
        self.assertIn((platform, instrument), DRIVERS)
        product = EOProduct(
            self.provider,
            self.download_url,
            self.local_filename,
            self.geometry,
            self.footprint,
            self.product_type,
            platform=platform,
            instrument=instrument
        )
        self.assertIsInstance(product.driver, Sentinel2)

    def test_eoproduct_encode_bad_encoding(self):
        """EOProduct encode method must return an empty bytes if encoding is not supported or is None"""
        encoding = random.choice(['not_supported', None])
        product = EOProduct(
            self.provider,
            self.download_url,
            self.local_filename,
            self.geometry,
            self.footprint,
            self.product_type,
        )
        encoded_raster = product.encode(self.raster, encoding)
        self.assertIsInstance(encoded_raster, bytes)
        self.assertEqual(encoded_raster, b'')

    def test_eoproduct_encode_protobuf(self):
        """Test encode method with protocol buffers encoding"""
        # Explicitly provide encoding
        product = EOProduct(
            self.provider,
            self.download_url,
            self.local_filename,
            self.geometry,
            self.footprint,
            self.product_type,
            platform=self.platform,
            instrument=self.instrument
        )
        encoded_raster = product.encode(self.raster, encoding='protobuf')
        self.assertIsInstance(encoded_raster, bytes)
        self.assertNotEqual(encoded_raster, b'')

    def test_eoproduct_encode_missing_platform_and_instrument(self):
        """Protobuf encode method must raise an error if no platform and instrument are given"""
        product = EOProduct(
            self.provider,
            self.download_url,
            self.local_filename,
            self.geometry,
            self.footprint,
            self.product_type,
        )
        self.assertRaises(TypeError, product.encode, self.raster, encoding='protobuf')

        product = EOProduct(
            self.provider,
            self.download_url,
            self.local_filename,
            self.geometry,
            self.footprint,
            self.product_type,
            platform=self.platform
        )
        self.assertRaises(TypeError, product.encode, self.raster, encoding='protobuf')

        product = EOProduct(
            self.provider,
            self.download_url,
            self.local_filename,
            self.geometry,
            self.footprint,
            self.product_type,
            instrument=self.instrument
        )
        self.assertRaises(TypeError, product.encode, self.raster, encoding='protobuf')

    def test_eoproduct_geointerface(self):
        """EOProduct must provide a geo-interface with a set of specific properties"""
        product = EOProduct(
            self.provider,
            self.download_url,
            self.local_filename,
            self.geometry,
            self.footprint,
            self.product_type,
        )
        geo_interface = geojson.loads(geojson.dumps(product))
        self.assertDictContainsSubset({
            'type': 'Feature',
            'geometry': self.__tuples_to_lists(geometry.mapping(self.geometry))
        }, geo_interface)
        self.assertDictContainsSubset({
            'eodag_provider': self.provider, 'eodag_download_url': self.download_url,
            'eodag_local_name': self.local_filename,
            'eodag_search_intersection': self.__tuples_to_lists(geometry.mapping(product.search_intersection))
        }, geo_interface['properties'])

    def test_eoproduct_from_geointerface(self):
        """EOProduct must be build-able from its geo-interface"""
        product = EOProduct(
            self.provider,
            self.download_url,
            self.local_filename,
            self.geometry,
            self.footprint,
            self.product_type,
        )
        same_product = EOProduct.from_geojson(geojson.loads(geojson.dumps(product)))
        self.assertSequenceEqual(
            [
                product.provider, product.location_url_tpl, product.local_filename, product.sensor,
                self.__tuples_to_lists(geometry.mapping(product.geometry)), product.search_intersection,
                product.product_type, product.sensing_platform
            ],
            [
                same_product.provider, same_product.location_url_tpl, same_product.local_filename, same_product.sensor,
                same_product.geometry, same_product.search_intersection, same_product.product_type,
                same_product.sensing_platform
            ]
        )

    @staticmethod
    def __tuples_to_lists(shapely_mapping):
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
