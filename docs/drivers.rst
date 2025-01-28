.. module:: eodag.api.product.drivers

Drivers
=======

Drivers enable additional methods to be called on the :class:`~eodag.api.product._product.EOProduct`. They are set as
:attr:`~eodag.api.product._product.EOProduct.driver` attribute of the :class:`~eodag.api.product._product.EOProduct`
during its initialization, using some criteria to determine the most adapted driver. The first driver having its
associated criteria matching will be used. If no driver is found, the :class:`~eodag.api.product.drivers.base.NoDriver`
criteria is used.


Criteria
^^^^^^^^

.. autoclass:: eodag.api.product.drivers.DriverCriteria
    :members:

.. autodata:: DRIVERS
    :no-value:
.. autodata:: LEGACY_DRIVERS
    :no-value:


Methods available
^^^^^^^^^^^^^^^^^

.. autoclass:: eodag.api.product.drivers.base.DatasetDriver
   :members:
   :member-order: bysource

.. autoclass:: eodag.api.product.drivers.base.AssetPatterns
   :members:

Drivers Available
^^^^^^^^^^^^^^^^^

EODAG currently advertises the following drivers:

.. autosummary::
   :toctree: drivers_generated/

   base.NoDriver
   generic.GenericDriver
   sentinel1.Sentinel1Driver
   sentinel2.Sentinel2Driver
