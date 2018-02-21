# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

import logging
import re

from eodag.plugins.crunch.base import Crunch
from eodag.utils.exceptions import MisconfiguredError


logger = logging.getLogger('eodag.plugins.crunch.filter_latest')


class FilterLatestByName(Crunch):
    NAME_PATTERN_CONSTRAINT = re.compile(r'\(\?P<tileid>\\d\{6\}\)')

    def __init__(self, config):
        name_pattern = config.pop('name_pattern')
        if not self.NAME_PATTERN_CONSTRAINT.search(name_pattern):
            raise MisconfiguredError('Name pattern should respect the regex: {}'.format(
                self.NAME_PATTERN_CONSTRAINT.pattern
            ))
        self.name_pattern = re.compile(name_pattern)

    def proceed(self, product_list):
        """Filter Search results to get only the latest product, based on the name of the product"""
        logger.debug('Starting products filtering')
        processed = []
        filtered = []
        for product in product_list:
            match = self.name_pattern.match(product.local_filename)
            if match:
                tileid = match.group('tileid')
                if tileid not in processed:
                    logger.debug('Latest product found for tileid=%s: date=%s', tileid,
                                 product.original_repr['properties']['Published'])
                    filtered.append(product)
                    processed.append(tileid)
                else:
                    logger.debug('Latest product already found for tileid=%s', tileid)
            else:
                logger.warning('The name of the product %r as returned by the search plugin does not match the name '
                               'pattern expected by the cruncher %s. Name of the product: %s. Name pattern expected: '
                               '%s', product, self.name, product.local_filename, self.name_pattern)
        logger.debug('Ending products filtering. Filtered products: %r', filtered)
        return filtered
