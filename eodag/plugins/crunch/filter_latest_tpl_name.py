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
import re
from typing import TYPE_CHECKING, Any, Optional, cast

from eodag.plugins.crunch.base import Crunch
from eodag.utils.exceptions import ValidationError

if TYPE_CHECKING:
    from eodag.api.product import EOProduct

logger = logging.getLogger("eodag.crunch.latest_tpl_name")


class FilterLatestByName(Crunch):
    """FilterLatestByName cruncher

    Filter Search results to get only the latest product, based on the name of the product

    :param config: Crunch configuration, must contain :

        * ``name_pattern`` (``str``) (**mandatory**): product name pattern
    """

    NAME_PATTERN_CONSTRAINT = re.compile(r"\(\?P<tileid>\\d\{6\}\)")

    def __init__(self, config: dict[str, Any]) -> None:
        super(FilterLatestByName, self).__init__(config)
        name_pattern = config.pop("name_pattern")
        if not self.NAME_PATTERN_CONSTRAINT.search(name_pattern):
            raise ValidationError(
                "Name pattern should respect the regex: {}".format(
                    self.NAME_PATTERN_CONSTRAINT.pattern
                )
            )
        self.name_pattern = re.compile(name_pattern)

    def proceed(
        self, products: list[EOProduct], **search_params: Any
    ) -> list[EOProduct]:
        """Execute crunch: Filter Search results to get only the latest product, based on the name of the product

        :param products: A list of products resulting from a search
        :returns: The filtered products
        """
        logger.debug("Starting products filtering")
        processed: list[str] = []
        filtered: list[EOProduct] = []
        for product in products:
            match = cast(
                Optional[re.Match[Any]],
                self.name_pattern.match(product.properties["title"]),
            )
            if match:
                tileid: str = match.group("tileid")
                if tileid not in processed:
                    logger.debug(
                        "Latest product found for tileid=%s: date=%s",
                        tileid,
                        product.properties["startTimeFromAscendingNode"],
                    )
                    filtered.append(product)
                    processed.append(tileid)
                else:
                    logger.debug("Latest product already found for tileid=%s", tileid)
            else:
                logger.warning(
                    "The name of the product %r as returned by the search plugin does not match the name "
                    "pattern expected by the cruncher %s. Name of the product: %s. Name pattern expected: "
                    "%s",
                    product,
                    self.__class__.__name__,
                    product.properties["title"],
                    self.name_pattern,
                )
        logger.info("Finished filtering products. %s resulting products", len(filtered))
        return filtered
