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
from __future__ import annotations

import datetime
import logging
import time
from typing import TYPE_CHECKING, Any, Union

import dateutil.parser
from shapely import geometry
from shapely.geometry.base import BaseGeometry

from eodag.plugins.crunch.base import Crunch

if TYPE_CHECKING:
    from datetime import datetime as dt

    from eodag.api.product import EOProduct

logger = logging.getLogger("eodag.crunch.latest_intersect")


class FilterLatestIntersect(Crunch):
    """FilterLatestIntersect cruncher

    Filter latest products (the ones with a the highest start date) that intersect search extent;
    The configuration for this plugin is an empty dict
    """

    @staticmethod
    def sort_product_by_start_date(product: EOProduct) -> dt:
        """Get product start date"""
        start_date = product.properties.get("startTimeFromAscendingNode")
        if not start_date:
            # Retrieve year, month, day, hour, minute, second of EPOCH start
            epoch = time.gmtime(0)[:-3]
            start_date = datetime.datetime(*epoch).isoformat()
        return dateutil.parser.parse(start_date)

    def proceed(
        self, products: list[EOProduct], **search_params: dict[str, Any]
    ) -> list[EOProduct]:
        """Execute crunch:
        Filter latest products (the ones with a the highest start date) that intersect search extent.

        :param products: A list of products resulting from a search
        :param search_params: Search criteria that must contain ``geometry`` or ``geom`` parameters having value of
                              type :class:`shapely.geometry.base.BaseGeometry` or ``dict[str, Any]``
        :returns: The filtered products
        """
        logger.debug("Start filtering for latest products")
        if not products:
            return []
        # Warning: May crash if startTimeFromAscendingNode is not in the appropriate format
        products.sort(key=self.sort_product_by_start_date, reverse=True)
        filtered: list[EOProduct] = []
        add_to_filtered = filtered.append
        footprint: Union[dict[str, Any], BaseGeometry, Any] = search_params.get(
            "geometry"
        ) or search_params.get("geom")
        if not footprint:
            logger.warning(
                "geometry not found in cruncher arguments, filtering disabled."
            )
            return products
        elif isinstance(footprint, dict):
            search_extent = geometry.box(
                footprint["lonmin"],
                footprint["latmin"],
                footprint["lonmax"],
                footprint["latmax"],
            )
        elif not isinstance(footprint, BaseGeometry):
            logger.warning(
                "geometry found in cruncher arguments did not match the expected format."
            )
            return products
        else:
            search_extent = footprint
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
