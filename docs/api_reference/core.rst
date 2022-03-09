.. module:: eodag.api.core

===================
EODataAccessGateway
===================

Constructor
-----------
.. autosummary::

   EODataAccessGateway

Configuration
-------------

.. autosummary::

   EODataAccessGateway.set_preferred_provider
   EODataAccessGateway.get_preferred_provider
   EODataAccessGateway.update_providers_config

Catalog
-------

.. autosummary::

   EODataAccessGateway.available_providers
   EODataAccessGateway.list_product_types
   EODataAccessGateway.guess_product_type

Search
------

.. autosummary::

   EODataAccessGateway.search
   EODataAccessGateway.search_all
   EODataAccessGateway.search_iter_page

Crunch
------

.. autosummary::

   EODataAccessGateway.crunch
   EODataAccessGateway.get_cruncher

Download
--------

.. autosummary::

   EODataAccessGateway.download
   EODataAccessGateway.download_all

Serialize/Deserialize
---------------------

.. autosummary::

   EODataAccessGateway.serialize
   EODataAccessGateway.deserialize
   EODataAccessGateway.deserialize_and_register


STAC
----

.. autosummary::

   EODataAccessGateway.load_stac_items

Misc
----

.. autosummary::

   EODataAccessGateway.group_by_extent

.. autoclass:: eodag.api.core.EODataAccessGateway
   :members: set_preferred_provider, get_preferred_provider, update_providers_config, list_product_types, available_providers,
             search, search_all, search_iter_page, crunch, download, download_all, serialize, deserialize, deserialize_and_register,
             load_stac_items, group_by_extent, guess_product_type, get_cruncher
