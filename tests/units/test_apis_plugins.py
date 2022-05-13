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
from tempfile import TemporaryDirectory
from unittest import mock

from ecmwfapi.api import ANONYMOUS_APIKEY_VALUES

from tests.context import (
    EODataAccessGateway,
    PluginManager,
    SearchResult,
    ValidationError,
    load_default_config,
    parse_qsl,
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
            "type": "pf",
            "class": "ti",
        }

    def test_plugins_apis_ecmwf_query_mandatory_params_missing(self):
        """EcmwfApi.query must fails if mandatory parameters are missing"""

        self.assertRaises(
            ValidationError,
            self.api_plugin.query,
        )
        self.assertRaises(
            ValidationError,
            self.api_plugin.query,
            startTimeFromAscendingNode="foo",
        )
        self.assertRaises(
            ValidationError,
            self.api_plugin.query,
            completionTimeFromAscendingNode="foo",
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

    @mock.patch("ecmwfapi.api.ECMWFService.execute", autospec=True)
    @mock.patch("ecmwfapi.api.ECMWFDataServer.retrieve", autospec=True)
    @mock.patch("ecmwfapi.api.Connection.call", autospec=True)
    def test_plugins_apis_ecmwf_download(
        self,
        mock_connection_call,
        mock_ecmwfdataserver_retrieve,
        mock_ecmwfservice_execute,
    ):
        """EcmwfApi.download must call the appriate ecmwf api service"""

        dag = EODataAccessGateway()
        dag.set_preferred_provider("ecmwf")
        output_data_path = os.path.join(os.path.expanduser("~"), "data")

        # public dataset request
        results, _ = dag.search(
            **self.query_dates,
            **self.custom_query_params,
        )
        eoproduct = results[0]
        expected_path = os.path.join(
            output_data_path, "%s.grib" % eoproduct.properties["title"]
        )
        path = eoproduct.download(outputs_prefix=output_data_path)
        mock_ecmwfservice_execute.assert_not_called()
        mock_ecmwfdataserver_retrieve.assert_called_once_with(
            mock.ANY,  # ECMWFDataServer instance
            dict(
                target=expected_path,
                **dict(parse_qsl(urlsplit(eoproduct.remote_location).query)),
            ),
        )
        assert path_to_uri(expected_path) == eoproduct.location

        mock_ecmwfservice_execute.reset_mock()
        mock_ecmwfdataserver_retrieve.reset_mock()

        # operation archive request
        def create_empty_file(*args, **kwargs):
            with open(args[2], "x"):
                pass

        mock_ecmwfservice_execute.side_effect = create_empty_file
        operation_archive_custom_query_params = self.custom_query_params.copy()
        operation_archive_custom_query_params.pop("dataset")
        operation_archive_custom_query_params["format"] = "netcdf"
        results, _ = dag.search(
            **self.query_dates,
            **operation_archive_custom_query_params,
        )
        eoproduct = results[0]
        expected_path = os.path.join(
            output_data_path, "%s.nc" % eoproduct.properties["title"]
        )
        path = eoproduct.download(outputs_prefix=output_data_path)
        mock_ecmwfservice_execute.assert_called_once_with(
            mock.ANY,  # ECMWFService instance
            dict(parse_qsl(urlsplit(eoproduct.remote_location).query)),
            expected_path,
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

    @mock.patch("ecmwfapi.api.ECMWFDataServer.retrieve", autospec=True)
    @mock.patch("ecmwfapi.api.Connection.call", autospec=True)
    def test_plugins_apis_ecmwf_download_all(
        self,
        mock_connection_call,
        mock_ecmwfdataserver_retrieve,
    ):
        """EcmwfApi.download_all must call the appriate ecmwf api service"""

        dag = EODataAccessGateway()
        dag.set_preferred_provider("ecmwf")

        eoproducts = SearchResult([])

        # public dataset request
        results, _ = dag.search(
            **self.query_dates,
            **self.custom_query_params,
            foo="bar",
        )
        eoproducts.extend(results)
        results, _ = dag.search(
            **self.query_dates,
            **self.custom_query_params,
            foo="baz",
        )
        eoproducts.extend(results)
        assert len(eoproducts) == 2

        paths = dag.download_all(
            eoproducts, outputs_prefix=os.path.join(os.path.expanduser("~"), "data")
        )
        assert mock_ecmwfdataserver_retrieve.call_count == 2
        assert len(paths) == 2
