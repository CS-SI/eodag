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

from typing import TYPE_CHECKING

from eodag.utils.deserialize import unregistered_product_from_item

if TYPE_CHECKING:
    from eodag.api.product._assets import Asset, AssetsDict
    from eodag.api.product._product import EOProduct

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
