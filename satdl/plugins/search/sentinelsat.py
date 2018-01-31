# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
import datetime
import logging

from shapely import geometry
from sentinelsat import SentinelAPI

from satdl.api.product import EOProduct
from .base import Search


logger = logging.getLogger('satdl.plugins.search.sentinelsat')


class SentinelSearch(Search):

    def query(self, product_type, **kwargs):
        sentinelsat = SentinelAPI(
            self.config['credentials']['user'],
            self.config['credentials']['password'],
            self.config['api_endpoint']
        )
        query_params = self.__convert_query_params(kwargs)
        try:
            return [
                EOProduct(original)
                for original in sentinelsat.query(producttype=product_type, limit=10, **query_params)
            ]
        except TypeError as e:
            # Sentinelsat api query method raises a TypeError for finding None in the json feed received as a response
            # from the sentinel server, when looking for 'opensearch:totalResults' key. This may be interpreted as the
            # the api not finding any result from the query. This is what is assumed here.
            logger.debug('Something went wrong during the query with sentinelsat api: %s', e)
            logger.info('No results found !')
            return []

    @staticmethod
    def __convert_query_params(params):
        query = {}
        if params.get('footprint'):
            footprint = params['footprint']
            if len(footprint.keys()) == 2:
                query['footprint'] = '{lat},{lon}'.format(**footprint)
            if len(footprint.keys()) == 4:
                box_values = (footprint['lonmin'], footprint['latmin'], footprint['lonmax'], footprint['latmax'])
                query['footprint'] = geometry.box(*box_values).to_wkt()
        if params.get('maxCloudCover'):
            query['cloudcoverpercentage'] = (0, params['maxCloudCover'])
        if params.get('startDate') and params.get('endDate'):
            start = params['startDate']
            end = params['endDate']
            if any(isinstance(start, klass) for klass in (datetime.datetime, datetime.date)):
                start = start.strftime('%Y%m%d')
            else:
                start = datetime.datetime.strptime(start, '%Y-%m-%d').strftime('%Y%m%d')
            if any(isinstance(params['endDate'], klass) for klass in (datetime.datetime, datetime.date)):
                end = end.strftime('%Y%m%d')
            else:
                end = datetime.datetime.strptime(end, '%Y-%m-%d').strftime('%Y%m%d')
            query['date'] = (start, end)
        return query
