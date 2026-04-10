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

import json
import logging
import os
import pathlib
import random
import shutil
import string
import tempfile
import time
import zipfile

import geojson
import responses
from lxml import html
from pystac import Item
from shapely import geometry

from eodag.config import PluginConfig
from tests import EODagTestBase
from tests.context import (
    DEFAULT_SHAPELY_GEOMETRY,
    NOT_AVAILABLE,
    USER_AGENT,
    AwsAuth,
    DatasetCreationError,
    DatasetDriver,
    Download,
    EOProduct,
    HTTPHeaderAuth,
    HttpQueryStringAuth,
    ProgressCallback,
    mock,
)


class TestEOProduct(EODagTestBase):
    NOT_ASSOCIATED_COLLECTION = "EODAG_DOES_NOT_SUPPORT_THIS_COLLECTION"

    def setUp(self):
        super(TestEOProduct, self).setUp()
        self.output_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.isdir(self.output_dir):
            shutil.rmtree(self.output_dir)
        responses.calls.reset()
        super(TestEOProduct, self).tearDown()

    def get_mock_downloader(self):
        """Returns a mock downloader with a default configuration."""
        mock_downloader = mock.MagicMock(
            spec_set=Download(provider=self.provider, config=None)
        )
        mock_downloader.config = PluginConfig.from_mapping(
            {"type": "Foo", "output_dir": self.output_dir}
        )
        return mock_downloader

    def test_eoproduct_search_intersection_geom(self):
        """EOProduct search_intersection attr must be it's geom when no bbox_or_intersect param given"""
        product = self._dummy_product()
        self.assertEqual(product.geometry, product.search_intersection)

    def test_eoproduct_default_geom(self):
        """EOProduct needs a geometry or can use confired eodag:default_geometry by default"""

        product_no_default_geom = self._dummy_product(
            properties={"geometry": NOT_AVAILABLE}
        )
        self.assertEqual(product_no_default_geom.geometry, DEFAULT_SHAPELY_GEOMETRY)

        product_default_geom = self._dummy_product(
            properties={
                "geometry": NOT_AVAILABLE,
                "eodag:default_geometry": (0, 0, 1, 1),
            }
        )
        self.assertEqual(product_default_geom.geometry.bounds, (0.0, 0.0, 1.0, 1.0))

    def test_eoproduct_search_intersection_none(self):
        """EOProduct search_intersection attr must be None if shapely.errors.GEOSException when intersecting"""
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

    def test_eoproduct_default_driver_unsupported_collection(self):
        """EOProduct driver attr must be set even if its collection is not supported"""
        product = self._dummy_product(collection=self.NOT_ASSOCIATED_COLLECTION)
        self.assertIsInstance(product.driver, DatasetDriver)

    def test_eoproduct_geointerface(self):
        """EOProduct must provide a geo-interface with a set of specific properties"""
        product = self._dummy_product()
        geo_interface = geojson.loads(geojson.dumps(product))
        self.assertEqual(geo_interface["type"], "Feature")
        self.assertEqual(
            geo_interface["geometry"],
            EODagTestBase._tuples_to_lists(geometry.mapping(self.geometry)),
        )
        properties = geo_interface["properties"]
        self.assertEqual(properties["eodag:provider"], self.provider)
        self.assertEqual(
            properties["eodag:search_intersection"],
            EODagTestBase._tuples_to_lists(
                geometry.mapping(product.search_intersection)
            ),
        )
        self.assertEqual(geo_interface["collection"], self.collection)

    def test_eoproduct_from_geointerface(self):
        """EOProduct must be build-able from its geo-interface"""
        product = self._dummy_product()
        same_product = EOProduct.from_dict(geojson.loads(geojson.dumps(product)))
        self.assertSequenceEqual(
            [
                product.provider,
                product.location,
                product.properties["title"],
                product.properties["instruments"],
                EODagTestBase._tuples_to_lists(geometry.mapping(product.geometry)),
                EODagTestBase._tuples_to_lists(
                    geometry.mapping(product.search_intersection)
                ),
                product.collection,
                product.properties["collection"],
                product.properties["platform"],
            ],
            [
                same_product.provider,
                same_product.location,
                same_product.properties["title"],
                same_product.properties["instruments"],
                EODagTestBase._tuples_to_lists(geometry.mapping(same_product.geometry)),
                EODagTestBase._tuples_to_lists(
                    geometry.mapping(same_product.search_intersection)
                ),
                same_product.collection,
                same_product.properties["collection"],
                same_product.properties["platform"],
            ],
        )

    @responses.activate
    def test_eoproduct_get_quicklook_no_quicklook_url(self):
        """EOProduct.get_quicklook must return an empty string if no quicklook property"""  # noqa
        responses.add(
            responses.GET,
            "https://fake.url.to/quicklook",
            body=b"",
            status=200,
            auto_calculate_content_length=True,
        )
        product = self._dummy_product()
        product.properties["eodag:quicklook"] = None

        quicklook_file_path = product.get_quicklook()
        self.assertEqual(quicklook_file_path, "")
        responses.assert_call_count("https://fake.url.to/quicklook", 0)

    @responses.activate
    def test_eoproduct_get_quicklook_http_error(self):
        """EOProduct.get_quicklook must return an empty string if there was an error during retrieval"""  # noqa
        product = self._dummy_product(
            properties=dict(
                self.eoproduct_props,
                **{
                    "eodag:quicklook": "https://fake.url.to/quicklook",
                },
            )
        )
        product.register_downloader(self.get_mock_downloader(), None)
        responses.add(
            responses.GET,
            "https://fake.url.to/quicklook",
            body=b"",
            status=404,
            auto_calculate_content_length=True,
        )
        # Download, and check request called
        quicklook_file_path = product.get_quicklook()
        self.assertEqual(quicklook_file_path, "")

    @responses.activate
    def test_eoproduct_get_quicklook_ok_without_auth(self):
        """EOProduct.get_quicklook must retrieve the quicklook without authentication."""  # noqa
        product = self._dummy_product()
        responses.add(
            responses.GET,
            "https://fake.url.to/quicklook",
            body=b"Quicklook content",
            status=200,
        )
        product.properties["eodag:quicklook"] = "https://fake.url.to/quicklook"
        product.register_downloader(self.get_mock_downloader(), None)

        with tempfile.TemporaryDirectory() as output_dir:
            quicklook_file_path = product.get_quicklook(output_dir=output_dir)
            responses.assert_call_count("https://fake.url.to/quicklook", 1)

            self.assertTrue(os.path.isfile(quicklook_file_path))
            with open(quicklook_file_path, "rb") as fd:
                content = fd.read()
                self.assertEqual(content, b"Quicklook content")

    @responses.activate
    def test_eoproduct_get_quicklook_ok(self):
        """EOProduct.get_quicklook must return the path to the successfully downloaded quicklook"""  # noqa
        product = self._dummy_product()

        responses.add(
            responses.GET,
            "https://fake.url.to/quicklook",
            body=b"Quicklook content",
            status=200,
        )
        product.properties["eodag:quicklook"] = "https://fake.url.to/quicklook"
        product.register_downloader(self.get_mock_downloader(), None)

        quicklook_file_path = product.get_quicklook()
        responses.assert_call_count("https://fake.url.to/quicklook", 1)

        self.assertEqual(
            os.path.basename(quicklook_file_path), product.properties["id"]
        )
        self.assertEqual(
            os.path.dirname(quicklook_file_path),
            os.path.join(self.output_dir, "quicklooks"),
        )
        os.remove(quicklook_file_path)

        # Test the same thing as above but with an explicit name given to the downloaded File
        quicklook_file_path = product.get_quicklook(filename="the_quicklook.png")
        responses.assert_call_count("https://fake.url.to/quicklook", 2)
        self.assertEqual(os.path.basename(quicklook_file_path), "the_quicklook.png")
        self.assertEqual(
            os.path.dirname(quicklook_file_path),
            os.path.join(self.output_dir, "quicklooks"),
        )
        os.remove(quicklook_file_path)

        # Overall teardown
        os.rmdir(os.path.dirname(quicklook_file_path))

    @responses.activate
    def test_eoproduct_get_quicklook_ok_existing(self):
        """EOProduct.get_quicklook must return the path to an already downloaded quicklook"""  # noqa

        # Tmp dir
        quicklook_dir = os.path.join(self.output_dir, "quicklooks")
        if not os.path.exists(quicklook_dir):
            os.mkdir(quicklook_dir)

        # Quicklook file
        quicklook_basename = "the_quicklook.png"
        existing_quicklook_file_path = os.path.join(quicklook_dir, quicklook_basename)
        with open(existing_quicklook_file_path, "wb") as fh:
            fh.write(b"content")

        product = self._dummy_product()
        product.properties["eodag:quicklook"] = "https://fake.url.to/quicklook"
        product.register_downloader(self.get_mock_downloader(), None)
        responses.add(
            responses.GET,
            "https://fake.url.to/quicklook",
            body=b"Quicklook content",
            status=200,
        )

        quicklook_file_path = product.get_quicklook(filename=quicklook_basename)
        responses.assert_call_count("https://fake.url.to/quicklook", 0)
        self.assertEqual(quicklook_file_path, existing_quicklook_file_path)
        os.remove(existing_quicklook_file_path)
        os.rmdir(quicklook_dir)

    @responses.activate
    def test_eoproduct_download_http_default(self):
        """eoproduct.download must save the product at output_dir and create a .downloaded dir"""  # noqa

        product = self._dummy_downloadable_product(extract=True)

        with self.assertLogs(level="INFO") as cm:
            # Download
            product_dir_path = product.download()
            responses.assert_call_count(product.properties["eodag:download_link"], 1)

            self.addCleanup(self._clean_product, product_dir_path)
            self.assertIn("Download url: %s" % product.remote_location, str(cm.output))
            self.assertIn(
                "Remote location of the product is still available", str(cm.output)
            )

        # Check that the mocked request was properly called.
        responses.assert_call_count(product.properties["eodag:download_link"], 1)

        # A .downloaded folder should be created, including a text file that
        download_records_dir = pathlib.Path(product_dir_path).parent / ".downloaded"
        self.assertTrue(download_records_dir.is_dir())

        # lists the downloaded product by their url
        files_in_records_dir = os.listdir(download_records_dir)
        self.assertEqual(len(files_in_records_dir), 1, "Expect one file")

        if len(files_in_records_dir) > 0:

            # Cache contains last url downloaded, check it match
            records_file = files_in_records_dir[0]
            actual_download_url = ""
            with open(os.path.join(download_records_dir, records_file), "r") as fd:
                actual_download_url = fd.read()
            self.assertEqual(
                actual_download_url, product.properties["eodag:download_link"]
            )

            # Since extraction is True by default, check that the returned path is the
            # product's directory.
            self.assertTrue(os.path.isdir(product_dir_path))

            # Check that the ZIP file is still there
            product_zip = "{}.zip".format(product_dir_path)
            self.assertTrue(zipfile.is_zipfile(product_zip))

            # Check that product is not downloaded again
            with self.assertLogs(level="INFO") as cm:
                product.download()
                self.assertIn(
                    "Product already present on this platform", str(cm.output)
                )

            # Check that product is not downloaded again even if location has not been updated
            product.location = product.remote_location
            with self.assertLogs(level="INFO") as cm:
                product.download()
                self.assertIn("Product already downloaded", str(cm.output))
                self.assertIn(
                    "Extraction cancelled, destination directory already exists",
                    str(cm.output),
                )

    @responses.activate
    def test_eoproduct_download_http_delete_archive(self):
        """eoproduct.download must delete the downloaded archive"""  # noqa

        product = self._dummy_downloadable_product(
            product=self._dummy_product(
                properties=dict(
                    self.eoproduct_props,
                    **{
                        "eodag:download_link": "http://example.com/foobar.zip",
                    },
                )
            ),
            extract=True,
            delete_archive=True,
        )
        product_dir_path = None

        try:

            # Download, and check that the mocked request was properly called.
            product_dir_path = product.download()
            responses.assert_call_count(product.properties["eodag:download_link"], 1)

            # Check that the product's directory exists.
            self.assertTrue(os.path.isdir(product_dir_path))

            # Check that the ZIP file was deleted there
            product_zip = "{}.zip".format(product_dir_path)
            self.assertFalse(os.path.isfile(product_zip))

            # Check that product is not downloaded again even if location has not been updated
            product.location = product.remote_location
            with self.assertLogs(level="INFO") as cm:
                product.download()
                product.download()
                self.assertIn("Product already downloaded", str(cm.output))
                self.assertIn(
                    "Extraction cancelled, destination directory already exists",
                    str(cm.output),
                )
        finally:
            # Teardown
            if product_dir_path is not None:
                self._clean_product(product_dir_path)

    @responses.activate
    def test_eoproduct_download_http_extract(self):
        """eoproduct.download over must be able to extract a product"""
        # Setup
        product = self._dummy_downloadable_product(extract=True)
        product_dir_path = product.download()

        # The returned path must be a directory.
        assert1 = os.path.isdir(product_dir_path)

        # Check that the extracted dir has at least one file, there are more
        # but that should be enough.
        assert2 = len(os.listdir(product_dir_path)) >= 1

        # The zip file should be around
        assert3 = os.path.isfile("{}.zip".format(product_dir_path))

        self._clean_product(product_dir_path)
        self.assertTrue(assert1)
        self.assertTrue(assert2)
        self.assertTrue(assert3)

    # Stream download

    @responses.activate
    def test_eoproduct_stream_download(self):
        """eoproduct.stream_download return a product file as StreamResponse"""  # noqa

        # Setup
        product = self._dummy_downloadable_product(
            product=self._dummy_product(
                properties=dict(
                    self.eoproduct_props,
                    **{"eodag:download_link": "http://example.com/foobar.zip"},
                )
            ),
            extract=False,
        )

        # Download, and check that the mocked request was properly called.
        product_stream = product.stream_download()
        responses.assert_call_count(product.properties["eodag:download_link"], 1)

        # Check response headers
        self.assertIn(
            product_stream.headers["Content-Type"],
            ["application/zip", "application/x-zip-compressed"],
        )

        # Download to tmp directory
        filepath = os.path.join(self.output_dir, product_stream.filename)
        with open(filepath, "wb") as fp:
            for chunk in product_stream.content:
                fp.write(chunk)

        # Check reference and result file has same size
        ref_stat = os.stat(self.local_product_as_archive_path)
        stat = os.stat(filepath)
        self.assertEqual(stat.st_size, ref_stat.st_size)
        self.assertTrue(zipfile.is_zipfile(filepath))

    @responses.activate
    def test_eoproduct_asset_stream_download(self):
        """eoproduct.assets[x].stream_download return a asset file as StreamResponse"""  # noqa
        # Setup
        product = self._dummy_downloadable_product(
            assets={
                "foo": {
                    "href": "http://example.com/foobar.jp2",
                    "title": "asset title",
                    "type": "image/jp2",
                }
            },
            extract=False,
        )

        # Download, and check that the mocked request was properly called.
        asset_stream = product.assets["foo"].stream_download()
        self.assertGreaterEqual(len(responses.calls), 1)

        # Check response headers
        self.assertEqual(asset_stream.headers["Content-Type"], "image/jp2")
        self.assertEqual(asset_stream.headers["Content-Length"], "2488555")

        # Download to tmp directory
        filepath = os.path.join(self.output_dir, asset_stream.filename)
        with open(filepath, "wb") as fp:
            for chunk in asset_stream.content:
                fp.write(chunk)

        self.assertTrue(os.path.isfile(filepath))
        stat = os.stat(filepath)
        self.assertEqual(stat.st_size, 2488555)

    # TODO: add a test on tarfiles extraction

    @responses.activate
    def test_eoproduct_download_http_dynamic_options(self):
        """eoproduct.download must accept the download options to be set automatically"""

        product = self._dummy_downloadable_product(
            product=self._dummy_product(
                properties=dict(
                    self.eoproduct_props,
                    **{"eodag:download_link": "http://example.com/foobar.zip"},
                )
            ),
            extract=True,
        )

        # Download, and check that dl_url_params are properly passed to the GET request
        product_dir_path = product.download(
            output_dir=self.output_dir,
            extract=True,
            delete_archive=False,
            dl_url_params={"fakeparam": "dummy"},
        )
        responses.assert_call_count("http://example.com/foobar.zip?fakeparam=dummy", 1)

        # Check that "output_dir" is respected.
        self.assertTrue(product_dir_path.startswith(self.output_dir))

        # We've asked to extract the product so there should be a directory.
        self.assertTrue(os.path.isdir(product_dir_path))

        # Check that the extracted dir has at least one file, there are more
        # but that should be enough.
        self.assertGreaterEqual(len(os.listdir(product_dir_path)), 1)

        # The downloaded zip file is still around
        product_zip_file = "{}.zip".format(product_dir_path)
        self.assertTrue(os.path.isfile(product_zip_file))

    @mock.patch("eodag.api.product._product.requests.get")
    def test_eoproduct_request_asset(self, mock_get):
        """EOProduct.request_asset must perform a GET request with storage options headers."""
        product = self._dummy_product()

        product.request_asset("https://example.com/zarr/.zmetadata")

        mock_get.assert_called_once_with(
            "https://example.com/zarr/.zmetadata",
            headers={},
            stream=True,
        )

    @mock.patch("eodag.api.product._product.requests.get")
    def test_eoproduct_request_asset_with_auth_headers(self, mock_get):
        """EOProduct.request_asset must forward authentication headers from get_storage_options."""
        product = self._dummy_product()
        # Mock downloader and auth
        mock_downloader = mock.MagicMock()
        mock_auth = mock.MagicMock()
        product.register_downloader(mock_downloader, mock_auth)

        # Mock get_storage_options to return auth headers
        product.get_storage_options = mock.MagicMock(
            return_value={
                "path": "https://example.com/zarr/.zmetadata",
                "headers": {"Authorization": "Bearer token123"},
            }
        )

        product.request_asset("https://example.com/zarr/.zmetadata")

        mock_get.assert_called_once_with(
            "https://example.com/zarr/.zmetadata",
            headers={"Authorization": "Bearer token123"},
            stream=True,
        )

    @responses.activate
    def test_eoproduct_download_progress_bar(self):
        """eoproduct.download must show a progress bar"""
        product = self._dummy_downloadable_product(
            product=self._dummy_product(
                properties=dict(
                    self.eoproduct_props,
                    **{
                        "id": 12345,
                        "title": "".join(random.choices(string.ascii_letters, k=10)),
                    },
                )
            ),
            extract=False,
        )
        progress_callback = ProgressCallback()

        # progress bar did not start
        self.assertEqual(progress_callback.n, 0)

        # extract=true would replace bar desc with extraction status
        product.download(
            progress_callback=progress_callback,
            output_dir=self.output_dir,
            extract=False,
        )

        # should be product id cast to str
        self.assertEqual(progress_callback.desc, "12345")

        # Progressbar need at least "progress_callback.mininterval" seconds, here 0.1 second
        # Wait 0.2 to be sure progress ends
        time.sleep(0.2)

        # progress bar finished
        self.assertEqual(progress_callback.initial, 0)
        self.assertEqual(progress_callback.total, 1)
        self.assertEqual(progress_callback.pos, 1)

    def test_eoproduct_register_downloader(self):
        """eoproduct.register_donwloader must set download and auth plugins"""
        product = self._dummy_product()

        self.assertIsNone(product.downloader)
        self.assertIsNone(product.downloader_auth)

        downloader = mock.MagicMock()
        downloader_auth = mock.MagicMock()

        product.register_downloader(downloader, downloader_auth)

        self.assertEqual(product.downloader, downloader)
        self.assertEqual(product.downloader_auth, downloader_auth)

    @responses.activate
    def test_eoproduct_register_downloader_resolve_ok(self):
        """eoproduct.register_donwloader must resolve locations and properties"""
        downloadable_product = self._dummy_downloadable_product(
            product=self._dummy_product(
                properties=dict(
                    self.eoproduct_props,
                    **{
                        "eodag:download_link": "%(base_uri)s/is/resolved",
                        "otherProperty": "%(output_dir)s/also/resolved",
                    },
                )
            ),
            extract=True,
        )
        self.assertEqual(
            downloadable_product.location,
            f"{downloadable_product.downloader.config.base_uri}/is/resolved",
        )
        self.assertEqual(
            downloadable_product.remote_location,
            f"{downloadable_product.downloader.config.base_uri}/is/resolved",
        )
        self.assertEqual(
            downloadable_product.properties["eodag:download_link"],
            f"{downloadable_product.downloader.config.base_uri}/is/resolved",
        )
        self.assertEqual(
            downloadable_product.properties["otherProperty"],
            f"{downloadable_product.downloader.config.output_dir}/also/resolved",
        )

    @responses.activate
    def test_eoproduct_register_downloader_resolve_ignored(self):
        """eoproduct.register_donwloader must ignore unresolvable locations and properties"""

        logger = logging.getLogger("eodag.product")
        with mock.patch.object(logger, "debug") as mock_debug:
            downloadable_product = self._dummy_downloadable_product(
                product=self._dummy_product(
                    properties=dict(
                        self.eoproduct_props,
                        **{
                            "eodag:download_link": "%(257B/cannot/be/resolved",
                            "otherProperty": "%(/%s/neither/resolved",
                        },
                    )
                ),
                extract=False,
            )
            self.assertEqual(downloadable_product.location, "%(257B/cannot/be/resolved")
            self.assertEqual(
                downloadable_product.remote_location, "%(257B/cannot/be/resolved"
            )
            self.assertEqual(
                downloadable_product.properties["eodag:download_link"],
                "%(257B/cannot/be/resolved",
            )
            self.assertEqual(
                downloadable_product.properties["otherProperty"],
                "%(/%s/neither/resolved",
            )

            needed_logs = [
                f"Could not resolve product.location ({downloadable_product.location})",
                f"Could not resolve product.remote_location ({downloadable_product.remote_location})",
                "Could not resolve eodag:download_link property (%s)"
                % downloadable_product.properties["eodag:download_link"],
                f"Could not resolve otherProperty property ({downloadable_product.properties['otherProperty']})",
            ]
            for needed_log in needed_logs:
                self.assertIn(needed_log, str(mock_debug.call_args_list))

    def test_eoproduct_repr_html(self):
        """eoproduct html repr must be correctly formatted"""
        product = self._dummy_product()
        product_repr = html.fromstring(product._repr_html_())
        self.assertIn("EOProduct", product_repr.xpath("//thead/tr/td")[0].text)

        # assets dict
        product.assets.update({"foo": {"href": "foo.href"}})
        assets_dict_repr = html.fromstring(product.assets._repr_html_())
        self.assertIn("AssetsDict", assets_dict_repr.xpath("//thead/tr/td")[0].text)

        # asset
        asset_repr = html.fromstring(product.assets._repr_html_())
        self.assertIn("Asset", asset_repr.xpath("//thead/tr/td")[0].text)

    def test_eoproduct_assets_get_values(self):
        """eoproduct.assets.get_values must return the expected values"""
        product = self._dummy_product()
        product.assets.update(
            {
                "foo": {"href": "foo.href"},
                "fooo": {"href": "fooo.href"},
                "foo?o,o": {"href": "foooo.href"},
            }
        )
        self.assertEqual(len(product.assets.get_values()), 3)
        self.assertEqual(len(product.assets.get_values("foo.*")), 3)
        self.assertEqual(len(product.assets.get_values("foo")), 1)
        self.assertEqual(product.assets.get_values("foo")[0]["href"], "foo.href")
        self.assertEqual(len(product.assets.get_values("foo?o,o")), 1)
        self.assertEqual(product.assets.get_values("foo?o,o")[0]["href"], "foooo.href")

    def test_eoproduct_sorted_properties(self):
        """eoproduct.properties must be sorted"""
        product = self._dummy_product(
            properties={
                "geometry": "POINT (0 0)",
                "b_property": "b_value",
                "a_property": "a_value",
                "c_property": "c_value",
                "foo:property": "foo_value",
                "eodag:z_property": "z_value",
                "eodag:y_property": "y_value",
            }
        )
        self.assertListEqual(
            list(product.properties.keys()),
            [
                "a_property",
                "b_property",
                "c_property",
                "datetime",
                "eodag:y_property",
                "eodag:z_property",
                "foo:property",
            ],
        )

    def test_eoproduct_none_properties(self):
        """eoproduct none properties must skipped"""
        product = self._dummy_product(
            properties={
                "geometry": "POINT (0 0)",
                "b_property": "b_value",
                "a_property": None,
            }
        )
        self.assertDictEqual(
            product.properties,
            {
                "b_property": "b_value",
                "datetime": None,
            },
        )

    def test_eoproduct_serialize(self):
        """eoproduct.as_dict must include the required STAC extensions"""
        product = self._dummy_product()
        product.properties["grid:code"] = "MGRS-31TCJ"
        product.properties["eo:cloud_cover"] = "bad-formatted"
        product.assets.update(
            {
                "foo": {
                    "href": "https://example.com/asset/foo.tif",
                    "title": "foo asset",
                    "type": "image/tiff",
                    "proj:shape": [3, 343, 343],
                    "mgrs:utm_zone": "also-bad-formatted",
                }
            }
        )
        prod_dict = product.as_dict()
        # well formatted properties must be present
        self.assertEqual(prod_dict["properties"]["grid:code"], "MGRS-31TCJ")
        self.assertEqual(prod_dict["assets"]["foo"]["proj:shape"], [3, 343, 343])
        self.assertTrue(
            any("grid" in ext for ext in prod_dict.get("stac_extensions", []))
        )
        self.assertTrue(
            any("proj" in ext for ext in prod_dict.get("stac_extensions", []))
        )
        # badly formatted properties must be skipped
        self.assertNotIn("eo:cloud_cover", prod_dict["properties"])
        self.assertNotIn("mgrs:utm_zone", prod_dict["assets"]["foo"])
        self.assertFalse(
            any("eo" in ext for ext in prod_dict.get("stac_extensions", []))
        )
        self.assertFalse(
            any("mgrs" in ext for ext in prod_dict.get("stac_extensions", []))
        )

    def test_eoproduct_as_pystac_object(self):
        """eoproduct.as_pystac_object must return a pystac.Item"""
        product = self._dummy_product(
            properties={"id": "dummy_id", "datetime": "2021-01-01T00:00:00Z"}
        )
        pystac_item = product.as_pystac_object()
        self.assertIsInstance(pystac_item, Item)
        pystac_item.validate()

    def test_eoproduct_from_pystac(self):
        """eoproduct.from_pystac must return an EOProduct instance from a pystac.Item"""
        product = self._dummy_product(
            properties={"id": "dummy_id", "datetime": "2021-01-01T00:00:00Z"}
        )
        pystac_item = Item.from_dict(product.as_dict())
        product_from_pystac = EOProduct.from_pystac(pystac_item)
        self.assertIsInstance(product_from_pystac, EOProduct)

    def test_get_storage_options_http_headers(self):
        """get_storage_options should be adapted to the provider config"""
        product = EOProduct(
            self.provider, self.eoproduct_props, collection=self.collection
        )
        # http headers auth
        product.register_downloader(
            Download("foo", PluginConfig()),
            HTTPHeaderAuth(
                "foo",
                PluginConfig.from_mapping(
                    {
                        "type": "Download",
                        "credentials": {"apikey": "foo"},
                        "headers": {"X-API-Key": "{apikey}"},
                    }
                ),
            ),
        )
        self.assertDictEqual(
            product.get_storage_options(),
            {
                "path": self.download_url,
                "headers": {"X-API-Key": "foo", **USER_AGENT},
            },
        )

    def test_get_storage_options_http_no_auth(self):
        """get_storage_options should return path when no auth"""
        product = EOProduct(
            self.provider, self.eoproduct_props, collection=self.collection
        )
        # http headers auth
        product.register_downloader(
            Download("foo", PluginConfig()),
            None,
        )
        self.assertDictEqual(
            product.get_storage_options(),
            {
                "path": self.download_url,
            },
        )

    def test_get_storage_options_http_qs(self):
        """get_storage_options should be adapted to the provider config"""
        product = EOProduct(
            self.provider, self.eoproduct_props, collection=self.collection
        )
        # http qs auth
        product.register_downloader(
            Download("foo", PluginConfig()),
            HttpQueryStringAuth(
                "foo",
                PluginConfig.from_mapping(
                    {
                        "type": "Download",
                        "credentials": {"apikey": "foo"},
                    }
                ),
            ),
        )
        self.assertDictEqual(
            product.get_storage_options(),
            {
                "path": f"{self.download_url}?apikey=foo",
                "headers": USER_AGENT,
            },
        )

    @mock.patch("eodag.api.product._product.ServiceResource", new=object)
    def test_get_storage_options_s3_credentials_endpoint(self):
        """get_storage_options should be adapted to the provider config using s3 credentials and endpoint"""
        product = EOProduct(
            self.provider, self.eoproduct_props, collection=self.collection
        )
        auth_plugin = AwsAuth(
            "foo",
            PluginConfig.from_mapping(
                {
                    "type": "Authentication",
                    "s3_endpoint": "http://foo.bar",
                    "credentials": {
                        "aws_access_key_id": "foo",
                        "aws_secret_access_key": "bar",
                        "aws_session_token": "baz",
                    },
                    "requester_pays": True,
                }
            ),
        )
        auth_plugin.s3_session = mock.MagicMock()
        auth_plugin.s3_session.get_credentials.return_value = mock.Mock(
            access_key="foo",
            secret_key="bar",
            token="baz",
        )
        auth_plugin.authenticate = mock.MagicMock(return_value=object())
        product.register_downloader(Download("foo", PluginConfig()), auth_plugin)
        self.assertDictEqual(
            product.get_storage_options(),
            {
                "path": self.download_url,
                "key": "foo",
                "secret": "bar",
                "token": "baz",
                "client_kwargs": {"endpoint_url": "http://foo.bar"},
                "requester_pays": True,
            },
        )

    @mock.patch("eodag.api.product._product.ServiceResource", new=object)
    def test_get_storage_options_s3_credentials(self):
        """get_storage_options should be adapted to the provider config using s3 credentials"""
        product = EOProduct(
            self.provider, self.eoproduct_props, collection=self.collection
        )
        auth_plugin = AwsAuth(
            "foo",
            PluginConfig.from_mapping(
                {
                    "type": "Authentication",
                    "credentials": {
                        "aws_access_key_id": "foo",
                        "aws_secret_access_key": "bar",
                        "aws_session_token": "baz",
                    },
                }
            ),
        )
        auth_plugin.s3_session = mock.MagicMock()
        auth_plugin.s3_session.get_credentials.return_value = mock.Mock(
            access_key="foo",
            secret_key="bar",
            token="baz",
        )
        auth_plugin.authenticate = mock.MagicMock(return_value=object())
        product.register_downloader(Download("foo", PluginConfig()), auth_plugin)
        self.assertDictEqual(
            product.get_storage_options(),
            {
                "path": self.download_url,
                "key": "foo",
                "secret": "bar",
                "token": "baz",
            },
        )

    @mock.patch("eodag.api.product._product.ServiceResource", new=object)
    def test_get_storage_options_s3_anon(self):
        """get_storage_options should be adapted to the provider config using anonymous s3 access"""
        product = EOProduct(
            self.provider, self.eoproduct_props, collection=self.collection
        )
        auth_plugin = AwsAuth(
            "foo",
            PluginConfig.from_mapping(
                {"type": "Authentication", "requester_pays": True}
            ),
        )
        auth_plugin.s3_session = mock.MagicMock()
        auth_plugin.s3_session.get_credentials.return_value = None
        auth_plugin.authenticate = mock.MagicMock(return_value=object())
        product.register_downloader(Download("foo", PluginConfig()), auth_plugin)
        self.assertDictEqual(
            product.get_storage_options(),
            {
                "path": self.download_url,
                "anon": True,
            },
        )

    def test_get_storage_options_error(self):
        """get_storage_options should raise when the asset key is missing"""
        product = EOProduct(
            self.provider, self.eoproduct_props, collection=self.collection
        )
        product.downloader = mock.MagicMock()
        with self.assertRaises(
            DatasetCreationError, msg=f"foo not found in {product} assets"
        ):
            product.get_storage_options(asset_key="foo")
