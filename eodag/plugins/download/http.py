# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

import hashlib
import logging
import os
import zipfile

import requests
from requests import HTTPError
from tqdm import tqdm

from eodag.plugins.download.base import Download
from eodag.plugins.search.base import MisconfiguredError


logger = logging.getLogger('eodag.plugins.download.http')


class HTTPDownload(Download):

    def __init__(self, config):
        super(HTTPDownload, self).__init__(config)
        if 'base_uri' not in self.config:
            raise MisconfiguredError('{} plugin require a base_uri configuration key'.format(self.name))
        self.config.setdefault('outputs_prefix', '/tmp')
        self.config.setdefault('extract', True)
        logger.debug('Images will be downloaded to directory %s', self.config['outputs_prefix'])

    def download(self, product, progress_callback=None, auth=None):
        """Download a product as zip archive using HTTP protocol"""
        if not product.location.startswith('file://'):
            url = self.__build_download_url(product, auth)
            if not url:
                logger.debug('Unable to get download url for %s, skipping download', product)
                return
            logger.debug('Download url: %s', url)

            # Strong asumption made here: all products downloaded will be zip archives
            filename = product.properties['title'] + '.zip'
            local_file_path = os.path.join(self.config['outputs_prefix'], filename)
            download_records = os.path.join(self.config['outputs_prefix'], '.downloaded')
            try:
                os.makedirs(download_records)
            except OSError as exc:
                import errno
                if exc.errno != errno.EEXIST:   # Skip error if dir exists
                    import traceback as tb
                    logger.warning('Unable to create record directory. Got:\n%s', tb.format_exc())
            url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
            record_filename = os.path.join(download_records, url_hash)
            if os.path.isfile(record_filename) and os.path.isfile(local_file_path):
                return self.__finalize(local_file_path)
            # Remove the record file if local_file_path is absent (e.g. it was deleted while record wasn't)
            elif os.path.isfile(record_filename):
                logger.debug('Record file found (%s) but not the actual file', record_filename)
                logger.debug('Removing record file : %s', record_filename)
                os.remove(record_filename)

            with requests.get(url, stream=True, auth=auth, params=self.config.get('dl_url_params', {})) as stream:
                try:
                    stream.raise_for_status()
                except HTTPError:
                    import traceback as tb
                    logger.error("Error while getting resource :\n%s", tb.format_exc())
                else:
                    stream_size = int(stream.headers.get('content-length', 0))
                    with open(local_file_path, 'wb') as fhandle:

                        for chunk in stream.iter_content(chunk_size=64 * 1024):
                            if chunk:
                                progress_callback(len(chunk), stream_size)
                                fhandle.write(chunk)

                    with open(record_filename, 'w') as fh:
                        fh.write(url)
                    logger.debug('Download recorded in %s', record_filename)
                    return self.__finalize(local_file_path)
        else:
            path = product.location.replace('file://', '')
            logger.info('Product already present on this platform. Identifier: %s', path)
            # Do not download data if we are on site. Instead give back the absolute path to the data
            return path

    def __build_download_url(self, product, auth):
        if product.location:
            try:
                url = product.location.format(
                    base=self.config.get('base_uri').rstrip('/'),
                )
                if product.properties['organisationName'] in ('ESA',):
                    url += '?token={}'.format(auth.token)
                return url
            except Exception:
                import traceback as tb
                raise RuntimeError('Product {} is incompatible with download plugin {}\n{}'.format(
                    product, self.name, tb.format_exc()
                ))

    def __finalize(self, local_file_path):
        """Finalize the download process.

        :param local_file_path: The path to the local zip archive downloaded or already present
        :type local_file_path: str or unicode
        :return: the absolute path to the product
        """
        if self.config['extract'] and zipfile.is_zipfile(local_file_path):
            if not os.path.exists(local_file_path[:local_file_path.index('.zip')]):
                logger.info('Extraction activated')
                with zipfile.ZipFile(local_file_path, 'r') as zfile:
                    fileinfos = zfile.infolist()
                    with tqdm(fileinfos, unit='file', desc='Extracting files from {}'.format(
                            local_file_path)) as progressbar:
                        for fileinfo in progressbar:
                            zfile.extract(
                                fileinfo,
                                path=os.path.join(
                                    self.config['outputs_prefix'],
                                    local_file_path[:local_file_path.index('.zip')])
                            )
            # Handle depth levels in the product archive. For example, if the downloaded archive was
            # extracted to: /top_level/product_base_dir and archive_depth was configured to 2, the product
            # location will be /top_level/product_base_dir.
            # WARNING: A strong assumption is made here: there is only one subdirectory per level
            archive_depth = self.config.get('archive_depth', 1)
            product_path = local_file_path[:local_file_path.index('.zip')]
            count = 1
            while count < archive_depth:
                product_path = os.path.join(product_path, os.listdir(product_path)[0])
                count += 1
            return product_path
        else:
            return local_file_path
