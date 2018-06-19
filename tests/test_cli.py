# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

import unittest
from contextlib import contextmanager


try:
    from unittest import mock  # PY3
except ImportError:
    import mock  # PY2

import click
from click.testing import CliRunner
from faker import Faker

from tests.utils import no_blanks
from tests.context import eodag, search_crunch


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

    @mock.patch('eodag.cli.SatImagesAPI', autospec=True)
    def test_eodag_search_bbox_valid(self, SatImagesAPI):
        """Calling eodag search with --geometry argument valid"""
        with self.user_conf() as conf_file:
            product_type = 'whatever'
            self.runner.invoke(eodag, ['search', '--conf', conf_file, '-p', product_type, '-b', 1, 43, 2, 44])
            api_obj = SatImagesAPI.return_value
            api_obj.search.assert_called_once_with(
                product_type, startTimeFromAscendingNode=None, completionTimeFromAscendingNode=None,
                cloudCover=None, geometry={'lonmin': 1, 'latmin': 43, 'lonmax': 2, 'latmax': 44})

    @mock.patch('eodag.cli.SatImagesAPI', autospec=True)
    def test_eodag_search_storage_arg(self, SatImagesAPI):
        """Calling eodag search with specified result filename without .geojson extension"""
        with self.user_conf() as conf_file:
            self.runner.invoke(eodag, ['search', '--conf', conf_file, '-p', 'whatever', '--storage', 'results'])
            api_obj = SatImagesAPI.return_value
            api_obj.serialize.assert_called_with(api_obj.search.return_value, filename='results.geojson')

    @mock.patch('eodag.cli.SatImagesAPI', autospec=True)
    def test_eodag_search_with_cruncher(self, SatImagesAPI):
        """Calling eodag search with --cruncher arg should call crunch method of search result"""
        with self.user_conf() as conf_file:
            product_type = 'whatever'
            cruncher = 'RemoveDoubles'
            criteria = dict(startTimeFromAscendingNode=None, completionTimeFromAscendingNode=None,
                            geometry=None, cloudCover=None)
            result = self.runner.invoke(eodag, ['search', '-f', conf_file, '-p', product_type, '--cruncher', cruncher])

            api_obj = SatImagesAPI.return_value
            search_results = api_obj.search.return_value
            crunch_results = search_results.crunch.return_value

            # Assertions
            SatImagesAPI.assert_called_once_with(user_conf_file_path=conf_file)
            api_obj.search.assert_called_once_with(product_type, **criteria)
            api_obj.get_cruncher.assert_called_once_with(cruncher, **{})
            api_obj.serialize.assert_called_with(crunch_results, filename='search_results.geojson')
            search_results.crunch.assert_called_once_with(api_obj.get_cruncher.return_value, **criteria)
            self.assertEqual(
                result.output,
                '\n'.join(("Found 0 products with product type '{}': {}".format(product_type, search_results),
                           "Results stored at '{!r}'\n".format(api_obj.serialize.return_value))))

            # Call with a cruncher taking arguments
            cruncher = 'FilterOverlap'
            self.runner.invoke(eodag, [
                'search', '-f', conf_file, '-p', product_type, '--cruncher', cruncher,
                '--cruncher-args', cruncher, 'minimum_overlap', 10
            ])
            api_obj.get_cruncher.assert_called_with(cruncher, minimum_overlap=10)
