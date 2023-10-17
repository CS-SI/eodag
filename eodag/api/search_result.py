# -*- coding: utf-8 -*-
# Copyright 2018, CS GROUP - France, https://www.csgroup.eu/
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
from __future__ import annotations

from collections import UserList
from typing import Any, Dict, List, Optional, Union

from shapely.geometry import GeometryCollection, shape
from shapely.geometry.base import BaseGeometry

from eodag.api.product import EOProduct
from eodag.plugins.crunch.base import Crunch
from eodag.plugins.crunch.filter_date import FilterDate
from eodag.plugins.crunch.filter_latest_intersect import FilterLatestIntersect
from eodag.plugins.crunch.filter_latest_tpl_name import FilterLatestByName
from eodag.plugins.crunch.filter_overlap import FilterOverlap
from eodag.plugins.crunch.filter_property import FilterProperty


class SearchResult(UserList[EOProduct]):
    """An object representing a collection of :class:`~eodag.api.product._product.EOProduct` resulting from a search.

    :param products: A list of products resulting from a search
    :type products: list(:class:`~eodag.api.product._product.EOProduct`)
    """

    products: List[EOProduct]

    def __init__(self, products: List[EOProduct]) -> None:
        super(SearchResult, self).__init__(products)

    def crunch(self, cruncher: Crunch, **search_params: Any) -> SearchResult:
        """Do some crunching with the underlying EO products.

        :param cruncher: The plugin instance to use to work on the products
        :type cruncher: subclass of :class:`~eodag.plugins.crunch.base.Crunch`
        :param search_params: The criteria that have been used to produce this result
        :type search_params: dict
        :returns: The result of the application of the crunching method to the EO products
        :rtype: :class:`~eodag.api.search_result.SearchResult`
        """
        crunched_results = cruncher.proceed(self.products, **search_params)
        return SearchResult(crunched_results)

    def filter_date(self, start: Optional[str] = None, end: Optional[str] = None) -> SearchResult:
        """
        Apply :class:`~eodag.plugins.crunch.filter_date.FilterDate` crunch,
        check its documentation to know more.
        """
        return self.crunch(FilterDate(dict(start=start, end=end)))

    def filter_latest_intersect(self, geometry: Union[Dict[str, Any], BaseGeometry, Any]):
        """
        Apply :class:`~eodag.plugins.crunch.filter_latest_intersect.FilterLatestIntersect` crunch,
        check its documentation to know more.
        """
        return self.crunch(FilterLatestIntersect({}), geometry=geometry)

    def filter_latest_by_name(self, name_pattern: str):
        """
        Apply :class:`~eodag.plugins.crunch.filter_latest_tpl_name.FilterLatestByName` crunch,
        check its documentation to know more.
        """
        return self.crunch(FilterLatestByName(dict(name_pattern=name_pattern)))

    def filter_overlap(
        self,
        geometry,
        minimum_overlap=0,
        contains=False,
        intersects=False,
        within=False,
    ):
        """
        Apply :class:`~eodag.plugins.crunch.filter_overlap.FilterOverlap` crunch,
        check its documentation to know more.
        """
        return self.crunch(
            FilterOverlap(
                dict(
                    minimum_overlap=minimum_overlap,
                    contains=contains,
                    intersects=intersects,
                    within=within,
                )
            ),
            geometry=geometry,
        )

    def filter_property(self, operator="eq", **search_property):
        """
        Apply :class:`~eodag.plugins.crunch.filter_property.FilterProperty` crunch,
        check its documentation to know more.
        """
        return self.crunch(FilterProperty(dict(operator=operator, **search_property)))

    def filter_online(self):
        """
        Use cruncher :class:`~eodag.plugins.crunch.filter_property.FilterProperty`,
        filter for online products.
        """
        return self.filter_property(storageStatus="ONLINE")

    @staticmethod
    def from_geojson(feature_collection: Dict[str, Any]) -> SearchResult:
        """Builds an :class:`~eodag.api.search_result.SearchResult` object from its representation as geojson

        :param feature_collection: A collection representing a search result.
        :type feature_collection: dict
        :returns: An eodag representation of a search result
        :rtype: :class:`~eodag.api.search_result.SearchResult`
        """
        return SearchResult(
            EOProduct.from_geojson(feature)
            for feature in feature_collection["features"]
        )

    def as_geojson_object(self) -> Dict[str, Any]:
        """GeoJSON representation of SearchResult"""
        return {
            "type": "FeatureCollection",
            "features": [product.as_dict() for product in self],
        }

    def as_shapely_geometry_object(self):
        """:class:`shapely.geometry.GeometryCollection` representation of SearchResult"""
        return GeometryCollection(
            [
                shape(feature["geometry"]).buffer(0)
                for feature in self.as_geojson_object()["features"]
            ]
        )

    def as_wkt_object(self):
        """WKT representation of SearchResult"""
        return self.as_shapely_geometry_object().wkt

    @property
    def __geo_interface__(self):
        """Implements the geo-interface protocol.

        See https://gist.github.com/sgillies/2217756
        """
        return self.as_geojson_object()
