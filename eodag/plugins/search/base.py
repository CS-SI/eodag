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

import logging

from eodag.api.product.metadata_mapping import (
    DEFAULT_METADATA_MAPPING,
    mtd_cfg_as_conversion_and_querypath,
)
from eodag.plugins.base import PluginTopic
from eodag.utils import GENERIC_PRODUCT_TYPE, format_dict_items

logger = logging.getLogger("eodag.search.base")


class Search(PluginTopic):
    """Base Search Plugin.

    :param provider: An eodag providers configuration dictionary
    :type provider: dict
    :param config: Path to the user configuration file
    :type config: str
    """

    def __init__(self, provider, config):
        super(Search, self).__init__(provider, config)
        # Prepare the metadata mapping
        # Do a shallow copy, the structure is flat enough for this to be sufficient
        metas = DEFAULT_METADATA_MAPPING.copy()
        # Update the defaults with the mapping value. This will add any new key
        # added by the provider mapping that is not in the default metadata
        metas.update(self.config.metadata_mapping)
        self.config.metadata_mapping = mtd_cfg_as_conversion_and_querypath(
            metas,
            self.config.metadata_mapping,
            result_type=getattr(self.config, "result_type", "json"),
        )

    def clear(self):
        """Method used to clear a search context between two searches."""
        pass

    def query(self, *args, count=True, **kwargs):
        """Implementation of how the products must be searched goes here.

        This method must return a tuple with (1) a list of EOProduct instances (see eodag.api.product module)
        which will be processed by a Download plugin (2) and the total number of products matching
        the search criteria. If ``count`` is False, the second element returned must be ``None``.
        """
        raise NotImplementedError("A Search plugin must implement a method named query")

    def discover_product_types(self):
        """Fetch product types list from provider using `discover_product_types` conf"""
        return

    def map_product_type(self, product_type, **kwargs):
        """Get the provider product type from eodag product type

        :param product_type: eodag product type
        :type product_type: str
        :returns: provider product type
        :rtype: str
        """
        if product_type is None:
            return
        logger.debug("Mapping eodag product type to provider product type")
        return self.config.products.get(product_type, {}).get(
            "productType", GENERIC_PRODUCT_TYPE
        )

    def get_product_type_def_params(self, product_type, **kwargs):
        """Get the provider product type definition parameters and specific settings

        :param product_type: the desired product type
        :type product_type: str
        :returns: The product type definition parameters
        :rtype: dict
        """
        if product_type in self.config.products.keys():
            logger.debug(
                "Getting provider product type definition parameters for %s",
                product_type,
            )
            return self.config.products[product_type]
        elif GENERIC_PRODUCT_TYPE in self.config.products.keys():
            logger.debug(
                "Getting generic provider product type definition parameters for %s",
                product_type,
            )
            return {
                k: v
                for k, v in format_dict_items(
                    self.config.products[GENERIC_PRODUCT_TYPE], **kwargs
                ).items()
                if v
            }
        else:
            return {}

    def get_metadata_mapping(self, product_type=None):
        """Get the plugin metadata mapping configuration (product type specific if exists)

        :param product_type: the desired product type
        :type product_type: str
        :returns: The product type specific metadata-mapping
        :rtype: dict
        """
        return self.config.products.get(product_type, {}).get(
            "metadata_mapping", self.config.metadata_mapping
        )
