# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved

import sys

import click

from eodag.api.core import SatImagesAPI
from eodag.utils.logging import setup_logging


@click.command(help='Program for searching and downloading satellite images')
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
@click.option('-v', '--verbose', count=True,
              help='Control the verbosity of the logs. For maximum verbosity, type -vvv')
@click.option('-p', '--productType',
              help='The product type to search')
def main(**kwargs):
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
        with click.Context(main) as ctx:
            print('Give me some work to do. See below for how to do that:', end='\n\n')
            click.echo(main.get_help(ctx))
        sys.exit(0)
    god = SatImagesAPI(user_conf_file_path=conf_file)
    for downloaded_file in god.download_all(god.filter(god.search(producttype, **criteria))):
        if downloaded_file is None:
            click.echo('A file may have been downloaded but we cannot locate it')
        else:
            click.echo('Downloaded {}'.format(downloaded_file))


if __name__ == '__main__':
    main()
