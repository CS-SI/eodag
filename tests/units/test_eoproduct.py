# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

import itertools
import random

import geojson
import numpy as np
from shapely import geometry, wkt

from tests import EODagTestCase
from tests.context import (
    Authentication, DRIVERS, Download, EOProduct, NoDriver, Sentinel2, UnsupportedDatasetAddressScheme,
)


try:
    from unittest import mock  # PY3
except ImportError:
    import mock  # PY2


class TestEOProduct(EODagTestCase):
    __nominal_search_url_on_eocloud = (
        'https://finder.eocloud.eu/resto/api/collections/Sentinel2/search.json?&maxRecords=10&cloudCover=%5B0%2C20%5D&'
        'processingLevel=LEVELL1C&sortParam=startDate&sortOrder=descending&geometry=POLYGON%28%281.3128662109375002%204'
        '3.65197548731186%2C1.6754150390625007%2043.699651229671446%2C1.6204833984375002%2043.48481212891605%2C1.389770'
        '5078125002%2043.47684039777894%2C1.3128662109375002%2043.65197548731186%29%29&dataset=ESA-DATASET&page=1')

    def setUp(self):
        super(TestEOProduct, self).setUp()
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

    def test_get_data_local_product_ok(self):
        """A call to get_data on a product present in the local filesystem must succeed"""
        product = EOProduct(
            self.provider,
            'file://{}'.format(self.local_product_abspath),  # Download url
            self.local_filename,
            self.geometry,
            self.footprint,
            self.product_type
        )
        product.driver = mock.MagicMock(spec_set=NoDriver())
        product.driver.get_data_address.return_value = self.local_band_file

        data, band = self.execute_get_data(product, give_back=('band',))

        self.assertEqual(product.driver.get_data_address.call_count, 1)
        product.driver.get_data_address.assert_called_with(product, band)
        self.assertIsInstance(data, np.ndarray)
        self.assertNotEqual(data.size, 0)

    def test_get_data_download_on_unsupported_dataset_address_scheme_error(self):
        """If a product is not on the local filesystem, it must download itself before returning the data"""
        product = EOProduct(
            self.provider,
            self.download_url,
            self.local_filename,
            self.geometry,
            self.footprint,
            self.product_type
        )

        def get_data_address(*args, **kwargs):
            eo_product = args[0]
            if eo_product.location_url_tpl.startswith('https'):
                raise UnsupportedDatasetAddressScheme
            return self.local_band_file

        product.driver = mock.MagicMock(spec_set=NoDriver())
        product.driver.get_data_address.side_effect = get_data_address

        mock_downloader = mock.MagicMock(spec_set=Download(config={'extract': False}))
        mock_downloader.download.return_value = self.local_product_as_archive_path
        mock_authenticator = mock.MagicMock(spec_set=Authentication(config={}))

        product.register_downloader(mock_downloader, mock_authenticator.authenticate())
        data, band = self.execute_get_data(product, give_back=('band',))

        self.assertEqual(product.driver.get_data_address.call_count, 2)
        product.driver.get_data_address.assert_called_with(product, band)
        self.assertIsInstance(data, np.ndarray)
        self.assertNotEqual(data.size, 0)

    def test_get_data_download_on_unsupported_dataset_address_scheme_error_without_downloader(self):
        """If a product is not on filesystem and a downloader isn't registered, get_data must return an empty array"""
        product = EOProduct(
            self.provider,
            self.download_url,
            self.local_filename,
            self.geometry,
            self.footprint,
            self.product_type
        )

        product.driver = mock.MagicMock(spec_set=NoDriver())
        product.driver.get_data_address.side_effect = UnsupportedDatasetAddressScheme

        self.assertRaises(RuntimeError, product.download)

        data = self.execute_get_data(product)

        self.assertEqual(product.driver.get_data_address.call_count, 1)
        self.assertIsInstance(data, np.ndarray)
        self.assertEqual(data.size, 0)

    def test_get_data_bad_download_on_unsupported_dataset_address_scheme_error(self):
        """If downloader doesn't return the downloaded file path, get_data must return an empty array"""
        product = EOProduct(
            self.provider,
            self.download_url,
            self.local_filename,
            self.geometry,
            self.footprint,
            self.product_type
        )

        product.driver = mock.MagicMock(spec_set=NoDriver())
        product.driver.get_data_address.side_effect = UnsupportedDatasetAddressScheme

        mock_downloader = mock.MagicMock(spec_set=Download(config={'extract': False}))
        mock_downloader.download.return_value = None
        mock_authenticator = mock.MagicMock(spec_set=Authentication(config={}))

        product.register_downloader(mock_downloader, mock_authenticator.authenticate())

        self.assertEqual(product.download(), '')

        data, band = self.execute_get_data(product, give_back=('band',))

        self.assertEqual(product.driver.get_data_address.call_count, 1)
        product.driver.get_data_address.assert_called_with(product, band)
        self.assertIsInstance(data, np.ndarray)
        self.assertEqual(data.size, 0)

    @staticmethod
    def execute_get_data(product, crs=None, resolution=None, band=None, extent=None, give_back=()):
        """Call the get_data method of given product with given parameters, then return the computed data and the
        parameters passed in whom names are in give_back for further assertions in the calling test method"""
        crs = crs or 'EPSG:4326'
        resolution = resolution or 0.0006
        band = band or 'B01'
        extent = extent or (2.1, 42.8, 2.2, 42.9)
        data = product.get_data(crs, resolution, band, extent)
        if give_back:
            returned_params = tuple(value for name, value in locals().items() if name in give_back)
            return tuple(itertools.chain.from_iterable(((data,), returned_params)))
        return data

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
            'geometry': self._tuples_to_lists(geometry.mapping(self.geometry))
        }, geo_interface)
        self.assertDictContainsSubset({
            'eodag_provider': self.provider, 'eodag_download_url': self.download_url,
            'eodag_local_name': self.local_filename,
            'eodag_search_intersection': self._tuples_to_lists(geometry.mapping(product.search_intersection))
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
                product.provider, product.location, product.local_filename, product.sensor,
                self._tuples_to_lists(geometry.mapping(product.geometry)), product.search_intersection,
                product.product_type, product.sensing_platform
            ],
            [
                same_product.provider, same_product.location, same_product.local_filename, same_product.sensor,
                same_product.geometry, same_product.search_intersection, same_product.product_type,
                same_product.sensing_platform
            ]
        )
