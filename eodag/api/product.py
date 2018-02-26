# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

import logging

from shapely import geometry


logger = logging.getLogger('eodag.api.product')


class EOProduct(object):
    """A wrapper around a search result.

    Every Search plugin instance should build an instance of this class for each of the result of its query method, and
    return a list made up of a list of such instances, providing a uniform object on which the other plugins can work.
    """

    def __init__(self, remote_repr, id, producer, download_url, local_filename, geom, search_bbox=None, **kwargs):
        """Initializes an EOProduct.

        remote_repr is assumed to be a geojson
        """
        self.original_repr = remote_repr
        self.location_url_tpl = download_url
        self.local_filename = local_filename
        self.id = id
        self.producer = producer
        self.geometry = geom
        if search_bbox:
            minx, miny = search_bbox['lonmin'], search_bbox['latmin']
            maxx, maxy = search_bbox['lonmax'], search_bbox['latmax']
            requested_geom = geometry.box(*(minx, miny, maxx, maxy))
            self.search_intersection = geom.intersection(requested_geom)
        else:
            self.search_intersection = geom
        self.properties = {
            key: value
            for key, value in kwargs.items()
        }

    def as_dict(self):
        """Builds a representation of EOProduct as a dictionary to enable its geojson serialization"""
        geojson_repr = {
            'type': 'Feature',
            'id': self.id,
            'geometry': self.geometry,
            'properties': {
                'eodag_producer': self.producer,
                'eodag_download_url': self.location_url_tpl,
                'eodag_local_name': self.local_filename,
            }
        }
        geojson_repr['properties'].update(self.properties)
        return geojson_repr

    @staticmethod
    def from_geojson(feature):
        """Builds an EOProduct object from its representation as geojson"""
        return EOProduct(
            feature,
            feature['id'],
            feature['properties']['eodag_producer'],
            feature['properties']['eodag_download_url'],
            feature['properties']['eodag_local_name'],
            feature['geometry']
        )

    # Implementation of geo-interface protocol (See https://gist.github.com/sgillies/2217756)
    __geo_interface__ = property(as_dict)

    def __repr__(self):
        return '{}(id={}, producer={})'.format(self.__class__.__name__, self.id, self.producer)
