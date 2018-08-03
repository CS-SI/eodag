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
from __future__ import absolute_import, print_function, unicode_literals

import sys
import textwrap

import click

from eodag.api.core import SatImagesAPI
from eodag.utils.exceptions import UnsupportedProvider
from eodag.utils.logging import setup_logging


# disable warning on Python 2
click.disable_unicode_literals_warning = True

# A list of supported crunchers that the user can choose (see --cruncher option below)
CRUNCHERS = [
    'RemoveDoubles', 'FilterLatestByName', 'FilterLatestIntersect', 'FilterOverlap',
]


@click.group()
@click.option('-v', '--verbose', count=True,
              help='Control the verbosity of the logs. For maximum verbosity, type -vvv')
@click.pass_context
def eodag(ctx, verbose):
    if ctx.obj is None:
        ctx.obj = {}
    ctx.obj['verbosity'] = verbose


@eodag.command(name='search',
               help='Search satellite images by their product types, and optionally crunch the search results before '
                    'storing them in a geojson file')
@click.option('-b', '--geometry', type=(float,) * 4, default=(None,) * 4,
              help='Search for a product on a bounding box, providing its minlon, minlat, maxlon and maxlat (in this '
                   'order)')
@click.option('-s', '--startTimeFromAscendingNode',
              help='Maximum age of the product (in ISO8601 format: yyyy-MM-ddThh:mm:ss.SSSZ)')
@click.option('-e', '--completionTimeFromAscendingNode',
              help='Minimum age of the product (in ISO8601 format: yyyy-MM-ddThh:mm:ss.SSSZ)')
@click.option('-c', '--cloudCover', type=click.IntRange(0, 100),
              help='Maximum cloud cover percentage needed for the product')
@click.option('-f', '--conf', help='File path to the user configuration file with its credentials',
              type=click.Path(exists=True))
@click.option('-p', '--productType',
              help='The product type to search')
@click.option('--cruncher', type=click.Choice(CRUNCHERS), multiple=True,
              help='A cruncher to be applied to search results. Repeat option many times to apply many crunchers')
@click.option('--cruncher-args', type=(str,) * 3, multiple=True,
              help='Named arguments acting as the parameters of a cruncher. '
                   'Enter it like this: --cruncher-args <CruncherName> <arg-name> <arg-value>. Repeat option many '
                   'times to give many args to a cruncher')
@click.option('--storage', type=click.Path(dir_okay=False, writable=True, readable=False),
              default='search_results.geojson',
              help='Path to the file where to store search results (.geojson extension will be automatically appended '
                   'to the filename). DEFAULT: search_results.geojson')
@click.pass_context
def search_crunch(ctx, **kwargs):
    # Process inputs for search
    kwargs['verbose'] = ctx.obj['verbosity']
    setup_logging(**kwargs)
    if kwargs['geometry'] != (None,) * 4:
        rect = kwargs.pop('geometry')
        footprint = {'lonmin': rect[0], 'latmin': rect[1], 'lonmax': rect[2], 'latmax': rect[3]}
    else:
        footprint = None
    criteria = {
        'geometry': footprint,
        'startTimeFromAscendingNode': kwargs.pop('starttimefromascendingnode'),
        'completionTimeFromAscendingNode': kwargs.pop('completiontimefromascendingnode'),
        'cloudCover': kwargs.pop('cloudcover'),
    }
    producttype = kwargs.pop('producttype')
    conf_file = kwargs.pop('conf')
    if conf_file:
        conf_file = click.format_filename(conf_file)
    if not producttype:
        with click.Context(search_crunch) as ctx:
            print('Give me some work to do. See below for how to do that:', end='\n\n')
            click.echo(search_crunch.get_help(ctx))
        sys.exit(-1)

    # Process inputs for crunch
    cruncher_names = set(kwargs.pop('cruncher') or [])
    cruncher_args = kwargs.pop('cruncher_args')
    cruncher_args_dict = {}
    if cruncher_args:
        for cruncher, argname, argval in cruncher_args:
            cruncher_args_dict.setdefault(cruncher, {}).setdefault(argname, argval)

    satim_api = SatImagesAPI(user_conf_file_path=conf_file)

    # Search
    results = satim_api.search(producttype, **criteria)
    click.echo("Found {} products with product type '{}': {}".format(len(results), producttype, results))

    # Crunch !
    for cruncher in (satim_api.get_cruncher(cname, **cruncher_args_dict.get(cname, {})) for cname in cruncher_names):
        results = results.crunch(cruncher, **criteria)

    storage_filepath = kwargs.pop('storage')
    if not storage_filepath.endswith('.geojson'):
        storage_filepath += '.geojson'
    result_storage = satim_api.serialize(results, filename=storage_filepath)
    click.echo("Results stored at '{}'".format(result_storage))


@eodag.command(name='list', help='List supported product types')
@click.option('-p', '--provider', help='List product types supported by this provider')
@click.pass_context
def list_pt(ctx, **kwargs):
    kwargs['verbose'] = ctx.obj['verbosity']
    setup_logging(**kwargs)
    dag = SatImagesAPI()
    provider = kwargs.pop('provider')
    text_wrapper = textwrap.TextWrapper()
    click.echo('Listing available product types:')
    try:
        for product_type in dag.list_product_types(provider=provider):
            text_wrapper.initial_indent = '\n* {}: '.format(product_type['ID'])
            text_wrapper.subsequent_indent = ' ' * len(text_wrapper.initial_indent)
            click.echo(text_wrapper.fill(product_type['desc'] or 'No description'))
    except UnsupportedProvider:
        click.echo('Unsupported provider. You may have a typo')
        click.echo('Available providers: {}'.format(', '.join(dag.available_providers())))
        sys.exit(1)


@eodag.command(help='Download a list of products from a serialized search result')
@click.option('--search-results', type=click.Path(exists=True, dir_okay=False),
              help='Path to a serialized search result')
@click.option('-f', '--conf', type=click.Path(exists=True),
              help='File path to the user configuration file with its credentials', )
@click.pass_context
def download(ctx, **kwargs):
    search_result_path = kwargs.pop('search_results')
    if not search_result_path:
        with click.Context(download) as ctx:
            click.echo('Nothing to do (no search results file provided)')
            click.echo(download.get_help(ctx))
        sys.exit(0)
    kwargs['verbose'] = ctx.obj['verbosity']
    setup_logging(**kwargs)
    conf_file = kwargs.pop('conf')
    if conf_file:
        conf_file = click.format_filename(conf_file)
        satim_api = SatImagesAPI(user_conf_file_path=conf_file)
        search_results = satim_api.deserialize(search_result_path)
        for downloaded_file in satim_api.download_all(search_results):
            if downloaded_file is None:
                click.echo('A file may have been downloaded but we cannot locate it')
            else:
                click.echo('Downloaded {}'.format(downloaded_file))


@eodag.command(help='Start eodag rpc server')
@click.option('-h', '--host', type=click.STRING, default='localhost',
              help='Interface where to listen for requests')
@click.option('-p', '--port', type=click.INT, default=50051,
              help='The port where to listen for requests', )
@click.option('-f', '--conf', type=click.Path(exists=True),
              help='File path to the user configuration file with its credentials', )
@click.pass_context
def serve(ctx, host, port, conf):
    setup_logging(verbose=ctx.obj['verbosity'])
    from eodag.rpc.server import EODAGRPCServer
    server = EODAGRPCServer(host, port, conf)
    server.serve()


if __name__ == '__main__':
    eodag(obj={})
