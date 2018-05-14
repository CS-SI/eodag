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
        """
        raise NotImplementedError


class NoDriver(DatasetDriver):
    """A default driver that does not implement any of the methods it should implement, used as a temporary fail over
    for all the plugins that don't give the names of the platform and the instrument during instantiation of eoproduct
    after they receive their search result. This driver is indexed with ``(None, None)`` in
    :const:`eodag.api.product.drivers.DRIVERS`.

    So, when developing a new :class:`~eodag.plugins.search.base.Search` plugin, if you don't give both ``platform`` and
    ``instrument`` keyword arguments when creating a new :class:`~eodag.api.product._product.EOProduct` instance in your
    :meth:`~eodag.plugins.search.base.Search.query` method, you should expect a call to this instance's
    :meth:`~eodag.api.product._product.EOProduct.get_data` method to fail with a :exc:`NotImplementedError`.

    .. note::
        Also, if you construct a :class:`~eodag.api.product._product.EOProduct` instance with a platform and instrument
        names that are not indexed in  :const:`eodag.api.product.drivers.DRIVERS`, you will end up with this instance's
        driver being :class:`.NoDriver`
    """
