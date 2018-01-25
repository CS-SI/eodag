# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
import hashlib
import os
import requests
from requests import HTTPError
from tqdm import tqdm

from satdl.plugins.download.base import Download
from satdl.plugins.search.base import MisconfiguredError


class HTTPDownload(Download):

    def __init__(self, config):
        super(HTTPDownload, self).__init__(config)
        if 'base_uri' not in self.config:
            raise MisconfiguredError('{} plugin require a base_uri configuration key'.format(self.name))
        self.config.setdefault('outputs_prefix', '/tmp')
        self.config.setdefault('on_site', False)

    def download(self, product, auth=None):
        """Download a product from resto-like platforms"""
        if not self.config['on_site']:
            url = self.__build_download_url(product, auth)
            filename = product.local_filename
            local_file_path = os.path.join(self.config['outputs_prefix'], filename)
            download_records = os.path.join(self.config['outputs_prefix'], '.downloaded')
            if not os.path.exists(download_records):
                os.makedirs(download_records)
            url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
            record_filename = os.path.join(download_records, url_hash)
            if os.path.isfile(record_filename) and os.path.isfile(local_file_path):
                return local_file_path
            # Remove the record file if local_file_path is absent (e.g. it was deleted but record wasn't)
            elif os.path.isfile(record_filename):
                os.remove(record_filename)
            hook_print = lambda r, *args, **kwargs: print('\n', r.url)
            with requests.get(url, stream=True, auth=auth, hooks={'response': hook_print}) as stream:
                stream_size = int(stream.headers.get('content-length', 0))
                with open(local_file_path, 'wb') as fhandle:
                    pbar = tqdm(total=stream_size, unit='KB')
                    for chunk in stream.iter_content(chunk_size=64*1024):
                        if chunk:
                            pbar.update(len(chunk))
                            fhandle.write(chunk)
                try:
                    stream.raise_for_status()
                except HTTPError as e:
                    print("Error while getting resource : %s" % e.args)
                else:
                    with open(record_filename, 'w') as fh:
                        fh.write(url)
                    return local_file_path
        else:
            # Do not download data if we are on site. Instead give back the absolute path to the data
            # TODO: this is broken
            return product['properties']['productIdentifier']

    def __build_download_url(self, product, auth):
        try:
            url = product.location_url_tpl.format(
                base=self.config['base_uri'],
            )
            if product.original_repr['properties']['organisationName'] in ('ESA',):
                url += '?token={}'.format(auth.token)
            return url
        except Exception:
            raise RuntimeError('Product {} is incompatible with download plugin {}'.format(product, self.name))

