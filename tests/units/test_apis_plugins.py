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
import ast
import io
import json
import logging
import os
import unittest
from datetime import datetime
from tempfile import TemporaryDirectory
from unittest import mock

import geojson
import responses
from ecmwfapi.api import ANONYMOUS_APIKEY_VALUES
from shapely.geometry import shape

from eodag.utils import MockResponse
from tests import TEST_RESOURCES_PATH
from tests.context import (
    DEFAULT_DOWNLOAD_WAIT,
    DEFAULT_MISSION_START_DATE,
    ONLINE_STATUS,
    USER_AGENT,
    AuthenticationError,
    EODataAccessGateway,
    EOProduct,
    NotAvailableError,
    PluginManager,
    SearchResult,
    USGSAuthExpiredError,
    USGSError,
    get_geometry_from_various,
    load_default_config,
    path_to_uri,
    setup_logging,
    urlsplit,
)


class BaseApisPluginTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(BaseApisPluginTest, cls).setUpClass()
        providers_config = load_default_config()
        cls.plugins_manager = PluginManager(providers_config)
        # Mock home and eodag conf directory to tmp dir
        cls.tmp_home_dir = TemporaryDirectory()
        expanduser_mock_side_effect = (
            lambda *x: x[0]
            .replace("~user", cls.tmp_home_dir.name)
            .replace("~", cls.tmp_home_dir.name)
        )
        cls.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, side_effect=expanduser_mock_side_effect
        )
        cls.expanduser_mock.start()

    @classmethod
    def tearDownClass(cls):
        super(BaseApisPluginTest, cls).tearDownClass()
        # stop Mock and remove tmp config dir
        cls.expanduser_mock.stop()
        cls.tmp_home_dir.cleanup()

    def get_search_plugin(self, product_type=None, provider=None):
        return next(
            self.plugins_manager.get_search_plugins(
                product_type=product_type, provider=provider
            )
        )


class TestApisPluginEcmwfApi(BaseApisPluginTest):
    def setUp(self):
        self.provider = "ecmwf"
        self.api_plugin = self.get_search_plugin(provider=self.provider)
        self.query_dates = {
            "startTimeFromAscendingNode": "2022-01-01",
            "completionTimeFromAscendingNode": "2022-01-02",
        }
        self.product_type = "TIGGE_CF_SFC"
        self.product_type_params = {
            "class": "ti",
            "dataset": "tigge",
            "expver": "prod",
            "type": "cf",
            "levtype": "sfc",
            "origin": "ecmf",
            "grid": "0.5/0.5",
            "param": "59/134/136/146/147/151/165/166/167/168/172/176/177/179/189/235/"
            + "228001/228002/228039/228139/228141/228144/228164/228228",
            "step": 0,
            "time": "00:00",
        }
        self.custom_query_params = {
            "origin": "ecmf",
            "levtype": "sfc",
            "number": "1",
            "expver": "prod",
            "dataset": "tigge",
            "step": "0",
            "grid": "2/2",
            "param": "228164",  # total cloud cover parameter
            "time": "00",
            "type": "cf",
            "class": "ti",
        }

    def test_plugins_apis_ecmwf_query_dates_missing(self):
        """Ecmwf.query must use default dates if missing"""
        # given start & stop
        results, _ = self.api_plugin.query(
            productType=self.product_type,
            startTimeFromAscendingNode="2020-01-01",
            completionTimeFromAscendingNode="2020-01-02",
        )
        eoproduct = results[0]
        self.assertEqual(
            eoproduct.properties["startTimeFromAscendingNode"], "2020-01-01"
        )
        self.assertEqual(
            eoproduct.properties["completionTimeFromAscendingNode"], "2020-01-02"
        )

        # missing start & stop
        results, _ = self.api_plugin.query(
            productType=self.product_type,
        )
        eoproduct = results[0]
        self.assertIn(
            eoproduct.properties["startTimeFromAscendingNode"],
            DEFAULT_MISSION_START_DATE,
        )
        self.assertIn(
            eoproduct.properties["completionTimeFromAscendingNode"],
            datetime.utcnow().isoformat(),
        )

        # missing start & stop and plugin.product_type_config set (set in core._prepare_search)
        self.api_plugin.config.product_type_config = {
            "productType": self.product_type,
            "missionStartDate": "1985-10-26",
            "missionEndDate": "2015-10-21",
        }
        results, _ = self.api_plugin.query(
            productType=self.product_type,
        )
        eoproduct = results[0]
        self.assertEqual(
            eoproduct.properties["startTimeFromAscendingNode"], "1985-10-26"
        )
        self.assertEqual(
            eoproduct.properties["completionTimeFromAscendingNode"], "2015-10-21"
        )

    def test_plugins_apis_ecmwf_query_without_producttype(self):
        """
        EcmwfApi.query must build a EOProduct from input parameters without product type.
        For test only, result cannot be downloaded.
        """
        results, count = self.api_plugin.query(**self.query_dates)
        assert count == 1
        eoproduct = results[0]
        assert eoproduct.geometry.bounds == (-180.0, -90.0, 180.0, 90.0)
        assert (
            eoproduct.properties["startTimeFromAscendingNode"]
            == self.query_dates["startTimeFromAscendingNode"]
        )
        assert (
            eoproduct.properties["completionTimeFromAscendingNode"]
            == self.query_dates["completionTimeFromAscendingNode"]
        )
        assert eoproduct.properties["title"] == eoproduct.properties["id"]
        assert eoproduct.properties["title"].startswith("MARS___")
        assert eoproduct.location.startswith("http")

    def test_plugins_apis_ecmwf_query_with_producttype(self):
        """EcmwfApi.query must build a EOProduct from input parameters with predefined product type"""
        results, _ = self.api_plugin.query(
            **self.query_dates, productType=self.product_type, geometry=[1, 2, 3, 4]
        )
        eoproduct = results[0]
        assert eoproduct.properties["title"].startswith(self.product_type)
        assert eoproduct.geometry.bounds == (1.0, 2.0, 3.0, 4.0)
        # check if product_type_params is a subset of eoproduct.properties
        assert self.product_type_params.items() <= eoproduct.properties.items()

        # product type default settings can be overwritten using search kwargs
        results, _ = self.api_plugin.query(
            **self.query_dates, productType=self.product_type, param="tcc"
        )
        eoproduct = results[0]
        assert eoproduct.properties["param"] == "tcc"

    def test_plugins_apis_ecmwf_query_with_custom_producttype(self):
        """EcmwfApi.query must build a EOProduct from input parameters with custom product type"""
        results, _ = self.api_plugin.query(
            **self.query_dates,
            **self.custom_query_params,
        )
        eoproduct = results[0]
        assert eoproduct.properties["title"].startswith(
            "%s_%s_%s"
            % (
                self.custom_query_params["dataset"].upper(),
                self.custom_query_params["type"].upper(),
                self.custom_query_params["levtype"].upper(),
            )
        )
        # check if custom_query_params is a subset of eoproduct.properties
        for param in self.custom_query_params:
            try:
                # for numeric values
                assert eoproduct.properties[param] == ast.literal_eval(
                    self.custom_query_params[param]
                )
            except Exception:
                assert eoproduct.properties[param] == self.custom_query_params[param]

    @mock.patch("ecmwfapi.api.Connection.call", autospec=True)
    def test_plugins_apis_ecmwf_authenticate(self, mock_connection_call):
        """EcmwfApi.authenticate must return a credentials dict"""
        # auth using ~/.ecmwfapirc
        auth_dict = self.api_plugin.authenticate()
        assert (
            auth_dict["key"],
            auth_dict["url"],
            auth_dict["email"],
        ) == ANONYMOUS_APIKEY_VALUES

        # auth using eodag credentials
        credentials = {
            "username": "foo",
            "password": "bar",
            "url": "http://foo.bar.baz",
        }
        self.api_plugin.config.credentials = credentials
        auth_dict = self.api_plugin.authenticate()
        assert auth_dict["email"] == credentials["username"]
        assert auth_dict["key"] == credentials["password"]
        assert auth_dict["url"] == self.api_plugin.config.api_endpoint
        del self.api_plugin.config.credentials

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    @mock.patch("ecmwfapi.api.ECMWFService.execute", autospec=True)
    @mock.patch("ecmwfapi.api.ECMWFDataServer.retrieve", autospec=True)
    @mock.patch("ecmwfapi.api.Connection.call", autospec=True)
    def test_plugins_apis_ecmwf_download(
        self,
        mock_connection_call,
        mock_ecmwfdataserver_retrieve,
        mock_ecmwfservice_execute,
        mock_fetch_product_types_list,
    ):
        """EcmwfApi.download must call the appriate ecmwf api service"""

        dag = EODataAccessGateway()
        dag.set_preferred_provider("ecmwf")
        output_data_path = os.path.join(os.path.expanduser("~"), "data")

        # public dataset request
        def create_empty_file_for_public_dataset(*args, **kwargs):
            with open(args[1]["target"], "x"):
                pass

        mock_ecmwfdataserver_retrieve.side_effect = create_empty_file_for_public_dataset
        results, _ = dag.search(
            **self.query_dates,
            **self.custom_query_params,
        )
        eoproduct = results[0]
        expected_path = os.path.join(
            output_data_path, "%s" % eoproduct.properties["title"]
        )
        arg_path = os.path.join(
            output_data_path,
            "%s" % eoproduct.properties["title"],
            "%s.grib" % eoproduct.properties["title"],
        )
        path = eoproduct.download(outputs_prefix=output_data_path)
        mock_ecmwfservice_execute.assert_not_called()
        mock_ecmwfdataserver_retrieve.assert_called_once_with(
            mock.ANY,  # ECMWFDataServer instance
            dict(
                target=arg_path,
                **geojson.loads(urlsplit(eoproduct.remote_location).query),
            ),
        )
        assert path == expected_path
        assert path_to_uri(expected_path) == eoproduct.location

        mock_ecmwfservice_execute.reset_mock()
        mock_ecmwfdataserver_retrieve.reset_mock()

        # operation archive request
        def create_empty_file_for_operation_archive(*args, **kwargs):
            with open(args[2], "x"):
                pass

        mock_ecmwfservice_execute.side_effect = create_empty_file_for_operation_archive
        operation_archive_custom_query_params = self.custom_query_params.copy()
        operation_archive_custom_query_params.pop("dataset")
        operation_archive_custom_query_params["format"] = "netcdf"
        results, _ = dag.search(
            **self.query_dates,
            **operation_archive_custom_query_params,
        )
        eoproduct = results[0]
        expected_path = os.path.join(
            output_data_path, "%s" % eoproduct.properties["title"]
        )
        arg_path = os.path.join(
            output_data_path,
            "%s" % eoproduct.properties["title"],
            "%s.nc" % eoproduct.properties["title"],
        )
        path = eoproduct.download(outputs_prefix=output_data_path)
        download_request = geojson.loads(urlsplit(eoproduct.remote_location).query)
        download_request.pop("dataset", None)
        mock_ecmwfservice_execute.assert_called_once_with(
            mock.ANY,  # ECMWFService instance
            dict(
                **download_request,
            ),
            arg_path,
        )
        mock_ecmwfdataserver_retrieve.assert_not_called()
        assert path == expected_path
        assert path_to_uri(expected_path) == eoproduct.location

        mock_ecmwfservice_execute.reset_mock()
        mock_ecmwfdataserver_retrieve.reset_mock()

        # download again
        eoproduct.download(outputs_prefix=output_data_path)
        mock_ecmwfservice_execute.assert_not_called()
        mock_ecmwfdataserver_retrieve.assert_not_called()

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    @mock.patch("ecmwfapi.api.ECMWFDataServer.retrieve", autospec=True)
    @mock.patch("ecmwfapi.api.Connection.call", autospec=True)
    def test_plugins_apis_ecmwf_download_all(
        self,
        mock_connection_call,
        mock_ecmwfdataserver_retrieve,
        mock_fetch_product_types_list,
    ):
        """EcmwfApi.download_all must call the appropriate ecmwf api service"""

        dag = EODataAccessGateway()
        dag.set_preferred_provider("ecmwf")

        eoproducts = SearchResult([])

        # public dataset request
        results, _ = dag.search(
            **self.query_dates,
            **self.custom_query_params,
            accuracy="bar",
        )
        eoproducts.extend(results)
        results, _ = dag.search(
            **self.query_dates,
            **self.custom_query_params,
            accuracy="baz",
        )
        eoproducts.extend(results)
        assert len(eoproducts) == 2

        paths = dag.download_all(
            eoproducts, outputs_prefix=os.path.join(os.path.expanduser("~"), "data")
        )
        assert mock_ecmwfdataserver_retrieve.call_count == 2
        assert len(paths) == 2


class TestApisPluginUsgsApi(BaseApisPluginTest):
    def setUp(self):
        self.provider = "usgs"
        self.api_plugin = self.get_search_plugin(provider=self.provider)

    @mock.patch("usgs.api.login", autospec=True)
    @mock.patch("usgs.api.logout", autospec=True)
    def test_plugins_apis_usgs_authenticate(self, mock_api_logout, mock_api_login):
        """UsgsApi.authenticate must return try to login"""
        # no credential
        self.api_plugin.authenticate()
        mock_api_login.assert_called_once_with("", "", save=True)
        mock_api_logout.assert_not_called()
        mock_api_login.reset_mock()

        # with credentials
        self.api_plugin.config.credentials = {
            "username": "foo",
            "password": "bar",
        }
        self.api_plugin.authenticate()
        mock_api_login.assert_called_once_with("foo", "bar", save=True)
        mock_api_logout.assert_not_called()
        mock_api_login.reset_mock()

        # with USGSAuthExpiredError
        mock_api_login.side_effect = [USGSAuthExpiredError(), None]
        self.api_plugin.authenticate()
        self.assertEqual(mock_api_login.call_count, 2)
        self.assertEqual(mock_api_logout.call_count, 1)
        mock_api_login.reset_mock()
        mock_api_logout.reset_mock()

        # with invalid credentials / USGSError
        mock_api_login.side_effect = USGSError()
        with self.assertRaises(AuthenticationError):
            self.api_plugin.authenticate()
            self.assertEqual(mock_api_login.call_count, 1)
            mock_api_logout.assert_not_called()

    @mock.patch("usgs.api.login", autospec=True)
    @mock.patch("usgs.api.logout", autospec=True)
    @mock.patch(
        "usgs.api.scene_search",
        autospec=True,
        return_value={
            "data": {
                "results": [
                    {
                        "browse": [
                            {
                                "browsePath": "https://path/to/quicklook.jpg",
                                "thumbnailPath": "https://path/to/thumbnail.jpg",
                            },
                            {},
                            {},
                        ],
                        "cloudCover": "77.46",
                        "entityId": "LC81780382020041LGN00",
                        "displayId": "LC08_L1GT_178038_20200210_20200224_01_T2",
                        "spatialBounds": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [28.03905, 30.68073],
                                    [28.03905, 32.79057],
                                    [30.46294, 32.79057],
                                    [30.46294, 30.68073],
                                    [28.03905, 30.68073],
                                ]
                            ],
                        },
                        "temporalCoverage": {
                            "endDate": "2020-02-10 00:00:00",
                            "startDate": "2020-02-10 00:00:00",
                        },
                        "publishDate": "2020-02-10 08:24:46",
                    },
                ],
                "recordsReturned": 5,
                "totalHits": 139,
                "startingNumber": 6,
                "nextRecord": 11,
            }
        },
    )
    @mock.patch(
        "usgs.api.download_options",
        autospec=True,
        return_value={
            "data": [
                {
                    "id": "5e83d0b8e7f6734c",
                    "entityId": "LC81780382020041LGN00",
                    "available": True,
                    "filesize": 9186067,
                    "productName": "LandsatLook Natural Color Image",
                    "downloadSystem": "dds",
                },
                {
                    "entityId": "LC81780382020041LGN00",
                    "available": False,
                    "downloadSystem": "wms",
                },
            ]
        },
    )
    def test_plugins_apis_usgs_query(
        self,
        mock_api_download_options,
        mock_api_scene_search,
        mock_api_logout,
        mock_api_login,
    ):
        """UsgsApi.query must search using usgs api"""

        search_kwargs = {
            "productType": "LANDSAT_C2L1",
            "startTimeFromAscendingNode": "2020-02-01",
            "completionTimeFromAscendingNode": "2020-02-10",
            "geometry": get_geometry_from_various(geometry=[10, 20, 30, 40]),
            "items_per_page": 5,
            "page": 2,
        }
        search_results, total_count = self.api_plugin.query(**search_kwargs)
        mock_api_scene_search.assert_called_once_with(
            "landsat_ot_c2_l1",
            start_date="2020-02-01",
            end_date="2020-02-10",
            ll={"longitude": 10.0, "latitude": 20.0},
            ur={"longitude": 30.0, "latitude": 40.0},
            max_results=5,
            starting_number=6,
        )
        self.assertEqual(search_results[0].provider, "usgs")
        self.assertEqual(search_results[0].product_type, "LANDSAT_C2L1")
        self.assertEqual(
            search_results[0].geometry,
            shape(
                mock_api_scene_search.return_value["data"]["results"][0][
                    "spatialBounds"
                ]
            ),
        )
        self.assertEqual(
            search_results[0].properties["id"],
            mock_api_scene_search.return_value["data"]["results"][0]["displayId"],
        )
        self.assertEqual(
            search_results[0].properties["cloudCover"],
            float(
                mock_api_scene_search.return_value["data"]["results"][0]["cloudCover"]
            ),
        )
        self.assertEqual(search_results[0].properties["storageStatus"], ONLINE_STATUS)
        self.assertEqual(
            total_count, mock_api_scene_search.return_value["data"]["totalHits"]
        )

    @mock.patch("usgs.api.login", autospec=True)
    @mock.patch("usgs.api.logout", autospec=True)
    @mock.patch("usgs.api.download_request", autospec=True)
    def test_plugins_apis_usgs_download(
        self,
        mock_api_download_request,
        mock_api_logout,
        mock_api_login,
    ):
        """UsgsApi.download must donwload using usgs api"""

        @responses.activate
        def run():

            product = EOProduct(
                "peps",
                dict(
                    geometry="POINT (0 0)",
                    title="dummy_product",
                    id="dummy",
                    entityId="dummyEntityId",
                    productId="dummyProductId",
                    productType="L8_OLI_TIRS_C1L1",
                ),
            )
            product.location = product.remote_location = product.properties[
                "downloadLink"
            ] = "http://somewhere"
            product.properties["id"] = "someproduct"

            responses.add(
                responses.GET,
                "http://path/to/product",
                status=200,
                content_type="application/octet-stream",
                body=b"something",
                auto_calculate_content_length=True,
                match=[
                    responses.matchers.request_kwargs_matcher(
                        dict(stream=True, timeout=DEFAULT_DOWNLOAD_WAIT * 60)
                    )
                ],
            )

            # missing download_request return value
            with self.assertRaises(NotAvailableError):
                self.api_plugin.download(product, outputs_prefix=self.tmp_home_dir.name)

            # download 1 available product
            mock_api_download_request.return_value = {
                "data": {"preparingDownloads": [{"url": "http://path/to/product"}]}
            }

            path = self.api_plugin.download(
                product, outputs_prefix=self.tmp_home_dir.name
            )

            self.assertEqual(len(responses.calls), 1)
            self.assertIn(
                list(USER_AGENT.items())[0], responses.calls[0].request.headers.items()
            )
            responses.calls.reset()

            self.assertEqual(
                path, os.path.join(self.tmp_home_dir.name, "dummy_product")
            )
            self.assertTrue(os.path.isfile(path))

            # check file extension
            # tar
            os.remove(path)
            with mock.patch("tarfile.is_tarfile", return_value=True, autospec=True):
                path = self.api_plugin.download(
                    product, outputs_prefix=self.tmp_home_dir.name, extract=False
                )
                self.assertEqual(
                    path, os.path.join(self.tmp_home_dir.name, "dummy_product.tar.gz")
                )
            # zip
            os.remove(path)
            product.product_type = "S2_MSI_L1C"
            with mock.patch("zipfile.is_zipfile", return_value=True, autospec=True):
                path = self.api_plugin.download(
                    product, outputs_prefix=self.tmp_home_dir.name, extract=False
                )
                self.assertEqual(
                    path, os.path.join(self.tmp_home_dir.name, "dummy_product.zip")
                )

        run()


class TestApisPluginCdsApi(BaseApisPluginTest):
    def setUp(self):
        self.provider = "cop_ads"
        self.api_plugin = self.get_search_plugin(provider=self.provider)
        self.query_dates = {
            "startTimeFromAscendingNode": "2020-01-01",
            "completionTimeFromAscendingNode": "2020-01-02",
        }
        self.product_type = "CAMS_EAC4"
        self.product_dataset = "cams-global-reanalysis-eac4"
        self.product_type_params = {
            "dataset": self.product_dataset,
            "format": "grib",
            "variable": "2m_dewpoint_temperature",
            "time": "00:00",
        }
        self.custom_query_params = {
            "dataset": "cams-global-ghg-reanalysis-egg4",
            "step": 0,
            "variable": "carbon_dioxide",
            "pressure_level": "10",
            "model_level": "1",
            "time": "00:00",
            "format": "grib",
        }

    def test_plugins_apis_cds_logging(self):
        """CdsApi must init client with logging level"""

        # auth dict needed for client init
        auth_dict = {"key": "foo:some-key", "url": "https://bar"}

        # 0: nothing, 1: only progress bars, 2: INFO, 3: DEBUG
        setup_logging(0)
        client = self.api_plugin._get_cds_client(**auth_dict)
        self.assertEqual(client.logger.level, logging.WARNING)

        setup_logging(1)
        client = self.api_plugin._get_cds_client(**auth_dict)
        self.assertEqual(client.logger.level, logging.WARNING)

        setup_logging(2)
        client = self.api_plugin._get_cds_client(**auth_dict)
        self.assertEqual(client.logger.level, logging.INFO)

        setup_logging(3)
        client = self.api_plugin._get_cds_client(**auth_dict)
        self.assertEqual(client.logger.level, logging.DEBUG)

        logger = logging.getLogger("eodag")
        logger.handlers = []
        logger.level = 0

    def test_plugins_apis_cds_query_dates_missing(self):
        """CdsApi.query must use default dates if missing"""
        # given start & stop
        results, _ = self.api_plugin.query(
            productType=self.product_type,
            startTimeFromAscendingNode="2020-01-01",
            completionTimeFromAscendingNode="2020-01-02",
        )
        eoproduct = results[0]
        self.assertEqual(
            eoproduct.properties["startTimeFromAscendingNode"], "2020-01-01"
        )
        self.assertEqual(
            eoproduct.properties["completionTimeFromAscendingNode"], "2020-01-02"
        )

        # missing start & stop
        results, _ = self.api_plugin.query(
            productType=self.product_type,
        )
        eoproduct = results[0]
        self.assertIn(
            eoproduct.properties["startTimeFromAscendingNode"],
            DEFAULT_MISSION_START_DATE,
        )
        self.assertIn(
            eoproduct.properties["completionTimeFromAscendingNode"],
            "2015-01-02T00:00:00Z",
        )

        # missing start & stop and plugin.product_type_config set (set in core._prepare_search)
        self.api_plugin.config.product_type_config = {
            "productType": self.product_type,
            "missionStartDate": "1985-10-26",
            "missionEndDate": "2015-10-21",
        }
        results, _ = self.api_plugin.query(
            productType=self.product_type,
        )
        eoproduct = results[0]
        self.assertEqual(
            eoproduct.properties["startTimeFromAscendingNode"], "1985-10-26"
        )
        self.assertEqual(
            eoproduct.properties["completionTimeFromAscendingNode"], "1985-10-27"
        )

    def test_plugins_apis_cds_query_without_producttype(self):
        """
        CdsApi.query must build a EOProduct from input parameters without product type.
        For test only, result cannot be downloaded.
        """
        results, count = self.api_plugin.query(
            dataset=self.product_dataset,
            **self.query_dates,
        )
        assert count == 1
        eoproduct = results[0]
        assert eoproduct.geometry.bounds == (-180.0, -90.0, 180.0, 90.0)
        assert (
            eoproduct.properties["startTimeFromAscendingNode"]
            == self.query_dates["startTimeFromAscendingNode"]
        )
        assert (
            eoproduct.properties["completionTimeFromAscendingNode"]
            == self.query_dates["completionTimeFromAscendingNode"]
        )
        assert eoproduct.properties["title"] == eoproduct.properties["id"]
        assert eoproduct.properties["title"].startswith(
            f"{self.product_dataset.upper()}"
        )
        assert eoproduct.location.startswith("http")

    def test_plugins_apis_cds_query_with_producttype(self):
        """CdsApi.query must build a EOProduct from input parameters with predefined product type"""
        results, _ = self.api_plugin.query(
            **self.query_dates, productType=self.product_type, geometry=[1, 2, 3, 4]
        )
        eoproduct = results[0]
        assert eoproduct.properties["title"].startswith(self.product_type)
        assert eoproduct.geometry.bounds == (1.0, 2.0, 3.0, 4.0)
        # check if product_type_params is a subset of eoproduct.properties
        assert self.product_type_params.items() <= eoproduct.properties.items()

        # product type default settings can be overwritten using search kwargs
        results, _ = self.api_plugin.query(
            **self.query_dates,
            productType=self.product_type,
            variable="temperature",
        )
        eoproduct = results[0]
        assert eoproduct.properties["variable"] == "temperature"

    def test_plugins_apis_cds_query_with_custom_producttype(self):
        """CdsApi.query must build a EOProduct from input parameters with custom product type"""
        results, _ = self.api_plugin.query(
            **self.query_dates,
            **self.custom_query_params,
        )
        eoproduct = results[0]
        assert eoproduct.properties["title"].startswith(
            self.custom_query_params["dataset"].upper()
        )
        # check if custom_query_params is a subset of eoproduct.properties
        for param in self.custom_query_params:
            try:
                # for numeric values
                assert eoproduct.properties[param] == ast.literal_eval(
                    self.custom_query_params[param]
                )
            except Exception:
                assert eoproduct.properties[param] == self.custom_query_params[param]

    @mock.patch("cdsapi.api.Client.status", autospec=True)
    def test_plugins_apis_cds_authenticate(self, mock_client_status):
        """CdsApi.authenticate must return a credentials dict"""
        # auth using eodag credentials
        credentials = {
            "username": "foo",
            "password": "bar",
            "api_endpoint": "http://foo.bar.baz",
        }
        self.api_plugin.config.credentials = credentials
        auth_dict = self.api_plugin.authenticate()
        assert credentials["username"] in auth_dict["key"]
        assert credentials["password"] in auth_dict["key"]
        assert auth_dict["url"] == self.api_plugin.config.api_endpoint
        del self.api_plugin.config.credentials

    @mock.patch("eodag.plugins.download.http.requests.head", autospec=True)
    @mock.patch("eodag.plugins.download.http.requests.get", autospec=True)
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    @mock.patch("eodag.plugins.apis.cds.CdsApi.authenticate", autospec=True)
    @mock.patch("cdsapi.api.Client._api", autospec=True)
    def test_plugins_apis_cds_download(
        self,
        mock_client_api,
        mock_cds_authenticate,
        mock_fetch_product_types_list,
        mock_get,
        mock_head,
    ):
        """CdsApi.download must call the authenticate function and cdsapi Client retrieve"""
        mock_cds_authenticate.return_value = {
            "key": "foo:bar",
            "url": "http://foo.bar.baz",
        }
        mock_client_api.return_value.location = "http://somewhere/something"

        mock_get.return_value.__enter__.return_value.iter_content.return_value = (
            io.BytesIO(b"some content")
        )
        mock_get.return_value.__enter__.return_value.headers = {
            "content-disposition": ""
        }
        mock_head.return_value.headers = {"content-disposition": ""}

        dag = EODataAccessGateway()
        dag.set_preferred_provider("cop_ads")
        output_data_path = os.path.join(os.path.expanduser("~"), "data")

        # public dataset request
        results, _ = dag.search(
            **self.query_dates,
            **self.custom_query_params,
        )
        eoproduct = results[0]

        query_str = "".join(urlsplit(eoproduct.location).fragment.split("?", 1)[1:])
        expected_download_request = geojson.loads(query_str)
        expected_dataset_name = expected_download_request.pop("dataset")
        expected_url = f"{mock_cds_authenticate.return_value['url']}/resources/{expected_dataset_name}"
        expected_path = os.path.join(output_data_path, eoproduct.properties["title"])

        path = eoproduct.download(outputs_prefix=output_data_path)
        mock_client_api.assert_called_once_with(
            mock.ANY,  # instance
            expected_url,
            expected_download_request,
            "POST",
        )

        assert path == expected_path
        assert path_to_uri(expected_path) == eoproduct.location

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    @mock.patch("eodag.plugins.apis.cds.CdsApi.authenticate", autospec=True)
    @mock.patch("eodag.plugins.apis.cds.CdsApi.download", autospec=True)
    @mock.patch("cdsapi.api.Client.retrieve", autospec=True)
    def test_plugins_apis_cds_download_all(
        self,
        mock_client_retrieve,
        mock_cds_download,
        mock_cds_authenticate,
        mock_fetch_product_types_list,
    ):
        """CdsApi.download_all must call download on each product"""
        mock_cds_authenticate.return_value = {
            "key": "foo:bar",
            "url": "http://foo.bar.baz",
        }

        dag = EODataAccessGateway()
        dag.set_preferred_provider("cop_ads")

        eoproducts = SearchResult([])

        # public dataset request
        results, _ = dag.search(
            **self.query_dates,
            **self.custom_query_params,
            accuracy="bar",
        )
        eoproducts.extend(results)
        results, _ = dag.search(
            **self.query_dates,
            **self.custom_query_params,
            accuracy="baz",
        )
        eoproducts.extend(results)
        assert len(eoproducts) == 2

        paths = dag.download_all(
            eoproducts, outputs_prefix=os.path.join(os.path.expanduser("~"), "data")
        )
        assert mock_cds_download.call_count == len(eoproducts)
        assert len(paths) == len(eoproducts)

    @mock.patch("eodag.utils.constraints.requests.get", autospec=True)
    def test_plugins_apis_cds_discover_queryables(self, mock_requests_constraints):
        constraints_path = os.path.join(TEST_RESOURCES_PATH, "constraints.json")
        with open(constraints_path) as f:
            constraints = json.load(f)
        mock_requests_constraints.return_value = MockResponse(
            constraints, status_code=200
        )
        queryables = self.api_plugin.discover_queryables(
            productType="CAMS_EU_AIR_QUALITY_RE"
        )
        self.assertEqual(12, len(queryables))
        self.assertIn("variable", queryables)
        # with additional param
        queryables = self.api_plugin.discover_queryables(
            productType="CAMS_EU_AIR_QUALITY_RE",
            variable="a",
        )
        self.assertEqual(12, len(queryables))
        queryable = queryables.get("variable")
        self.assertEqual("a", queryable.__metadata__[0].get_default())
        queryable = queryables.get("month")
        self.assertTrue(queryable.__metadata__[0].is_required())
