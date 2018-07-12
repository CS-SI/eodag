# -*- coding: utf-8 -*-
# Copyright 2018, CS Systemes d'Information, http://www.c-s.fr
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
from __future__ import unicode_literals


def get_metadata_path(map_value):
    """Return the jsonpath or xpath to the value of a EO product metadata in a provider search result.

    The path is retrieved depending on if the metadata is queryable (the value associated to it in the provider search
    config metadata mapping is a list) or not (the value is directly the string corresponding to the path).

    Assume we have the following provider config::

        provider:
            ...
            search:
                ...
                metadata_mapping:
                    productType:
                        - productType
                        - $.properties.productType
                    id: $.properties.id
                    ...
                ...
            ...

    Then the metadata `id` is not queryable for this provider meanwhile `productType` is queryable. The first value of
    the `metadata_mapping.productType` is how the eodag search parameter `productType` is interpreted in the
    :class:`~eodag.plugins.search.base.Search` plugin implemented by `provider`, and is used when eodag delegates search
    process to the corresponding plugin.

    :param map_value: The value originating from the definition of `metadata_mapping` in the provider search config. For
        example, it is the list `['productType', '$.properties.productType']` with the sample above
    :type map_value: str (Python 3) or unicode (Python 2) or list(str or unicode)
    :return: The value of the path to the metadata value in the provider search result
    :rtype: str (Python 3) or unicode (Python 2)
    """
    if isinstance(map_value, list):
        path = map_value[1]
    else:
        path = map_value
    return path


def get_search_param(map_value):
    """See :func:`~eodag.utils.metadata_mapping.get_metadata_path`

    :param map_value: The value originating from the definition of `metadata_mapping` in the provider search config
    :type map_value: list
    :return: The value of the search parameter as defined in the provider config
    :rtype: str (Python 3) or unicode (Python 2)
    """
    # Assume that caller will pass in the value as a list
    return map_value[0]
