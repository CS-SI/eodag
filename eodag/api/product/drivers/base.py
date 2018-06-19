# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
import six


class DatasetDriver(six.with_metaclass(type)):

    def get_data_address(self, eo_product, band):
        """Retrieve the address of the dataset represented by `eo_product`.

        :param eo_product: The product whom underlying dataset address is to be retrieved
        :type eo_product: :class:`~eodag.api.product.EOProduct`
        :param band: The band to retrieve (e.g: 'B01')
        :type band: str or unicode
        :returns: An address for the dataset
        :rtype: str or unicode
        :raises: :class:`~eodag.utils.exceptions.AddressNotFound`
        :raises: :class:`~eodag.utils.exceptions.UnsupportedDatasetAddressScheme`
        """
        raise NotImplementedError


class NoDriver(DatasetDriver):
    """A default driver that does not implement any of the methods it should implement, used for all product types for
    which the :meth:`~eodag.api.product._product.EOProduct.get_data` method is not yet implemented in eodag. Expect a
    :exc:`NotImplementedError` when trying to get the data in that case.
    """
