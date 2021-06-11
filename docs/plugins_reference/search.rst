.. module:: eodag.plugins.search

==============
Search Plugins
==============

Search plugins must inherit the following class and implement :meth:`query`:

.. autoclass:: eodag.plugins.search.base.Search
   :members:

This table lists all the search plugins currently available:

.. autosummary::
   :toctree: generated/

   eodag.plugins.search.qssearch.QueryStringSearch
   eodag.plugins.search.qssearch.AwsSearch
   eodag.plugins.search.qssearch.ODataV4Search
   eodag.plugins.search.qssearch.PostJsonSearch
   eodag.plugins.search.qssearch.StacSearch
   eodag.plugins.search.static_stac_search.StaticStacSearch
   eodag.plugins.search.csw.CSWSearch
