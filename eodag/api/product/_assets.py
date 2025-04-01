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
from typing import TYPE_CHECKING, Any, Optional

from eodag.utils.exceptions import NotAvailableError
from eodag.utils.repr import dict_to_html_table

if TYPE_CHECKING:
    from eodag.api.product import EOProduct
    from eodag.types.download_args import DownloadConf
    from eodag.utils import Unpack


class AssetsDict(UserDict):
    """A UserDict object which values are :class:`~eodag.api.product._assets.Asset`
    contained in a :class:`~eodag.api.product._product.EOProduct` resulting from a
    search.

    :param product: Product resulting from a search
    :param args: (optional) Arguments used to init the dictionary
    :param kwargs: (optional) Additional named-arguments used to init the dictionary

    Example
    -------

    >>> from eodag.api.product import EOProduct
    >>> product = EOProduct(
    ...     provider="foo",
    ...     properties={"id": "bar", "geometry": "POINT (0 0)"}
    ... )
    >>> type(product.assets)
    <class 'eodag.api.product._assets.AssetsDict'>
    >>> product.assets.update({"foo": {"href": "http://somewhere/something"}})
    >>> product.assets
    {'foo': {'href': 'http://somewhere/something'}}
    """

    product: EOProduct

    def __init__(self, product: EOProduct, *args: Any, **kwargs: Any) -> None:
        self.product = product
        super(AssetsDict, self).__init__(*args, **kwargs)

    def __setitem__(self, key: str, value: dict[str, Any]) -> None:
        super().__setitem__(key, Asset(self.product, key, value))

    def as_dict(self) -> dict[str, Any]:
        """Builds a representation of AssetsDict to enable its serialization

        :returns: The representation of a :class:`~eodag.api.product._assets.AssetsDict`
                  as a Python dict
        """
        return {k: v.as_dict() for k, v in self.data.items()}

    def get_values(self, asset_filter: str = "", regex=True) -> list[Asset]:
        """
        retrieves the assets matching the given filter

        :param asset_filter: regex filter with which the assets should be matched
        :param regex: Uses regex to match the asset key or simply compare strings
        :return: list of assets
        """
        if asset_filter:
            if regex:
                filter_regex = re.compile(asset_filter)
                assets_keys = list(self.keys())
                assets_keys = list(filter(filter_regex.fullmatch, assets_keys))
            else:
                assets_keys = [a for a in self.keys() if a == asset_filter]
            filtered_assets = {}
            if len(assets_keys) > 0:
                filtered_assets = {a_key: self.get(a_key) for a_key in assets_keys}
            assets_values = [a for a in filtered_assets.values() if a and "href" in a]
            if not assets_values and regex:
                # retry without regex
                return self.get_values(asset_filter, regex=False)
            elif not assets_values:
                raise NotAvailableError(
                    rf"No asset key matching re.fullmatch(r'{asset_filter}') was found in {self.product}"
                )
            else:
                return assets_values
        else:
            return [a for a in self.values() if "href" in a]

    def _repr_html_(self, embeded=False):
        thead = (
            f"""<thead><tr><td style='text-align: left; color: grey;'>
                {type(self).__name__}&ensp;({len(self)})
                </td></tr></thead>
            """
            if not embeded
            else ""
        )
        tr_style = "style='background-color: transparent;'" if embeded else ""
        return (
            f"<table>{thead}"
            + "".join(
                [
                    f"""<tr {tr_style}><td style='text-align: left;'>
                <details><summary style='color: grey;'>
                    <span style='color: black'>'{k}'</span>:&ensp;
                    {{
                        {"'roles': '<span style='color: black'>" + str(v['roles']) + "</span>',&ensp;"
                         if v.get("roles") else ""}
                        {"'type': '" + str(v['type']) + "',&ensp;"
                         if v.get("type") else ""}
                        {"'title': '<span style='color: black'>" + str(v['title']) + "</span>',&ensp;"
                         if v.get("title") else ""}
                        ...
                    }}
                </summary>
                    {dict_to_html_table(v, depth=1)}
                </details>
                </td></tr>
                """
                    for k, v in self.items()
                ]
            )
            + "</table>"
        )


class Asset(UserDict):
    """A UserDict object containg one of the
    :attr:`~eodag.api.product._product.EOProduct.assets` resulting from a search.

    :param product: Product resulting from a search
    :param key: asset key
    :param args: (optional) Arguments used to init the dictionary
    :param kwargs: (optional) Additional named-arguments used to init the dictionary

    Example
    -------

    >>> from eodag.api.product import EOProduct
    >>> product = EOProduct(
    ...     provider="foo",
    ...     properties={"id": "bar", "geometry": "POINT (0 0)"}
    ... )
    >>> product.assets.update({"foo": {"href": "http://somewhere/something"}})
    >>> type(product.assets["foo"])
    <class 'eodag.api.product._assets.Asset'>
    >>> product.assets["foo"]
    {'href': 'http://somewhere/something'}
    """

    product: EOProduct
    size: int
    filename: Optional[str]
    rel_path: str

    def __init__(self, product: EOProduct, key: str, *args: Any, **kwargs: Any) -> None:
        self.product = product
        self.key = key
        super(Asset, self).__init__(*args, **kwargs)

    def as_dict(self) -> dict[str, Any]:
        """Builds a representation of Asset to enable its serialization

        :returns: The representation of a :class:`~eodag.api.product._assets.Asset` as a
                  Python dict
        """
        return self.data

    def download(self, **kwargs: Unpack[DownloadConf]) -> str:
        """Downloads a single asset

        :param kwargs: (optional) Additional named-arguments passed to `plugin.download()`
        :returns: The absolute path to the downloaded product on the local filesystem
        """
        return self.product.download(asset=self.key, **kwargs)

    def _repr_html_(self):
        thead = f"""<thead><tr><td style='text-align: left; color: grey;'>
            {type(self).__name__}&ensp;-&ensp;{self.key}
            </td></tr></thead>
        """
        return f"""<table>{thead}
                <tr><td style='text-align: left;'>
                    {dict_to_html_table(self)}
                </details>
                </td></tr>
            </table>"""
