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
from __future__ import annotations

from eodag.plugins.download import Download
from eodag.plugins.search import Search


class Api(Search, Download):
    """Plugins API Base plugin

    An Api plugin inherits the methods from Search and Download plugins.

    There are three methods that it must implement:

    - ``query``: search for products
    - ``download``: download a single :class:`~eodag.api.product._product.EOProduct`
    - ``download_all``: download multiple products from a :class:`~eodag.api.search_result.SearchResult`

    The download methods must:

    - download data in the ``output_dir`` folder defined in the plugin's
      configuration or passed through kwargs
    - extract products from their archive (if relevant) if ``extract`` is set to ``True``
      (``True`` by default)
    - save a product in an archive/directory (in ``output_dir``) whose name must be
      the product's ``title`` property

    :param provider: An EODAG provider name
    :type provider: str
    :param config: An EODAG plugin configuration
    :type config: dict[str, Any]
    """


__all__ = ["Api"]
