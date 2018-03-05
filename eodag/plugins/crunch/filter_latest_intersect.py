# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

import logging

import dateutil.parser
from shapely import geometry

from eodag.plugins.crunch.base import Crunch


logger = logging.getLogger('eodag.plugins.crunch.filter_latest')


class FilterLatestIntersect(Crunch):

    def proceed(self, products, **search_params):
        """Filter latest products (the ones with a the highest start date) that intersect search extent."""
        logger.debug('Start filtering for latest products')
        if not products:
            return []
        products.sort(key=lambda product: dateutil.parser.parse(product.properties.get('startDate')), reverse=True)
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
