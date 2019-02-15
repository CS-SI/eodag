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

import re
from datetime import datetime
from string import Formatter

from dateutil.tz import tzutc
from shapely import geometry

from eodag.utils import get_timestamp


SEP = r'#'
INGEST_CONVERSION_REGEX = re.compile(r'^{(?P<path>[^#]*)' + SEP + r'(?P<converter>[^\d\W]\w*)}$')


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
    :class:`~eodag.plugins.search.base.Search` plugin implemented by `provider`, and is used when eodag delegates
    search process to the corresponding plugin.

    :param map_value: The value originating from the definition of `metadata_mapping` in the provider search config.
        For example, it is the list `['productType', '$.properties.productType']` with the sample above
    :type map_value: str (Python 3) or unicode (Python 2) or list(str or unicode)
    :return: The value of the path to the metadata value in the provider search result
    :rtype: str (Python 3) or unicode (Python 2)
    """
    path = map_value[1] if isinstance(map_value, list) else map_value
    match = INGEST_CONVERSION_REGEX.match(path)
    if match:
        g = match.groupdict()
        return g['converter'], g['path']
    return None, path


def get_search_param(map_value):
    """See :func:`~eodag.utils.metadata_mapping.get_metadata_path`

    :param map_value: The value originating from the definition of `metadata_mapping` in the provider search config
    :type map_value: list
    :return: The value of the search parameter as defined in the provider config
    :rtype: str (Python 3) or unicode (Python 2)
    """
    # Assume that caller will pass in the value as a list
    return map_value[0]


def format_metadata(search_param, *args, **kwargs):
    """Format a string of form {<field_name>#<conversion_function>}

    The currently understood converters are:
        - to_timestamp_milliseconds: converts a utc date string to a timestamp in milliseconds
        - to_wkt: converts a geometry to its well known text representation
        - to_iso_utc_datetime_from_milliseconds: converts a utc timestamp in given milliseconds to a utc iso datetime

    :param search_param: The string to be formatted
    :type search_param: str or unicode
    :param args: (optional) Additional arguments to use in the formatting process
    :type args: tuple
    :param kwargs: (optional) Additional named-arguments to use in the formatting process
    :type kwargs: dict
    :returns: The formatted string
    :rtype: str or unicode
    """

    class MetadataFormatter(Formatter):
        CONVERSION_REGEX = re.compile(r'^(?P<field_name>.+)' + SEP + r'(?P<converter>[^\d\W]\w*)$')

        def __init__(self):
            self.custom_converter = None

        def get_field(self, field_name, args, kwargs):
            conversion_func_spec = self.CONVERSION_REGEX.match(field_name)
            # Register a custom converter if any for later use (see convert_field)
            # This is done because we don't have the value associated to field_name at this stage
            if conversion_func_spec:
                field_name = conversion_func_spec.groupdict()['field_name']
                converter = conversion_func_spec.groupdict()['converter']
                self.custom_converter = getattr(self, 'convert_{}'.format(converter))
            return super(MetadataFormatter, self).get_field(field_name, args, kwargs)

        def convert_field(self, value, conversion):
            # Do custom conversion if any (see get_field)
            if self.custom_converter is not None:
                converted = self.custom_converter(value) if value is not None else ''
                # Clear this state variable in case the same converter is used to resolve other named arguments
                self.custom_converter = None
                return converted
            return super(MetadataFormatter, self).convert_field(value, conversion)

        @staticmethod
        def convert_to_timestamp_milliseconds(value):
            return int(1e3 * get_timestamp(value))

        @staticmethod
        def convert_to_wkt(value):
            return geometry.box(*[
                float(v) for v in '{lonmin} {latmin} {lonmax} {latmax}'.format(**value).split()
            ]).to_wkt()

        @staticmethod
        def convert_to_iso_utc_datetime_from_milliseconds(timestamp):
            return datetime.fromtimestamp(timestamp / 1e3, tzutc()).isoformat()

        @staticmethod
        def convert_to_iso_utc_datetime(date_string):
            return datetime.strptime(date_string, '%Y-%m-%d').replace(
                tzinfo=tzutc()).isoformat().replace('+00:00', 'Z')

    return MetadataFormatter().vformat(search_param, args, kwargs)
