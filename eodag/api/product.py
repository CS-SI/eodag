# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

import logging

from shapely import geometry
from shapely.errors import TopologicalError


logger = logging.getLogger('eodag.api.product')
EOPRODUCT_PROPERTIES = (
    'centroid', 'cloudCover', 'description', 'keywords', 'organisationName', 'resolution', 'snowCover', 'startDate',
    'endDate', 'title', 'productIdentifier',
)


class EOProduct(object):
    """A wrapper around a search result.

    Every Search plugin instance should build an instance of this class for each of the result of its query method, and
    return a list made up of a list of such instances, providing a uniform object on which the other plugins can work.
    Note that EOProduct stores geometries in WGS84 CRS (EPSG:4326), as it is intended to be transmitted as geojson
    between applications and geojson spec enforces this (see: https://github.com/geojson/draft-geojson/pull/6)
    """

    def __init__(self, id, producer, download_url, local_filename, geom, bbox_or_intersect, **kwargs):
        """Initializes an EOProduct.

        remote_repr is assumed to be a geojson
        """
        self.location_url_tpl = download_url
        self.local_filename = local_filename
        self.id = id
        self.producer = producer
        self.geometry = geom
        if bbox_or_intersect:
            # Handle the case where we initialize EOProduct from a geojson representation of another EOProduct
            # (bbox_or_intersect is a geometry representing the intersection of the extent covered by the product and
            # the extent requested in the search)
            if 'type' in bbox_or_intersect and 'coordinates' in bbox_or_intersect:
                self.search_intersection = geometry.asShape(bbox_or_intersect)
            else:
                minx, miny = bbox_or_intersect['lonmin'], bbox_or_intersect['latmin']
                maxx, maxy = bbox_or_intersect['lonmax'], bbox_or_intersect['latmax']
                requested_geom = geometry.box(minx, miny, maxx, maxy)
                try:
                    self.search_intersection = geom.intersection(requested_geom)
                except TopologicalError as e:
                    # TODO before finding a good way to handle this, just ignore the error
                    logger.warning('Unable to intersect the requested geometry: %s with the geometry: %s. Cause: %s',
                                   requested_geom, geom, e)
                    self.search_intersection = None
        # If There was no extent requested, store the product geometry as its "intersection" with a fictional search
        # extent
        else:
            self.search_intersection = geom
        self.properties = {
            prop_key: kwargs.get(prop_key)
            for prop_key in EOPRODUCT_PROPERTIES
        }
        # This allows plugin developers to add their own properties to the EOProduct object
        self.properties.update(kwargs)

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
                'eodag_search_intersection': self.search_intersection,
            }
        }
        geojson_repr['properties'].update(self.properties)
        return geojson_repr

    @classmethod
    def from_geojson(cls, feature):
        """Builds an EOProduct object from its representation as geojson"""
        return cls(
            feature['id'],
            feature['properties']['eodag_producer'],
            feature['properties']['eodag_download_url'],
            feature['properties']['eodag_local_name'],
            feature['geometry'],
            feature['properties']['eodag_search_intersection'],
            **feature['properties']
        )

    # Implementation of geo-interface protocol (See https://gist.github.com/sgillies/2217756)
    __geo_interface__ = property(as_dict)

    def __repr__(self):
        return '{}(id={}, producer={})'.format(self.__class__.__name__, self.id, self.producer)
