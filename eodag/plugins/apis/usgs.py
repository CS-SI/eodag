# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

import datetime
import hashlib
import logging
import zipfile

import shapely.geometry
import pytz
import click
from tqdm import tqdm

try:  # PY3
    from urllib.parse import urljoin, urlparse
except ImportError:  # PY2
    from urlparse import urljoin, urlparse

import requests
from dateutil.parser import parse as dateparse
from requests import HTTPError

from eodag.api.product import EOProduct, EOPRODUCT_PROPERTIES
from shapely import geometry
import sys
from usgs import api
from .base import Api
import logging as logger
import os


class usgsApi(Api):

    def __init__(self, config):
        super(usgsApi, self).__init__(config)

    def query(self, product_type, **kwargs):

        api.login(self.config['credentials']['username'], self.config['credentials']['password'], save=True)

        usgs_product_type = None
        pt_config = self.config['products'].setdefault(product_type, {})
        if pt_config:
            usgs_product_type = pt_config['product_type']

        usgs_node_type = ['EE', 'CWIC', 'HDSS', 'LPCS']

        start_date = kwargs.pop('startDate', None)
        if start_date is None:
            raise ValueError('Start date must be given')

        end_date = kwargs.pop('endDate', None)

        if end_date is None:
            raise ValueError('end_date must be given')

        footprint = kwargs.pop('footprint', None)
        if footprint:

            # api.search(usgs_product_type, usgs_node_type, start_date=start_date, end_date=end_date, lng=50.074194, lat=50.240475)
            if len(footprint.keys()) == 4:  # a rectangle (or bbox)
                ll = {}
                ll['longitude'] = footprint['lonmin']
                ll['latitude'] = footprint['latmin']
                ur = {}
                ur['longitude'] = footprint['lonmax']
                ur['latitude'] = footprint['latmax']

                final = []
                for i in range(0, len(usgs_node_type)):
                    try:
                        result = api.search(usgs_product_type, usgs_node_type[i], start_date=start_date,
                                            end_date=end_date,
                                            ll=ll, ur=ur)
                        params = self.get_parameters(result)

                        for j in range(0, params['products_number']):
                            bbox = (params['ll_long'][j], params['ll_lat'][j], params['ur_long'][j], params['ur_lat'][j])
                            url = self.make_google_download_url(params, j)
                            geom = geometry.box(*bbox)
                            final.append(
                                EOProduct(params['entity_ids'][j], self.instance_name, url, params['entity_ids'][j],
                                          geom, footprint, startDate=params['startDates'][j]))
                    except Exception:
                        logger.debug('Product type %s does not exist on catalogue %s', usgs_product_type, usgs_node_type[i])

        api.logout()
        return final

    def get_parameters(self, result):

        products_number = result['data']['totalHits']
        entity_ids = []
        paths = []
        rows = []
        startDates = []
        ll_long = []
        ll_lat = []
        ur_long = []
        ur_lat = []
        params = {}
        for i in range(0, products_number):
            entity_ids.append(result['data']['results'][i]['entityId'])
            paths.append(result['data']['results'][i]['summary'].split(',')[2].split(':')[1])
            rows.append(result['data']['results'][i]['summary'].split(',')[3].split(':')[1])
            startDates.append(result['data']['results'][i]['acquisitionDate'])
            ll_long.append(result['data']['results'][i]['lowerLeftCoordinate']['longitude'])
            ll_lat.append(result['data']['results'][i]['lowerLeftCoordinate']['latitude'])
            ur_long.append(result['data']['results'][i]['upperRightCoordinate']['longitude'])
            ur_lat.append(result['data']['results'][i]['upperRightCoordinate']['latitude'])

        params['products_number'] = products_number
        params['entity_ids'] = entity_ids
        params['paths'] = paths
        params['rows'] = rows
        params['startDates'] = startDates
        params['ll_long'] = ll_long
        params['ll_lat'] = ll_lat
        params['ur_long'] = ur_long
        params['ur_lat'] = ur_lat

        return params

    def make_google_download_url(self, params, i):

        if len(str(params['paths'][i])) < 4:
            extension = 'L8' + '/' + '0' + str(params['paths'][i])[1:len(str(params['paths'][i]))] + '/' + str(
                params['rows'][i])[1:len(str(params['rows'][i]))] + '/' + str(
                params['entity_ids'][i]) + '.tar.bz'
            url = urljoin(self.config['google_base_url'], extension)

        elif len(str(params['rows'][i])) < 4:
            extension = 'L8' + '/' + str(params['paths'][i])[1:len(str(params['paths'][i]))] + '/' + '0' + str(
                params['rows'][i])[1:len(str(params['rows'][i]))] + '/' + str(
                params['entity_ids'][i]) + '.tar.bz'
            url = urljoin(self.config['google_base_url'], extension)

        else:
            extension = 'L8' + '/' + str(params['paths'][i])[1:len(str(params['paths'][i]))] + '/' + str(
                params['rows'][i])[1:len(str(params['rows'][i]))] + '/' + str(
                params['entity_ids'][i]) + '.tar.bz'
            url = urljoin(self.config['google_base_url'], extension)
        return url

    def download(self, product, auth=None):

        url = product.location_url_tpl
        if not url:
            logger.debug('Unable to get download url for %s, skipping download', product)
            return
        logger.debug('Download url: %s', url)

        filename = product.local_filename
        local_file_path = os.path.join(self.config['outputs_prefix'], filename)
        download_records = os.path.join(self.config['outputs_prefix'], '.downloaded')
        if not os.path.exists(download_records):
            os.makedirs(download_records)
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        record_filename = os.path.join(download_records, url_hash)
        if os.path.isfile(record_filename) and os.path.isfile(local_file_path):
            logger.info('Product already downloaded. Retrieve it at %s', local_file_path)
            yield local_file_path
            return
        # Remove the record file if local_file_path is absent (e.g. it was deleted while record wasn't)
        elif os.path.isfile(record_filename):
            logger.debug('Record file found (%s) but not the actual file', record_filename)
            logger.debug('Removing record file : %s', record_filename)
            os.remove(record_filename)

        hook_print = lambda r, *args, **kwargs: print('\n', r.url)
        with requests.get(url, stream=True, auth=auth, hooks={'response': hook_print},
                          params=self.config.get('dl_url_params', {}), verify=False) as stream:
            stream_size = int(stream.headers.get('content-length', 0))
            with open(local_file_path, 'wb') as fhandle:
                progressbar = tqdm(total=stream_size, unit='KB', unit_scale=True)
                for chunk in stream.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        progressbar.update(len(chunk))
                        fhandle.write(chunk)
            try:
                stream.raise_for_status()
            except HTTPError as e:
                logger.error("Error while getting resource : %s", e)
            else:
                with open(record_filename, 'w') as fh:
                    fh.write(url)
                logger.debug('Download recorded in %s', record_filename)
                if self.config['extract'] and zipfile.is_zipfile(local_file_path):
                    logger.info('Extraction activated')
                    with zipfile.ZipFile(local_file_path, 'r') as zfile:
                        fileinfos = zfile.infolist()
                        with click.progressbar(fileinfos, fill_char='x', length=len(fileinfos), width=0,
                                               label='Extracting files from {}'.format(
                                                   local_file_path)) as progressbar:
                            for fileinfo in progressbar:
                                yield zfile.extract(fileinfo, path=self.config['outputs_prefix'])
                else:
                    yield local_file_path


