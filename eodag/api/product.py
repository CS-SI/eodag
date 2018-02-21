# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

import copy
import logging


logger = logging.getLogger('eodag.api.product')


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

    def as_dict(self):
        """Builds a representation of EOProduct as a dictionary to enable its geojson serialization"""
        try:
            from geojson import Feature
            Feature(**self.original_repr)
        except Exception as e:
            logger.warning('Original representation of %s is not a geojson: %s', self, e)
            return {'type': 'Feature', 'coordinates': (0.0, 0.0)}
        else:
            geojson_repr = {key: value for key, value in self.original_repr.items()}
            geojson_repr['properties']['eodag_producer'] = self.producer
            geojson_repr['properties']['eodag_location_url_template'] = self.location_url_tpl
            geojson_repr['properties']['eodag_local_filename'] = self.local_filename
            return geojson_repr

    @staticmethod
    def from_geojson(feature):
        """Builds an EOProduct object from its representation as geojson"""
        orig_repr = copy.deepcopy(feature)
        obj = EOProduct(orig_repr, orig_repr['properties'].pop('eodag_producer'))
        obj.location_url_tpl = orig_repr['properties'].pop('eodag_location_url_template')
        obj.local_filename = orig_repr['properties'].pop('eodag_local_filename')
        obj.id = orig_repr['properties'].get('eodag_local_filename')
        return obj

    # Implementation of geo-interface protocol (See https://gist.github.com/sgillies/2217756)
    __geo_interface__ = property(as_dict)

    def __repr__(self):
        return '{}(id={}, producer={})'.format(self.__class__.__name__, self.id, self.producer)
