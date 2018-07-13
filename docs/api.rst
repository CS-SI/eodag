.. _api:

.. module:: eodag.api.core

Python API
==========

Core
----

.. autoclass:: eodag.api.core.SatImagesAPI
   :members:
   :undoc-members:

.. module:: eodag.api.product

Representation Of Earth Observation Products
--------------------------------------------

The EOProduct object
^^^^^^^^^^^^^^^^^^^^

.. autoclass:: eodag.api.product._product.EOProduct
   :members:
   :show-inheritance:
   :undoc-members:

.. module:: eodag.api.product.drivers

Data access drivers
^^^^^^^^^^^^^^^^^^^

.. autoclass:: eodag.api.product.drivers.base.DatasetDriver
   :members:
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.api.product.drivers.base.NoDriver
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.api.product.drivers.sentinel2_l1c.Sentinel2L1C
   :show-inheritance:
   :undoc-members:

.. module:: eodag.api.search_result

Representation Of Search Results
--------------------------------

.. autoclass:: eodag.api.search_result.SearchResult
   :members:
   :undoc-members:

.. module:: eodag.plugins

Plugins
-------

EODAG uses a two-level plugin system. *Plugin topics* are abstract interfaces for a specific functionality of EODAG
like *Search* or *Download*. EODAG providers are implementations of at least one plugin topic. The more plugin topics
are implemented by a provider, the more functionality of eodag are available for this provider.

Plugin Management
^^^^^^^^^^^^^^^^^

The plugin machinery is managed by one instance of :class:`~eodag.plugins.instances_manager.PluginInstancesManager`.

.. autoclass:: eodag.plugins.instances_manager.PluginInstancesManager
   :members:
   :show-inheritance:


Plugin Types
^^^^^^^^^^^^

EODAG currently advertises 5 types of plugins: *Search*, *Download*, *Crunch*, *Authentication* and *Api*.

.. autoclass:: eodag.plugins.base.PluginTopic
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.search.base.Search
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.download.base.Download
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.crunch.base.Crunch
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.authentication.base.Authentication
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.apis.base.Api
   :show-inheritance:
   :undoc-members:

.. module:: eodag.plugins.search

Search Plugins
^^^^^^^^^^^^^^

.. autoclass:: eodag.plugins.search.csw.CSWSearch
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.search.resto.RestoSearch
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.search.aws.AwsSearch
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.search.arlas.ArlasSearch
   :show-inheritance:
   :undoc-members:

.. module:: eodag.plugins.download

Download Plugins
^^^^^^^^^^^^^^^^

.. autoclass:: eodag.plugins.download.http.HTTPDownload
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.download.aws.AwsDownload
   :show-inheritance:
   :undoc-members:

.. module:: eodag.plugins.crunch

Crunch Plugins
^^^^^^^^^^^^^^

.. autoclass:: eodag.plugins.crunch.filter_latest_intersect.FilterLatestIntersect
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.crunch.filter_latest_tpl_name.FilterLatestByName
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.crunch.filter_overlap.FilterOverlap
   :show-inheritance:
   :undoc-members:

.. module:: eodag.plugins.authentication

Authentication Plugins
^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: eodag.plugins.authentication.generic.GenericAuth
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.authentication.token.TokenAuth
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.authentication.header.HTTPHeaderAuth
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.authentication.oauth.OAuth
   :show-inheritance:
   :undoc-members:

.. module:: eodag.plugins.apis

External Apis Plugins
^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: eodag.plugins.apis.usgs.UsgsApi
   :show-inheritance:
   :undoc-members:


Utils
-----

.. automodule:: eodag.utils
   :members:
   :show-inheritance:
   :undoc-members:

.. automodule:: eodag.utils.exceptions
   :members:
   :show-inheritance:
   :undoc-members:

.. automodule:: eodag.utils.import_system
   :members:
   :show-inheritance:
   :undoc-members:

.. automodule:: eodag.utils.known_systems_utils
   :members:
   :show-inheritance:
   :undoc-members:

.. automodule:: eodag.utils.logging
   :members:
   :show-inheritance:
   :undoc-members:

.. automodule:: eodag.utils.metadata_mapping
   :members:
   :show-inheritance:
   :undoc-members:

