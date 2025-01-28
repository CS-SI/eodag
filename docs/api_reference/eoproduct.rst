.. module:: eodag.api.product._product

=========
EOProduct
=========

Constructor
-----------

.. autosummary::

   EOProduct

Download
--------

.. autosummary::

   EOProduct.download
   EOProduct.get_quicklook

Driver
--------

.. autosummary::

   EOProduct.driver

Conversion
----------

.. autosummary::

   EOProduct.as_dict
   EOProduct.from_geojson

Interface
---------

.. autosummary::

   EOProduct.__geo_interface__


.. autoclass:: eodag.api.product._product.EOProduct
   :members: driver, download, get_quicklook, as_dict, from_geojson, __geo_interface__
