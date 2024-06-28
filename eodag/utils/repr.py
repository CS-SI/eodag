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
from typing import Any, Optional
from urllib.parse import urlparse


def str_as_href(link: str) -> str:
    """URL to html link"""
    if urlparse(link).scheme in ("file", "http", "https", "s3"):
        return f"<a href='{link}' target='_blank'>{link}</a>"
    else:
        return link


def html_table(input: Any, depth: Optional[int] = None) -> str:
    """Transform input to HTML table"""
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
    """Transform input dict to HTML table"""
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
    """Transform input list to HTML table"""
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
