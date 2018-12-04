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
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

import boto3

from eodag.plugins.download.base import Download
from eodag.utils import urlparse

logger = logging.getLogger('eodag.plugins.download.aws')


class AwsDownload(Download):

    def download(self, product, auth=None, progress_callback=None):
        bucket_name, prefix = self.get_bucket_name_and_prefix(product)
        access_key, access_secret = auth
        s3 = boto3.resource('s3', aws_access_key_id=access_key, aws_secret_access_key=access_secret)
        bucket = s3.Bucket(bucket_name)

        for product_chunk in bucket.objects.filter(Prefix=prefix):
            product_local_path = os.path.join(
                self.config.outputs_prefix,
                product.properties.get('title', product.properties['id'])
            )
            if not os.path.isdir(product_local_path):
                os.makedirs(product_local_path)

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

    def get_bucket_name_and_prefix(self, product):
        bucket, prefix = None, None
        # Assume the bucket is encoded into the product location as a URL or given as the 'associated_bucket' config
        # param
        scheme, netloc, path, params, query, fragment = urlparse(product.location)
        if not netloc and scheme == 's3':
            bucket, path = self.config.associated_bucket, path
        elif scheme in ('http', 'https', 'ftp'):
            parts = path.split('/')
            bucket, prefix = parts[1], '/{}'.format('/'.join(parts[2:]))
        return bucket, prefix
