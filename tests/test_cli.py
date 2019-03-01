# -*- coding: utf-8 -*-
# Copyright 2018, CS Systemes d'Information, http://www.c-s.fr
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
from __future__ import unicode_literals

import os
import random
import unittest
from contextlib import contextmanager

import click
from click.testing import CliRunner
from faker import Faker

from tests import TEST_RESOURCES_PATH
from tests.units.test_core import TestCore
from tests.utils import no_blanks
from tests.context import eodag, search_crunch, download
from tests.utils import mock


class TestEodagCli(unittest.TestCase):

    @contextmanager
    def user_conf(self, conf_file='user_conf.yml', content=b'key: to unused conf'):
        """Utility method"""
        with self.runner.isolated_filesystem():
            with open(conf_file, 'wb') as fd:
                fd.write(content if isinstance(content, bytes) else content.encode('utf-8'))
            yield conf_file

    def setUp(self):
        self.runner = CliRunner()
        self.faker = Faker()

    def test_eodag_without_args(self):
        """Calling eodag without arguments should print help message"""
        result = self.runner.invoke(eodag)
        self.assertIn('Usage: eodag [OPTIONS] COMMAND [ARGS]...', result.output)
        self.assertEqual(result.exit_code, 0)

    def test_eodag_with_only_verbose_opt(self):
        """Calling eodag only with -v option should print error message"""
        result = self.runner.invoke(eodag, ['-v'])
        self.assertIn('Error: Missing command.', result.output)
        self.assertNotEqual(result.exit_code, 0)

    def test_eodag_search_without_args(self):
        """Calling eodag search subcommand without arguments should print help message and return error code"""
        result = self.runner.invoke(eodag, ['search'])
        with click.Context(search_crunch) as ctx:
            self.assertEqual(
                no_blanks(result.output),
                no_blanks(''.join(('Give me some work to do. See below for how to do that:', ctx.get_help())))
            )
        self.assertNotEqual(result.exit_code, 0)

    def test_eodag_search_without_producttype_arg(self):
        """Calling eodag search without -p | --productType should print the help message and return error code"""
        start_date = self.faker.date()
        end_date = self.faker.date()
        result = self.runner.invoke(eodag, ['search', '-s', start_date, '-e', end_date])
        with click.Context(search_crunch) as ctx:
            self.assertEqual(
                no_blanks(result.output),
                no_blanks(''.join(('Give me some work to do. See below for how to do that:', ctx.get_help())))
            )
        self.assertNotEqual(result.exit_code, 0)

    def test_eodag_search_with_conf_file_inexistent(self):
        """Calling eodag search with --conf | -f set to a non-existent file should print error message"""
        conf_file = 'does_not_exist.yml'
        result = self.runner.invoke(eodag, ['search', '--conf', conf_file, '-p', 'whatever'])
        self.assertIn(
            'Error: Invalid value for "-f" / "--conf": Path "{}" does not exist.'.format(conf_file),
            result.output
        )
        self.assertNotEqual(result.exit_code, 0)

    def test_eodag_search_with_max_cloud_out_of_range(self):
        """Calling eodag search with -c | --maxCloud set to a value < 0 or > 100 should print error message"""
        with self.user_conf() as conf_file:
            for max_cloud in (110, -1):
                result = self.runner.invoke(eodag, ['search', '--conf', conf_file, '-p', 'whatever', '-c', max_cloud])
                self.assertIn(
                    'Error: Invalid value for "-c" / "--cloudCover": {} is not in the valid range of 0 to 100.'.format(
                        max_cloud),
                    result.output
                )
                self.assertNotEqual(result.exit_code, 0)

    def test_eodag_search_bbox_invalid(self):
        """Calling eodag search with -b | --bbox set with less than 4 params should print error message"""
        with self.user_conf() as conf_file:
            result = self.runner.invoke(eodag, ['search', '--conf', conf_file, '-p', 'whatever', '-b', 1, 2])
            self.assertIn('Error: -b option requires 4 arguments', result.output)
            self.assertNotEqual(result.exit_code, 0)

    @mock.patch('eodag.cli.EODataAccessGateway', autospec=True)
    def test_eodag_search_bbox_valid(self, SatImagesAPI):
        """Calling eodag search with --bbox argument valid"""
        with self.user_conf() as conf_file:
            product_type = 'whatever'
            self.runner.invoke(eodag, ['search', '--conf', conf_file, '-p', product_type, '-b', 1, 43, 2, 44])
            api_obj = SatImagesAPI.return_value
            api_obj.search.assert_called_once_with(
                product_type, items_per_page=20, page=1, startTimeFromAscendingNode=None,
                completionTimeFromAscendingNode=None, cloudCover=None,
                geometry={'lonmin': 1, 'latmin': 43, 'lonmax': 2, 'latmax': 44})

    @mock.patch('eodag.cli.EODataAccessGateway', autospec=True)
    def test_eodag_search_storage_arg(self, SatImagesAPI):
        """Calling eodag search with specified result filename without .geojson extension"""
        with self.user_conf() as conf_file:
            api_obj = SatImagesAPI.return_value
            api_obj.search.return_value = (mock.MagicMock(),) * 2
            self.runner.invoke(eodag, ['search', '--conf', conf_file, '-p', 'whatever', '--storage', 'results'])
            api_obj.serialize.assert_called_with(api_obj.search.return_value[0], filename='results.geojson')

    @mock.patch('eodag.cli.EODataAccessGateway', autospec=True)
    def test_eodag_search_with_cruncher(self, SatImagesAPI):
        """Calling eodag search with --cruncher arg should call crunch method of search result"""
        with self.user_conf() as conf_file:
            api_obj = SatImagesAPI.return_value
            api_obj.search.return_value = (mock.MagicMock(),) * 2

            product_type = 'whatever'
            cruncher = 'FilterLatestIntersect'
            criteria = dict(startTimeFromAscendingNode=None, completionTimeFromAscendingNode=None,
                            geometry=None, cloudCover=None)
            self.runner.invoke(eodag, ['search', '-f', conf_file, '-p', product_type, '--cruncher', cruncher])

            search_results = api_obj.search.return_value[0]
            crunch_results = api_obj.crunch.return_value

            # Assertions
            SatImagesAPI.assert_called_once_with(user_conf_file_path=conf_file)
            api_obj.search.assert_called_once_with(product_type, items_per_page=20, page=1, **criteria)
            api_obj.crunch.assert_called_once_with(search_results, search_criteria=criteria, **{cruncher: {}})
            api_obj.serialize.assert_called_with(crunch_results, filename='search_results.geojson')

            # Call with a cruncher taking arguments
            cruncher = 'FilterOverlap'
            self.runner.invoke(eodag, [
                'search', '-f', conf_file, '-p', product_type, '--cruncher', cruncher,
                '--cruncher-args', cruncher, 'minimum_overlap', 10
            ])
            api_obj.crunch.assert_called_with(search_results, search_criteria=criteria,
                                              **{cruncher: {'minimum_overlap': 10}})

    def test_eodag_list_product_type_ok(self):
        """Calling eodag list without provider return all supported product types"""
        all_supported_product_types = [pt for pt, provs in TestCore.SUPPORTED_PRODUCT_TYPES.items() if len(provs) != 0]
        result = self.runner.invoke(eodag, ['list'])
        self.assertEqual(result.exit_code, 0)
        for pt in all_supported_product_types:
            self.assertIn(pt, result.output)

    def test_eodag_list_product_type_with_provider_ok(self):
        """Calling eodag list with provider should return all supported product types of specified provider"""
        provider = random.choice(TestCore.SUPPORTED_PROVIDERS)
        provider_supported_product_types = [pt for pt, provs in TestCore.SUPPORTED_PRODUCT_TYPES.items()
                                            if provider in provs]
        result = self.runner.invoke(eodag, ['list', '-p', provider])
        self.assertEqual(result.exit_code, 0)
        for pt in provider_supported_product_types:
            self.assertIn(pt, result.output)

    def test_eodag_list_product_type_with_provider_ko(self):
        """Calling eodag list with unsupported provider should fail and print a list of available providers"""
        provider = 'random'
        result = self.runner.invoke(eodag, ['list', '-p', provider])
        self.assertEqual(result.exit_code, 1)
        self.assertIn('Unsupported provider. You may have a typo', result.output)
        self.assertIn('Available providers: {}'.format(', '.join(sorted(TestCore.SUPPORTED_PROVIDERS))), result.output)

    def test_eodag_download_no_search_results_arg(self):
        """Calling eodag download without a path to a search result should fail"""
        result = self.runner.invoke(eodag, ['download'])
        with click.Context(download) as ctx:
            self.assertEqual(
                no_blanks(result.output),
                no_blanks(''.join(('Nothing to do (no search results file provided)', ctx.get_help())))
            )
        self.assertEqual(result.exit_code, 1)

    @mock.patch('eodag.cli.EODataAccessGateway', autospec=True)
    def test_eodag_download_no_conf_file(self, dag):
        """Calling eodag download without configuration file do nothing"""
        search_results_path = os.path.join(TEST_RESOURCES_PATH, 'eodag_search_result.geojson')
        self.runner.invoke(eodag, ['download', '--search-results', search_results_path])
        dag.assert_not_called()

    @mock.patch('eodag.cli.EODataAccessGateway', autospec=True)
    def test_eodag_download_ok(self, dag):
        """Calling eodag download with all args well formed succeed"""
        search_results_path = os.path.join(TEST_RESOURCES_PATH, 'eodag_search_result.geojson')
        config_path = os.path.join(TEST_RESOURCES_PATH, 'file_config_override.yml')
        dag.return_value.download_all.return_value = ['file:///fake_path']
        result = self.runner.invoke(eodag, ['download', '--search-results', search_results_path, '-f', config_path])
        dag.assert_called_once_with(user_conf_file_path=config_path)
        dag.return_value.deserialize.assert_called_once_with(search_results_path)
        self.assertEqual(dag.return_value.download_all.call_count, 1)
        self.assertEqual('Downloaded file:///fake_path\n', result.output)

        # Testing the case when no downloaded path is returned
        dag.return_value.download_all.return_value = [None]
        result = self.runner.invoke(eodag, ['download', '--search-results', search_results_path, '-f', config_path])
        self.assertEqual('A file may have been downloaded but we cannot locate it\n', result.output)

    @mock.patch('eodag.rpc.server.EODAGRPCServer', autospec=True)
    def test_eodag_serve_rpc_ok(self, rpc_server):
        """Calling eodag serve-rpc serve eodag methods as RPC server"""
        config_path = os.path.join(TEST_RESOURCES_PATH, 'file_config_override.yml')
        self.runner.invoke(eodag, ['serve-rpc', '-f', config_path])
        rpc_server.assert_called_once_with('localhost', 50051, config_path)
        rpc_server.return_value.serve.assert_any_call()
        self.assertEqual(rpc_server.return_value.serve.call_count, 1)
