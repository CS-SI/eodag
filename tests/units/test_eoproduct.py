# -*- coding: utf-8 -*-
# Copyright 2020, CS GROUP - France, http://www.c-s.fr
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

import io
import itertools
import os
import random
import tempfile

import geojson
import numpy as np
import requests
import xarray as xr
from shapely import geometry

from tests import EODagTestCase
from tests.context import (
    DEFAULT_PROJ,
    Authentication,
    Download,
    DownloadError,
    EOProduct,
    NoDriver,
    Sentinel2L1C,
    UnsupportedDatasetAddressScheme,
    config,
)
from tests.utils import mock


class TestEOProduct(EODagTestCase):
    NOT_ASSOCIATED_PRODUCT_TYPE = "EODAG_DOES_NOT_SUPPORT_THIS_PRODUCT_TYPE"

    def setUp(self):
        super(TestEOProduct, self).setUp()
        self.raster = xr.DataArray(np.arange(25).reshape(5, 5))

    def test_eoproduct_search_intersection_geom(self):
        """EOProduct search_intersection attr must be it's geom when no bbox_or_intersect param given"""  # noqa
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        self.assertEqual(product.geometry, product.search_intersection)

    def test_eoproduct_search_intersection_none(self):
        """EOProduct search_intersection attr must be None if shapely.errors.TopologicalError when intersecting"""  # noqa
        # Invalid geometry
        self.eoproduct_props["geometry"] = {
            "type": "Polygon",
            "coordinates": [
                [
                    [10.469970703124998, 3.9957805129630373],
                    [12.227783203124998, 4.740675384778385],
                    [12.095947265625, 4.061535597066097],
                    [10.491943359375, 4.412136788910175],
                    [10.469970703124998, 3.9957805129630373],
                ]
            ],
        }
        product = EOProduct(
            self.provider,
            self.eoproduct_props,
            productType=self.product_type,
            geometry=geometry.Polygon(
                (
                    (10.469970703124998, 3.9957805129630373),
                    (10.469970703124998, 4.740675384778385),
                    (12.227783203124998, 4.740675384778385),
                    (12.227783203124998, 3.9957805129630373),
                )
            ),
        )
        self.assertIsNone(product.search_intersection)

    def test_eoproduct_default_driver_unsupported_product_type(self):
        """EOProduct driver attr must be NoDriver if its product type is not associated with a eodag dataset driver"""  # noqa
        product = EOProduct(
            self.provider,
            self.eoproduct_props,
            productType=self.NOT_ASSOCIATED_PRODUCT_TYPE,
        )
        self.assertIsInstance(product.driver, NoDriver)

    def test_eoproduct_driver_ok(self):
        """EOProduct driver attr must be the one registered for valid platform and instrument in DRIVERS"""  # noqa
        product_type = random.choice(["S2_MSI_L1C"])
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=product_type
        )
        self.assertIsInstance(product.driver, Sentinel2L1C)

    def test_get_data_local_product_ok(self):
        """A call to get_data on a product present in the local filesystem must succeed"""  # noqa
        self.eoproduct_props.update(
            {"downloadLink": "file://{}".format(self.local_product_abspath)}
        )
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        product.driver = mock.MagicMock(spec_set=NoDriver())
        product.driver.get_data_address.return_value = self.local_band_file

        data, band = self.execute_get_data(product, give_back=("band",))

        self.assertEqual(product.driver.get_data_address.call_count, 1)
        product.driver.get_data_address.assert_called_with(product, band)
        self.assertIsInstance(data, xr.DataArray)
        self.assertNotEqual(data.values.size, 0)

    def test_get_data_download_on_unsupported_dataset_address_scheme_error(self):
        """If a product is not on the local filesystem, it must download itself before returning the data"""  # noqa
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )

        def get_data_address(*args, **kwargs):
            eo_product = args[0]
            if eo_product.location.startswith("https"):
                raise UnsupportedDatasetAddressScheme
            return self.local_band_file

        product.driver = mock.MagicMock(spec_set=NoDriver())
        product.driver.get_data_address.side_effect = get_data_address

        mock_downloader = mock.MagicMock(
            spec_set=Download(
                provider=self.provider,
                config=config.PluginConfig.from_mapping(
                    {"extract": False, "archive_depth": 1}
                ),
            )
        )
        mock_downloader.download.return_value = self.local_product_as_archive_path
        # mock_downloader.config = {'extract': False, 'archive_depth': 1}
        mock_authenticator = mock.MagicMock(
            spec_set=Authentication(
                provider=self.provider, config=config.PluginConfig.from_mapping({})
            )
        )

        product.register_downloader(mock_downloader, mock_authenticator.authenticate())
        data, band = self.execute_get_data(product, give_back=("band",))

        self.assertEqual(product.driver.get_data_address.call_count, 2)
        product.driver.get_data_address.assert_called_with(product, band)
        self.assertIsInstance(data, xr.DataArray)
        self.assertNotEqual(data.values.size, 0)

    def test_get_data_dl_on_unsupported_ds_address_scheme_error_wo_downloader(self):
        """If a product is not on filesystem and a downloader isn't registered, get_data must return an empty array"""  # noqa
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )

        product.driver = mock.MagicMock(spec_set=NoDriver())
        product.driver.get_data_address.side_effect = UnsupportedDatasetAddressScheme

        self.assertRaises(RuntimeError, product.download)

        data = self.execute_get_data(product)

        self.assertEqual(product.driver.get_data_address.call_count, 1)
        self.assertIsInstance(data, xr.DataArray)
        self.assertEqual(data.values.size, 0)

    def test_get_data_bad_download_on_unsupported_dataset_address_scheme_error(self):
        """If downloader doesn't return the downloaded file path, get_data must return an empty array"""  # noqa
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )

        product.driver = mock.MagicMock(spec_set=NoDriver())
        product.driver.get_data_address.side_effect = UnsupportedDatasetAddressScheme

        mock_downloader = mock.MagicMock(
            spec_set=Download(
                provider=self.provider,
                config=config.PluginConfig.from_mapping({"extract": False}),
            )
        )
        mock_downloader.download.return_value = None
        mock_authenticator = mock.MagicMock(
            spec_set=Authentication(
                provider=self.provider, config=config.PluginConfig.from_mapping({})
            )
        )

        product.register_downloader(mock_downloader, mock_authenticator)

        self.assertRaises(DownloadError, product.download)

        data, band = self.execute_get_data(product, give_back=("band",))

        self.assertEqual(product.driver.get_data_address.call_count, 1)
        product.driver.get_data_address.assert_called_with(product, band)
        self.assertIsInstance(data, xr.DataArray)
        self.assertEqual(data.values.size, 0)

    @staticmethod
    def execute_get_data(
        product, crs=None, resolution=None, band=None, extent=None, give_back=()
    ):
        """Call the get_data method of given product with given parameters, then return
         the computed data and the parameters passed in whom names are in give_back for
         further assertions in the calling test method"""
        crs = crs or DEFAULT_PROJ
        resolution = resolution or 0.0006
        band = band or "B01"
        extent = extent or (2.1, 42.8, 2.2, 42.9)
        data = product.get_data(crs, resolution, band, extent)
        if give_back:
            returned_params = tuple(
                value for name, value in locals().items() if name in give_back
            )
            return tuple(itertools.chain.from_iterable(((data,), returned_params)))
        return data

    def test_eoproduct_encode_bad_encoding(self):
        """EOProduct encode method must return an empty bytes if encoding is not supported or is None"""  # noqa
        encoding = random.choice(["not_supported", None])
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        encoded_raster = product.encode(self.raster, encoding)
        self.assertIsInstance(encoded_raster, bytes)
        self.assertEqual(encoded_raster, b"")

    def test_eoproduct_encode_protobuf(self):
        """Test encode method with protocol buffers encoding"""
        # Explicitly provide encoding
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        encoded_raster = product.encode(self.raster, encoding="protobuf")
        self.assertIsInstance(encoded_raster, bytes)
        self.assertNotEqual(encoded_raster, b"")

    def test_eoproduct_encode_missing_platform_and_instrument(self):
        """Protobuf encode method must raise an error if no platform and instrument are given"""  # noqa
        self.eoproduct_props["platformSerialIdentifier"] = None
        self.eoproduct_props["instrument"] = None
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        self.assertRaises(TypeError, product.encode, self.raster, encoding="protobuf")

        self.eoproduct_props["platformSerialIdentifier"] = None
        self.eoproduct_props["instrument"] = "MSI"
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        self.assertRaises(TypeError, product.encode, self.raster, encoding="protobuf")

        self.eoproduct_props["platformSerialIdentifier"] = "S2A"
        self.eoproduct_props["instrument"] = None
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        self.assertRaises(TypeError, product.encode, self.raster, encoding="protobuf")

    def test_eoproduct_geointerface(self):
        """EOProduct must provide a geo-interface with a set of specific properties"""
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        geo_interface = geojson.loads(geojson.dumps(product))
        self.assertDictContainsSubset(
            {
                "type": "Feature",
                "geometry": self._tuples_to_lists(geometry.mapping(self.geometry)),
            },
            geo_interface,
        )
        self.assertDictContainsSubset(
            {
                "eodag_provider": self.provider,
                "eodag_search_intersection": self._tuples_to_lists(
                    geometry.mapping(product.search_intersection)
                ),
                "eodag_product_type": self.product_type,
            },
            geo_interface["properties"],
        )

    def test_eoproduct_from_geointerface(self):
        """EOProduct must be build-able from its geo-interface"""
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        same_product = EOProduct.from_geojson(geojson.loads(geojson.dumps(product)))
        self.assertSequenceEqual(
            [
                product.provider,
                product.location,
                product.properties["title"],
                product.properties["instrument"],
                self._tuples_to_lists(geometry.mapping(product.geometry)),
                self._tuples_to_lists(geometry.mapping(product.search_intersection)),
                product.product_type,
                product.properties["productType"],
                product.properties["platformSerialIdentifier"],
            ],
            [
                same_product.provider,
                same_product.location,
                same_product.properties["title"],
                same_product.properties["instrument"],
                self._tuples_to_lists(geometry.mapping(same_product.geometry)),
                self._tuples_to_lists(
                    geometry.mapping(same_product.search_intersection)
                ),
                same_product.product_type,
                same_product.properties["productType"],
                same_product.properties["platformSerialIdentifier"],
            ],
        )

    def test_eoproduct_get_quicklook_no_quicklook_url(self):
        """EOProduct.get_quicklook must return an empty string if no quicklook property"""  # noqa
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        product.properties["quicklook"] = None

        quicklook_file_path = product.get_quicklook()
        self.assertEqual(quicklook_file_path, "")

    def test_eoproduct_get_quicklook_http_error(self):
        """EOProduct.get_quicklook must return an empty string if there was an error during retrieval"""  # noqa
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        product.properties["quicklook"] = "https://fake.url.to/quicklook"

        self.requests_http_get.return_value.__enter__.return_value.raise_for_status.side_effect = (  # noqa
            requests.HTTPError
        )
        mock_downloader = mock.MagicMock(
            spec_set=Download(provider=self.provider, config=None)
        )
        mock_downloader.config = config.PluginConfig.from_mapping(
            {"outputs_prefix": tempfile.gettempdir()}
        )
        product.register_downloader(mock_downloader, None)

        quicklook_file_path = product.get_quicklook()
        self.requests_http_get.assert_called_with(
            "https://fake.url.to/quicklook", stream=True, auth=None
        )
        self.assertEqual(quicklook_file_path, "")

    def test_eoproduct_get_quicklook_ok(self):
        """EOProduct.get_quicklook must return the path to the successfully downloaded quicklook"""  # noqa
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        product.properties["quicklook"] = "https://fake.url.to/quicklook"

        self.requests_http_get.return_value = self._quicklook_response()
        mock_downloader = mock.MagicMock(
            spec_set=Download(provider=self.provider, config=None)
        )
        mock_downloader.config = config.PluginConfig.from_mapping(
            {"outputs_prefix": tempfile.gettempdir()}
        )
        product.register_downloader(mock_downloader, None)

        quicklook_file_path = product.get_quicklook()
        self.requests_http_get.assert_called_with(
            "https://fake.url.to/quicklook", stream=True, auth=None
        )
        self.assertEqual(
            os.path.basename(quicklook_file_path), product.properties["id"]
        )
        self.assertEqual(
            os.path.dirname(quicklook_file_path),
            os.path.join(tempfile.gettempdir(), "quicklooks"),
        )
        os.remove(quicklook_file_path)

        # Test the same thing as above but with an explicit name given to the downloaded File
        quicklook_file_path = product.get_quicklook(filename="the_quicklook.png")
        self.requests_http_get.assert_called_with(
            "https://fake.url.to/quicklook", stream=True, auth=None
        )
        self.assertEqual(self.requests_http_get.call_count, 2)
        self.assertEqual(os.path.basename(quicklook_file_path), "the_quicklook.png")
        self.assertEqual(
            os.path.dirname(quicklook_file_path),
            os.path.join(tempfile.gettempdir(), "quicklooks"),
        )
        os.remove(quicklook_file_path)

        # Overall teardown
        os.rmdir(os.path.dirname(quicklook_file_path))

    def test_eoproduct_get_quicklook_ok_existing(self):
        """EOProduct.get_quicklook must return the path to an already downloaded quicklook"""  # noqa
        quicklook_dir = os.path.join(tempfile.gettempdir(), "quicklooks")
        quicklook_basename = "the_quicklook.png"
        existing_quicklook_file_path = os.path.join(quicklook_dir, quicklook_basename)
        if not os.path.exists(quicklook_dir):
            os.mkdir(quicklook_dir)
        with open(existing_quicklook_file_path, "wb") as fh:
            fh.write(b"content")
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        product.properties["quicklook"] = "https://fake.url.to/quicklook"
        mock_downloader = mock.MagicMock(
            spec_set=Download(provider=self.provider, config=None)
        )
        mock_downloader.config = config.PluginConfig.from_mapping(
            {"outputs_prefix": tempfile.gettempdir()}
        )
        product.register_downloader(mock_downloader, None)

        quicklook_file_path = product.get_quicklook(filename=quicklook_basename)
        self.assertEqual(self.requests_http_get.call_count, 0)
        self.assertEqual(quicklook_file_path, existing_quicklook_file_path)
        os.remove(existing_quicklook_file_path)
        os.rmdir(quicklook_dir)

    @staticmethod
    def _quicklook_response():
        class Response(object):
            """Emulation of a response to requests.get method for a quicklook"""

            def __init__(response):
                response.headers = {"content-length": 2 ** 5}

            def __enter__(response):
                return response

            def __exit__(response, *args):
                pass

            @staticmethod
            def iter_content(**kwargs):
                with io.BytesIO(b"a" * 2 ** 5) as fh:
                    while True:
                        chunk = fh.read(kwargs["chunk_size"])
                        if not chunk:
                            break
                        yield chunk

            def raise_for_status(response):
                pass

        return Response()
