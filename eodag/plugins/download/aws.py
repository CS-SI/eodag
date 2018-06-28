# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

import boto3

from eodag.plugins.download.base import Download

logger = logging.getLogger('eodag.plugins.download.http')


class AwsDownload(Download):

    def __init__(self, config):
        super(AwsDownload, self).__init__(config)

        self.config.setdefault('outputs_prefix', '/tmp')
        logger.debug('Images will be downloaded to directory %s', self.config['outputs_prefix'])

    def download(self, product, auth=None, progress_callback=None):
        access_key, access_secret = auth
        s3 = boto3.resource('s3', aws_access_key_id=access_key, aws_secret_access_key=access_secret)
        bucket = s3.Bucket(self.config['associated_bucket'])
        product_local_path = os.path.join(
            self.config['outputs_prefix'],
            product.properties['title']
        )
        if not os.path.isdir(product_local_path):
            os.makedirs(product_local_path)

        for product_chunk in bucket.objects.filter(Prefix=product.location):
            chunck_path_as_list = product_chunk.key.split('/')
            if len(chunck_path_as_list) > 9:
                chunk_dir = os.path.join(product_local_path, chunck_path_as_list[-2])
                if not os.path.isdir(chunk_dir):
                    os.makedirs(chunk_dir)
                chunk_file_path = os.path.join(chunk_dir, chunck_path_as_list[-1])
            else:
                chunk_file_path = os.path.join(product_local_path, chunck_path_as_list[-1])
            if not os.path.isfile(chunk_file_path):
                bucket.download_file(product_chunk.key, chunk_file_path)
        return product_local_path
