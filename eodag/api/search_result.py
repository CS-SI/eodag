# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

from eodag.api.product import EOProduct


class SearchResult(object):
    """An object representing a collection of :class:`~eodag.api.product.EOProduct` resulting from a search.

    :param products: A list of products resulting from a search
    :type products: list(:class:`~eodag.api.product.EOProduct`)
    """

    def __init__(self, products):
        self.__final_result = []
        self.__original = products
        self.__crunch_calls_count = 0

    def crunch(self, cruncher, **search_params):
        """Do some crunching with the underlying EO products.

        :param cruncher: The plugin instance to use to work on the products
        :type cruncher: subclass of :class:`~eodag.plugins.crunch.base.Crunch`
        :param dict search_params: The criteria that have been used to produce this result
        :returns: The result of the application of the crunching method to the EO products
        :rtype: :class:`~eodag.api.search_result.SearchResult`
        """
        crunched_results = cruncher.proceed(self.__original, **search_params)
        self.__final_result.extend(crunched_results)
        self.__crunch_calls_count += 1
        return SearchResult(crunched_results)

    @staticmethod
    def from_geojson(feature_collection):
        """Builds an :class:`~eodag.api.search_result.SearchResult` object from its representation as geojson

        :param feature_collection: A collection representing a search result.
        :type feature_collection: dict
        :returns: An eodag representation of a search result
        :rtype: :class:`~eodag.api.search_result.SearchResult`
        """
        return SearchResult([
            EOProduct.from_geojson(feature)
            for feature in feature_collection['features']
        ])

    @property
    def __geo_interface__(self):
        """Implements the geo-interface protocol.

        See https://gist.github.com/sgillies/2217756
        """
        return {
            'type': 'FeatureCollection',
            'features': [product.as_dict() for product in (
                self.__final_result if self.__crunch_calls_count > 0 else self.__original
            )]
        }

    def __len__(self):
        return self.__speculate_on_result(len)

    def __nonzero__(self):
        return self.__speculate_on_result(bool)

    def __iter__(self):
        return self.__speculate_on_result(iter)

    def __repr__(self):
        return self.__speculate_on_result(repr)

    def __speculate_on_result(self, func):
        if self.__crunch_calls_count == 0 and not self.__final_result:
            return func(self.__original)
        return func(self.__final_result)
