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
import sys
import types
import unicodedata
from datetime import datetime

import click
import pyproj
from requests.auth import AuthBase
from six import string_types

# All modules using these should import them from utils package
try:  # PY3
    from urllib.parse import urljoin, urlparse      # noqa
except ImportError:  # PY2
    from urlparse import urljoin, urlparse          # noqa


class RequestsTokenAuth(AuthBase):
    def __init__(self, token):
        if isinstance(token, string_types):
            self.token = token
        elif isinstance(token, dict):
            self.token = token.get('tokenIdentity', '')
        self.bearer_str = "Bearer {}".format(self.token)

    def __call__(self, req):
        req.headers['Authorization'] = self.bearer_str
        return req


class FloatRange(click.types.FloatParamType):
    """A parameter that works similar to :data:`click.FLOAT` but restricts the value to fit into a range. Fails if the
    value doesn't fit into the range.
    """
    name = 'percentage'

    def __init__(self, min=None, max=None):
        self.min = min
        self.max = max

    def convert(self, value, param, ctx):
        rv = click.types.FloatParamType.convert(self, value, param, ctx)
        if self.min is not None and rv < self.min or \
                self.max is not None and rv > self.max:
            if self.min is None:
                self.fail('%s is bigger than the maximum valid value '
                          '%s.' % (rv, self.max), param, ctx)
            elif self.max is None:
                self.fail('%s is smaller than the minimum valid value '
                          '%s.' % (rv, self.min), param, ctx)
            else:
                self.fail('%s is not in the valid range of %s to %s.'
                          % (rv, self.min, self.max), param, ctx)
        return rv

    def __repr__(self):
        return 'FloatRange(%r, %r)' % (self.min, self.max)


def slugify(value, allow_unicode=False):
    """Copied from Django Source code, only modifying last line (no need for safe strings).
    source: https://github.com/django/django/blob/master/django/utils/text.py

    Convert to ASCII if 'allow_unicode' is False. Convert spaces to hyphens.
    Remove characters that aren't alphanumerics, underscores, or hyphens.
    Convert to lowercase. Also strip leading and trailing whitespace.
    """
    try:  # PY2
        value = unicode(value)
    except NameError:  # PY3
        value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[-\s]+', '-', value)


def utf8_everywhere(mapping):
    """Recursively transforms all string found in the dict mapping to UTF-8 if we are on Python 2"""
    mutate_dict_in_place((
        lambda value:
        value.decode('utf-8')
        if isinstance(value, str) and sys.version_info.major == 2 and sys.version_info.minor == 7
        else value),
        mapping
    )


def mutate_dict_in_place(func, mapping):
    """Apply func to values of mapping.

    The mapping object's values are modified in-place. The function is recursive, allowing to also modify values of
    nested dicts that may be level-1 values of mapping.

    :param func: A function to apply to each value of mapping which is not a dict object
    :type func: func
    :param mapping: A Python dict object
    :type mapping: dict
    :returns: None
    """
    for key, value in mapping.items():
        if isinstance(value, dict):
            mutate_dict_in_place(func, value)
        else:
            mapping[key] = func(value)


def maybe_generator(obj):
    """Generator function that get an arbitrary object and generate values from it if the object is a generator."""
    if isinstance(obj, types.GeneratorType):
        for elt in obj:
            yield elt
    else:
        yield obj


DEFAULT_PROJ = pyproj.Proj(init='EPSG:4326')


def get_timestamp(date_time, date_format='%Y-%m-%d'):
    """Returns the given date_time string formatted with date_format as timestamp, in a PY2/3 compatible way

    :param date_time: the datetime string to return as timestamp
    :type date_time: str or unicode
    :param date_format: (optional) the date format in which date_time is given, defaults to '%Y-%m-%d'
    :type date_format: str or unicode
    :returns: the timestamp corresponding to the date_time string in seconds
    :rtype: float
    """
    date_time = datetime.strptime(date_time, date_format)
    try:
        return date_time.timestamp()
    except AttributeError:  # There is no timestamp method on datetime objects in Python 2
        import time
        return time.mktime(date_time.timetuple()) + date_time.microsecond / 1e6
