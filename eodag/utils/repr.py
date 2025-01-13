# -*- coding: utf-8 -*-
# Copyright 2024, CS GROUP - France, https://www.csgroup.eu/
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

import collections.abc
import re
from typing import Any, Optional
from urllib.parse import urlparse


def str_as_href(link: str) -> str:
    """URL to html link

    :param link: URL to format
    :returns: HMLT formatted link

    >>> str_as_href("http://foo.bar")
    "<a href='http://foo.bar' target='_blank'>http://foo.bar</a>"

    """
    if urlparse(link).scheme in ("file", "http", "https", "s3"):
        return f"<a href='{link}' target='_blank'>{link}</a>"
    else:
        return link


def html_table(input: Any, depth: Optional[int] = None) -> str:
    """Transform input object to HTML table

    :param input: input object to represent
    :param depth: maximum depth level until which nested objects should be represented
                  in new tables (unlimited by default)
    :returns: HTML table
    """
    if isinstance(input, collections.abc.Mapping):
        return dict_to_html_table(input, depth=depth)
    elif isinstance(input, collections.abc.Sequence) and not isinstance(input, str):
        return list_to_html_table(input, depth=depth)
    elif isinstance(input, str):
        return f"'{str_as_href(input)}'"
    else:
        return str_as_href(str(input))


def dict_to_html_table(
    input_dict: collections.abc.Mapping,
    depth: Optional[int] = None,
    brackets: bool = True,
) -> str:
    """Transform input dict to HTML table

    :param input_dict: input dict to represent
    :param depth: maximum depth level until which nested objects should be represented
                  in new tables (unlimited by default)
    :param brackets: whether surrounding brackets should be displayed or not
    :returns: HTML table
    """
    opening_bracket = "<span style='color: grey;'>{</span>" if brackets else ""
    closing_bracket = "<span style='color: grey;'>}</span>" if brackets else ""
    indent = "10px" if brackets else "0"

    if depth is not None:
        depth -= 1

    if depth is None or depth >= 0:
        return (
            f"{opening_bracket}<table style='margin: 0;'>"
            + "".join(
                [
                    f"""<tr style='background-color: transparent;'>
                    <td style='padding: 5px 0 0 {indent}; text-align: left; color: grey; vertical-align:top;'>{k}:</td>
                    <td style='padding: 5px 0 0 10px; text-align: left;'>{
                        html_table(v, depth=depth)
                    },</td>
                </tr>
                """
                    for k, v in input_dict.items()
                ]
            )
            + f"</table>{closing_bracket}"
        )
    else:
        return (
            f"{opening_bracket}"
            + ", ".join(
                [
                    f"""<span style='text-align: left;'>
                    '{k}': {html_table(v, depth=depth)}
                </span>"""
                    for k, v in input_dict.items()
                ]
            )
            + f"{closing_bracket}"
        )


def list_to_html_table(
    input_list: collections.abc.Sequence, depth: Optional[int] = None
) -> str:
    """Transform input list to HTML table

    :param input_list: input list to represent
    :param depth: maximum depth level until which nested objects should be represented
                  in new tables (unlimited by default)
    :returns: HTML table
    """
    if depth is not None:
        depth -= 1
    separator = (
        ",<br />"
        if any(isinstance(v, collections.abc.Mapping) for v in input_list)
        else ", "
    )
    return (
        "<span style='color: grey;'>[</span>"
        + separator.join(
            [
                f"""<span style='text-align: left;'>{
                    html_table(v, depth=depth)
                }</span>
            """
                for v in input_list
            ]
        )
        + "<span style='color: grey;'>]</span>"
    )


def remove_class_repr(type_repr: str) -> str:
    """Removes class tag from type representation

    :param type_repr: input type representation
    :returns: type without class tag

    >>> remove_class_repr(str(type("foo")))
    'str'
    """
    return re.sub(r"<class '(\w+)'>", r"\1", type_repr)


def shorter_type_repr(long_type: str) -> str:
    """Shorten long type representation

    :param long_type: long type representation
    :returns: type reprensentation shortened

    >>> import typing
    >>> shorter_type_repr(str(typing.Literal["foo", "bar"]))
    "Literal['foo', ...]"
    """
    # shorten lists
    shorter = re.sub(r",[^\[^\]]+\]", ", ...]", str(long_type))
    # remove class prefix
    shorter = remove_class_repr(shorter)
    # remove parent objects
    shorter = re.sub(r"\w+\.", "", shorter)
    return shorter
