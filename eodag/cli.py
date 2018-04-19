# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

import os
import sys

import click
import yaml
import yaml.parser

from eodag.api.core import SatImagesAPI
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
@click.option('-b', '--bbox', type=(float,) * 4, default=(None,) * 4,
              help='Search for a product on a bounding box, providing its minlon, minlat, maxlon and maxlat (in this '
                   'order)')
@click.option('-s', '--startDate',
              help='Maximum age of the product (in ISO8601 format: yyyy-MM-ddThh:mm:ss.SSSZ)')
@click.option('-e', '--endDate',
              help='Minimum age of the product (in ISO8601 format: yyyy-MM-ddThh:mm:ss.SSSZ)')
@click.option('-c', '--maxCloud', type=click.IntRange(0, 100),
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
    if kwargs['bbox'] != (None,) * 4:
        rect = kwargs.pop('bbox')
        footprint = {'lonmin': rect[0], 'latmin': rect[1], 'lonmax': rect[2], 'latmax': rect[3]}
    else:
        footprint = None
    criteria = {
        'footprint': footprint,
        'startDate': kwargs.pop('startdate'),
        'endDate': kwargs.pop('enddate'),
        'maxCloudCover': kwargs.pop('maxcloud'),
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
@click.option('-s', '--system', help='Name of the system for which we should list available product types')
@click.pass_context
def list_pt(ctx, **kwargs):
    def format_system_pt(sys_conf):
        return 'product_type={product_type};collection={collection}'.format(**sys_conf)

    def print_list(name, config):
        if 'search' in config and 'products' in config['search']:
            click.echo('Product types available for instance {}:'.format(name))
            for eodag_pt, real_pt in config['search']['products'].items():
                click.echo('- eodag code: {}\t\tcode on system: {}'.format(
                    eodag_pt, format_system_pt(real_pt)
                ))

    kwargs['verbose'] = ctx.obj['verbosity']
    setup_logging(**kwargs)
    with open(os.path.join(os.path.dirname(__file__), 'resources', 'providers.yml'), 'r') as fh:
        conf = yaml.load(fh)
        system = kwargs.pop('system')
        try:
            if system and system not in conf:
                click.echo('Unsupported system. You may have a typo')
                click.echo('Available systems: {}'.format(', '.join(conf.keys())))
                sys.exit(1)
            for name, config in conf.items():
                if system:
                    if name == system:
                        print_list(name, config)
                        break
                else:
                    print_list(name, config)
        except yaml.parser.ParserError as e:
            click.echo('Unable to load user configuration file: {}'.format(e))
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
              help='The port where to listen for requests',)
@click.option('-f', '--conf', type=click.Path(exists=True),
              help='File path to the user configuration file with its credentials',)
@click.pass_context
def serve(ctx, host, port, conf):
    setup_logging(verbose=ctx.obj['verbosity'])
    from eodag.rpc.server import EODAGRPCServer
    server = EODAGRPCServer(host, port, conf)
    server.serve()


if __name__ == '__main__':
    eodag(obj={})
