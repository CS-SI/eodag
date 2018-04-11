# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
import six


class DatasetDriver(six.with_metaclass(type)):

    def get_dataset_address(self, eo_product, band):
        """Retrieve the address of the dataset represented by self.

        :param eo_product: The product whom underlying dataset address is to be retrieved
        :type eo_product: `~eodag.api.product.EOProduct`
        :param band: The band to retrieve (e.g: 'B01')
        :type band: str
        :returns: An address for the dataset
        :rtype: str
        :raises: AddressNotFound
        """
        raise NotImplementedError
