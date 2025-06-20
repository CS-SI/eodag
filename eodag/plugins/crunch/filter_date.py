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
from datetime import datetime as dt
from typing import TYPE_CHECKING, Any

import dateutil.parser
from dateutil import tz

if TYPE_CHECKING:
    from eodag.api.product import EOProduct

from eodag.plugins.crunch.base import Crunch

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
    def sort_product_by_start_date(product: EOProduct) -> dt:
        """Get product start date"""
        start_date = product.properties.get("startTimeFromAscendingNode")
        if not start_date:
            # Retrieve year, month, day, hour, minute, second of EPOCH start
            epoch = time.gmtime(0)[:-3]
            start_date = datetime.datetime(*epoch).isoformat()
        return dateutil.parser.parse(start_date)

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
            filter_start = dateutil.parser.parse(filter_start_str)
            if not filter_start.tzinfo:
                filter_start = filter_start.replace(tzinfo=tz.UTC)
        else:
            filter_start = None

        # filter end date
        filter_end_str = self.config.__dict__.get("end")
        if filter_end_str:
            filter_end = dateutil.parser.parse(filter_end_str)
            if not filter_end.tzinfo:
                filter_end = filter_end.replace(tzinfo=tz.UTC)
        else:
            filter_end = None

        if not filter_start and not filter_end:
            return products

        filtered: list[EOProduct] = []
        for product in products:

            # product start date
            product_start_str = product.properties.get("startTimeFromAscendingNode")
            if product_start_str:
                product_start = dateutil.parser.parse(product_start_str)
                if not product_start.tzinfo:
                    product_start = product_start.replace(tzinfo=tz.UTC)
            else:
                product_start = None

            # product end date
            product_end_str = product.properties.get("completionTimeFromAscendingNode")
            if product_end_str:
                product_end = dateutil.parser.parse(product_end_str)
                if not product_end.tzinfo:
                    product_end = product_end.replace(tzinfo=tz.UTC)
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
