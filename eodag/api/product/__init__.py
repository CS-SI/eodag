# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

import logging

import numpy
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from shapely import geometry
from shapely.errors import TopologicalError

from eodag.api.product.drivers import DRIVERS


logger = logging.getLogger('eodag.api.product')
EOPRODUCT_PROPERTIES = (
    'centroid', 'cloudCover', 'description', 'keywords', 'organisationName', 'resolution', 'snowCover', 'startDate',
    'endDate', 'title', 'productIdentifier', 'orbitNumber'
)


class EOProduct(object):
    """A wrapper around an Earth Observation Product originating from a search.

    Every Search plugin instance should build an instance of this class for each of the result of its query method, and
    return a list made up of a list of such instances, providing a uniform object on which the other plugins can work.
    Note that EOProduct stores geometries in WGS84 CRS (EPSG:4326), as it is intended to be transmitted as geojson
    between applications and geojson spec enforces this (see: https://github.com/geojson/draft-geojson/pull/6)
    """

    def __init__(self, id, producer, download_url, local_filename, geom, bbox_or_intersect, product_type, platform,
                 instrument, **kwargs):
        """Initializes an EOProduct"""
        self.location_url_tpl = download_url
        self.local_filename = local_filename
        self.id = id
        self.producer = producer
        self.geometry = geom
        self.product_type = product_type
        self.sensing_platform = platform
        self.sensor = instrument
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
        self.driver = DRIVERS[
            (self.sensing_platform, self.sensor)
        ]()

    def get_subdataset(self, crs, resolution, band, extent):
        """Retrieves all or part of the raster data abstracted by self.

        :param crs: The coordinate reference system in which the dataset should be returned
        :type crs: str
        :param resolution: The resolution in which the dataset should be returned (given in the unit of the crs)
        :type resolution: float
        :param band: The band of the dataset to retrieve (e.g.: 'B01')
        :type band: str
        :param extent: The coordinates on which to zoom as a tuple (min_x, min_y, max_x, max_y) in the given
                       :param:`crs`
        :type extent: (float, float, float, float)
        :returns: The numeric matrix corresponding to the sub dataset
        :rtype: numpy.ndarray
        """
        dataset_address = self.driver.get_dataset_address(self, band)
        min_x, min_y, max_x, max_y = extent
        height = int((max_y - min_y) / resolution)
        width = int((max_x - min_x) / resolution)
        out_shape = (width, height)
        with rasterio.open(dataset_address) as src:
            with WarpedVRT(src, dst_crs=crs, resampling=Resampling.bilinear) as vrt:
                return vrt.read(1, window=vrt.window(*extent), out_shape=out_shape, resampling=Resampling.bilinear)

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
                'productType': self.product_type,
                'platform': self.sensing_platform,
                'instrument': self.sensor,
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
            feature['properties']['productType'],
            feature['properties']['platform'],
            feature['properties']['instrument'],
            **feature['properties']
        )

    # Implementation of geo-interface protocol (See https://gist.github.com/sgillies/2217756)
    __geo_interface__ = property(as_dict)

    def __repr__(self):
        return '{}(id={}, producer={})'.format(self.__class__.__name__, self.id, self.producer)

    def encode(self, raster, encoding='protobuf'):
        """Encode the subset to a network-compatible format.

        :param raster: The raster data to encode
        :type raster: numpy.ndarray
        :param encoding: The encoding of the export
        :type encoding: str
        :return: The data encoded in the specified encoding
        :rtype: bytes
        """
        # If no encoding return an empty byte
        if not encoding:
            return b''
        return getattr(self, '__{encoding}'.format(**locals()), None)(raster)

    def __protobuf(self, raster):
        """Google's Protocol buffers encoding strategy.

        :param raster: The raster to encode
        :type raster: numpy.ndarray
        :returns: The raster data represented by this subset in protocol buffers encoding
        :rtype: bytes
        """
