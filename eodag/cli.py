# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

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
    'RemoveDoubles', 'FilterLatestByName'
]


@click.group()
@click.option('-v', '--verbose', count=True,
              help='Control the verbosity of the logs. For maximum verbosity, type -vvv')
@click.pass_context
def eodag(ctx, verbose):
    if ctx.obj is None:
        ctx.obj = {}
    ctx.obj['verbosity'] = verbose


@eodag.command(help='Search, crunch and download satellite images')
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
@click.pass_context
def go(ctx, **kwargs):
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
        with click.Context(go) as ctx:
            print('Give me some work to do. See below for how to do that:', end='\n\n')
            click.echo(go.get_help(ctx))
        sys.exit(0)

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
        results.crunch(cruncher)

    # Download
    for downloaded_file in satim_api.download_all(results):
        if downloaded_file is None:
            click.echo('A file may have been downloaded but we cannot locate it')
        else:
            click.echo('Downloaded {}'.format(downloaded_file))


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
    with open(os.path.join(os.path.dirname(__file__), 'resources', 'system_conf_default.yml'), 'r') as fh:
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


if __name__ == '__main__':
    eodag(obj={})
