# -*- coding: utf-8 -*-
# Copyright 2023, CS GROUP - France, https://www.csgroup.eu/
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

import re
from collections import UserDict
from typing import TYPE_CHECKING, Any, Dict, List

from eodag.utils.exceptions import NotAvailableError

if TYPE_CHECKING:
    from eodag.api.product import EOProduct


class AssetsDict(UserDict):
    """A UserDict object listing assets contained in a
    :class:`~eodag.api.product._product.EOProduct` resulting from a search.

    :param product: Product resulting from a search
    :type product: :class:`~eodag.api.product._product.EOProduct`
    :param args: (optional) Arguments used to init the dictionary
    :type args: Any
    :param kwargs: (optional) Additional named-arguments used to init the dictionary
    :type kwargs: Any
    """

    product: EOProduct

    def __init__(self, product: EOProduct, *args: Any, **kwargs: Any) -> None:
        self.product = product
        super(AssetsDict, self).__init__(*args, **kwargs)

    def __setitem__(self, key: str, value: Dict[str, Any]) -> None:
        super().__setitem__(key, Asset(self.product, key, value))

    def as_dict(self) -> Dict[str, Any]:
        """Builds a representation of AssetsDict to enable its serialization

        :returns: The representation of a :class:`~eodag.api.product._assets.AssetsDict`
                  as a Python dict
        :rtype: dict
        """
        return {k: v.as_dict() for k, v in self.data.items()}

    def get_values(self, asset_filter: str = "") -> List[Asset]:
        """
        retrieves the assets matching the given filter
        :param asset_filter: filter with which the assets should be matched
        :type asset_filter: str
        :return: list of assets
        :rtype: List[Asset]
        """
        if asset_filter:
            filter_regex = re.compile(asset_filter)
            assets_keys = self.keys()
            assets_keys = list(filter(filter_regex.fullmatch, assets_keys))
            filtered_assets = {}
            if len(assets_keys) > 0:
                filtered_assets = {a_key: self.get(a_key) for a_key in assets_keys}
            assets_values = [a for a in filtered_assets.values() if "href" in a]
            if not assets_values:
                raise NotAvailableError(
                    rf"No asset key matching re.fullmatch(r'{asset_filter}') was found in {self.product}"
                )
            else:
                return assets_values
        else:
            return [a for a in self.values() if "href" in a]


class Asset(UserDict):
    """A UserDict object containg one of the assets of a
    :class:`~eodag.api.product._product.EOProduct` resulting from a search.

    :param product: Product resulting from a search
    :type product: :class:`~eodag.api.product._product.EOProduct`
    :param key: asset key
    :type key: str
    :param args: (optional) Arguments used to init the dictionary
    :type args: Any
    :param kwargs: (optional) Additional named-arguments used to init the dictionary
    :type kwargs: Any
    """

    product: EOProduct

    def __init__(self, product: EOProduct, key: str, *args: Any, **kwargs: Any) -> None:
        self.product = product
        self.key = key
        super(Asset, self).__init__(*args, **kwargs)

    def as_dict(self) -> Dict[str, Any]:
        """Builds a representation of Asset to enable its serialization

        :returns: The representation of a :class:`~eodag.api.product._assets.Asset` as a
                  Python dict
        :rtype: dict
        """
        return self.data

    def download(self, **kwargs: Any) -> str:
        """Downloads a single asset

        :param kwargs: (optional) Additional named-arguments passed to `plugin.download()`
        :type kwargs: Any
        :returns: The absolute path to the downloaded product on the local filesystem
        :rtype: str
        """
        return self.product.download(asset=self.key, **kwargs)
