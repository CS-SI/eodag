# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved

import click

from satdl.api.core import SatImagesAPI
from satdl.utils.logging import setup_logging


@click.command()
@click.option('--point', type=(float,) * 2, default=(None,) * 2,
              help='Search for a product on a point providing its lat and lon (in this order)')
@click.option('--rectangle', type=(float,) * 4, default=(None,) * 4,
              help='Search for a product on a rectangle providing its minlat, minlon, maxlat and maxlon (in this '
                   'order)')
@click.option('--startDate', help='Maximum age of the product')
@click.option('--endDate', help='Minimum age of the product')
@click.option('--dates', type=(str, str), default=(None,) * 2, help='start and date of products (in this order)')
@click.option('--maxcloud', help='Maximum cloud cover percentage needed for the product', type=click.IntRange(0, 100))
@click.option('--conf', help='File path to the user configuration file with its credentials',
              type=click.Path(exists=True))
@click.option('-v', '--verbose', count=True)
@click.argument('productType')
def main(producttype, **kwargs):
    setup_logging(**kwargs)
    if kwargs['point'] != (None,) * 2:
        point = kwargs.pop('point')
        footprint = {'lat': point[0], 'lon': point[1]}
    elif kwargs['rectangle'] != (None,) * 4:
        rect = kwargs.pop('rectangle')
        footprint = {'latmin': rect[0], 'lonmin': rect[1], 'latmax': rect[2], 'lonmax': rect[3]}
    else:
        footprint = None
    if kwargs['dates'] != (None,) * 2:
        start_date, end_date = kwargs.pop('dates')
    else:
        start_date, end_date = kwargs.pop('startdate'), kwargs.pop('enddate')
    criteria = {
        'footprint': footprint,
        'startDate': start_date,
        'endDate': end_date,
        'maxCloudCover': kwargs.pop('maxcloud'),
    }
    god = SatImagesAPI(user_conf_file_path=click.format_filename(kwargs.pop('conf')))
    for downloaded_file in god.download_all(god.filter(god.search(producttype, **criteria))):
        if downloaded_file is None:
            click.echo('A file may have been downloaded but we cannot locate it')
        else:
            click.echo('Downloaded {}'.format(downloaded_file))


if __name__ == '__main__':
    main()
