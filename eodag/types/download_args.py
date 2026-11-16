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

from typing_extensions import TypedDict


class DownloadConf(TypedDict, total=False):
    """Download configuration

    :cvar output_dir: where to store downloaded products, as an absolute file path
                         (Default: local temporary directory)
    :cvar output_extension: downloaded file extension
    :cvar extract: whether to extract the downloaded products, only applies to archived products
    :cvar dl_url_params: additional parameters to pass over to the download url as an url parameter
    :cvar delete_archive: whether to delete the downloaded archives
    :cvar asset: regex filter to identify assets to download
    :cvar roles: only download the assets having at least one of these roles
                 (combined with ``asset``: an asset must match both)
    """

    output_dir: str
    output_extension: str | None
    extract: bool
    dl_url_params: dict[str, str]
    delete_archive: bool
    asset: str | None
    roles: list[str] | None
