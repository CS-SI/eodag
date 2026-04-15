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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from eodag.api.product import EOProduct

from eodag.plugins.crunch.base import Crunch
from eodag.utils.dates import parse_to_utc

logger = logging.getLogger("eodag.crunch.date")


class FilterDate(Crunch):
    """FilterDate cruncher: filter products by date

    Allows to filter out products that are older than a start date (optional) or more recent than an end date
    (optional).

    :param config: Crunch configuration, may contain :

        * ``start`` (``str``): start sensing time in iso format
        * ``end`` (``str``): end sensing time in iso format
    """

    @staticmethod
    def sort_product_by_start_date(product: EOProduct) -> dt.datetime:
        """Get product start date"""
        start_date = product.properties.get("start_datetime")
        if not start_date:
            return dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
        return parse_to_utc(start_date)

    def proceed(
        self, products: list[EOProduct], **search_params: Any
    ) -> list[EOProduct]:
        """Execute crunch: Filter products between start and end dates.

        :param products: A list of products resulting from a search
        :returns: The filtered products
        """
        logger.debug("Start filtering by date")
        if not products:
            return []

        # filter start date
        filter_start_str = self.config.__dict__.get("start")
        if filter_start_str:
            filter_start = parse_to_utc(filter_start_str)
        else:
            filter_start = None

        # filter end date
        filter_end_str = self.config.__dict__.get("end")
        if filter_end_str:
            filter_end = parse_to_utc(filter_end_str)
        else:
            filter_end = None

        if not filter_start and not filter_end:
            return products

        filtered: list[EOProduct] = []
        for product in products:

            # product start date
            product_start_str = product.properties.get("start_datetime")
            if product_start_str:
                product_start = parse_to_utc(product_start_str)
            else:
                product_start = None

            # product end date
            product_end_str = product.properties.get("end_datetime")
            if product_end_str:
                product_end = parse_to_utc(product_end_str)
            else:
                product_end = None

            if filter_start and product_start and product_start < filter_start:
                continue
            if filter_end and product_end and product_end > filter_end:
                continue
            if filter_end and product_start and product_start > filter_end:
                continue

            filtered.append(product)
        logger.info("Finished filtering products. %s resulting products", len(filtered))
        return filtered
