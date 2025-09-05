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
#
"""EODAG product package"""

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from eodag.plugins.manager import PluginManager

try:
    # import from eodag-cube if installed
    from eodag_cube.api.product import (  # pyright: ignore[reportMissingImports]
        Asset,
        AssetsDict,
        EOProduct,
    )
except ImportError:
    from ._assets import Asset, AssetsDict  # type: ignore[assignment]
    from ._product import EOProduct  # type: ignore[assignment]

# exportable content
__all__ = ["Asset", "AssetsDict", "EOProduct"]


def unregistered_product_from_item(
    feature: dict[str, Any], provider: str, plugins_manager: "PluginManager"
) -> Optional[EOProduct]:
    """Create an EOProduct from a STAC item, map its metadata, but without registering its plugins.

    :param feature: The STAC item to convert into an EOProduct.
    :param provider: The associated provider from which configuration should be used for mapping.
    :param plugins_manager: The plugins manager instance to use for retrieving search plugins.
    :returns: An EOProduct instance if the item can be normalized, otherwise None.
    """
    for search_plugin in plugins_manager.get_search_plugins(provider=provider):
        if hasattr(search_plugin, "normalize_results"):
            products = search_plugin.normalize_results([feature])
            if len(products) > 0:
                # properties cleanup
                for prop in ("start_datetime", "end_datetime"):
                    products[0].properties.pop(prop, None)
                # set collection if not already set
                if products[0].collection is None:
                    products[0].collection = products[0].properties.get("collection")
                return products[0]
    return None
