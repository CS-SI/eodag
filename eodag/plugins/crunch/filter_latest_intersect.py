# -*- coding: utf-8 -*-
# Copyright 2018, CS GROUP - France, https://www.csgroup.eu/
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

import datetime
import logging
import time

import dateutil.parser
from shapely import geometry

from eodag.plugins.crunch.base import Crunch

logger = logging.getLogger("eodag.plugins.crunch.filter_latest_intersect")


class FilterLatestIntersect(Crunch):
    """FilterLatestIntersect cruncher

    Filter latest products (the ones with a the highest start date) that intersect search extent
    """

    @staticmethod
    def sort_product_by_start_date(product):
        """Get product start date"""
        start_date = product.properties.get("startTimeFromAscendingNode")
        if not start_date:
            # Retrieve year, month, day, hour, minute, second of EPOCH start
            epoch = time.gmtime(0)[:-3]
            start_date = datetime.datetime(*epoch).isoformat()
        return dateutil.parser.parse(start_date)

    def proceed(self, products, **search_params):
        """Execute crunch:
        Filter latest products (the ones with a the highest start date) that intersect search extent.

        :param products: A list of products resulting from a search
        :type products: list(:class:`~eodag.api.product._product.EOProduct`)
        :param search_params: Search criteria that must contain `geometry` (dict)
        :type search_params: dict
        :returns: The filtered products
        :rtype: list(:class:`~eodag.api.product._product.EOProduct`)
        """
        logger.debug("Start filtering for latest products")
        if not products:
            return []
        # Warning: May crash if startTimeFromAscendingNode is not in the appropriate format
        products.sort(key=self.sort_product_by_start_date, reverse=True)
        filtered = []
        add_to_filtered = filtered.append
        footprint = search_params.get("geometry")
        if not footprint:
            logger.warning(
                "geometry not found in cruncher arguments, filtering disabled."
            )
            return products
        search_extent = geometry.box(
            footprint["lonmin"],
            footprint["latmin"],
            footprint["lonmax"],
            footprint["latmax"],
        )
        logger.debug("Initial requested extent area: %s", search_extent.area)
        for product in products:
            logger.debug("Uncovered extent area: %s", search_extent.area)
            if product.search_intersection:
                logger.debug(
                    "Product %r intersects the requested extent. Adding it to the final result",
                    product,
                )
                add_to_filtered(product)
            search_extent = search_extent.difference(product.geometry)
            if search_extent.is_empty:
                logger.debug(
                    "The requested extent is now entirely covered by the search result"
                )
                break
        logger.info("Finished filtering products. %s resulting products", len(filtered))
        return filtered
