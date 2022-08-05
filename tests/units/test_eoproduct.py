# -*- coding: utf-8 -*-
# Copyright 2018, CS GROUP - France, https://www.csgroup.eu/
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
import pathlib
import shutil
import tempfile
import zipfile

import geojson
import requests
from shapely import geometry

from tests import EODagTestCase
from tests.context import (
    DEFAULT_STREAM_REQUESTS_TIMEOUT,
    Download,
    EOProduct,
    HTTPDownload,
    NoDriver,
    ProgressCallback,
    config,
)
from tests.utils import mock


class TestEOProduct(EODagTestCase):
    NOT_ASSOCIATED_PRODUCT_TYPE = "EODAG_DOES_NOT_SUPPORT_THIS_PRODUCT_TYPE"

    def setUp(self):
        super(TestEOProduct, self).setUp()
        self.output_dir = tempfile.mkdtemp()

    def tearDown(self):
        super(TestEOProduct, self).tearDown()
        if os.path.isdir(self.output_dir):
            shutil.rmtree(self.output_dir)

    def test_eoproduct_search_intersection_geom(self):
        """EOProduct search_intersection attr must be it's geom when no bbox_or_intersect param given"""  # noqa
        product = self._dummy_product()
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
        product = self._dummy_product(
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
        product = self._dummy_product(productType=self.NOT_ASSOCIATED_PRODUCT_TYPE)
        self.assertIsInstance(product.driver, NoDriver)

    def test_eoproduct_geointerface(self):
        """EOProduct must provide a geo-interface with a set of specific properties"""
        product = self._dummy_product()
        geo_interface = geojson.loads(geojson.dumps(product))
        self.assertEqual(geo_interface["type"], "Feature")
        self.assertEqual(
            geo_interface["geometry"],
            self._tuples_to_lists(geometry.mapping(self.geometry)),
        )
        properties = geo_interface["properties"]
        self.assertEqual(properties["eodag_provider"], self.provider)
        self.assertEqual(
            properties["eodag_search_intersection"],
            self._tuples_to_lists(geometry.mapping(product.search_intersection)),
        )
        self.assertEqual(properties["eodag_product_type"], self.product_type)

    def test_eoproduct_from_geointerface(self):
        """EOProduct must be build-able from its geo-interface"""
        product = self._dummy_product()
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
        product = self._dummy_product()
        product.properties["quicklook"] = None

        quicklook_file_path = product.get_quicklook()
        self.assertEqual(quicklook_file_path, "")

    def test_eoproduct_get_quicklook_http_error(self):
        """EOProduct.get_quicklook must return an empty string if there was an error during retrieval"""  # noqa
        product = self._dummy_product()
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
        product = self._dummy_product()
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
        product = self._dummy_product()
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
                response.headers = {"content-length": 2**5}

            def __enter__(response):
                return response

            def __exit__(response, *args):
                pass

            @staticmethod
            def iter_content(**kwargs):
                with io.BytesIO(b"a" * 2**5) as fh:
                    while True:
                        chunk = fh.read(kwargs["chunk_size"])
                        if not chunk:
                            break
                        yield chunk

            def raise_for_status(response):
                pass

        return Response()

    def test_eoproduct_download_http_default(self):
        """eoproduct.download must save the product at outputs_prefix and create a .downloaded dir"""  # noqa
        # Setup
        product = self._dummy_downloadable_product()
        try:
            with self.assertLogs(level="INFO") as cm:
                # Download
                product_dir_path = product.download()
                self.assertIn(
                    "Download url: %s" % product.remote_location, str(cm.output)
                )
                self.assertIn(
                    "Remote location of the product is still available", str(cm.output)
                )

            # Check that the mocked request was properly called.
            self.requests_http_get.assert_called_with(
                self.download_url,
                stream=True,
                auth=None,
                params={},
                timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
            )
            download_records_dir = pathlib.Path(product_dir_path).parent / ".downloaded"
            # A .downloaded folder should be created, including a text file that
            # lists the downloaded product by their url
            self.assertTrue(download_records_dir.is_dir())
            files_in_records_dir = list(download_records_dir.iterdir())
            self.assertEqual(len(files_in_records_dir), 1)
            records_file = files_in_records_dir[0]
            actual_download_url = records_file.read_text()
            self.assertEqual(actual_download_url, self.download_url)
            # Since extraction is True by default, check that the returned path is the
            # product's directory.
            self.assertTrue(os.path.isdir(product_dir_path))
            # Check that the ZIP file is still there
            product_dir_path = pathlib.Path(product_dir_path)
            product_zip = product_dir_path.parent / (product_dir_path.name + ".zip")
            self.assertTrue(zipfile.is_zipfile(product_zip))
            # check that product is not downloaded again
            with self.assertLogs(level="INFO") as cm:
                product.download()
                self.assertIn(
                    "Product already present on this platform", str(cm.output)
                )
            # check that product is not downloaded again even if location has not been updated
            product.location = product.remote_location
            with self.assertLogs(level="INFO") as cm:
                product.download()
                self.assertIn("Product already downloaded", str(cm.output))
                self.assertIn(
                    "Extraction cancelled, destination directory already exists",
                    str(cm.output),
                )
        finally:
            # Teardown
            self._clean_product(product_dir_path)

    def test_eoproduct_download_http_delete_archive(self):
        """eoproduct.download must delete the downloaded archive"""  # noqa
        # Setup
        product = self._dummy_downloadable_product(delete_archive=True)
        try:
            # Download
            product_dir_path = product.download()
            # Check that the mocked request was properly called.
            self.requests_http_get.assert_called_with(
                self.download_url,
                stream=True,
                auth=None,
                params={},
                timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
            )
            # Check that the product's directory exists.
            self.assertTrue(os.path.isdir(product_dir_path))
            # Check that the ZIP file was deleted there
            _product_dir_path = pathlib.Path(product_dir_path)
            product_zip = _product_dir_path.parent / (_product_dir_path.name + ".zip")
            self.assertFalse(os.path.exists(product_zip))
            # check that product is not downloaded again even if location has not been updated
            product.location = product.remote_location
            with self.assertLogs(level="INFO") as cm:
                product.download()
                self.assertIn("Product already downloaded", str(cm.output))
                self.assertIn(
                    "Extraction cancelled, destination directory already exists",
                    str(cm.output),
                )
        finally:
            # Teardown
            self._clean_product(product_dir_path)

    def test_eoproduct_download_http_extract(self):
        """eoproduct.download over must be able to extract a product"""
        # Setup
        product = self._dummy_downloadable_product(extract=True)
        try:
            # Download
            product_dir_path = product.download()
            product_dir_path = pathlib.Path(product_dir_path)
            # The returned path must be a directory.
            self.assertTrue(product_dir_path.is_dir())
            # Check that the extracted dir has at least one file, there are more
            # but that should be enough.
            self.assertGreaterEqual(len(list(product_dir_path.glob("**/*"))), 1)
            # The zip file should is around
            product_zip_file = product_dir_path.with_suffix(".SAFE.zip")
            self.assertTrue(product_zip_file.is_file)
        finally:
            # Teardown
            self._clean_product(product_dir_path)

    def test_eoproduct_download_http_dynamic_options(self):
        """eoproduct.download must accept the download options to be set automatically"""
        # Setup
        product = self._dummy_product()
        self._set_download_simulation()
        dl_config = config.PluginConfig.from_mapping(
            {"base_uri": "fake_base_uri", "outputs_prefix": "will_be_overriden"}
        )
        downloader = HTTPDownload(provider=self.provider, config=dl_config)
        product.register_downloader(downloader, None)

        output_dir_name = "_testeodag"
        output_dir = pathlib.Path(tempfile.gettempdir()) / output_dir_name
        try:
            if output_dir.is_dir():
                shutil.rmtree(output_dir)
            output_dir.mkdir()

            # Download
            product_dir_path = product.download(
                outputs_prefix=str(output_dir),
                extract=True,
                dl_url_params={"fakeparam": "dummy"},
            )
            # Check that dl_url_params are properly passed to the GET request
            self.requests_http_get.assert_called_with(
                self.download_url,
                stream=True,
                auth=None,
                params={"fakeparam": "dummy"},
                timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
            )
            # Check that "outputs_prefix" is respected.
            product_dir_path = pathlib.Path(product_dir_path)
            self.assertEqual(product_dir_path.parent.name, output_dir_name)
            # We've asked to extract the product so there should be a directory.
            self.assertTrue(product_dir_path.is_dir())
            # Check that the extracted dir has at least one file, there are more
            # but that should be enough.
            self.assertGreaterEqual(len(list(product_dir_path.glob("**/*"))), 1)
            # The downloaded zip file is still around
            product_zip_file = product_dir_path.with_suffix(".SAFE.zip")
            self.assertTrue(product_zip_file.is_file)
        finally:
            # Teardown (all the created files are within outputs_prefix)
            shutil.rmtree(output_dir)

    def test_eoproduct_download_progress_bar(self):
        """eoproduct.download must show a progress bar"""
        product = self._dummy_downloadable_product()
        product.properties["id"] = 12345
        progress_callback = ProgressCallback()

        # progress bar did not start
        self.assertEqual(progress_callback.n, 0)

        # extract=true would replace bar desc with extraction status
        product.download(
            progress_callback=progress_callback,
            outputs_prefix=self.output_dir,
            extract=False,
        )

        # should be product id cast to str
        self.assertEqual(progress_callback.desc, "12345")

        # progress bar finished
        self.assertEqual(progress_callback.n, progress_callback.total)
        self.assertGreater(progress_callback.total, 0)
