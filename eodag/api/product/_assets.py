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
from collections import UserDict


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

    def __init__(self, product, *args, **kwargs):
        self.product = product
        super(AssetsDict, self).__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        super().__setitem__(key, Asset(self.product, key, value))

    def as_dict(self):
        """Builds a representation of AssetsDict to enable its serialization

        :returns: The representation of a :class:`~eodag.api.product._assets.AssetsDict`
                  as a Python dict
        :rtype: dict
        """
        return {k: v.as_dict() for k, v in self.data.items()}


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

    def __init__(self, product, key, *args, **kwargs):
        self.product = product
        self.key = key
        super(Asset, self).__init__(*args, **kwargs)

    def as_dict(self):
        """Builds a representation of Asset to enable its serialization

        :returns: The representation of a :class:`~eodag.api.product._assets.Asset` as a
                  Python dict
        :rtype: dict
        """
        return self.data

    def download(self, **kwargs):
        """Downloads a single asset

        :param kwargs: (optional) Additional named-arguments passed to `plugin.download()`
        :type kwargs: Any
        """
        return self.product.download(asset=self.key, **kwargs)
