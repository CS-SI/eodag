# -*- coding: utf-8 -*-
# Copyright 2021, CS GROUP - France, https://www.csgroup.eu/
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
from collections import UserList

from eodag.api.product import EOProduct


class SearchResult(UserList):
    """An object representing a collection of :class:`~eodag.api.product._product.EOProduct` resulting from a search.

    :param products: A list of products resulting from a search
    :type products: list(:class:`~eodag.api.product._product.EOProduct`)
    """

    def __init__(self, products):
        super(SearchResult, self).__init__(products)

    def crunch(self, cruncher, **search_params):
        """Do some crunching with the underlying EO products.

        :param cruncher: The plugin instance to use to work on the products
        :type cruncher: subclass of :class:`~eodag.plugins.crunch.base.Crunch`
        :param dict search_params: The criteria that have been used to produce this result
        :returns: The result of the application of the crunching method to the EO products
        :rtype: :class:`~eodag.api.search_result.SearchResult`
        """
        crunched_results = cruncher.proceed(self, **search_params)
        return SearchResult(crunched_results)

    @staticmethod
    def from_geojson(feature_collection):
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

    def as_geojson_object(self):
        """GeoJSON representation of SearchResult"""
        return {
            "type": "FeatureCollection",
            "features": [product.as_dict() for product in self],
        }

    @property
    def __geo_interface__(self):
        """Implements the geo-interface protocol.

        See https://gist.github.com/sgillies/2217756
        """
        return self.as_geojson_object()
