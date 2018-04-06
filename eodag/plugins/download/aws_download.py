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


class aws_download(Download):

    def __init__(self, config):
        super(aws_download, self).__init__(config)

        self.config.setdefault('outputs_prefix', '/tmp')
        logger.debug('Images will be downloaded to directory %s', self.config['outputs_prefix'])

    def download(self, product, auth=None):

        #login
        access_key, access_secret = auth
        boto3.client('s3', aws_access_key_id=access_key,
                     aws_secret_access_key=access_secret)
        s3 = boto3.resource('s3')

        #amazon bucket where to download the data from
        bucket = s3.Bucket(self.config['associated_bucket'])

        output_dir = str(self.config['outputs_prefix'])
        doss = 'EO_product_{}'.format(product.id)

        #check if the directory where to store the product already exists of not creates it
        if os.path.isdir(os.path.join(output_dir, doss)):
            pass
        else:
            os.makedirs(os.path.join(output_dir, doss))

            for i in bucket.objects.filter(Prefix=product.location_url_tpl):

                dir = i.key.split('/')

                if len(dir) > 9:

                    if os.path.isdir(os.path.join(output_dir, doss, dir[-2])):
                        pass

                    else:
                        os.makedirs(os.path.join(output_dir, doss, dir[-2]))

                    l = i.key.split('/')
                    suffix = l[-1]
                    name = os.path.join(output_dir, doss, dir[-2], suffix)

                    #avoid to re download a file which has already been downloaded
                    if os.path.isfile(name):
                        pass
                    else:
                        bucket.download_file(i.key, name)

                else:

                    l = i.key.split('/')
                    suffix = l[-1]
                    name = os.path.join(output_dir, doss, suffix)
                    # avoid to re download a file which has already been downloaded
                    if os.path.isfile(name):
                        pass
                    else:
                        bucket.download_file(i.key, name)
