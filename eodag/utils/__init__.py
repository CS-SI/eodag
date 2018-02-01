# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
import types

import click
from requests.auth import AuthBase


class RequestsTokenAuth(AuthBase):
    def __init__(self, token):
        if isinstance(token, str):
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


def maybe_generator(obj):
    """Generator function that get an arbitrary object and generate values from it if the object is a generator."""
    if isinstance(obj, types.GeneratorType):
        for elt in obj:
            yield elt
    else:
        yield obj

