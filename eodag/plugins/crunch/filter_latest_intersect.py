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

import datetime as dt
import logging
from typing import TYPE_CHECKING, Any, Optional, Union

from shapely.errors import ShapelyError
from shapely.geometry.base import BaseGeometry

from eodag.plugins.crunch.base import Crunch
from eodag.utils import get_geometry_from_various
from eodag.utils.dates import parse_to_utc

if TYPE_CHECKING:
    from eodag.api.product import EOProduct

logger = logging.getLogger("eodag.crunch.latest_intersect")


class FilterLatestIntersect(Crunch):
    """FilterLatestIntersect cruncher

    Filter latest products (the ones with a the highest start date) that intersect search extent;
    The configuration for this plugin is an empty dict
    """

    @staticmethod
    def sort_product_by_start_date(product: EOProduct) -> dt.datetime:
        """Get product start date"""
        start_date = product.properties.get("start_datetime")
        if not start_date:
            return dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
        return parse_to_utc(start_date)

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
        if not products or (isinstance(products, list) and len(products) == 0):
            return []
        # Warning: May crash if start_datetime is not in the appropriate format
        products.sort(key=self.sort_product_by_start_date, reverse=True)
        filtered: list[EOProduct] = []
        search_extent: Optional[BaseGeometry]
        add_to_filtered = filtered.append
        footprint: Union[dict[str, Any], BaseGeometry, Any] = search_params.get(
            "geometry"
        ) or search_params.get("geom")
        if not footprint:
            logger.warning(
                "geometry not found in cruncher arguments, filtering disabled."
            )
            return products
        try:
            search_extent = get_geometry_from_various(geometry=footprint)
        except (ShapelyError, TypeError):
            logger.warning(
                "geometry found in cruncher arguments did not match the expected format."
            )
            return products
        if search_extent is None:
            logger.warning("Could not build geometry from cruncher arguments")
            return products

        logger.debug("Initial requested extent area: %s", search_extent.area)
        for product in products:
            logger.debug("Uncovered extent area: %s", search_extent.area)
            try:
                search_intersection = product.geometry.intersection(search_extent)
            except ShapelyError:
                search_intersection = None
            if search_intersection:
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
