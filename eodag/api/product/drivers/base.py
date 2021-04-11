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


class DatasetDriver(metaclass=type):
    """Dataset driver"""

    def get_data_address(self, eo_product, band):
        """Retrieve the address of the dataset represented by `eo_product`.

        :param eo_product: The product whom underlying dataset address is to be retrieved
        :type eo_product: :class:`~eodag.api.product.EOProduct`
        :param band: The band to retrieve (e.g: 'B01')
        :type band: str
        :returns: An address for the dataset
        :rtype: str
        :raises: :class:`~eodag.utils.exceptions.AddressNotFound`
        :raises: :class:`~eodag.utils.exceptions.UnsupportedDatasetAddressScheme`
        """
        raise NotImplementedError


class NoDriver(DatasetDriver):
    """A default driver that does not implement any of the methods it should implement, used for all product types for
    which the :meth:`~eodag.api.product._product.EOProduct.get_data` method is not yet implemented in eodag. Expect a
    :exc:`NotImplementedError` when trying to get the data in that case.
    """
