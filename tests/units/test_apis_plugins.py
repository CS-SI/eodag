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
import os
import unittest
from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
from unittest import mock

import geojson
import responses
from dateutil.parser import isoparse
from ecmwfapi.api import ANONYMOUS_APIKEY_VALUES
from shapely.geometry import shape

from eodag.utils import deepcopy
from tests.context import (
    DEFAULT_DOWNLOAD_WAIT,
    DEFAULT_MISSION_START_DATE,
    ONLINE_STATUS,
    USER_AGENT,
    USGS_TMPFILE,
    AuthenticationError,
    EODataAccessGateway,
    EOProduct,
    NotAvailableError,
    PluginManager,
    PreparedSearch,
    SearchResult,
    USGSAuthExpiredError,
    USGSError,
    get_geometry_from_various,
    load_default_config,
    path_to_uri,
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

    def get_search_plugin(self, collection=None, provider=None):
        return next(
            self.plugins_manager.get_search_plugins(
                collection=collection, provider=provider
            )
        )


class TestApisPluginEcmwfApi(BaseApisPluginTest):
    def setUp(self):
        self.provider = "ecmwf"
        self.api_plugin = self.get_search_plugin(provider=self.provider)
        self.query_dates = {
            "start_datetime": "2022-01-01T00:00:00.000Z",
            "end_datetime": "2022-01-02T00:00:00.000Z",
        }
        self.collection = "TIGGE_CF_SFC"
        self.collection_params = {
            "ecmwf:dataset": "tigge",
        }
        self.custom_query_params = {
            "ecmwf:origin": "ecmwf",
            "ecmwf:levtype": "sfc",
            "ecmwf:number": "1",
            "ecmwf:expver": "prod",
            "ecmwf:dataset": "tigge",
            "ecmwf:step": "0",
            "ecmwf:grid": "2/2",
            "ecmwf:param": "228164",  # total cloud cover parameter
            "ecmwf:time": "00",
            "ecmwf:type": "cf",
            "ecmwf:class": "ti",
        }

    def test_plugins_apis_ecmwf_query_dates_missing(self):
        """Ecmwf.query must use default dates if missing"""
        # given start & stop
        results = self.api_plugin.query(
            collection=self.collection,
            start_datetime="2020-01-01",
            end_datetime="2020-01-02",
        )
        eoproduct = results.data[0]
        self.assertEqual(
            eoproduct.properties["start_datetime"],
            "2020-01-01T00:00:00.000Z",
        )
        self.assertEqual(
            eoproduct.properties["end_datetime"],
            "2020-01-02T00:00:00.000Z",
        )

        # missing start & stop
        results = self.api_plugin.query(
            collection=self.collection,
        )
        eoproduct = results.data[0]
        self.assertIn(
            eoproduct.properties["start_datetime"],
            DEFAULT_MISSION_START_DATE,
        )
        # less than 10 seconds should have passed since the product was created
        self.assertLess(
            datetime.now(timezone.utc) - isoparse(eoproduct.properties["end_datetime"]),
            timedelta(seconds=10),
            "stop date should have been created from datetime.now",
        )

        # missing start & stop and plugin.collection_config set (set in core._prepare_search)
        self.api_plugin.config.collection_config = {
            "_collection": self.collection,
            "extent": {
                "spatial": {"bbox": [[-180.0, -90.0, 180.0, 90.0]]},
                "temporal": {"interval": [["1985-10-26", "2015-10-21"]]},
            },
        }
        results = self.api_plugin.query(
            collection=self.collection,
        )
        eoproduct = results[0]
        self.assertEqual(
            eoproduct.properties["start_datetime"],
            "1985-10-26T00:00:00.000Z",
        )
        self.assertEqual(
            eoproduct.properties["end_datetime"],
            "2015-10-21T00:00:00.000Z",
        )

    def test_plugins_apis_ecmwf_query_without_collection(self):
        """
        EcmwfApi.query must build a EOProduct from input parameters without collection.
        For test only, result cannot be downloaded.
        """
        results = self.api_plugin.query(**self.query_dates)
        assert results.number_matched == 1
        eoproduct = results.data[0]
        assert eoproduct.geometry.bounds == (-180.0, -90.0, 180.0, 90.0)
        assert (
            eoproduct.properties["start_datetime"] == self.query_dates["start_datetime"]
        )
        assert eoproduct.properties["end_datetime"] == self.query_dates["end_datetime"]
        assert eoproduct.properties["title"] == eoproduct.properties["id"]
        assert eoproduct.properties["title"].startswith("MARS___")
        assert eoproduct.location.startswith("http")

    def test_plugins_apis_ecmwf_query_with_collection(self):
        """EcmwfApi.query must build a EOProduct from input parameters with predefined collection"""
        results = self.api_plugin.query(
            **self.query_dates, collection=self.collection, geometry=[1, 2, 3, 4]
        )
        eoproduct = results.data[0]
        assert eoproduct.properties["title"].startswith(self.collection)
        assert eoproduct.geometry.bounds == (1.0, 2.0, 3.0, 4.0)
        # check if collection_params is a subset of eoproduct.properties
        assert self.collection_params.items() <= eoproduct.properties.items()
        params = deepcopy(self.query_dates)
        params["collection"] = self.collection
        params["ecmwf:param"] = "tcc"

        # collection default settings can be overwritten using search kwargs
        results = self.api_plugin.query(**params)
        eoproduct = results.data[0]
        assert eoproduct.properties["ecmwf:param"] == "tcc"

    def test_plugins_apis_ecmwf_query_with_custom_collection(self):
        """EcmwfApi.query must build a EOProduct from input parameters with custom collection"""
        results = self.api_plugin.query(
            **self.query_dates,
            **self.custom_query_params,
        )
        eoproduct = results.data[0]
        assert eoproduct.properties["title"].startswith(
            "%s_%s_%s"
            % (
                self.custom_query_params["ecmwf:dataset"].upper(),
                self.custom_query_params["ecmwf:type"].upper(),
                self.custom_query_params["ecmwf:levtype"].upper(),
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
        assert auth_dict["url"] == self.api_plugin.config.auth_endpoint
        del self.api_plugin.config.credentials

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.sessions.Session.request",
        autospec=True,
    )
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_collections_list", autospec=True
    )
    @mock.patch("ecmwfapi.api.ECMWFService.execute", autospec=True)
    @mock.patch("ecmwfapi.api.ECMWFDataServer.retrieve", autospec=True)
    @mock.patch("ecmwfapi.api.Connection.call", autospec=True)
    def test_plugins_apis_ecmwf_download(
        self,
        mock_connection_call,
        mock_ecmwfdataserver_retrieve,
        mock_ecmwfservice_execute,
        mock_fetch_collections_list,
        mock_auth_session_request,
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
        results = dag.search(
            **self.query_dates,
            **self.custom_query_params,
            validate=False,
        )
        eoproduct = results.data[0]
        expected_path = os.path.join(
            output_data_path, "%s" % eoproduct.properties["title"]
        )
        arg_path = os.path.join(
            output_data_path,
            "%s" % eoproduct.properties["title"],
            "%s.grib" % eoproduct.properties["title"],
        )
        path = eoproduct.download(output_dir=output_data_path)
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
        operation_archive_custom_query_params.pop("ecmwf:dataset")
        results = dag.search(
            **self.query_dates,
            **operation_archive_custom_query_params,
            validate=False,
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
        path = eoproduct.download(output_dir=output_data_path)
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
        eoproduct.download(output_dir=output_data_path)
        mock_ecmwfservice_execute.assert_not_called()
        mock_ecmwfdataserver_retrieve.assert_not_called()

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.sessions.Session.request",
        autospec=True,
    )
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_collections_list", autospec=True
    )
    @mock.patch("ecmwfapi.api.ECMWFDataServer.retrieve", autospec=True)
    @mock.patch("ecmwfapi.api.Connection.call", autospec=True)
    def test_plugins_apis_ecmwf_download_all(
        self,
        mock_connection_call,
        mock_ecmwfdataserver_retrieve,
        mock_fetch_collections_list,
        mock_auth_session_request,
    ):
        """EcmwfApi.download_all must call the appropriate ecmwf api service"""

        dag = EODataAccessGateway()
        dag.set_preferred_provider("ecmwf")

        eoproducts = SearchResult([])

        # public dataset request
        params = deepcopy(self.query_dates)
        params.update(self.custom_query_params)
        params["ecmwf:accuracy"] = "bar"
        params["validate"] = False
        results = dag.search(**params)
        eoproducts.extend(results)
        params["ecmwf:accuracy"] = "baz"
        results = dag.search(**params)
        eoproducts.extend(results)
        assert len(eoproducts) == 2

        paths = dag.download_all(
            eoproducts, output_dir=os.path.join(os.path.expanduser("~"), "data")
        )
        assert mock_ecmwfdataserver_retrieve.call_count == 2
        assert len(paths) == 2


class TestApisPluginUsgsApi(BaseApisPluginTest):
    SCENE_SEARCH_RETURN = {
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
    }

    DOWNLOAD_OPTION_RETURN = {
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
    }

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

        # with obsolete `.usgs` API file (USGSError)
        mock_api_login.side_effect = [
            USGSError("USGS error"),
            None,
        ]
        with (
            mock.patch("os.remove", autospec=True) as mock_os_remove,
            mock.patch("os.path.isfile", autospec=True) as mock_isfile,
        ):
            self.api_plugin.authenticate()
            self.assertEqual(mock_api_login.call_count, 2)
            self.assertEqual(mock_api_logout.call_count, 0)
            mock_isfile.assert_called_once_with(USGS_TMPFILE)
            mock_os_remove.assert_called_once_with(USGS_TMPFILE)
        mock_api_login.reset_mock()
        mock_api_logout.reset_mock()

        # with invalid credentials / USGSError
        mock_api_login.side_effect = USGSError()
        with (
            mock.patch("os.remove", autospec=True),
            mock.patch("os.path.isfile", autospec=True),
            self.assertRaises(AuthenticationError),
        ):
            self.api_plugin.authenticate()
            self.assertEqual(mock_api_login.call_count, 2)
            mock_api_logout.assert_not_called()

    @mock.patch("usgs.api.login", autospec=True)
    @mock.patch("usgs.api.logout", autospec=True)
    @mock.patch(
        "usgs.api.scene_search",
        autospec=True,
        return_value=SCENE_SEARCH_RETURN,
    )
    @mock.patch(
        "usgs.api.download_options",
        autospec=True,
        return_value=DOWNLOAD_OPTION_RETURN,
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
            "collection": "LANDSAT_C2L1",
            "start_datetime": "2020-02-01",
            "end_datetime": "2020-02-10",
            "geometry": get_geometry_from_various(geometry=[10, 20, 30, 40]),
            "prep": PreparedSearch(
                items_per_page=5,
            ),
        }
        search_kwargs["prep"].next_page_token = "6"
        search_results = self.api_plugin.query(**search_kwargs)
        mock_api_scene_search.assert_called_once_with(
            "landsat_ot_c2_l1",
            start_date="2020-02-01",
            end_date="2020-02-10",
            ll={"longitude": 10.0, "latitude": 20.0},
            ur={"longitude": 30.0, "latitude": 40.0},
            max_results=5,
            starting_number=6,
        )
        self.assertEqual(search_results.data[0].provider, "usgs")
        self.assertEqual(search_results.data[0].collection, "LANDSAT_C2L1")
        self.assertEqual(
            search_results.data[0].geometry,
            shape(
                mock_api_scene_search.return_value["data"]["results"][0][
                    "spatialBounds"
                ]
            ),
        )
        self.assertEqual(
            search_results.data[0].properties["id"],
            mock_api_scene_search.return_value["data"]["results"][0]["displayId"],
        )
        self.assertEqual(
            search_results.data[0].properties["eo:cloud_cover"],
            float(
                mock_api_scene_search.return_value["data"]["results"][0]["cloudCover"]
            ),
        )
        self.assertEqual(
            search_results.data[0].properties["order:status"], ONLINE_STATUS
        )
        self.assertEqual(
            search_results.number_matched,
            mock_api_scene_search.return_value["data"]["totalHits"],
        )

    @mock.patch("usgs.api.login", autospec=True)
    @mock.patch("usgs.api.logout", autospec=True)
    @mock.patch(
        "usgs.api.scene_search",
        autospec=True,
        return_value=SCENE_SEARCH_RETURN,
    )
    @mock.patch(
        "usgs.api.download_options",
        autospec=True,
        return_value=DOWNLOAD_OPTION_RETURN,
    )
    @mock.patch(
        "usgs.api.dataset_filters",
        autospec=True,
        return_value={
            "data": [
                {"id": "foo_id", "searchSql": "DONT_USE_THIS !"},
                {"id": "bar_id", "searchSql": "USE_THIS_ID !"},
            ]
        },
    )
    def test_plugins_apis_usgs_query_by_id(
        self,
        mock_dataset_filters,
        mock_api_download_options,
        mock_api_scene_search,
        mock_api_logout,
        mock_api_login,
    ):
        """UsgsApi.query by id must search using usgs api"""

        search_kwargs = {
            "collection": "LANDSAT_C2L1",
            "id": "SOME_PRODUCT_ID",
            "prep": PreparedSearch(
                items_per_page=500,
            ),
        }
        search_kwargs["prep"].next_page_token = "1"
        search_results = self.api_plugin.query(**search_kwargs)
        mock_api_scene_search.assert_called_once_with(
            "landsat_ot_c2_l1",
            where={"filter_id": "bar_id", "value": "SOME_PRODUCT_ID"},
            start_date=None,
            end_date=None,
            ll=None,
            ur=None,
            max_results=500,
            starting_number=1,
        )
        self.assertEqual(search_results.data[0].provider, "usgs")
        self.assertEqual(search_results.data[0].collection, "LANDSAT_C2L1")
        self.assertEqual(len(search_results.data), 1)

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
                    collection="L8_OLI_TIRS_C1L1",
                    **{
                        "usgs:entityId": "dummyEntityId",
                        "usgs:productId": "dummyProductId",
                    },
                ),
            )
            product.location = product.remote_location = product.properties[
                "eodag:download_link"
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
                self.api_plugin.download(product, output_dir=self.tmp_home_dir.name)

            # download 1 available product
            mock_api_download_request.return_value = {
                "data": {"preparingDownloads": [{"url": "http://path/to/product"}]}
            }

            path = self.api_plugin.download(product, output_dir=self.tmp_home_dir.name)

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
                    product, output_dir=self.tmp_home_dir.name, extract=False
                )
                self.assertEqual(
                    path, os.path.join(self.tmp_home_dir.name, "dummy_product.tar.gz")
                )
            # zip
            os.remove(path)
            product.collection = "S2_MSI_L1C"
            with mock.patch("zipfile.is_zipfile", return_value=True, autospec=True):
                path = self.api_plugin.download(
                    product, output_dir=self.tmp_home_dir.name, extract=False
                )
                self.assertEqual(
                    path, os.path.join(self.tmp_home_dir.name, "dummy_product.zip")
                )

        run()
