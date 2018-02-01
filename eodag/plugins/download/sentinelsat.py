# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
import logging
import zipfile

import click
from sentinelsat import SentinelAPI

from eodag.plugins.authentication import DummyAuth
from eodag.plugins.download.base import Download


logger = logging.getLogger('eodag.plugins.download.sentinelsat')


class SentinelSatDownload(Download):

    def __init__(self, config):
        super(SentinelSatDownload, self).__init__(config)
        self.config.setdefault('outputs_prefix', '/tmp')
        self.config.setdefault('on_site', False)
        self.config.setdefault('extract', True)
        logger.debug('Images will be downloaded to directory %s', self.config['outputs_prefix'])

    def download(self, product, auth=None):
        if not isinstance(auth, DummyAuth):
            raise RuntimeError('Invalid authentication plugin for SentinelSatDownload : {}. Must be {}'.format(
                auth.name, DummyAuth.name
            ))
        sentinelsat = SentinelAPI(
            auth.config['credentials']['user'],
            auth.config['credentials']['password'],
            self.config['base_uri']
        )

        if self.config['on_site']:
            data = sentinelsat.get_product_odata(product.original_repr, full=True)
            logger.info('Product already present on this platform. Identifier: %s', data['Identifier'])
            yield data['Identifier']
        else:
            product_info = sentinelsat.download_all(
                [product.original_repr],
                directory_path=self.config['outputs_prefix']
            )
            product_info = product_info[0][product.original_repr]

            if self.config['extract'] and product_info['path'].endswith('.zip'):
                logger.info('Extraction activated')
                with zipfile.ZipFile(product_info['path'], 'r') as zfile:
                    fileinfos = zfile.infolist()
                    with click.progressbar(fileinfos, fill_char='x', length=len(fileinfos), width=0,
                                           label='Extracting files from {}'.format(product_info['path'])) as progressbar:
                        for fileinfo in progressbar:
                            yield zfile.extract(fileinfo, path=self.config['outputs_prefix'])
            else:
                yield product_info['path']
