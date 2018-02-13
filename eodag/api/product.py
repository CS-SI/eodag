# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved


class EOProduct(object):
    """A wrapper around a search result.

    Every Search plugin instance should build an instance of this class for each of the result of its query method, and
    return a list made up of a list of such instances, providing a uniform object on which the other plugins can work.
    """

    def __init__(self, remote_repr):
        self.original_repr = remote_repr
        self.location_url_tpl = None
        self.local_filename = None
        self.id = None

    def __repr__(self):
        return self.id

