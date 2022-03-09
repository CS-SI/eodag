# -*- coding: utf-8 -*-
# Copyright 2022, CS GROUP - France, https://www.csgroup.eu/
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

import logging

from eodag.plugins.crunch.base import Crunch
from eodag.utils import get_geometry_from_various

try:
    from shapely.errors import TopologicalError
except ImportError:
    from shapely.geos import TopologicalError


logger = logging.getLogger("eodag.plugins.crunch.filter_overlap")


class FilterOverlap(Crunch):
    """FilterOverlap cruncher

    Filter products, retaining only those that are overlapping with the search_extent

    :param config: Crunch configuration, may contain :

                   - `minimum_overlap` : minimal overlap percentage
                   - `contains` : True if product geometry contains the search area
                   - `intersects` : True if product geometry intersects the search area
                   - `within` : True if product geometry is within the search area

                   These configuration parameters are mutually exclusive.
    :type config: dict
    """

    def proceed(self, products, **search_params):
        """Execute crunch: Filter products, retaining only those that are overlapping with the search_extent

        :param products: A list of products resulting from a search
        :type products: list(:class:`~eodag.api.product._product.EOProduct`)
        :param search_params: Search criteria that must contain `geometry`
        :type search_params: dict
        :returns: The filtered products
        :rtype: list(:class:`~eodag.api.product._product.EOProduct`)
        """
        logger.debug("Start filtering for overlapping products")
        filtered = []
        add_to_filtered = filtered.append

        search_geom = get_geometry_from_various(**search_params)
        if not search_geom:
            logger.warning(
                "geometry not found in cruncher arguments, filtering disabled."
            )
            return products
        minimum_overlap = float(self.config.get("minimum_overlap", "0"))
        contains = self.config.get("contains", False)
        intersects = self.config.get("intersects", False)
        within = self.config.get("within", False)

        if contains and (within or intersects) or (within and intersects):
            logger.warning(
                "contains, intersects and within parameters are mutually exclusive"
            )
            return products
        elif (
            minimum_overlap > 0
            and minimum_overlap < 100
            and (contains or within or intersects)
        ):
            logger.warning(
                "minimum_overlap will be ignored because of contains/intersects/within usage"
            )
        elif not contains and not within and not intersects:
            logger.debug("Minimum overlap is: {} %".format(minimum_overlap))

        logger.debug("Initial requested extent area: %s", search_geom.area)
        if search_geom.area == 0:
            logger.debug(
                "No product can overlap a requested extent that is not a polygon (i.e with area=0)"
            )
        else:
            for product in products:
                logger.debug("Uncovered extent area: %s", search_geom.area)
                if product.search_intersection:
                    intersection = product.search_intersection
                    product_geometry = product.geometry
                else:  # Product geometry may be invalid
                    if not product.geometry.is_valid:
                        logger.debug(
                            "Trying our best to deal with invalid geometry on product: %r",
                            product,
                        )
                        product_geometry = product.geometry.buffer(0)
                        try:
                            intersection = search_geom.intersection(product_geometry)
                        except TopologicalError:
                            logger.debug(
                                "Product geometry still invalid. Overlap test restricted to containment"
                            )
                            if search_geom.contains(product_geometry):
                                logger.debug(
                                    "Product %r overlaps the search extent. Adding it to filtered results"
                                )
                                add_to_filtered(product)
                            continue
                    else:
                        product_geometry = product.geometry
                        intersection = search_geom.intersection(product_geometry)

                if (
                    (contains and product_geometry.contains(search_geom))
                    or (within and product_geometry.within(search_geom))
                    or (intersects and product_geometry.intersects(search_geom))
                ):
                    add_to_filtered(product)
                    continue
                elif contains or within or intersects:
                    continue

                ipos = (intersection.area / search_geom.area) * 100
                ipop = (intersection.area / product_geometry.area) * 100
                logger.debug(
                    "Intersection of product extent and search extent covers %f percent of the search extent "
                    "area",
                    ipos,
                )
                logger.debug(
                    "Intersection of product extent and search extent covers %f percent of the product extent "
                    "area",
                    ipop,
                )
                if any(
                    (
                        search_geom.contains(product.geometry),
                        ipos >= minimum_overlap,
                        ipop >= minimum_overlap,
                    )
                ):
                    logger.debug(
                        "Product %r overlaps the search extent by the specified constraint. Adding it to "
                        "filtered results",
                        product,
                    )
                    add_to_filtered(product)
                else:
                    logger.debug(
                        "Product %r does not overlaps the search extent by the specified constraint. "
                        "Skipping it",
                        product,
                    )
        logger.info("Finished filtering products. %s resulting products", len(filtered))
        return filtered
