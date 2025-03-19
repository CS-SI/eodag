.. module:: eodag.api.product._assets

======
Assets
======

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
.. automethod:: eodag_cube.api.product._assets.Asset.get_data
