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

import hashlib
import logging
import os
import shutil
import zipfile

import requests
from requests import HTTPError
from tqdm import tqdm

from eodag.plugins.download.base import Download
from eodag.utils.exceptions import MisconfiguredError


logger = logging.getLogger('eodag.plugins.download.http')


class HTTPDownload(Download):

    def __init__(self, provider, config):
        super(HTTPDownload, self).__init__(provider, config)
        if not hasattr(self.config, 'base_uri'):
            raise MisconfiguredError('{} plugin require a base_uri configuration key'.format(self.__name__))

    def download(self, product, auth=None, progress_callback=None):
        """Download a product using HTTP protocol.

        The downloaded product is assumed to be a Zip file. If it is not,
        the user is warned, it is renamed to remove the zip extension and
        no further treatment is done (no extraction)
        """
        if product.location != product.remote_location:
            fs_path = product.location[len('file://'):]
            # The fs path of a product is either a file (if 'extract' config is False) or a directory
            if os.path.isfile(fs_path) or os.path.isdir(fs_path):
                logger.info('Product already present on this platform. Identifier: %s', fs_path)
                # Do not download data if we are on site. Instead give back the absolute path to the data
                return fs_path

        url = self.__build_download_url(product, auth)
        if not url:
            logger.debug('Unable to get download url for %s, skipping download', product)
            return
        logger.info('Download url: %s', url)

        # Strong asumption made here: all products downloaded will be zip files
        # If they are not, the '.zip' extension will be removed when they are downloaded and returned as is
        prefix = os.path.abspath(self.config.outputs_prefix)
        fs_path = os.path.join(prefix, '{}.zip'.format(product.properties['title']))
        download_records_dir = os.path.join(prefix, '.downloaded')
        try:
            os.makedirs(download_records_dir)
        except OSError as exc:
            import errno
            if exc.errno != errno.EEXIST:   # Skip error if dir exists
                import traceback as tb
                logger.warning('Unable to create records directory. Got:\n%s', tb.format_exc())
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        record_filename = os.path.join(download_records_dir, url_hash)
        if os.path.isfile(record_filename) and os.path.isfile(fs_path):
            return self.__finalize(fs_path)
        # Remove the record file if fs_path is absent (e.g. it was deleted while record wasn't)
        elif os.path.isfile(record_filename):
            logger.debug('Record file found (%s) but not the actual file', record_filename)
            logger.debug('Removing record file : %s', record_filename)
            os.remove(record_filename)

        with requests.get(url, stream=True, auth=auth, params=getattr(self.config, 'dl_url_params', {})) as stream:
            try:
                stream.raise_for_status()
            except HTTPError:
                import traceback as tb
                logger.error("Error while getting resource :\n%s", tb.format_exc())
            else:
                stream_size = int(stream.headers.get('content-length', 0))
                with open(fs_path, 'wb') as fhandle:
                    for chunk in stream.iter_content(chunk_size=64 * 1024):
                        if chunk:
                            fhandle.write(chunk)
                            progress_callback(len(chunk), stream_size)

                with open(record_filename, 'w') as fh:
                    fh.write(url)
                logger.debug('Download recorded in %s', record_filename)

                # Check that the downloaded file is really a zip file
                if not zipfile.is_zipfile(fs_path):
                    logger.warning('Downloaded product is not a Zip File. Please check its file type before using it')
                    new_fs_path = fs_path[:fs_path.index('.zip')]
                    shutil.move(fs_path, new_fs_path)
                    return new_fs_path
                return self.__finalize(fs_path)

    def __build_download_url(self, product, auth):
        url = product.remote_location.format(base=self.config.base_uri.rstrip('/'))
        if product.properties['organisationName'] in ('ESA',):
            url += '?token={}'.format(auth.token)
        return url

    def __finalize(self, fs_path):
        """Finalize the download process.

        :param fs_path: The path to the local zip archive downloaded or already present
        :type fs_path: str or unicode
        :return: the absolute path to the product
        """
        if not self.config.extract:
            logger.info('Extraction not activated. The product is available as is.')
            return fs_path
        product_path = fs_path[:fs_path.index('.zip')]
        product_path_exists = os.path.exists(product_path)
        if not product_path_exists or (product_path_exists and len(os.listdir(product_path)) == 0):
            logger.info('Extraction activated')
            with zipfile.ZipFile(fs_path, 'r') as zfile:
                fileinfos = zfile.infolist()
                with tqdm(fileinfos, unit='file', desc='Extracting files from {}'.format(
                        os.path.basename(fs_path))) as progressbar:
                    for fileinfo in progressbar:
                        zfile.extract(
                            fileinfo,
                            path=os.path.join(self.config.outputs_prefix, product_path)
                        )
        # Handle depth levels in the product archive. For example, if the downloaded archive was
        # extracted to: /top_level/product_base_dir and archive_depth was configured to 2, the product
        # location will be /top_level/product_base_dir.
        # WARNING: A strong assumption is made here: there is only one subdirectory per level
        archive_depth = getattr(self.config, 'archive_depth', 1)
        count = 1
        while count < archive_depth:
            product_path = os.path.join(product_path, os.listdir(product_path)[0])
            count += 1
        return product_path
