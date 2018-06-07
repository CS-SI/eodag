# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

import datetime
import logging
import zipfile

import shapely.wkt
from sentinelsat import SentinelAPI
from shapely import geometry
from tqdm import tqdm

from eodag.api.product import EOProduct
from eodag.api.product.representations import properties_from_json
from .base import Api


logger = logging.getLogger('eodag.plugins.apis.sentinelsat')


class SentinelsatAPI(Api):

    def __init__(self, config):
        super(SentinelsatAPI, self).__init__(config)
        self.api = None

    def query(self, product_type, **kwargs):
        self.__init_api()
        query_params = self.__convert_query_params(kwargs)
        try:
            final = []
            results = self.api.query(
                producttype=self.config['products'][product_type]['product_type'],
                limit=10,
                **query_params)
            if results:
                append_to_final = final.append
                for _id, original in results.items():
                    original['footprint'] = shapely.wkt.loads(original['footprint'])
                    original['beginposition'] = original['beginposition'].isoformat()
                    append_to_final(EOProduct(
                        self.instance_name,
                        original['link'],
                        properties_from_json(original, self.config['metadata_mapping']),
                        searched_bbox=kwargs.get('footprint')
                    ))
            return final
        except TypeError:
            import traceback as tb
            # Sentinelsat api query method raises a TypeError for finding None in the json feed received as a response
            # from the sentinel server, when looking for 'opensearch:totalResults' key. This may be interpreted as the
            # the api not finding any result from the query. This is what is assumed here.
            logger.debug('Something went wrong during the query with self.api api:\n %s', tb.format_exc())
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
                    with tqdm(fileinfos, unit='file', desc='Extracting files from {}'.format(
                            product_info['path'])) as progressbar:
                        for fileinfo in progressbar:
                            yield zfile.extract(fileinfo, path=self.config['outputs_prefix'])
            else:
                yield product_info['path']

    def __init_api(self):
        if not self.api:
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
