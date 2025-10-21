.. module:: eodag.api.product._assets

======
Assets
======

The `Assets` module provides classes and methods to manage and interact with assets associated with :class:`~eodag.api.product._product.EOProduct`.
These assets can include files, metadata, or other resources that are part of a product's data package.
The module offers functionality for accessing, manipulating, and extending asset-related operations.

.. autoclass:: AssetsDict
   :members:

.. autoclass:: Asset
   :members:

Pixel access
------------

.. warning::

   The following methods will only be available with `eodag-cube <https://github.com/CS-SI/eodag-cube>`__ installed.

.. class:: eodag_cube.api.product._assets.AssetsDict
   :canonical: eodag_cube.api.product._assets.AssetsDict

   Inherits from :class:`eodag.api.product._assets.AssetsDict` and implements pixel access related methods.

.. class:: eodag_cube.api.product._assets.Asset

   Inherits from :class:`eodag.api.product._assets.Asset` and implements pixel access related methods.

.. automethod:: eodag_cube.api.product._assets.Asset.to_xarray
.. automethod:: eodag_cube.api.product._assets.Asset.get_file_obj
.. automethod:: eodag_cube.api.product._assets.Asset.rio_env
