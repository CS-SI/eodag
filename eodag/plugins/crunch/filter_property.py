# -*- coding: utf-8 -*-
# Copyright 2020, CS GROUP - France, http://www.c-s.fr
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
import operator

from eodag.plugins.crunch.base import Crunch

logger = logging.getLogger("eodag.plugins.crunch.filter_property")


class FilterProperty(Crunch):
    """FilterProperty cruncher

    Filter products, retaining only those whose property match criteria

    :param dict config: crunch configuration, should contain :

            - `property=value` : property key from product.properties, associated to its filter value
            - `operator` : (optional) Operator used for filtering (one of `lt,le,eq,ne,ge,gt`). Default is `eq`
    """

    def proceed(self, products, **search_params):
        """Execute crunch: Filter products, retaining only those that match property filtering

        :param products: A list of products resulting from a search
        :type products: list(:class:`~eodag.api.product.EOProduct`)
        :returns: The filtered products
        :rtype: list(:class:`~eodag.api.product.EOProduct`)
        """
        operator_name = self.config.pop("operator", "eq")
        try:
            operator_method = getattr(operator, operator_name)
        except AttributeError:
            logger.warning(
                "Unknown operator `%s`, should be one of `lt,le,eq,ne,ge,gt`",
                operator_name,
            )
            return products

        if len(self.config.keys()) != 1:
            logger.warning("One property is needed for filtering, filtering disabled.")
            return products

        property_key = next(iter(self.config))
        property_value = self.config.get(property_key, None)

        logger.debug(
            "Start filtering for products matching operator.%s(product.properties['%s'], %s)",
            operator_name,
            property_key,
            property_value,
        )
        filtered = []
        add_to_filtered = filtered.append

        for product in products:
            if property_key not in product.properties.keys():
                logger.warning(
                    "%s not found in product.properties, filtering disabled.",
                    property_key,
                )
                return products
            if operator_method(product.properties[property_key], property_value):
                add_to_filtered(product)

        logger.info("Finished filtering products. %s resulting products", len(filtered))
        return filtered
