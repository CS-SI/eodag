# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import logging
import zipfile

import click
import shapely.wkt
from sentinelsat import SentinelAPI
from shapely import geometry

from eodag.api.product import EOProduct
from .base import Api


logger = logging.getLogger(b'eodag.plugins.apis.sentinelsat')


class SentinelsatAPI(Api):

    def __init__(self, config):
        super(SentinelsatAPI, self).__init__(config)
        self.api = None

    def query(self, product_type, **kwargs):
        self.__init_api()
        query_params = self.__convert_query_params(kwargs)
        try:
            final = []
            results = self.api.query(producttype=product_type, limit=10, **query_params)
            if results:
                append_to_final = final.append
                for _id, original in results.items():
                    geom = shapely.wkt.loads(original['footprint'])
                    append_to_final(EOProduct(
                        self.instance_name,
                        original['link'],
                        original['filename'],
                        geom,
                        kwargs.get('footprint'),
                        product_type,
                        original['platform'],       # TODO
                        original['instrument'],     # TODO
                        provider_id=_id,
                        centroid=geom.centroid,
                        description=original['summary'],
                        title=original['title'],
                        productIdentifier=original['identifier'],
                        startDate=original['ingestionDate']
                    ))
            return final
        except TypeError as e:
            # Sentinelsat api query method raises a TypeError for finding None in the json feed received as a response
            # from the sentinel server, when looking for 'opensearch:totalResults' key. This may be interpreted as the
            # the api not finding any result from the query. This is what is assumed here.
            logger.debug('Something went wrong during the query with self.api api: %s', e)
            logger.info('No results found !')
            return []

    def download(self, product, auth=None):
        self.__init_api()
        if self.config['on_site']:
            data = self.api.get_product_odata(product.id, full=True)
            logger.info('Product already present on this platform. Identifier: %s', data['Identifier'])
            yield data['Identifier']
        else:
            product_info = self.api.download_all(
                [product.id],
                directory_path=self.config['outputs_prefix']
            )
            product_info = product_info[0][product.id]

            if self.config['extract'] and product_info['path'].endswith('.zip'):
                logger.info('Extraction activated')
                with zipfile.ZipFile(product_info['path'], 'r') as zfile:
                    fileinfos = zfile.infolist()
                    with click.progressbar(fileinfos, fill_char='x', length=len(fileinfos), width=0,
                                           label='Extracting files from {}'.format(
                                               product_info['path'])) as progressbar:
                        for fileinfo in progressbar:
                            yield zfile.extract(fileinfo, path=self.config['outputs_prefix'])
            else:
                yield product_info['path']

    def __init_api(self):
        if not self.api or not isinstance(self.api, SentinelAPI):
            logger.debug('Initialising sentinelsat api')
            self.api = SentinelAPI(
                self.config['credentials']['user'],
                self.config['credentials']['password'],
                self.config['endpoint']
            )
        else:
            logger.debug('Sentinelsat api already initialized')

    @staticmethod
    def __convert_query_params(params):
        query = {}
        if params.get('footprint'):
            footprint = params['footprint']
            box_values = (footprint['lonmin'], footprint['latmin'], footprint['lonmax'], footprint['latmax'])
            query['footprint'] = geometry.box(*box_values).to_wkt()
        if params.get('maxCloudCover'):
            query['cloudcoverpercentage'] = (0, params['maxCloudCover'])
        if params.get('startDate') and params.get('endDate'):
            def __handle_date(date):
                if any(isinstance(date, klass) for klass in (datetime.datetime, datetime.date)):
                    return date.strftime('%Y%m%d')
                return datetime.datetime.strptime(date, '%Y-%m-%d').strftime('%Y%m%d')
            query['date'] = (__handle_date(params['startDate']), __handle_date(params['endDate']))
        return query
