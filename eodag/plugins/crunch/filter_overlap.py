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

import logging

from shapely import geometry

try:
    from shapely.errors import TopologicalError
except ImportError:
    from shapely.geos import TopologicalError

from eodag.plugins.crunch.base import Crunch


logger = logging.getLogger('eodag.plugins.crunch.filter_latest')


class FilterOverlap(Crunch):

    def proceed(self, products, **search_params):
        """Filter products, retaining only those that are overlapping with the search_extent"""
        logger.debug('Start filtering for overlapping products')
        filtered = []
        add_to_filtered = filtered.append
        footprint = search_params.get('footprint')
        if not footprint:
            return products
        minimum_overlap = float(self.config.get('minimum_overlap', '0'))
        search_extent = geometry.box(footprint['lonmin'], footprint['latmin'],
                                     footprint['lonmax'], footprint['latmax'])
        logger.debug('Initial requested extent area: %s', search_extent.area)
        for product in products:
            logger.debug('Uncovered extent area: %s', search_extent.area)
            if product.search_intersection:
                intersection = product.search_intersection
                product_geometry = product.geometry
            else:  # Product geometry may be invalid
                if not product.geometry.is_valid():
                    logger.debug('Trying our best to deal with invalid geometry on product: %r', product)
                    product_geometry = product.geometry.buffer(0)
                    try:
                        intersection = search_extent.intersection(product_geometry)
                    except TopologicalError:
                        logger.debug('Product geometry still invalid. Overlap test restricted to containment')
                        if search_extent.contains(product_geometry):
                            logger.debug('Product %r overlaps the search extent. Adding it to filtered results')
                            add_to_filtered(product)
                        continue
                else:
                    product_geometry = product.geometry
                    intersection = search_extent.intersection(product_geometry)
            ipos = (intersection.area / search_extent.area) * 100
            ipop = (intersection.area / product_geometry.area) * 100
            logger.debug('Intersection of product extent and search extent covers %f percent of the search extent '
                         'area', ipos)
            logger.debug('Intersection of product extent and search extent covers %f percent of the product extent '
                         'area', ipop)
            if any((search_extent.contains(product.geometry), ipos >= minimum_overlap, ipop >= minimum_overlap)):
                logger.debug('Product %r overlaps the search extent. Adding it to filtered results', product)
                add_to_filtered(product)
        logger.debug('Finished filtering products. Resulting products: %r', filtered)
        return filtered
