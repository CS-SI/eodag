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

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from eodag.api.product._assets import Asset, AssetsDict
    from eodag.api.product._product import EOProduct
    from eodag.plugins.manager import PluginManager

# exportable content
__all__ = ["Asset", "AssetsDict", "EOProduct", "unregistered_product_from_item"]

# Lazy imports (PEP 562) — defer heavy _product / _assets loading
_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "EOProduct": ("._product", "EOProduct"),
    "Asset": ("._assets", "Asset"),
    "AssetsDict": ("._assets", "AssetsDict"),
}


def _resolve(name: str):
    """Resolve a lazy import, trying eodag-cube first for EOProduct/Asset/AssetsDict."""
    module_path, attr_name = _LAZY_IMPORTS[name]
    from importlib import import_module

    # Try eodag_cube first (provides extended classes with xarray/rasterio support).
    # Users just need ``pip install eodag_cube`` — no other change required.
    try:
        cube_module = import_module("eodag_cube.api.product")
        value = getattr(cube_module, attr_name, None)
        if value is not None:
            globals()[name] = value
            return value
    except ImportError:
        pass

    # Fallback to eodag's own modules
    module = import_module(module_path, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        return _resolve(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return __all__


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


# exportable content
__all__ = ["Asset", "AssetsDict", "EOProduct", "unregistered_product_from_item"]
