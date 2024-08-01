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

import contextlib
import io
import os
import random
import shutil
import tempfile
import unittest
from collections import OrderedDict, namedtuple
from io import StringIO
from unittest import mock  # PY3

from owslib.etree import etree
from owslib.ows import ExceptionReport
from shapely import wkt

from eodag import config
from eodag.api.product import EOProduct
from eodag.api.product.metadata_mapping import DEFAULT_METADATA_MAPPING
from eodag.plugins.download.http import HTTPDownload

jp = os.path.join
dirn = os.path.dirname

TEST_RESOURCES_PATH = jp(dirn(__file__), "resources")
RESOURCES_PATH = jp(dirn(__file__), "..", "eodag", "resources")


class EODagTestCase(unittest.TestCase):
    def setUp(self):
        self.provider = "creodias"
        self.download_url = (
            "https://zipper.creodias.eu/download/8ff765a2-e089-465d-a48f-cc27008a0962"
        )
        self.local_filename = (
            "S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911"
        )
        self.local_product_abspath = os.path.abspath(
            jp(TEST_RESOURCES_PATH, "products", self.local_filename)
        )
        self.local_product_as_archive_path = os.path.abspath(
            jp(
                TEST_RESOURCES_PATH,
                "products",
                "as_archive",
                "{}.zip".format(self.local_filename),
            )
        )
        self.local_band_file = jp(
            self.local_product_abspath,
            "GRANULE",
            "L1C_T31TDH_A013204_20180101T105435",
            "IMG_DATA",
            "T31TDH_20180101T105441_B01.jp2",
        )
        # A good valid geometry of a sentinel 2 product around Toulouse
        self.geometry = wkt.loads(
            "POLYGON((0.495928592903789 44.22596415476343, 1.870237286761489 "
            "44.24783068396879, "
            "1.888683014192297 43.25939191053712, 0.536772323136669 43.23826255332707, "
            "0.495928592903789 44.22596415476343))"
        )
        # The footprint requested
        self.footprint = {
            "lonmin": 1.3128662109375002,
            "latmin": 43.65197548731186,
            "lonmax": 1.6754150390625007,
            "latmax": 43.699651229671446,
        }
        self.product_type = "S2_MSI_L1C"
        self.platform = "S2A"
        self.instrument = "MSI"
        self.provider_id = "9deb7e78-9341-5530-8fe8-f81fd99c9f0f"

        self.eoproduct_props = {
            "id": "9deb7e78-9341-5530-8fe8-f81fd99c9f0f",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [0.495928592903789, 44.22596415476343],
                        [1.870237286761489, 44.24783068396879],
                        [1.888683014192297, 43.25939191053712],
                        [0.536772323136669, 43.23826255332707],
                        [0.495928592903789, 44.22596415476343],
                    ]
                ],
            },
            "productType": self.product_type,
            "platform": "Sentinel-2",
            "platformSerialIdentifier": self.platform,
            "instrument": self.instrument,
            "title": self.local_filename,
            "downloadLink": self.download_url,
        }
        # Put an empty string as value of properties which are not relevant for the
        # tests
        self.eoproduct_props.update(
            {
                key: ""
                for key in DEFAULT_METADATA_MAPPING
                if key not in self.eoproduct_props
            }
        )

        self.requests_http_get_patcher = mock.patch("requests.get", autospec=True)
        self.requests_request_patcher = mock.patch(
            "requests.Session.request", autospec=True
        )
        self.requests_http_get = self.requests_http_get_patcher.start()
        self.requests_request = self.requests_request_patcher.start()

    def tearDown(self):
        self.requests_http_get_patcher.stop()
        self.requests_request_patcher.stop()
        unwanted_product_dir = jp(
            dirn(self.local_product_as_archive_path), self.local_filename
        )
        if os.path.isdir(unwanted_product_dir):
            shutil.rmtree(unwanted_product_dir)

    def override_properties(self, **kwargs):
        """Overrides the properties with the values specified in the input parameters"""
        self.__dict__.update(
            {
                prop: new_value
                for prop, new_value in kwargs.items()
                if prop in self.__dict__ and new_value != self.__dict__[prop]
            }
        )

    def assertHttpGetCalledOnceWith(self, expected_url, expected_params=None):
        """Helper method for doing assertions on requests http get method mock"""
        self.assertEqual(self.requests_http_get.call_count, 1)
        actual_url = self.requests_http_get.call_args[0][0]
        self.assertEqual(actual_url, expected_url)
        if expected_params:
            actual_params = self.requests_http_get.call_args[1]["params"]
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

        Then this helper exists to transform all tuples in
        ``shapely_mapping['coordinates']`` to lists in-place, so
        that ``shapely_mapping['coordinates']`` can be compared to
        ``geojson_load['coordinates']``
        """
        shapely_mapping["coordinates"] = list(shapely_mapping["coordinates"])
        for i, coords in enumerate(shapely_mapping["coordinates"]):
            shapely_mapping["coordinates"][i] = list(coords)
            coords = shapely_mapping["coordinates"][i]
            for j, pair in enumerate(coords):

                # Coordinates rounded to 6 decimals by geojson lib
                # So rounding coordinates in order to be able to compare
                # coordinates after a `geojson.loads`
                # see https://github.com/jazzband/geojson.git
                pair = tuple(round(i, 6) for i in pair)

                coords[j] = list(pair)
        return shapely_mapping

    def compute_csw_records(self, mock_catalog, raise_error_for="", *args, **kwargs):
        if raise_error_for:
            for constraint in kwargs["constraints"]:
                if constraint.propertyname == raise_error_for:
                    exception_report = etree.parse(
                        StringIO(
                            '<ExceptionReport xmlns="http://www.opengis.net/ows/1.1" '
                            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation='  # noqa
                            '"http://schemas.opengis.net/ows/1.1.0/owsExceptionReport.xsd" version="1.0.0" language="en">'  # noqa
                            '<Exception exceptionCode="NoApplicableCode"><ExceptionText>Unknown exception</ExceptionText>'  # noqa
                            "</Exception></ExceptionReport>"
                        )
                    )
                    raise ExceptionReport(exception_report)
        bbox_wgs84 = random.choice(
            [
                None,
                (
                    self.footprint["lonmin"],
                    self.footprint["latmin"],
                    self.footprint["lonmax"],
                    self.footprint["latmax"],
                ),
            ]
        )
        Record = namedtuple(
            "CswRecord",
            [
                "identifier",
                "title",
                "creator",
                "publisher",
                "abstract",
                "subjects",
                "date",
                "references",
                "bbox_wgs84",
                "bbox",
                "xml",
            ],
        )
        BBox = namedtuple("BBox", ["minx", "miny", "maxx", "maxy", "crs"])
        Crs = namedtuple("Crs", ["code", "id"])
        mock_catalog.records = OrderedDict(
            {
                "id ent ifier": Record(
                    identifier="id ent ifier",
                    title="MyRecord",
                    creator="eodagUnitTests",
                    publisher="eodagUnitTests",
                    abstract="A dumb CSW record for testing purposes",
                    subjects=[],
                    date="",
                    references=[
                        {
                            "scheme": "WWW:DOWNLOAD-1.0-http--download",
                            "url": "http://www.url.eu/dl",
                        }
                    ],
                    bbox_wgs84=bbox_wgs84,
                    bbox=BBox(
                        minx=self.footprint["lonmin"],
                        miny=self.footprint["latmin"],
                        maxx=self.footprint["lonmax"],
                        maxy=self.footprint["latmax"],
                        crs=Crs(code=4326, id="EPSG"),
                    ),
                    xml="""
                    <csw:Record xmlns:csw="http://www.opengis.net/cat/csw/2.0.2"
                        xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dct="http://purl.org/dc/terms/"    # noqa
                        xmlns:gmd="http://www.isotc211.org/2005/gmd" xmlns:gml="http://www.opengis.net/gml"    # noqa
                        xmlns:ows="http://www.opengis.net/ows" xmlns:xs="http://www.w3.org/2001/XMLSchema"    # noqa
                        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
                        <dc:identifier>urn:x-gs:resource:localhost::52</dc:identifier>
                        <dc:title>S2 mosaic on Madrid</dc:title>
                        <dc:format/>
                        <dct:references scheme="WWW:LINK-1.0-http--link">
                            http://localhost:8000/admin/storm_csw/resource/52/change/
                        </dct:references>
                        <dct:modified>2017-05-05 13:02:35.548758+00:00</dct:modified>
                        <dct:abstract/>
                        <dc:date>2017-05-05 13:02:35.139807+00:00</dc:date>
                        <dc:creator> </dc:creator>
                        <dc:coverage/>
                        <ows:BoundingBox dimensions="2" crs="EPSG">
                        <ows:LowerCorner>40.405012373 -3.70433905592</ows:LowerCorner>
                        <ows:UpperCorner>40.420696583 -3.67011406889</ows:UpperCorner>
                        </ows:BoundingBox>
                    </csw:Record>
                """,
                )
            }
        )
        return mock.DEFAULT

    def _dummy_product(
        self, provider=None, properties=None, productType=None, **kwargs
    ):
        return EOProduct(
            self.provider if provider is None else provider,
            self.eoproduct_props if properties is None else properties,
            productType=self.product_type if productType is None else productType,
            **kwargs,
        )

    def _dummy_downloadable_product(
        self,
        product=None,
        base_uri=None,
        output_dir=None,
        extract=None,
        delete_archive=None,
    ):
        self._set_download_simulation()
        self.tmp_download_dir = tempfile.TemporaryDirectory()
        dl_config = config.PluginConfig.from_mapping(
            {
                "base_uri": "fake_base_uri" if base_uri is None else base_uri,
                "output_dir": self.tmp_download_dir.name
                if output_dir is None
                else output_dir,
                "extract": True if extract is None else extract,
                "delete_archive": False if delete_archive is None else delete_archive,
            }
        )
        downloader = HTTPDownload(provider=self.provider, config=dl_config)
        if product is None:
            product = self._dummy_product()
        product.register_downloader(downloader, None)
        return product

    def _clean_product(self, product_path):
        self.tmp_download_dir.cleanup()

    def _set_download_simulation(self):
        self.requests_request.return_value = self._download_response_archive()

    def _download_response_archive(self):
        class Response:
            """Emulation of a response to requests.get method for a zipped product"""

            def __init__(response):
                # Using a zipped product file
                with open(self.local_product_as_archive_path, "rb") as fh:
                    response.__zip_buffer = io.BytesIO(fh.read())
                cl = response.__zip_buffer.getbuffer().nbytes
                response.headers = {"content-length": cl}
                response.url = "http://foo.bar"

            def __enter__(response):
                return response

            def __exit__(response, *args):
                pass

            def iter_content(response, **kwargs):
                with response.__zip_buffer as fh:
                    while True:
                        chunk = fh.read(kwargs["chunk_size"])
                        if not chunk:
                            break
                        yield chunk

            def raise_for_status(response):
                pass

        return Response()


@contextlib.contextmanager
def temporary_environment(**env_vars):
    # Save the original environment variables
    original_env = os.environ.copy()

    # Set the new temporary environment variables
    os.environ.update(env_vars)

    try:
        yield
    finally:
        # Restore the original environment variables
        os.environ.clear()
        os.environ.update(original_env)
