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

import os
import sys
import textwrap

import click

from eodag.api.core import EODataAccessGateway
from eodag.utils.exceptions import UnsupportedProvider
from eodag.utils.logging import setup_logging


# disable warning on Python 2
click.disable_unicode_literals_warning = True

# A list of supported crunchers that the user can choose (see --cruncher option below)
CRUNCHERS = [
    'FilterLatestByName', 'FilterLatestIntersect', 'FilterOverlap',
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
              type=click.DateTime(),
              help='Maximum age of the product (in ISO8601 format: yyyy-MM-ddThh:mm:ss.SSSZ)')
@click.option('-e', '--completionTimeFromAscendingNode',
              type=click.DateTime(),
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
    producttype = kwargs.pop('producttype')
    if not producttype:
        with click.Context(search_crunch) as ctx:
            print('Give me some work to do. See below for how to do that:', end='\n\n')
            click.echo(search_crunch.get_help(ctx))
        sys.exit(-1)

    kwargs['verbose'] = ctx.obj['verbosity']
    setup_logging(**kwargs)
    if kwargs['geometry'] != (None,) * 4:
        rect = kwargs.pop('geometry')
        footprint = {'lonmin': rect[0], 'latmin': rect[1], 'lonmax': rect[2], 'latmax': rect[3]}
    else:
        footprint = None
    start_date = kwargs.pop('starttimefromascendingnode')
    stop_date = kwargs.pop('completiontimefromascendingnode')
    criteria = {
        'geometry': footprint,
        'startTimeFromAscendingNode': None,
        'completionTimeFromAscendingNode': None,
        'cloudCover': kwargs.pop('cloudcover'),
        'return_all': True,
    }
    if start_date:
        criteria['startTimeFromAscendingNode'] = start_date.isoformat()
    if stop_date:
        criteria['completionTimeFromAscendingNode'] = stop_date.isoformat()
    conf_file = kwargs.pop('conf')
    if conf_file:
        conf_file = click.format_filename(conf_file)

    # Process inputs for crunch
    cruncher_names = set(kwargs.pop('cruncher') or [])
    cruncher_args = kwargs.pop('cruncher_args')
    cruncher_args_dict = {}
    if cruncher_args:
        for cruncher, argname, argval in cruncher_args:
            cruncher_args_dict.setdefault(cruncher, {}).setdefault(argname, argval)

    gateway = EODataAccessGateway(user_conf_file_path=conf_file)

    # Search
    results, page, total, page_size = gateway.search(producttype, **criteria)
    click.echo("Found {} overall products with product type '{}'".format(total, producttype))
    click.echo("Returned page {} of {} products: {}".format(page, page_size, results))

    # Crunch !
    crunch_args = {
        cruncher_name: cruncher_args_dict.get(cruncher_name, {})
        for cruncher_name in cruncher_names
    }
    for cruncher_name in cruncher_names:
        results = gateway.crunch(results, search_criteria=criteria, **crunch_args[cruncher_name])

    storage_filepath = kwargs.pop('storage')
    if not storage_filepath.endswith('.geojson'):
        storage_filepath += '.geojson'
    result_storage = gateway.serialize(results, filename=storage_filepath)
    click.echo("Results stored at '{}'".format(result_storage))


@eodag.command(name='list', help='List supported product types')
@click.option('-p', '--provider', help='List product types supported by this provider')
@click.pass_context
def list_pt(ctx, **kwargs):
    kwargs['verbose'] = ctx.obj['verbosity']
    setup_logging(**kwargs)
    dag = EODataAccessGateway()
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
        satim_api = EODataAccessGateway(user_conf_file_path=conf_file)
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
def serve_rpc(ctx, host, port, conf):
    setup_logging(verbose=ctx.obj['verbosity'])
    from eodag.rpc.server import EODAGRPCServer
    server = EODAGRPCServer(host, port, conf)
    server.serve()


@eodag.command(help='Start eodag HTTP server')
@click.option('-f', '--config', type=click.Path(exists=True, resolve_path=True), required=True,
              help='File path to the user configuration file with its credentials')
@click.option('-d', '--daemon', is_flag=True, show_default=True, help='run in daemon mode')
@click.option('-w', '--world', is_flag=True, show_default=True,
              help=('run flask using IPv4 0.0.0.0 (all network interfaces), '
                    'otherwise bind to 127.0.0.1 (localhost). '
                    'This maybe necessary in systems that only run Flask')
              )
@click.option('-p', '--port', type=int, default=5000, show_default=True,
              help='The port on which to listen')
@click.option('--debug', is_flag=True, show_default=True,
              help='Run in debug mode (for development purpose)')
@click.pass_context
def serve_rest(ctx, daemon, world, port, config, debug):
    setup_logging(verbose=ctx.obj['verbosity'])
    # Set the settings of the app
    # IMPORTANT: the order of imports counts here (first we override the settings, then we import the app so that the
    # updated settings is taken into account in the app initialization)
    from eodag.rest import settings
    settings.EODAG_CFG_FILE = config

    from eodag.rest.server import app

    bind_host = '127.0.0.1'
    if world:
        bind_host = '0.0.0.0'
    if daemon:
        try:
            pid = os.fork()
        except OSError as e:
            raise Exception('%s [%d]' % (e.strerror, e.errno))

        if pid == 0:
            os.setsid()
            app.run(threaded=True, host=bind_host, port=port)
        else:
            sys.exit(0)
    else:
        app.run(debug=debug, host=bind_host, port=port)


if __name__ == '__main__':
    eodag(obj={})
