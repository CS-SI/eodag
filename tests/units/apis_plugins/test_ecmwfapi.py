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
from unittest import mock

import geojson

from eodag import EODataAccessGateway
from eodag.api.search_result import SearchResult
from eodag.utils import deepcopy, urlsplit
from tests.units.apis_plugins.base import BaseApisPluginTest


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
        self.assertNotIn("start_datetime", eoproduct.properties)
        self.assertNotIn("end_datetime", eoproduct.properties)

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
        self.assertNotIn("start_datetime", eoproduct.properties)
        self.assertNotIn("end_datetime", eoproduct.properties)

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

        assert (
            eoproduct.assets.get("download_link", {}).get("href", "").startswith("http")
        )

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

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.requests.sessions.Session.request",
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
            path = args[1]["target"]
            if not os.path.isfile(path):
                open(path, "x").close()

        mock_ecmwfdataserver_retrieve.side_effect = create_empty_file_for_public_dataset
        results = dag.search(
            **self.query_dates,
            **self.custom_query_params,
            validate=False,
        )
        eoproduct = results.data[0]
        expected_path = os.path.join(
            output_data_path,
            "%s" % eoproduct.properties["title"],
            "download_link.grib",
        )
        path = eoproduct.download(output_dir=output_data_path, no_cache=True)
        href = eoproduct.assets.get("download_link", {}).get("href", "")
        mock_ecmwfservice_execute.assert_not_called()

        self.assertEqual(path[0], expected_path)

        mock_ecmwfdataserver_retrieve.assert_called_with(
            mock.ANY,  # ECMWFDataServer instance
            dict(
                target=expected_path,
                **geojson.loads(urlsplit(href).query),
            ),
        )

        mock_ecmwfservice_execute.reset_mock()
        mock_ecmwfdataserver_retrieve.reset_mock()

        # operation archive request
        def create_empty_file_for_operation_archive(*args, **kwargs):
            path = args[2]
            if not os.path.isfile(path):
                open(path, "x").close()

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
            output_data_path,
            "%s" % eoproduct.properties["title"],
            "download_link.grib",
        )

        path = eoproduct.download(no_cache=True, output_dir=output_data_path)

        href = eoproduct.assets.get("download_link", {}).get("href", "")

        download_request = geojson.loads(urlsplit(href).query)
        download_request.pop("dataset", None)
        mock_ecmwfdataserver_retrieve.assert_called_with(
            mock.ANY,  # ECMWFDataServer instance
            dict(
                target=expected_path,
                **geojson.loads(urlsplit(href).query),
            ),
        )

        mock_ecmwfservice_execute.reset_mock()
        assert path[0] == expected_path

        mock_ecmwfservice_execute.reset_mock()
        mock_ecmwfdataserver_retrieve.reset_mock()

        # download again (cached)
        eoproduct.download(output_dir=output_data_path)
        mock_ecmwfservice_execute.assert_not_called()
        mock_ecmwfdataserver_retrieve.assert_not_called()

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.requests.sessions.Session.request",
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
        call_count = 0

        # public dataset request
        params: dict = deepcopy(self.query_dates)  # type: ignore
        params.update(self.custom_query_params)
        params["ecmwf:accuracy"] = "bar"
        params["validate"] = False
        results = dag.search(**params)
        call_count += len(results)

        eoproducts.extend(results)
        params["ecmwf:accuracy"] = "baz"
        results = dag.search(**params)
        call_count += len(results)

        eoproducts.extend(results)
        assert len(eoproducts) == 2

        paths = dag.download_all(
            eoproducts, output_dir=os.path.join(os.path.expanduser("~"), "data")
        )
        call_count += len(paths)

        assert mock_ecmwfdataserver_retrieve.call_count == call_count
        assert len(paths) == 2


__all__ = ["TestApisPluginEcmwfApi"]
