# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from .base import Crunch


class RemoveDoubles(Crunch):
    """This is an example of the kind of crunching that can be done on a list of results from a search"""

    def proceed(self, product_list):
        """Removes duplicates in product_list based on their ids, preserving the order of the list"""
        product_ids = (product.id for product in product_list)
        seen = set()
        seen_add = seen.add
        unique_ids = (_id for _id in product_ids if not (_id in seen or seen_add(_id)))
        results = []
        append_to_results = results.append
        for product in product_list:
            if product.id in unique_ids and product not in results:
                append_to_results(product)
        return results

