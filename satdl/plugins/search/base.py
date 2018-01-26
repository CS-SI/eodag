# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from satdl.plugins.base import GeoProductDownloaderPluginMount
from satdl.utils.exceptions import ValidationError
from satdl.utils.validators import URLValidator


class Search(metaclass=GeoProductDownloaderPluginMount):
    def __init__(self, config):
        self.config = {
            'api_endpoint': '',
            'products': {},
            'authenticate': False,
        }
        self.config.update(config)
        if not isinstance(self.config['products'], dict):
            raise MisconfiguredError("'products' must be a dictionary of values")
        if self.config['products']:
            for product_coll in self.config['products'].values():
                if 'product_types' not in product_coll:
                    raise MisconfiguredError("'products' value must have a 'product_types' key")
                if not isinstance(product_coll['product_types'], list):
                    if not isinstance(product_coll['product_types'], str):
                        raise MisconfiguredError("'product_types' key in 'products' must be either a list or a string")
                    product_coll['product_types'] = [product_coll['product_types']]
            # TODO: an instance without products should have minimum possible priority => priority should lower bounded
        if not self.config['api_endpoint']:
            raise MisconfiguredError("'api_endpoint' must be a valid url")
        validate_url = URLValidator(schemes=['http', 'https'], message="'api_endpoint' must be a valid url")
        try:
            validate_url(self.config['api_endpoint'])
        except ValidationError as e:
            raise MisconfiguredError(e.message)
        # try:
        #     self.priority = int(config.get('priority', self.priority))
        # except ValueError:
        #     raise MisconfiguredError("'priority' must be an integer (lower value means lower priority, even for "
        #                              "negative values)")

    def query(self, *args, **kwargs):
        """Implementation of how the products must be searched goes here.

        This method must return a list of EOProduct instances (see satdl.api.product module) which will
        be processed by a Download plugin.
        """
        raise NotImplementedError('A Search plugin must implement a method named query')


class MisconfiguredError(Exception):
    """An error indicating a Search Plugin that is not well configured"""
