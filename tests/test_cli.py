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

import os
import random
import re
import unittest
from contextlib import contextmanager
from datetime import datetime
from tempfile import TemporaryDirectory

import click
from click.testing import CliRunner
from faker import Faker
from packaging import version
from pkg_resources import resource_filename

from eodag.utils import GENERIC_PRODUCT_TYPE
from tests import TEST_RESOURCES_PATH
from tests.context import (
    DEFAULT_ITEMS_PER_PAGE,
    AuthenticationError,
    MisconfiguredError,
    NoMatchingProductType,
    download,
    eodag,
    search_crunch,
    setup_logging,
)
from tests.units import test_core
from tests.utils import mock, no_blanks, write_eodag_conf_with_fake_credentials


class TestEodagCli(unittest.TestCase):
    @contextmanager
    def user_conf(self, conf_file="user_conf.yml", content=b"key: to unused conf"):
        """Utility method"""
        with self.runner.isolated_filesystem():
            with open(conf_file, "wb") as fd:
                fd.write(
                    content if isinstance(content, bytes) else content.encode("utf-8")
                )
            yield conf_file

    def setUp(self):
        super(TestEodagCli, self).setUp()
        self.runner = CliRunner()
        self.faker = Faker()

        # Mock home and eodag conf directory to tmp dir
        self.tmp_home_dir = TemporaryDirectory()
        self.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, return_value=self.tmp_home_dir.name
        )
        self.expanduser_mock.start()

        # create eodag conf dir in tmp home dir
        eodag_conf_dir = os.path.join(self.tmp_home_dir.name, ".config", "eodag")
        os.makedirs(eodag_conf_dir, exist_ok=False)
        # use empty config file with fake credentials in order to have full
        # list for tests and prevent providers to be pruned
        write_eodag_conf_with_fake_credentials(
            os.path.join(eodag_conf_dir, "eodag.yml")
        )

    def tearDown(self):
        super(TestEodagCli, self).tearDown()
        # Default logging: no logging but still displays progress bars
        setup_logging(1)
        # stop Mock and remove tmp config dir
        self.expanduser_mock.stop()
        self.tmp_home_dir.cleanup()

    def test_eodag_without_args(self):
        """Calling eodag without arguments should print help message"""
        result = self.runner.invoke(eodag)
        self.assertIn("Usage: eodag [OPTIONS] COMMAND [ARGS]...", result.output)
        self.assertEqual(result.exit_code, 0)

    def test_eodag_with_only_verbose_opt(self):
        """Calling eodag only with -v option should print error message"""
        result = self.runner.invoke(eodag, ["-v"])
        self.assertIn("Error: Missing command.", result.output)
        self.assertNotEqual(result.exit_code, 0)

    def test_eodag_cli_version(self):
        """Calling eodag version should return the version"""
        result = self.runner.invoke(eodag, ["version"])
        version_str = re.search(r"eodag .* version (.+)\s*$", result.output).group(1)
        self.assertGreater(version.parse(version_str), version.parse("2.0.0"))

    def test_eodag_search_without_args(self):
        """Calling eodag search subcommand without arguments should print help message and return error code"""  # noqa
        result = self.runner.invoke(eodag, ["search"])
        with click.Context(search_crunch) as ctx:
            self.assertEqual(
                no_blanks(result.output),
                no_blanks(
                    "".join(
                        (
                            "Give me some work to do. See below for how to do that:",
                            ctx.get_help(),
                        )
                    )
                ),
            )
        self.assertNotEqual(result.exit_code, 0)

    def test_eodag_search_without_producttype_arg(self):
        """Calling eodag search without -p | --productType should print the help message and return error code"""  # noqa
        start_date = self.faker.date()
        end_date = self.faker.date()
        result = self.runner.invoke(eodag, ["search", "-s", start_date, "-e", end_date])
        with click.Context(search_crunch) as ctx:
            self.assertEqual(
                no_blanks(result.output),
                no_blanks(
                    "".join(
                        (
                            "Give me some work to do. See below for how to do that:",
                            ctx.get_help(),
                        )
                    )
                ),
            )
        self.assertNotEqual(result.exit_code, 0)

    def test_eodag_search_with_conf_file_inexistent(self):
        """Calling eodag search with --conf | -f set to a non-existent file should print error message"""  # noqa
        conf_file = "does_not_exist.yml"
        result = self.runner.invoke(
            eodag, ["search", "--conf", conf_file, "-p", "whatever"]
        )
        expect_output = "Error: Invalid value for '-f' / '--conf': Path '{}' does not exist.".format(  # noqa
            conf_file
        )
        self.assertTrue(
            expect_output in result.output or expect_output.replace("'", '"')
        )
        self.assertNotEqual(result.exit_code, 0)

    def test_eodag_search_with_max_cloud_out_of_range(self):
        """Calling eodag search with -c | --maxCloud set to a value < 0 or > 100 should print error message"""  # noqa
        with self.user_conf() as conf_file:
            for max_cloud in (110, -1):
                result = self.runner.invoke(
                    eodag,
                    ["search", "--conf", conf_file, "-p", "whatever", "-c", max_cloud],
                )
                expect_output = (
                    "Error: Invalid value for '-c' / '--cloudCover': {} is not in the"
                    " valid range of 0 to 100."
                ).format(max_cloud)
                self.assertTrue(
                    expect_output in result.output or expect_output.replace("'", '"')
                )
                self.assertNotEqual(result.exit_code, 0)

    def test_eodag_search_bbox_invalid(self):
        """Calling eodag search with -b | --bbox set with less than 4 params should print error message"""  # noqa
        with self.user_conf() as conf_file:
            result = self.runner.invoke(
                eodag, ["search", "--conf", conf_file, "-p", "whatever", "-b", 1, 2]
            )
            self.assertIn("-b", result.output)
            self.assertIn("requires 4 arguments", result.output)
            self.assertNotEqual(result.exit_code, 0)

    @mock.patch("eodag.cli.EODataAccessGateway", autospec=True)
    def test_eodag_search_bbox_valid(self, dag):
        """Calling eodag search with --bbox argument valid"""
        with self.user_conf() as conf_file:
            product_type = "whatever"
            self.runner.invoke(
                eodag,
                ["search", "--conf", conf_file, "-p", product_type, "-b", 1, 43, 2, 44],
            )
            api_obj = dag.return_value
            api_obj.search.assert_called_once_with(
                items_per_page=DEFAULT_ITEMS_PER_PAGE,
                page=1,
                startTimeFromAscendingNode=None,
                completionTimeFromAscendingNode=None,
                cloudCover=None,
                geometry={"lonmin": 1, "latmin": 43, "lonmax": 2, "latmax": 44},
                instrument=None,
                platform=None,
                platformSerialIdentifier=None,
                processingLevel=None,
                sensorType=None,
                productType=product_type,
                id=None,
                locations=None,
            )

    def test_eodag_search_geom_wkt_invalid(self):
        """Calling eodag search with -g | --geom set with invalit WKT geometry string"""  # noqa
        with self.user_conf() as conf_file:
            result = self.runner.invoke(
                eodag,
                ["search", "--conf", conf_file, "-p", "whatever", "-g", "not a wkt"],
            )
            self.assertIn("WKTReadingError", str(result))
            self.assertNotEqual(result.exit_code, 0)

    @mock.patch("eodag.cli.EODataAccessGateway", autospec=True)
    def test_eodag_search_geom_wkt_valid(self, dag):
        """Calling eodag search with --geom WKT argument valid"""
        with self.user_conf() as conf_file:
            product_type = "whatever"
            self.runner.invoke(
                eodag,
                [
                    "search",
                    "--conf",
                    conf_file,
                    "-p",
                    product_type,
                    "-g",
                    "POLYGON ((1 43, 1 44, 2 44, 2 43, 1 43))",
                ],
            )
            api_obj = dag.return_value
            api_obj.search.assert_called_once_with(
                items_per_page=DEFAULT_ITEMS_PER_PAGE,
                page=1,
                startTimeFromAscendingNode=None,
                completionTimeFromAscendingNode=None,
                cloudCover=None,
                geometry="POLYGON ((1 43, 1 44, 2 44, 2 43, 1 43))",
                instrument=None,
                platform=None,
                platformSerialIdentifier=None,
                processingLevel=None,
                sensorType=None,
                productType=product_type,
                id=None,
                locations=None,
            )

    def test_eodag_search_bbox_geom_mutually_exclusive(self):
        """Calling eodag search with both --geom and --box"""  # noqa
        with self.user_conf() as conf_file:
            result = self.runner.invoke(
                eodag,
                [
                    "search",
                    "--conf",
                    conf_file,
                    "-p",
                    "whatever",
                    "-b",
                    1,
                    2,
                    3,
                    4,
                    "-g",
                    "a wkt",
                ],
            )
            self.assertIn("Illegal usage", result.output)
            self.assertNotEqual(result.exit_code, 0)

    @mock.patch("eodag.cli.EODataAccessGateway", autospec=True)
    def test_eodag_search_storage_arg(self, dag):
        """Calling eodag search with specified result filename without .geojson extension"""  # noqa
        with self.user_conf() as conf_file:
            api_obj = dag.return_value
            api_obj.search.return_value = (mock.MagicMock(),) * 2
            self.runner.invoke(
                eodag,
                [
                    "search",
                    "--conf",
                    conf_file,
                    "-p",
                    "whatever",
                    "--storage",
                    "results",
                ],
            )
            api_obj.serialize.assert_called_with(
                api_obj.search.return_value[0], filename="results.geojson"
            )

    @mock.patch("eodag.cli.EODataAccessGateway", autospec=True)
    def test_eodag_search_with_cruncher(self, dag):
        """Calling eodag search with --cruncher arg should call crunch method of search result"""  # noqa
        with self.user_conf() as conf_file:
            api_obj = dag.return_value
            api_obj.search.return_value = (mock.MagicMock(),) * 2

            product_type = "whatever"
            cruncher = "FilterLatestIntersect"
            criteria = dict(
                startTimeFromAscendingNode=None,
                completionTimeFromAscendingNode=None,
                geometry=None,
                cloudCover=None,
                instrument=None,
                platform=None,
                platformSerialIdentifier=None,
                processingLevel=None,
                sensorType=None,
                productType=product_type,
                id=None,
                locations=None,
            )
            self.runner.invoke(
                eodag,
                ["search", "-f", conf_file, "-p", product_type, "--cruncher", cruncher],
            )

            search_results = api_obj.search.return_value[0]
            crunch_results = api_obj.crunch.return_value

            # Assertions
            dag.assert_called_once_with(
                user_conf_file_path=conf_file, locations_conf_path=None
            )
            api_obj.search.assert_called_once_with(
                items_per_page=DEFAULT_ITEMS_PER_PAGE, page=1, **criteria
            )
            api_obj.crunch.assert_called_once_with(
                search_results, search_criteria=criteria, **{cruncher: {}}
            )
            api_obj.serialize.assert_called_with(
                crunch_results, filename="search_results.geojson"
            )

            # Call with a cruncher taking arguments
            cruncher = "FilterOverlap"
            self.runner.invoke(
                eodag,
                [
                    "search",
                    "-f",
                    conf_file,
                    "-p",
                    product_type,
                    "--cruncher",
                    cruncher,
                    "--cruncher-args",
                    cruncher,
                    "minimum_overlap",
                    "10",
                ],
            )
            api_obj.crunch.assert_called_with(
                search_results,
                search_criteria=criteria,
                **{cruncher: {"minimum_overlap": "10"}},
            )

    @mock.patch("eodag.cli.EODataAccessGateway", autospec=True)
    def test_eodag_search_all(self, dag):
        """Calling eodag search with --bbox argument valid"""
        with self.user_conf() as conf_file:
            product_type = "whatever"
            self.runner.invoke(
                eodag,
                [
                    "search",
                    "--conf",
                    conf_file,
                    "-p",
                    product_type,
                    "-g",
                    "POLYGON ((1 43, 1 44, 2 44, 2 43, 1 43))",
                    "--all",
                ],
            )
            api_obj = dag.return_value
            api_obj.search_all.assert_called_once_with(
                items_per_page=None,
                startTimeFromAscendingNode=None,
                completionTimeFromAscendingNode=None,
                cloudCover=None,
                geometry="POLYGON ((1 43, 1 44, 2 44, 2 43, 1 43))",
                instrument=None,
                platform=None,
                platformSerialIdentifier=None,
                processingLevel=None,
                sensorType=None,
                productType=product_type,
                id=None,
                locations=None,
            )

    @mock.patch("eodag.cli.EODataAccessGateway", autospec=True)
    def test_eodag_search_query(self, dag):
        """Calling eodag search with --query argument"""
        with self.user_conf() as conf_file:
            product_type = "whatever"
            self.runner.invoke(
                eodag,
                [
                    "search",
                    "--conf",
                    conf_file,
                    "-p",
                    product_type,
                    "--query",
                    "foo=1&bar=2&bar=3",
                ],
            )
            api_obj = dag.return_value
            api_obj.search.assert_called_once_with(
                page=1,
                items_per_page=20,
                geometry=None,
                startTimeFromAscendingNode=None,
                completionTimeFromAscendingNode=None,
                cloudCover=None,
                productType=product_type,
                instrument=None,
                platform=None,
                platformSerialIdentifier=None,
                processingLevel=None,
                sensorType=None,
                id=None,
                foo="1",
                bar=["2", "3"],
                locations=None,
            )

    @mock.patch("eodag.cli.EODataAccessGateway", autospec=True)
    def test_eodag_search_locations(self, dag):
        """Calling eodag search with --locations argument"""
        with self.user_conf() as conf_file:
            product_type = "whatever"
            self.runner.invoke(
                eodag,
                [
                    "search",
                    "--conf",
                    conf_file,
                    "-p",
                    product_type,
                    "--locations",
                    "country=FRA&continent=Africa",
                ],
            )
            api_obj = dag.return_value
            api_obj.search.assert_called_once_with(
                page=1,
                items_per_page=20,
                geometry=None,
                startTimeFromAscendingNode=None,
                completionTimeFromAscendingNode=None,
                cloudCover=None,
                productType=product_type,
                instrument=None,
                platform=None,
                platformSerialIdentifier=None,
                processingLevel=None,
                sensorType=None,
                id=None,
                locations={"country": "FRA", "continent": "Africa"},
            )

    @mock.patch("eodag.cli.EODataAccessGateway", autospec=True)
    def test_eodag_search_start_date(self, dag):
        """Calling eodag search with --start argument"""
        with self.user_conf() as conf_file:
            product_type = "whatever"
            start_date_str = "2022-01-01"
            start_date_datetime = datetime.strptime(
                start_date_str, "%Y-%m-%d"
            ).isoformat()
            self.runner.invoke(
                eodag,
                [
                    "search",
                    "--conf",
                    conf_file,
                    "-p",
                    product_type,
                    "--start",
                    start_date_str,
                ],
            )
            api_obj = dag.return_value
            api_obj.search.assert_called_once_with(
                page=1,
                items_per_page=20,
                geometry=None,
                startTimeFromAscendingNode=start_date_datetime,
                completionTimeFromAscendingNode=None,
                cloudCover=None,
                productType=product_type,
                instrument=None,
                platform=None,
                platformSerialIdentifier=None,
                processingLevel=None,
                sensorType=None,
                id=None,
                locations=None,
            )

    @mock.patch("eodag.cli.EODataAccessGateway", autospec=True)
    def test_eodag_search_stop_date(self, dag):
        """Calling eodag search with --end argument"""
        with self.user_conf() as conf_file:
            product_type = "whatever"
            stop_date_str = "2022-01-01"
            stop_date_datetime = datetime.strptime(
                stop_date_str, "%Y-%m-%d"
            ).isoformat()
            self.runner.invoke(
                eodag,
                [
                    "search",
                    "--conf",
                    conf_file,
                    "-p",
                    product_type,
                    "--end",
                    stop_date_str,
                ],
            )
            api_obj = dag.return_value
            api_obj.search.assert_called_once_with(
                page=1,
                items_per_page=20,
                geometry=None,
                startTimeFromAscendingNode=None,
                completionTimeFromAscendingNode=stop_date_datetime,
                cloudCover=None,
                productType=product_type,
                instrument=None,
                platform=None,
                platformSerialIdentifier=None,
                processingLevel=None,
                sensorType=None,
                id=None,
                locations=None,
            )

    @mock.patch("eodag.cli.EODataAccessGateway", autospec=True)
    def test_eodag_search_locs(self, dag):
        """Calling eodag search with --locs argument"""
        with self.user_conf() as conf_file:
            locs_file = os.path.join(TEST_RESOURCES_PATH, "file_locations_override.yml")

            product_type = "whatever"
            self.runner.invoke(
                eodag,
                [
                    "search",
                    "--conf",
                    conf_file,
                    "--locs",
                    locs_file,
                    "-p",
                    product_type,
                ],
            )

            dag.assert_called_once_with(
                user_conf_file_path=conf_file, locations_conf_path=locs_file
            )

    def test_eodag_list_product_type_ok(self):
        """Calling eodag list without provider should return all supported product types"""
        all_supported_product_types = [
            pt
            for pt, provs in test_core.TestCore.SUPPORTED_PRODUCT_TYPES.items()
            if len(provs) != 0 and pt != GENERIC_PRODUCT_TYPE
        ]
        result = self.runner.invoke(eodag, ["list", "--no-fetch"])
        self.assertEqual(result.exit_code, 0)
        for pt in all_supported_product_types:
            self.assertIn(pt, result.output)

    def test_eodag_list_product_type_with_provider_ok(self):
        """Calling eodag list with provider should return all supported product types of specified provider"""  # noqa
        provider = random.choice(test_core.TestCore.SUPPORTED_PROVIDERS)
        provider_supported_product_types = [
            pt
            for pt, provs in test_core.TestCore.SUPPORTED_PRODUCT_TYPES.items()
            if provider in provs
            if pt != GENERIC_PRODUCT_TYPE
        ]
        result = self.runner.invoke(eodag, ["list", "-p", provider, "--no-fetch"])
        self.assertEqual(result.exit_code, 0)
        for pt in provider_supported_product_types:
            self.assertIn(pt, result.output)

    def test_eodag_list_product_type_with_provider_ko(self):
        """Calling eodag list with unsupported provider should fail and print a list of available providers"""  # noqa
        provider = "random"
        result = self.runner.invoke(eodag, ["list", "-p", provider, "--no-fetch"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Unsupported provider. You may have a typo", result.output)
        self.assertIn(
            "Available providers: {}".format(
                ", ".join(sorted(test_core.TestCore.SUPPORTED_PROVIDERS))
            ),
            result.output,
        )

    @mock.patch("eodag.cli.EODataAccessGateway.fetch_product_types_list", autospec=True)
    def test_eodag_list_product_type_fetch(self, mock_fetch_product_types_list):
        """Calling eodag list should fetch for new product types depending on passed option"""
        result = self.runner.invoke(eodag, ["list", "--no-fetch"])
        self.assertEqual(result.exit_code, 0)
        assert not mock_fetch_product_types_list.called

        result = self.runner.invoke(eodag, ["list"])
        self.assertEqual(result.exit_code, 0)
        mock_fetch_product_types_list.assert_called_once_with(mock.ANY, provider=None)

        result = self.runner.invoke(eodag, ["list", "-p", "peps"])
        self.assertEqual(result.exit_code, 0)
        mock_fetch_product_types_list.assert_called_with(mock.ANY, provider="peps")
        self.assertEqual(mock_fetch_product_types_list.call_count, 2)

    @mock.patch("eodag.cli.EODataAccessGateway.list_product_types", autospec=True)
    @mock.patch("eodag.cli.EODataAccessGateway.guess_product_type", autospec=True)
    def test_eodag_guess_product_type_ok(
        self, mock_guess_product_type, mock_list_product_types
    ):
        """Calling eodag list with one or several valid product type feature(s) should return all supported product types with this (these) feature(s) among the ones of its provider and with or without fetching provider according to the command"""  # noqa
        provider = "peps"
        mock_guess_product_type.return_value = ["foo", "bar"]
        mock_list_product_types.return_value = [
            {"ID": "foo", "title": "this is foo"},
            {"ID": "bar", "title": "this is bar"},
            {"ID": "baz", "title": "this is baz"},
        ]

        result = self.runner.invoke(
            eodag,
            ["list", "-p", provider, "--platformSerialIdentifier", "S2A", "--no-fetch"],
        )
        self.assertEqual(result.exit_code, 0)

        self.assertIn("foo", result.output)
        self.assertIn("bar", result.output)
        self.assertNotIn("baz", result.output)

        mock_list_product_types.assert_called_with(
            mock.ANY, provider=provider, fetch_providers=False
        )

    @mock.patch(
        "eodag.cli.EODataAccessGateway.guess_product_type",
        autospec=True,
        side_effect=NoMatchingProductType(),
    )
    def test_eodag_guess_product_type_ko(self, mock_guess_product_type):
        """Calling eodag list with invalid product type feature(s) should print a 'no matching' type message and return error code"""  # noqa
        result = self.runner.invoke(
            eodag,
            ["list", "--platformSerialIdentifier", "fake_identifier", "--no-fetch"],
        )
        self.assertIn(
            "No product type match the following criteria you provided:\n",
            result.output,
        )
        self.assertNotEqual(result.exit_code, 0)

    @mock.patch(
        "eodag.cli.EODataAccessGateway.discover_product_types",
        autospec=True,
        return_value={},
    )
    def test_eodag_discover_product_types(self, mock_discover_product_types):
        """Calling eodag discover should fetch providers for new product types"""
        origin_dir = os.getcwd()
        try:
            os.chdir(self.tmp_home_dir.name)
            default_output_path = os.path.join(
                self.tmp_home_dir.name, "ext_product_types.json"
            )
            self.assertFalse(os.path.isfile(default_output_path))

            # call without any arg
            result = self.runner.invoke(eodag, ["discover"])
            self.assertEqual(result.exit_code, 0)
            mock_discover_product_types.assert_called_once_with(mock.ANY)
            self.assertTrue(os.path.isfile(default_output_path))

            # call with provider
            result = self.runner.invoke(eodag, ["discover", "-p", "peps"])
            self.assertEqual(result.exit_code, 0)
            mock_discover_product_types.assert_called_with(mock.ANY, provider="peps")
            self.assertEqual(mock_discover_product_types.call_count, 2)
            os.remove(default_output_path)

            other_file_path = os.path.join(self.tmp_home_dir.name, "toto")
            # call with filename without extension
            self.assertFalse(os.path.isfile(other_file_path))
            self.assertFalse(os.path.isfile(f"{other_file_path}.json"))
            result = self.runner.invoke(eodag, ["discover", "--storage", "toto"])
            self.assertEqual(result.exit_code, 0)
            mock_discover_product_types.assert_called_with(mock.ANY)
            self.assertEqual(mock_discover_product_types.call_count, 3)
            self.assertFalse(os.path.isfile(other_file_path))
            self.assertTrue(os.path.isfile(f"{other_file_path}.json"))
            os.remove(f"{other_file_path}.json")

            # call with filename with extension
            self.assertFalse(os.path.isfile(f"{other_file_path}.json"))
            result = self.runner.invoke(eodag, ["discover", "--storage", "toto.json"])
            self.assertEqual(result.exit_code, 0)
            mock_discover_product_types.assert_called_with(mock.ANY)
            self.assertEqual(mock_discover_product_types.call_count, 4)
            self.assertTrue(os.path.isfile(f"{other_file_path}.json"))
            os.remove(f"{other_file_path}.json")
        finally:
            os.chdir(origin_dir)

    def test_eodag_download_no_search_results_arg(self):
        """Calling eodag download without a path to a search result should fail"""
        result = self.runner.invoke(eodag, ["download"])
        with click.Context(download) as ctx:
            self.assertEqual(
                no_blanks(result.output),
                no_blanks(
                    "".join(
                        (
                            "Nothing to do (no search results file provided)",
                            ctx.get_help(),
                        )
                    )
                ),
            )
        self.assertEqual(result.exit_code, 1)

    @mock.patch("eodag.cli.EODataAccessGateway", autospec=True)
    def test_eodag_download_ok(self, dag):
        """Calling eodag download with all args well formed succeed"""
        search_results_path = os.path.join(
            TEST_RESOURCES_PATH, "eodag_search_result.geojson"
        )
        config_path = os.path.join(TEST_RESOURCES_PATH, "file_config_override.yml")
        dag.return_value.download_all.return_value = ["/fake_path"]
        result = self.runner.invoke(
            eodag,
            ["download", "--search-results", search_results_path, "-f", config_path],
        )
        dag.assert_called_once_with(user_conf_file_path=config_path)
        dag.return_value.deserialize.assert_called_once_with(search_results_path)
        self.assertEqual(dag.return_value.download_all.call_count, 1)
        self.assertEqual("Downloaded /fake_path\n", result.output)

        # Testing the case when no downloaded path is returned
        dag.return_value.download_all.return_value = [None]
        result = self.runner.invoke(
            eodag,
            ["download", "--search-results", search_results_path, "-f", config_path],
        )
        self.assertEqual(
            "A file may have been downloaded but we cannot locate it\n", result.output
        )

    @mock.patch("eodag.cli.EODataAccessGateway", autospec=True)
    def test_eodag_download_ko(self, dag):
        """Calling eodag download with all args well formed fails"""
        search_results_path = os.path.join(
            TEST_RESOURCES_PATH, "eodag_search_result.geojson"
        )
        config_path = os.path.join(TEST_RESOURCES_PATH, "file_config_override.yml")
        dag.return_value.download_all.return_value = []
        result = self.runner.invoke(
            eodag,
            ["download", "--search-results", search_results_path, "-f", config_path],
        )
        self.assertEqual(
            "Error during download, a file may have been downloaded but we cannot locate it\n",
            result.output,
        )

    def test_eodag_download_missingcredentials(self):
        """Calling eodag download with missing credentials must raise MisconfiguredError"""
        search_results_path = os.path.join(
            TEST_RESOURCES_PATH, "eodag_search_result.geojson"
        )
        default_conf_file = resource_filename(
            "eodag", os.path.join("resources", "user_conf_template.yml")
        )
        result = self.runner.invoke(
            eodag,
            [
                "download",
                "--search-results",
                search_results_path,
                "-f",
                default_conf_file,
            ],
        )
        self.assertEqual(result.exit_code, 1)
        self.assertIsInstance(result.exception, MisconfiguredError)

    @mock.patch("eodag.plugins.download.http.HTTPDownload.download", autospec=True)
    def test_eodag_download_wrongcredentials(self, download):
        """Calling eodag download with wrong credentials must raise AuthenticationError"""
        # This is not an end-to-end test so we have to manually raise the error down
        # to HTTPDownload.download. This is indeed the download plugin of PEPS which
        # is used here since the GeoJSON results were obtained from this provider.
        download.side_effect = AuthenticationError
        search_results_path = os.path.join(
            TEST_RESOURCES_PATH, "eodag_search_result.geojson"
        )
        result = self.runner.invoke(
            eodag,
            ["download", "--search-results", search_results_path],
            # We override the default (empty) credentials with dummy values not
            # to raise a MisconfiguredError.
            env={
                "EODAG__PEPS__AUTH__CREDENTIALS__USERNAME": "dummy",
                "EODAG__PEPS__AUTH__CREDENTIALS__PASSWORD": "dummy",
            },
        )
        self.assertEqual(result.exit_code, 1)
        self.assertIsInstance(result.exception, AuthenticationError)
        self.assertEqual(download.call_count, 1)

    @mock.patch("eodag.api.product._product.EOProduct.get_quicklook", autospec=True)
    def test_eodag_download_quicklooks(self, mock_get_quicklook):
        """Calling eodag download with --quicklooks argument"""
        search_results_path = os.path.join(
            TEST_RESOURCES_PATH, "eodag_search_result_peps.geojson"
        )
        config_path = os.path.join(TEST_RESOURCES_PATH, "file_config_override.yml")
        mock_get_quicklook.return_value = "/fake_path"
        result = self.runner.invoke(
            eodag,
            [
                "download",
                "--search-results",
                search_results_path,
                "-f",
                config_path,
                "--quicklooks",
            ],
        )
        self.assertIn(
            "Flag 'quicklooks' specified, downloading only quicklooks of products\n",
            result.output,
        )

        # 2 quicklooks are called in search_results_path
        self.assertEqual(mock_get_quicklook.call_count, 2)
        self.assertIn("Downloaded /fake_path\n", result.output)

        # Testing the case when no quicklook path is returned
        mock_get_quicklook.return_value = None
        result = self.runner.invoke(
            eodag,
            [
                "download",
                "--search-results",
                search_results_path,
                "-f",
                config_path,
                "--quicklooks",
            ],
        )
        self.assertIn(
            "A quicklook may have been downloaded but we cannot locate it. "
            "Increase verbosity for more details: `eodag -v download [OPTIONS]`",
            result.output,
        )
