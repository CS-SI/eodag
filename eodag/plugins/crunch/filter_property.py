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

import logging
import operator
from typing import TYPE_CHECKING, Any

from eodag.plugins.crunch.base import Crunch

logger = logging.getLogger("eodag.crunch.property")

if TYPE_CHECKING:
    from eodag.api.product import EOProduct


class FilterProperty(Crunch):
    """FilterProperty cruncher

    Filter products, retaining only those whose property match criteria

    :param config: Crunch configuration, must contain :

        * ``<property>`` ``(Any)`` (**mandatory**): property key from ``product.properties``, associated to its filter
          value
        * ``operator`` (``str``): Operator used for filtering (one of ``lt,le,eq,ne,ge,gt``). Default is ``eq``
    """

    def proceed(
        self, products: list[EOProduct], **search_params: Any
    ) -> list[EOProduct]:
        """Execute crunch: Filter products, retaining only those that match property filtering

        :param products: A list of products resulting from a search
        :returns: The filtered products
        """
        operator_name = self.config.__dict__.pop("operator", "eq") or "eq"
        try:
            operator_method = getattr(operator, operator_name)
        except AttributeError:
            logger.warning(
                "Unknown operator `%s`, should be one of `lt,le,eq,ne,ge,gt`",
                operator_name,
            )
            return products

        if len(self.config.__dict__.keys()) != 1:
            logger.warning("One property is needed for filtering, filtering disabled.")
            return products

        property_key = next(iter(self.config.__dict__))
        property_value = self.config.__dict__.get(property_key, None)

        logger.debug(
            "Start filtering for products matching operator.%s(product.properties['%s'], %s)",
            operator_name,
            property_key,
            property_value,
        )
        filtered: list[EOProduct] = []
        add_to_filtered = filtered.append

        for product in products:
            if property_key not in product.properties.keys():
                logger.warning(
                    f"{property_key} not found in {product}.properties, product skipped",
                )
                continue
            if operator_method(product.properties[property_key], property_value):
                add_to_filtered(product)

        logger.info("Finished filtering products. %s resulting products", len(filtered))
        return filtered
