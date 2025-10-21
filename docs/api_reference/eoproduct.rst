.. module:: eodag.api.product._product

=========
EOProduct
=========

EOProduct is the main class representing Earth Observation (EO) products in the EODAG library.
It provides a comprehensive interface for interacting with EO products, including metadata access, downloading, and conversion to various formats.
This section details the attributes, methods, and additional functionalities available in the EOProduct class.

Constructor
-----------

.. autoclass:: EOProduct

   :Attributes:

      .. autoattribute:: provider
      .. autoattribute:: properties
      .. autoattribute:: collection
      .. autoattribute:: geometry
      .. autoattribute:: search_intersection
      .. autoattribute:: location
      .. autoattribute:: remote_location
      .. autoattribute:: assets
      .. autoattribute:: driver

Download
--------

.. automethod:: EOProduct.download
.. automethod:: EOProduct.get_quicklook

Conversion
----------

.. automethod:: EOProduct.as_dict
.. automethod:: EOProduct.from_geojson

Interface
---------

.. autoproperty:: EOProduct.__geo_interface__

Pixel access
------------

.. warning::

   The following methods will only be available with `eodag-cube <https://github.com/CS-SI/eodag-cube>`__ installed.

.. class:: eodag_cube.api.product._product.EOProduct
   :canonical: eodag_cube.api.product._product.EOProduct

   Inherits from :class:`eodag.api.product._product.EOProduct` and implements pixel access related methods.

.. automethod:: eodag_cube.api.product._product.EOProduct.to_xarray
.. automethod:: eodag_cube.api.product._product.EOProduct.get_file_obj
.. automethod:: eodag_cube.api.product._product.EOProduct.rio_env
