.. _api:

.. module:: eodag

We gather here all the information necessary to work with `eodag` as a Python api.


Core
====

.. autoclass:: eodag.api.core.SatImagesAPI
   :members:
   :undoc-members:


Representation Of Earth Observation Products
============================================

.. autoclass:: eodag.api.product._product.EOProduct
   :members:
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.api.product.drivers.base.DatasetDriver
   :members:
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.api.product.drivers.base.NoDriver
   :members:
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.api.product.drivers.sentinel2.Sentinel2L1C
   :members:
   :show-inheritance:
   :undoc-members:


Representation Of Search Results
================================

.. autoclass:: eodag.api.search_result.SearchResult
   :members:
   :undoc-members:


Plugins
=======

Plugin Instances Management
---------------------------

.. autoclass:: eodag.plugins.instances_manager.PluginInstancesManager
   :members:
   :show-inheritance:


Plugin Types
-------------

.. autoclass:: eodag.plugins.base.PluginTopic
   :members:
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.search.base.Search
   :members:
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.download.base.Download
   :members:
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.crunch.base.Crunch
   :members:
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.authentication.base.Authentication
   :members:
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.apis.base.Api
   :members:
   :show-inheritance:
   :undoc-members:


Search Plugins
--------------

.. autoclass:: eodag.plugins.search.csw.CSWSearch
   :members:
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.search.resto.RestoSearch
   :members:
   :show-inheritance:
   :undoc-members:


Download Plugins
----------------

.. autoclass:: eodag.plugins.download.http.HTTPDownload
   :members:
   :show-inheritance:
   :undoc-members:


Crunch Plugins
--------------

.. autoclass:: eodag.plugins.crunch.filter_latest_intersect.FilterLatestIntersect
   :members:
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.crunch.filter_latest_tpl_name.FilterLatestByName
   :members:
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.crunch.filter_overlap.FilterOverlap
   :members:
   :show-inheritance:
   :undoc-members:


Authentication Plugins
----------------------

.. autoclass:: eodag.plugins.authentication.generic.GenericAuth
   :members:
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.authentication.token.TokenAuth
   :members:
   :show-inheritance:
   :undoc-members:


External Apis Plugins
---------------------

.. autoclass:: eodag.plugins.apis.sentinelsat.SentinelsatAPI
   :members:
   :show-inheritance:
   :undoc-members:


Utils
=====

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

