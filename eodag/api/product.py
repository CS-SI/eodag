# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals


class EOProduct(object):
    """A wrapper around a search result.

    Every Search plugin instance should build an instance of this class for each of the result of its query method, and
    return a list made up of a list of such instances, providing a uniform object on which the other plugins can work.
    """

    def __init__(self, remote_repr, producer):
        self.original_repr = remote_repr
        self.location_url_tpl = None
        self.local_filename = None
        self.id = None
        self.producer = producer

    def __repr__(self):
        return '{}(id={}, producer={})'.format(self.__class__.__name__, self.id, self.producer)

