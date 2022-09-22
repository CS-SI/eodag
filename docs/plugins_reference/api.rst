.. module:: eodag.plugins.apis

===========
API Plugins
===========

Api plugins must inherit the following class and implement :meth:`query` and :meth:`download`:

.. autoclass:: eodag.plugins.apis.base.Api
   :members:

This table lists all the api plugins currently available:

.. autosummary::
   :toctree: generated/

   eodag.plugins.apis.usgs.UsgsApi
   eodag.plugins.apis.ecmwf.EcmwfApi
   eodag.plugins.apis.cds.CdsApi
