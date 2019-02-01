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
from __future__ import unicode_literals

import datetime
import logging
import time

import dateutil.parser
from dateutil.tz import tzutc
from shapely import geometry

from eodag.plugins.crunch.base import Crunch


logger = logging.getLogger('eodag.plugins.crunch.filter_latest')


class FilterLatestIntersect(Crunch):

    @staticmethod
    def sort_product_by_start_date(product):
        start_date = product.properties.get('startTimeFromAscendingNode')
        if not start_date:
            # Retrieve year, month, day, hour, minute, second of EPOCH start
            epoch = time.gmtime(0)[:-3]
            start_date = datetime.datetime(*epoch).isoformat()
        if product.provider == 'sobloo':
            # Sobloo provides dates as timestamps in milliseconds
            # Transform it to a UTC datetime object which is timezone-aware
            start_date = datetime.datetime.fromtimestamp(start_date / 1000, tzutc()).isoformat()
        return dateutil.parser.parse(start_date)

    def proceed(self, products, **search_params):
        """Filter latest products (the ones with a the highest start date) that intersect search extent."""
        logger.debug('Start filtering for latest products')
        if not products:
            return []
        # Warning: May crash if startTimeFromAscendingNode is not in the appropriate format
        products.sort(key=self.sort_product_by_start_date, reverse=True)
        filtered = []
        add_to_filtered = filtered.append
        footprint = search_params.get('footprint')
        if not footprint:
            return products
        search_extent = geometry.box(
            footprint['lonmin'],
            footprint['latmin'],
            footprint['lonmax'],
            footprint['latmax']
        )
        logger.debug('Initial requested extent area: %s', search_extent.area)
        for product in products:
            logger.debug('Uncovered extent area: %s', search_extent.area)
            if product.search_intersection:
                logger.debug('Product %r intersects the requested extent. Adding it to the final result', product)
                add_to_filtered(product)
            search_extent = search_extent.difference(product.geometry)
            if search_extent.is_empty:
                logger.debug('The requested extent is now entirely covered by the search result')
                break
        logger.debug('Finished filtering products. Resulting products: %r', filtered)
        return filtered
