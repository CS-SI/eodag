# -*- coding: utf-8 -*-
# Copyright 2025, CS GROUP - France, https://www.csgroup.eu/
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
from collections import UserDict
from textwrap import shorten
from typing import TYPE_CHECKING, Any, Optional

from eodag.config import ProviderConfig
from eodag.utils.exceptions import UnsupportedProvider
from eodag.utils.repr import dict_to_html_table, str_as_href

if TYPE_CHECKING:
    pass

logger = logging.getLogger("eodag.provider")


class Provider:
    """
    Represents a data provider with its configuration and utility methods.

    :param config: Provider configuration as :meth:`~eodag.api.provider.ProviderConfig` instance or :class:`dict`
    :param collections_fetched: Flag indicating whether collections have been fetched

    Example
    -------

    >>> from eodag.api.provider import Provider
    >>> config = {
    ...     'name': 'example_provider',
    ...     'description': 'Example provider for testing',
    ...     'search': {'type': 'StacSearch'},
    ...     'products': {'S2_MSI_L1C': {'_collection': 'S2_MSI_L1C'}}
    ... }
    >>> provider = Provider(config)
    >>> provider.name
    'example_provider'
    >>> 'S2_MSI_L1C' in provider.collections_config
    True
    >>> provider.priority  # Default priority
    0
    """

    name: str
    priority: int
    enabled: bool
    metadata: dict[str, Any]

    def __init__(
        self, name: str, priority: int, enabled: bool, metadata: dict[str, Any]
    ):
        self._name = name
        self.priority = priority
        self.enabled = enabled
        self.metadata = metadata

    def __str__(self) -> str:
        """Return the provider's name as string."""
        return self.name

    def __repr__(self) -> str:
        """Return a string representation of the Provider."""
        return f"Provider('{self.name}')"

    def __eq__(self, other: object):
        """Compare providers by name or with a string."""
        if isinstance(other, Provider):
            return self.name == other.name

        elif isinstance(other, str):
            return self.name == other

        return False

    def __hash__(self):
        """Hash based on provider name, for use in sets/dicts."""
        return hash(self.name)

    def _repr_html_(self, embedded: bool = False) -> str:
        """HTML representation for Jupyter/IPython display."""
        group_display = f" ({group})" if (group := self.group) else ""
        thead = (
            f"""<thead><tr><td style='text-align: left; color: grey;'>
                {type(self).__name__}("<span style='color: black'>{self.name}{group_display}</span>")</td></tr></thead>
            """
            if not embedded
            else ""
        )
        tr_style = "style='background-color: transparent;'" if embedded else ""

        summaries = {
            "name": self.name,
            "title": self.title,
            "url": self.url,
            "priority": self.priority,
        }
        if group := self.group:
            summaries["group"] = group

        col_html_table = dict_to_html_table(summaries, depth=1, brackets=False)

        return (
            f"<table>{thead}<tbody>"
            f"<tr {tr_style}><td style='text-align: left;'>"
            f"{col_html_table}</td></tr>"
            "</tbody></table>"
        )

    @property
    def title(self) -> Optional[str]:
        """The title of the provider."""
        return self.metadata.get("description", None)

    @property
    def url(self) -> Optional[str]:
        """The url of the provider."""
        return self.metadata.get("url", None)

    @property
    def group(self) -> Optional[str]:
        """Return the provider's group, if any."""
        return self.metadata.get("group", None)


class ProvidersDict(UserDict[str, Provider]):
    """
    A dictionary-like collection of :class:`~eodag.api.provider.Provider` objects, keyed by provider name.

    :param providers: Initial providers to populate the dictionary.
    """

    def __contains__(self, item: object) -> bool:
        """
        Check if a provider is in the dictionary by name or :class:`~eodag.api.provider.Provider` instance.

        :param item: Provider name or Provider instance to check.
        :return: True if the provider is in the dictionary, False otherwise.
        """
        if isinstance(item, Provider):
            return item.name in self.data
        return item in self.data

    def __setitem__(self, key: str, value: Provider) -> None:
        """
        Add a :class:`~eodag.api.provider.Provider` to the dictionary.

        :param key: The name of the provider.
        :param value: The Provider instance to add.
        :raises ValueError: If the provider key already exists.
        """
        if key in self.data:
            msg = f"Provider '{key}' already exists."
            raise ValueError(msg)
        super().__setitem__(key, value)

    def __delitem__(self, key: str) -> None:
        """
        Delete a provider by name.

        :param key: The name of the provider to delete.
        :raises UnsupportedProvider: If the provider key is not found.
        """
        if key not in self.data:
            msg = f"Provider '{key}' not found."
            raise UnsupportedProvider(msg)
        super().__delitem__(key)

    def __repr__(self) -> str:
        """
        String representation of :class:`~eodag.api.provider.ProvidersDict`.

        :return: String listing provider names.
        """
        return f"ProvidersDict({list(self.data.keys())})"

    def _repr_html_(self, embeded=False) -> str:
        """
        HTML representation for Jupyter/IPython display.

        :return: HTML string representation of the :class:`~eodag.api.provider.ProvidersDict`.
        """
        longest_name = max([len(k) for k in self.keys()])
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
                    <span style='color: black; font-family: monospace;'>{k}:{'&nbsp;' * (longest_name - len(k))}</span>
                    Provider(
                        {"'priority': '<span style='color: black'>" + str(v.priority) + "</span>',&ensp;"
                         if v.priority is not None else ""}
                        {"'title': '<span style='color: black'>"
                         + shorten(v.title, width=70, placeholder="[...]") + "</span>',&ensp;"
                         if v.title else ""}
                        {"'url': '" + str_as_href(v.url) + "'" if v.url else ""}
                    )
                </summary>
                    {v._repr_html_(embedded=True)}
                </details>
                </td></tr>
                """
                    for k, v in self.items()
                ]
            )
            + "</table>"
        )

    @property
    def names(self) -> list[str]:
        """
        List of provider names.

        :return: List of provider names.
        """
        return [provider.name for provider in self.data.values()]

    @property
    def groups(self) -> list[str]:
        """
        List of provider groups if exist or names.

        :return: List of provider groups if exist or names.
        """
        return list(
            set(provider.group or provider.name for provider in self.data.values())
        )

    @property
    def configs(self) -> dict[str, ProviderConfig]:
        """
        Dictionary of provider configs keyed by provider name.

        :return: Dictionary mapping provider name to :class:`~eodag.api.provider.ProviderConfig`.
        """
        return {provider.name: provider.config for provider in self.data.values()}

    @property
    def priorities(self) -> dict[str, int]:
        """
        Dictionary of provider priorities keyed by provider name.

        :return: Dictionary mapping provider name to priority integer.
        """
        return {provider.name: provider.priority for provider in self.data.values()}
