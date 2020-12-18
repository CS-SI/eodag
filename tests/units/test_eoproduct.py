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
import os
import tempfile

import geojson
import requests
from shapely import geometry

from tests import EODagTestCase
from tests.context import Download, EOProduct, NoDriver, config
from tests.utils import mock


class TestEOProduct(EODagTestCase):
    NOT_ASSOCIATED_PRODUCT_TYPE = "EODAG_DOES_NOT_SUPPORT_THIS_PRODUCT_TYPE"

    def setUp(self):
        super(TestEOProduct, self).setUp()

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
