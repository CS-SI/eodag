# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

import hashlib
import logging
import os
import re
import zipfile


try:  # PY3
    from urllib.parse import urljoin, urlparse
except ImportError:  # PY2
    from urlparse import urljoin, urlparse

import requests
from requests import HTTPError
from shapely import geometry
from tqdm import tqdm
from usgs import CATALOG_NODES, USGSError, api

from eodag.api.product import EOProduct
from eodag.api.product.representations import properties_from_json
from .base import Api


logger = logging.getLogger('eodag.plugins.apis.usgs')


class UsgsApi(Api):

    def query(self, product_type, **kwargs):
        api.login(self.config['credentials']['username'], self.config['credentials']['password'], save=True)
        usgs_product_type = self.config['products'][product_type]['product_type']
        start_date = kwargs.pop('startDate', None)
        end_date = kwargs.pop('endDate', None)
        footprint = kwargs.pop('footprint', None)

        # Configuration to generate the download url of search results
        result_summary_pattern = re.compile(
            r'^Entity ID: .+, Acquisition Date: .+, Path: (?P<path>\d+), Row: (?P<row>\d+)$')
        # See https://pyformat.info/, on section "Padding and aligning strings" to understand {path:0>3} and {row:0>3}.
        # It roughly means: 'if the string that will be passed as "path" has length < 3, prepend as much "0"s as needed
        # to reach length 3' and same for "row"
        dl_url_pattern = '{base_url}/L8/{path:0>3}/{row:0>3}/{entity}.tar.bz'

        final = []
        if footprint and len(footprint.keys()) == 4:  # a rectangle (or bbox)
            lower_left = {'longitude': footprint['lonmin'], 'latitude': footprint['latmin']}
            upper_right = {'longitude': footprint['lonmax'], 'latitude': footprint['latmax']}
        else:
            lower_left, upper_right = None, None
        for node_type in CATALOG_NODES:
            try:
                results = api.search(usgs_product_type, node_type, start_date=start_date, end_date=end_date,
                                     ll=lower_left, ur=upper_right)

                for result in results['data']['results']:
                    r_lower_left = result['lowerLeftCoordinate']
                    r_upper_right = result['upperRightCoordinate']
                    summary_match = result_summary_pattern.match(result['summary']).groupdict()
                    result['geometry'] = geometry.box(
                        r_lower_left['longitude'], r_lower_left['latitude'],
                        r_upper_right['longitude'], r_upper_right['latitude']
                    )
                    result['productType'] = usgs_product_type
                    final.append(EOProduct(
                        self.instance_name,
                        dl_url_pattern.format(
                            base_url=self.config['google_base_url'].rstrip('/'),
                            entity=result['entityId'],
                            **summary_match
                        ),
                        properties_from_json(result, self.config['metadata_mapping']),
                        searched_bbox=footprint,
                    ))
            except USGSError as e:
                logger.debug('Product type %s does not exist on catalogue %s', usgs_product_type, node_type)
                logger.debug("Skipping error: %s", e)
        api.logout()
        return final

    def download(self, product, auth=None):
        url = product.location
        if not url:
            logger.debug('Unable to get download url for %s, skipping download', product)
            return
        logger.debug('Download url: %s', url)

        filename = product.properties['title'] + '.tar.bz'
        local_file_path = os.path.join(self.config['outputs_prefix'], filename)
        download_records = os.path.join(self.config['outputs_prefix'], '.downloaded')
        if not os.path.exists(download_records):
            os.makedirs(download_records)
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        record_filename = os.path.join(download_records, url_hash)
        if os.path.isfile(record_filename) and os.path.isfile(local_file_path):
            logger.info('Product already downloaded. Retrieve it at %s', local_file_path)
            return local_file_path
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
            except HTTPError:
                import traceback
                logger.error("Error while getting resource : %s", traceback.format_exc())
            else:
                with open(record_filename, 'w') as fh:
                    fh.write(url)
                logger.debug('Download recorded in %s', record_filename)
                if self.config['extract'] and zipfile.is_zipfile(local_file_path):
                    logger.info('Extraction activated')
                    with zipfile.ZipFile(local_file_path, 'r') as zfile:
                        fileinfos = zfile.infolist()
                        with tqdm(fileinfos, unit='file', desc='Extracting files from {}'.format(
                                local_file_path)) as progressbar:
                            for fileinfo in progressbar:
                                zfile.extract(fileinfo, path=self.config['outputs_prefix'])
                    return local_file_path[:local_file_path.index('.tar.bz')]
                else:
                    return local_file_path
