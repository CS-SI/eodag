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
import os
import shutil
import tempfile
import time
import zipfile

import geojson
import responses
from lxml import html
from pystac import Item
from shapely import geometry

from eodag.api.product import EOProduct
from eodag.api.product.drivers import DatasetDriver
from eodag.api.product.metadata_mapping import NOT_AVAILABLE
from eodag.utils import DEFAULT_SHAPELY_GEOMETRY, ProgressCallback
from eodag.utils.exceptions import DownloadError
from tests.utils import EODagTestBase


class TestEOProduct(EODagTestBase):

    NOT_ASSOCIATED_COLLECTION = "EODAG_DOES_NOT_SUPPORT_THIS_COLLECTION"

    def create_zip_file(self, local_path: str, prepath: str = ""):

        files: dict[str, str] = {
            "file1.txt": "this is a text content",
            "config.json": json.dumps(
                {
                    "type": "Download",
                    "extract": True,
                    "archive_depth": 1,
                    "output_extension": ".json",
                    "max_workers": 4,
                    "ssl_verify": True,
                }
            ),
            "404.html": "<!doctype html><body><h1>404 Not found</h1><hr /></body></html>",
        }
        with zipfile.ZipFile(local_path, "w") as zip:
            for filename in files:
                zip.writestr(
                    "{}{}".format(prepath, filename),
                    files[filename],
                    zipfile.ZIP_DEFLATED,
                )

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
        quicklook_file_path = product.get_quicklook()
        self.assertEqual(quicklook_file_path, None)
        responses.assert_call_count("https://fake.url.to/quicklook", 0)

    @responses.activate
    def test_eoproduct_get_quicklook_http_error(self):
        """EOProduct.get_quicklook must return an empty string if there was an error during retrieval"""  # noqa
        responses.add(
            responses.GET,
            "https://fake.url.to/quicklook",
            body=b"",
            status=403,
            auto_calculate_content_length=True,
        )
        product = self._dummy_product()
        product.assets.update(
            {
                "quicklook": {
                    "title": "quicklook",
                    "href": "https://fake.url.to/quicklook",
                    "type": "image/png",
                }
            }
        )
        # Download, and check request called
        try:
            _ = product.get_quicklook(no_cache=True)
            self.fail("Except download error")
        except DownloadError:
            pass

    @responses.activate
    def test_eoproduct_get_quicklook_ok_without_auth(self):
        """EOProduct.get_quicklook must retrieve the quicklook without authentication."""  # noqa
        responses.add(
            responses.GET,
            "https://fake.url.to/quicklook",
            body=b"Quicklook content",
            status=200,
        )
        product = self._dummy_product()
        product.assets.update(
            {
                "quicklook": {
                    "title": "quicklook",
                    "href": "https://fake.url.to/quicklook",
                    "type": "image/png",
                }
            }
        )

        with tempfile.TemporaryDirectory() as output_dir:
            quicklook_file_path = product.get_quicklook(
                no_cache=True, output_dir=output_dir
            )
            responses.assert_call_count("https://fake.url.to/quicklook", 1)

            self.assertTrue(os.path.isfile(quicklook_file_path))
            with open(quicklook_file_path, "rb") as fd:
                content = fd.read()
                self.assertEqual(content, b"Quicklook content")

    @responses.activate
    def test_eoproduct_get_quicklook_ok(self):
        """EOProduct.get_quicklook must return the path to the successfully downloaded quicklook"""  # noqa
        product = self._dummy_product()
        product.assets.update(
            {
                "quicklook": {
                    "title": "quicklook",
                    "href": "https://fake.url.to/quicklook",
                    "type": "image/png",
                }
            }
        )
        responses.add(
            responses.GET,
            "https://fake.url.to/quicklook",
            body=b"Quicklook content",
            status=200,
        )
        quicklook_file_path = product.get_quicklook(no_cache=True)
        responses.assert_call_count("https://fake.url.to/quicklook", 1)
        self.assertTrue(os.path.isfile(quicklook_file_path))
        os.remove(quicklook_file_path)

    @responses.activate
    def test_eoproduct_get_quicklook_ok_existing(self):
        """EOProduct.get_quicklook must return the path to an already downloaded quicklook"""  # noqa
        product = self._dummy_product()
        product.assets.update(
            {
                "quicklook": {
                    "title": "quicklook",
                    "href": "https://fake.url.to/quicklook",
                    "type": "image/png",
                }
            }
        )
        responses.add(
            responses.GET,
            "https://fake.url.to/quicklook",
            body=b"Quicklook content",
            status=200,
        )
        _ = product.get_quicklook(no_cache=True)
        responses.assert_call_count("https://fake.url.to/quicklook", 1)

        _ = product.get_quicklook(no_cache=False)
        responses.assert_call_count("https://fake.url.to/quicklook", 1)

    @responses.activate
    def test_eoproduct_download_http_default(self):
        """eoproduct.download must save the product at output_dir and create a .downloaded dir"""  # noqa

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = os.path.join(tmp_dir, "output")
            os.makedirs(output_dir)

            archive_url = "https://fake.url.to/data.txt"

            product = self._dummy_product()
            product.assets.update(
                {
                    "download_link": {
                        "title": "download_link",
                        "href": archive_url,
                        "type": "text/plain",
                    }
                }
            )
            responses.add(
                responses.GET,
                archive_url,
                body=b"Quicklook content",
                status=200,
            )

            product_dir_path = product.download(no_cache=True, output_dir=output_dir)
            self.assertGreaterEqual(len(product_dir_path), 1)
            statement_dir = os.path.normpath(
                os.path.join(os.path.dirname(product_dir_path[0]), "..", ".downloaded")
            )
            self.assertTrue(os.path.isdir(statement_dir))

            # check statements generated
            files = os.listdir(statement_dir)
            self.assertEqual(len(files), 1)
            statement = None
            if len(files) > 0:
                path = os.path.join(statement_dir, files[0])
                with open(path, "r") as fd:
                    statement = json.loads(fd.read())

            self.assertEqual(statement.get("href"), archive_url)
            self.assertEqual(statement.get("local_path"), product_dir_path[0])

            shutil.rmtree(output_dir)

    @responses.activate
    def test_eoproduct_download_http_extract_archive(self):
        """eoproduct.download must delete the downloaded archive"""  # noqa

        with tempfile.TemporaryDirectory() as tmp_dir:
            local_dir = os.path.join(tmp_dir, "local")
            os.makedirs(local_dir)
            output_dir = os.path.join(tmp_dir, "output")
            os.makedirs(output_dir)
            remote_path = os.path.join(local_dir, "archive.zip")
            self.create_zip_file(remote_path)
            with open(remote_path, "rb") as fd:
                content = fd.read()
            archive_url = "https://fake.url.to/archive.zip"

            responses.add(
                responses.GET,
                archive_url,
                body=content,
                status=200,
            )

            product = self._dummy_product()
            product.assets.update(
                {
                    "download_link": {
                        "title": "download_link",
                        "href": archive_url,
                        "type": "application/zip",
                    }
                }
            )
            product_dir_path = product.download(
                no_cache=True, extract=True, delete_archive=False, output_dir=output_dir
            )
            self.assertEqual(len(product_dir_path), 1)
            product_dir_path = product_dir_path[0]
            self.assertTrue(os.path.isdir(product_dir_path))
            self.assertTrue(os.path.isfile("{}.zip".format(product_dir_path)))

            shutil.rmtree(local_dir)
            shutil.rmtree(output_dir)

    @responses.activate
    def test_eoproduct_download_http_delete_archive(self):
        """eoproduct.download must delete the downloaded archive"""  # noqa
        with tempfile.TemporaryDirectory() as tmp_dir:
            local_dir = os.path.join(tmp_dir, "local")
            os.makedirs(local_dir)
            output_dir = os.path.join(tmp_dir, "output")
            os.makedirs(output_dir)
            remote_path = os.path.join(local_dir, "archive.zip")
            self.create_zip_file(remote_path)
            with open(remote_path, "rb") as fd:
                content = fd.read()
            archive_url = "https://fake.url.to/archive.zip"

            responses.add(
                responses.GET,
                archive_url,
                body=content,
                status=200,
            )

            product = self._dummy_product()
            product.assets.update(
                {
                    "download_link": {
                        "title": "download_link",
                        "href": archive_url,
                        "type": "application/zip",
                    }
                }
            )
            product_dir_path = product.download(
                no_cache=True, extract=True, delete_archive=True, output_dir=output_dir
            )
            self.assertEqual(len(product_dir_path), 1)
            product_dir_path = product_dir_path[0]
            self.assertTrue(os.path.isdir(product_dir_path))
            self.assertFalse(os.path.isfile("{}.zip".format(product_dir_path)))

            shutil.rmtree(local_dir)
            shutil.rmtree(output_dir)

    @responses.activate
    def test_eoproduct_download_http_extract(self):
        """eoproduct.download over must be able to extract a product"""

        with tempfile.TemporaryDirectory() as tmp_dir:
            local_dir = os.path.join(tmp_dir, "local")
            os.makedirs(local_dir)
            output_dir = os.path.join(tmp_dir, "output")
            os.makedirs(output_dir)
            remote_path = os.path.join(local_dir, "archive.zip")
            self.create_zip_file(remote_path)
            with open(remote_path, "rb") as fd:
                content = fd.read()
            archive_url = "https://fake.url.to/archive.zip"

            responses.add(
                responses.GET,
                archive_url,
                body=content,
                status=200,
            )

            product = self._dummy_product()
            product.assets.update(
                {
                    "download_link": {
                        "title": "download_link",
                        "href": archive_url,
                        "type": "application/zip",
                    }
                }
            )
            product_dir_path = product.download(
                no_cache=True, extract=True, delete_archive=True, output_dir=output_dir
            )
            self.assertEqual(len(product_dir_path), 1)
            product_dir_path = product_dir_path[0]
            self.assertTrue(os.path.isdir(product_dir_path))
            self.assertFalse(os.path.isfile("{}.zip".format(product_dir_path)))

            shutil.rmtree(local_dir)
            shutil.rmtree(output_dir)

    # Stream download

    @responses.activate
    def test_eoproduct_stream_download(self):
        """eoproduct.stream_download return a product file as StreamResponse"""  # noqa
        with tempfile.TemporaryDirectory() as tmp_dir:
            local_dir = os.path.join(tmp_dir, "local")
            os.makedirs(local_dir)
            output_dir = os.path.join(tmp_dir, "output")
            os.makedirs(output_dir)

            remote_path = os.path.join(local_dir, "archive.zip")
            self.create_zip_file(remote_path)
            with open(remote_path, "rb") as fd:
                content = fd.read()
            archive_url = "https://fake.url.to/archive.zip"

            responses.add(
                responses.GET,
                archive_url,
                body=content,
                status=200,
            )
            product = self._dummy_product()
            product.assets.update(
                {
                    "download_link": {
                        "title": "download_link",
                        "href": archive_url,
                        "type": "application/zip",
                    }
                }
            )

            stream = product.stream_download(no_cache=True, output_dir=output_dir)
            local_path = os.path.join(local_dir, "local-archive.zip")
            with open(local_path, "wb") as fd:
                for chunk in stream.content:
                    fd.write(chunk)
            stat = os.stat(local_path)
            self.assertIn(stat.st_size, [489, 493])  # windows could add 3 bytes BOM
            self.assertTrue(zipfile.is_zipfile(local_path))

            shutil.rmtree(local_dir)
            shutil.rmtree(output_dir)

    @responses.activate
    def test_eoproduct_download_http_dynamic_options(self):
        """eoproduct.download must accept the download options to be set automatically"""

        with tempfile.TemporaryDirectory() as tmp_dir:
            local_dir = os.path.join(tmp_dir, "local")
            os.makedirs(local_dir)
            output_dir = os.path.join(tmp_dir, "output")
            os.makedirs(output_dir)
            remote_path = os.path.join(local_dir, "archive.zip")
            self.create_zip_file(remote_path)
            with open(remote_path, "rb") as fd:
                content = fd.read()
            archive_url = "https://fake.url.to/archive.zip"

            responses.add(
                responses.GET,
                archive_url,
                body=content,
                status=200,
            )
            product = self._dummy_product()
            product.assets.update(
                {
                    "download_link": {
                        "title": "download_link",
                        "href": archive_url,
                        "type": "application/zip",
                    }
                }
            )

            paths = product.download(
                no_cache=True,
                output_dir=output_dir,
                extract=True,
                delete_archive=False,
                dl_url_params={"fakeparam": "dummy"},
            )
            responses.assert_call_count("{}?fakeparam=dummy".format(archive_url), 1)
            self.assertEqual(len(paths), 1)

            shutil.rmtree(local_dir)
            shutil.rmtree(output_dir)

    @responses.activate
    def test_eoproduct_download_progress_bar(self):
        """eoproduct.download must show a progress bar"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            local_dir = os.path.join(tmp_dir, "local")
            os.makedirs(local_dir)
            output_dir = os.path.join(tmp_dir, "output")
            os.makedirs(output_dir)
            remote_path = os.path.join(local_dir, "archive.zip")
            self.create_zip_file(remote_path)
            with open(remote_path, "rb") as fd:
                content = fd.read()
            archive_url = "https://fake.url.to/archive.zip"

            responses.add(
                responses.GET,
                archive_url,
                body=content,
                status=200,
            )
            product = self._dummy_product()
            product.assets.update(
                {
                    "download_link": {
                        "title": "download_link",
                        "href": archive_url,
                        "type": "application/zip",
                    }
                }
            )

            paths = product.download(
                no_cache=True,
                output_dir=output_dir,
                extract=True,
                delete_archive=False,
                dl_url_params={"fakeparam": "dummy"},
            )
            responses.assert_call_count("{}?fakeparam=dummy".format(archive_url), 1)
            self.assertEqual(len(paths), 1)

            shutil.rmtree(local_dir)
            shutil.rmtree(output_dir)

        progress_callback = ProgressCallback()

        # progress bar did not start
        self.assertEqual(progress_callback.n, 0)

        # extract=true would replace bar desc with extraction status
        product.download(
            progress_callback=progress_callback,
            output_dir=output_dir,
            extract=False,
        )

        # should be product id cast to str
        self.assertEqual(
            progress_callback.desc, "9deb7e78-9341-5530-8fe8-f81fd99c9f0f:download_link"
        )

        # Progressbar need at least "progress_callback.mininterval" seconds, here 0.1 second
        # Wait 0.2 to be sure progress ends
        time.sleep(0.2)

        # progress bar finished
        self.assertEqual(progress_callback.initial, 0)
        self.assertEqual(progress_callback.total, 1)
        self.assertEqual(progress_callback.pos, 1)

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
        """eoproduct none properties must be kept"""
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
                "a_property": None,
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
            any("/grid/" in ext for ext in prod_dict.get("stac_extensions", []))
        )
        self.assertTrue(
            any("/projection/" in ext for ext in prod_dict.get("stac_extensions", []))
        )
        # badly formatted properties must be skipped
        self.assertNotIn("eo:cloud_cover", prod_dict["properties"])
        self.assertNotIn("mgrs:utm_zone", prod_dict["assets"]["foo"])
        self.assertFalse(
            any("/eo/" in ext for ext in prod_dict.get("stac_extensions", []))
        )
        self.assertFalse(
            any("/mgrs/" in ext for ext in prod_dict.get("stac_extensions", []))
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
