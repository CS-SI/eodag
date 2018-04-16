# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
import six


class DatasetDriver(six.with_metaclass(type)):

    def get_dataset_address(self, eo_product, band):
        """Retrieve the address of the dataset represented by `eo_product`.

        :param eo_product: The product whom underlying dataset address is to be retrieved
        :type eo_product: :class:`~eodag.api.product.EOProduct`
        :param str band: The band to retrieve (e.g: 'B01')
        :returns: An address for the dataset
        :rtype: str or unicode
        :raises: :class:`~eodag.utils.exceptions.AddressNotFound`
        """
        raise NotImplementedError
