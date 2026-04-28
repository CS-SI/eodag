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
from unittest import mock
from unittest.mock import call

import boto3
import botocore
import requests
from botocore.stub import Stubber

from eodag.utils import deepcopy, get_geometry_from_various
from eodag.utils.exceptions import RequestError, UnsupportedCollection
from tests.units.search_plugins.base import BaseSearchPluginTest


class TestSearchPluginCopMarineSearch(BaseSearchPluginTest):
    def setUp(self):
        super(TestSearchPluginCopMarineSearch, self).setUp()
        self.provider = "cop_marine"
        self.product_data = {
            "id": "PRODUCT_A",
            "type": "Collection",
            "stac_version": "1.0.0",
            "stac_extensions": [
                "https://stac-extensions.github.io/scientific/v1.0.0/schema.json"
            ],
            "title": "Product A",
            "description": "A nice description",
            "license": "other",
            "providers": [
                {"name": "CLS (France)", "roles": ["producer"]},
                {
                    "name": "Copernicus Marine Service",
                    "roles": ["host", "processor"],
                    "url": "https://marine.copernicus.eu",
                },
            ],
            "keywords": [
                "oceanographic-geographical-features",
                "satellite-observation",
                "level-3",
            ],
            "links": [
                {
                    "rel": "root",
                    "href": "../catalog.stac.json",
                    "title": "Copernicus Marine Data Store",
                    "type": "application/json",
                },
                {
                    "rel": "parent",
                    "href": "../catalog.stac.json",
                    "title": "Copernicus Marine Data Store",
                    "type": "application/json",
                },
                {
                    "rel": "item",
                    "href": "dataset-number-one/dataset.stac.json",
                    "title": "dataset-number-one",
                    "type": "application/json",
                },
                {
                    "rel": "item",
                    "href": "dataset-number-two/dataset.stac.json",
                    "title": "dataset-number-two",
                    "type": "application/json",
                },
                {
                    "rel": "license",
                    "href": "https://marine.copernicus.eu/user-corner/service-commitments-and-licence",
                    "title": "Copernicus Marine Service Commitments and Licence",
                    "type": "text/html",
                },
            ],
            "extent": {
                "temporal": {
                    "interval": [
                        ["1970-01-01T00:00:00.000000Z", "1970-01-01T00:00:00.000000Z"]
                    ]
                },
                "spatial": {"bbox": [[0.0, 0.0, 0.0, 0.0]]},
            },
            "assets": {
                "thumbnail": {
                    "href": "https://catalogue.marine.copernicus.eu/documents/IMG/WAVE_GLO_PHY_SPC_L3_MY_014_006.png",
                    "type": "image/png",
                    "roles": ["thumbnail"],
                    "title": "GLOBAL OCEAN L3 SPECTRAL PARAMETERS FROM REPROCESSED SATELLITE MEASUREMENTS thumbnail",
                }
            },
            "properties": {
                "altId": "450bf368-2407-4c2c-8535-f215a4cda963",
                "created": "2021-04-23",
                "modifiedDate": "2021-04-23",
                "contacts": [
                    {
                        "name": "Jim Gabriel",
                        "organisationName": "Heaven Inc",
                        "responsiblePartyRole": "custodian",
                        "email": "jim.gabriel@heaven.com",
                    }
                ],
                "projection": "WGS84 / Simple Mercator (EPSG:41001)",
                "formats": ["NetCDF-4"],
                "featureTypes": ["Swath", "Trajectory"],
                "tempResolutions": ["Instantaneous"],
                "rank": 15015,
                "areas": [
                    "Global Ocean",
                ],
                "times": ["Past"],
                "sources": ["Satellite observations"],
                "colors": ["Blue Ocean"],
                "directives": [
                    "Water Framework Directive (WFD)",
                    "Maritime Spatial Planning (MSP)",
                ],
                "crs": "EPSG:3857",
                "isStaging": False,
                "admp_updated": "2023-11-07T16:54:54.688320Z",
            },
            "sci:doi": "10.48670/moi-00174",
        }
        self.dataset1_data = {
            "id": "dataset-number-one",
            "type": "Feature",
            "stac_version": "1.0.0",
            "stac_extensions": [
                "https://stac-extensions.github.io/datacube/v2.1.0/schema.json"
            ],
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]
                ],
            },
            "bbox": [0.0, 0.0, 0.0, 0.0],
            "properties": {
                "title": "dataset-number-one",
                "datetime": "1970-01-01T00:00:00.000000Z",
            },
            "links": [
                {
                    "rel": "root",
                    "href": "../../catalog.stac.json",
                    "title": "Copernicus Marine Data Store",
                    "type": "application/json",
                },
                {
                    "rel": "parent",
                    "href": "../product.stac.json",
                    "title": "PRODUCT A",
                    "type": "application/json",
                },
                {
                    "rel": "collection",
                    "href": "../product.stac.json",
                    "title": "PRODUCT A",
                    "type": "application/json",
                },
            ],
            "assets": {
                "native": {
                    "id": "native",
                    "href": "https://s3.test.com/bucket1/native/PRODUCT_A/dataset-number-one",
                    "type": "application/x-netcdf",
                    "roles": ["data"],
                    "title": "Native dataset",
                    "description": "The original, non-ARCO version of this dataset, as published by the data provider.",
                }
            },
            "collection": "PRODUCT_A",
        }
        self.dataset2_data = deepcopy(self.dataset1_data)
        self.dataset2_data["id"] = "dataset-number-two"
        self.dataset2_data["properties"]["title"] = "dataset-number-two"
        self.dataset2_data["assets"]["native"][
            "href"
        ] = "https://s3.test.com/bucket1/native/PRODUCT_A/dataset-number-two"

        self.list_objects_response1 = {
            "Contents": [
                {
                    "Key": "native/PRODUCT_A/dataset-number-one/item_20200102_20200103_hdkIFE.KFNEDNF_20210101.nc"
                },
                {
                    "Key": "native/PRODUCT_A/dataset-number-one/item_20200104_20200105_hdkIFEKFNEDNF_20210101.nc"
                },
                {
                    "Key": "native/PRODUCT_A/dataset-number-one/item_20200302_20200303_hdkIFEKFNEDN_20210101.nc"
                },
            ]
        }
        self.list_objects_response2 = {
            "Contents": [
                {
                    "Key": "native/PRODUCT_A/dataset-number-two/item_20200102_20200103_fizncnqijei_20210101.nc"
                },
                {
                    "Key": "native/PRODUCT_A/dataset-number-two/item_20200204_20200205_niznjvnqkrf_20210101.nc"
                },
                {
                    "Key": "native/PRODUCT_A/dataset-number-two/item_20200302_20200303_fIZHVCOINine_20210101.nc"
                },
            ]
        }
        self.list_objects_response3 = {
            "Contents": [
                {
                    "Key": "native/PRODUCT_A/dataset-number-two/item_15325642_fizncnqijei.nc"
                },
                {
                    "Key": "native/PRODUCT_A/dataset-number-two/item_846282_niznjvnqkrf.nc"
                },
            ]
        }
        self.s3 = boto3.client(
            "s3",
            config=botocore.config.Config(
                # Configures to use subdomain/virtual calling format.
                s3={"addressing_style": "virtual"},
                signature_version=botocore.UNSIGNED,
            ),
        )

    @mock.patch("eodag.plugins.search.cop_marine.requests.get")
    def test_plugins_search_cop_marine_query_with_dates(self, mock_requests_get):
        mock_requests_get.return_value.json.side_effect = [
            self.product_data,
            self.dataset1_data,
            self.dataset2_data,
        ]
        search_plugin = self.get_search_plugin("PRODUCT_A", self.provider)

        with mock.patch("eodag.plugins.search.cop_marine._get_s3_client") as s3_stub:
            s3_stub.return_value = self.s3
            stubber = Stubber(self.s3)
            stubber.add_response(
                "list_objects",
                self.list_objects_response1,
                {"Bucket": "bucket1", "Prefix": "native/PRODUCT_A/dataset-number-one"},
            )
            stubber.add_response(
                "list_objects",
                self.list_objects_response2,
                {"Bucket": "bucket1", "Prefix": "native/PRODUCT_A/dataset-number-two"},
            )
            stubber.activate()
            result = search_plugin.query(
                collection="PRODUCT_A",
                start_datetime="2020-01-01T01:00:00Z",
                end_datetime="2020-02-01T01:00:00Z",
            )
            mock_requests_get.assert_has_calls(
                calls=[
                    call(
                        "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/product.stac.json"
                    ),
                    call().json(),
                    call(
                        "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/dataset-number-one/dataset.stac.json"
                    ),
                    call().json(),
                    call(
                        "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/dataset-number-two/dataset.stac.json"
                    ),
                    call().json(),
                ]
            )
            self.assertEqual(3, result.number_matched)
            products_dataset1 = [
                product
                for product in result.data
                if product.properties["dataset"] == "dataset-number-one"
            ]
            products_dataset2 = [
                product
                for product in result.data
                if product.properties["dataset"] == "dataset-number-two"
            ]
            self.assertEqual(2, len(products_dataset1))
            self.assertEqual(1, len(products_dataset2))
            self.assertEqual(
                "2020-01-02T00:00:00Z",
                products_dataset2[0].properties["start_datetime"],
            )
            self.assertEqual(
                "2020-01-03T00:00:00Z",
                products_dataset2[0].properties["end_datetime"],
            )

    @mock.patch("eodag.plugins.search.cop_marine.requests.get")
    def test_plugins_search_cop_marine_query_no_dates_in_id(self, mock_requests_get):
        mock_requests_get.return_value.json.side_effect = [
            self.product_data,
            self.dataset1_data,
            self.dataset2_data,
        ]

        search_plugin = self.get_search_plugin("PRODUCT_A", self.provider)
        search_plugin.config.products = {
            "PRODUCT_A": {
                "_collection": "PRODUCT_A",
                "code_mapping": {"param": "platform", "index": 1},
            }
        }

        with mock.patch("eodag.plugins.search.cop_marine._get_s3_client") as s3_stub:
            s3_stub.return_value = self.s3
            stubber = Stubber(self.s3)
            stubber.add_response(
                "list_objects",
                self.list_objects_response1,
                {"Bucket": "bucket1", "Prefix": "native/PRODUCT_A/dataset-number-one"},
            )
            stubber.add_response(
                "list_objects",
                self.list_objects_response3,
                {"Bucket": "bucket1", "Prefix": "native/PRODUCT_A/dataset-number-two"},
            )
            stubber.add_response(
                "list_objects",
                {},
                {
                    "Bucket": "bucket1",
                    "Prefix": "native/PRODUCT_A/dataset-number-two",
                    "Marker": "native/PRODUCT_A/dataset-number-two/item_846282_niznjvnqkrf.nc",
                },
            )
            stubber.activate()
            result = search_plugin.query(
                collection="PRODUCT_A",
                start_datetime="1969-01-01T01:00:00Z",
                end_datetime="1970-02-01T01:00:00Z",
            )
            mock_requests_get.assert_has_calls(
                calls=[
                    call(
                        "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/product.stac.json"
                    ),
                    call().json(),
                    call(
                        "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/dataset-number-one/dataset.stac.json"
                    ),
                    call().json(),
                    call(
                        "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/dataset-number-two/dataset.stac.json"
                    ),
                    call().json(),
                ]
            )
            self.assertEqual(2, result.number_matched)
            products_dataset2 = [
                product
                for product in result.data
                if product.properties["dataset"] == "dataset-number-two"
            ]
            self.assertEqual(2, len(products_dataset2))
            self.assertEqual(
                "1970-01-01T00:00:00.000000Z",
                products_dataset2[0].properties["start_datetime"],
            )
            self.assertEqual(
                "1970-01-01T00:00:00.000000Z",
                products_dataset2[0].properties["end_datetime"],
            )
            self.assertEqual(
                "15325642",
                products_dataset2[0].properties["platform"],
            )

    @mock.patch("eodag.plugins.search.cop_marine.requests.get")
    def test_plugins_search_cop_marine_query_with_id(self, mock_requests_get):
        mock_requests_get.return_value.json.side_effect = [
            self.product_data,
            self.dataset1_data,
            self.dataset2_data,
            self.product_data,
            self.dataset1_data,
            self.dataset2_data,
        ]

        search_plugin = self.get_search_plugin("PRODUCT_A", self.provider)

        with mock.patch("eodag.plugins.search.cop_marine._get_s3_client") as s3_stub:
            s3_stub.return_value = self.s3
            stubber = Stubber(self.s3)
            for i in [
                0,
                1,
            ]:  # add responses twice because 2 search requests will be executed
                stubber.add_response(
                    "list_objects",
                    self.list_objects_response1,
                    {
                        "Bucket": "bucket1",
                        "Prefix": "native/PRODUCT_A/dataset-number-one",
                    },
                )
                stubber.add_response(
                    "list_objects",
                    {},
                    {
                        "Bucket": "bucket1",
                        "Marker": "native/PRODUCT_A/dataset-number-one/item_20200302_20200303_hdkIFEKFNEDN_20210101.nc",
                        "Prefix": "native/PRODUCT_A/dataset-number-one",
                    },
                )
                stubber.add_response(
                    "list_objects",
                    self.list_objects_response2,
                    {
                        "Bucket": "bucket1",
                        "Prefix": "native/PRODUCT_A/dataset-number-two",
                    },
                )
            stubber.activate()
            result = search_plugin.query(
                collection="PRODUCT_A",
                id="item_20200204_20200205_niznjvnqkrf_20210101",
            )
            self.assertEqual(1, result.number_matched)
            self.assertEqual(
                "item_20200204_20200205_niznjvnqkrf_20210101",
                result.data[0].properties["id"],
            )
            result = search_plugin.query(
                collection="PRODUCT_A",
                id="item_20200102_20200103_hdkIFE.KFNEDNF_20210101",
            )
            self.assertEqual(1, result.number_matched)
            self.assertEqual(
                "item_20200102_20200103_hdkIFE.KFNEDNF_20210101",
                result.data[0].properties["id"],
            )

    @mock.patch("eodag.plugins.search.cop_marine.requests.get")
    def test_plugins_search_cop_marine_search_by_id_no_dates_in_id(
        self, mock_requests_get
    ):
        mock_requests_get.return_value.json.side_effect = [
            self.product_data,
            self.dataset1_data,
            self.dataset2_data,
        ]

        search_plugin = self.get_search_plugin("PRODUCT_A", self.provider)
        search_plugin.config.products = {
            "PRODUCT_A": {
                "_collection": "PRODUCT_A",
                "code_mapping": {"param": "platform", "index": 1},
            }
        }

        with mock.patch("eodag.plugins.search.cop_marine._get_s3_client") as s3_stub:
            s3_stub.return_value = self.s3
            stubber = Stubber(self.s3)
            stubber.add_response(
                "list_objects",
                self.list_objects_response1,
                {"Bucket": "bucket1", "Prefix": "native/PRODUCT_A/dataset-number-one"},
            )
            stubber.add_response(
                "list_objects",
                {},
                {
                    "Bucket": "bucket1",
                    "Marker": "native/PRODUCT_A/dataset-number-one/item_20200302_20200303_hdkIFEKFNEDN_20210101.nc",
                    "Prefix": "native/PRODUCT_A/dataset-number-one",
                },
            )
            stubber.add_response(
                "list_objects",
                self.list_objects_response3,
                {"Bucket": "bucket1", "Prefix": "native/PRODUCT_A/dataset-number-two"},
            )
            stubber.add_response(
                "list_objects",
                {},
                {
                    "Bucket": "bucket1",
                    "Prefix": "native/PRODUCT_A/dataset-number-two",
                    "Marker": "native/PRODUCT_A/dataset-number-two/item_846282_niznjvnqkrf.nc",
                },
            )
            stubber.activate()
            result = search_plugin.query(
                collection="PRODUCT_A", id="item_846282_niznjvnqkrf"
            )
            mock_requests_get.assert_has_calls(
                calls=[
                    call(
                        "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/product.stac.json"
                    ),
                    call().json(),
                    call(
                        "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/dataset-number-one/dataset.stac.json"
                    ),
                    call().json(),
                    call(
                        "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/dataset-number-two/dataset.stac.json"
                    ),
                    call().json(),
                ]
            )
            self.assertEqual(1, result.number_matched)
            self.assertEqual("item_846282_niznjvnqkrf", result.data[0].properties["id"])

    @mock.patch("eodag.plugins.search.cop_marine.requests.get")
    def test_plugins_search_cop_marine_query_with_not_intersected_geom(
        self, mock_requests_get
    ):
        """A query with a geometry that does not intersect the dataset geometries must return no result"""
        mock_requests_get.return_value.json.side_effect = [
            self.product_data,
            self.dataset1_data,
            self.dataset2_data,
        ]

        geometry = get_geometry_from_various(geometry=[10, 20, 30, 40])

        # check that "geometry" does not intersect the dataset geometries
        self.assertFalse(
            get_geometry_from_various(
                geometry=self.dataset1_data["geometry"]
            ).intersects(geometry)
        )
        self.assertFalse(
            get_geometry_from_various(
                geometry=self.dataset2_data["geometry"]
            ).intersects(geometry)
        )

        search_plugin = self.get_search_plugin("PRODUCT_A", self.provider)

        result = search_plugin.query(
            collection="PRODUCT_A",
            geometry=geometry,
        )

        mock_requests_get.assert_has_calls(
            calls=[
                call(
                    "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/product.stac.json"
                ),
                call().json(),
                call(
                    "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/dataset-number-one/dataset.stac.json"
                ),
                call().json(),
                call(
                    "https://stac.marine.copernicus.eu/metadata/PRODUCT_A/dataset-number-two/dataset.stac.json"
                ),
                call().json(),
            ]
        )

        # check that no result has been found
        self.assertListEqual(result.data, [])
        self.assertEqual(result.number_matched, 0)

    @mock.patch("eodag.plugins.search.cop_marine.requests.get")
    def test_plugins_search_cop_marine_with_errors(self, mock_requests_get):
        exc = requests.RequestException()
        exc.errno = 404
        mock_requests_get.side_effect = exc
        search_plugin = self.get_search_plugin("PRODUCT_A", self.provider)
        with self.assertRaises(UnsupportedCollection):
            search_plugin.query(
                collection="PRODUCT_AX",
                id="item_20200204_20200205_niznjvnqkrf_20210101",
            )
        mock_requests_get.reset()
        mock_requests_get.side_effect = requests.exceptions.ConnectionError()
        with self.assertRaises(RequestError):
            search_plugin.query(
                collection="PRODUCT_A",
                id="item_20200204_20200205_niznjvnqkrf_20210101",
            )

    def test_plugins_search_postjsonsearch_discover_queryables(self):
        """Queryables discovery with a CopMarineSearch must return static queryables with an adaptative default value"""  # noqa
        search_plugin = self.get_search_plugin("PRODUCT_A", self.provider)
        kwargs = {"collection": "PRODUCT_A", "provider": self.provider}

        queryables = search_plugin.discover_queryables(**kwargs)

        self.assertIsNotNone(queryables)
        # check that the queryables are the ones expected (they are always the same ones)
        self.assertListEqual(
            list(queryables.keys()), ["collection", "id", "start", "end", "geom"]
        )
        # check that each queryable does not have a default value except the one set in the kwargs
        for key, queryable in queryables.items():
            if key in kwargs:
                self.assertIsNotNone(queryable.__metadata__[0].get_default())
            else:
                self.assertIsNone(queryable.__metadata__[0].get_default())
