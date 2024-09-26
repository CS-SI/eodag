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

   qssearch.QueryStringSearch
   qssearch.ODataV4Search
   qssearch.PostJsonSearch
   qssearch.StacSearch
   qssearch.PostJsonSearchWithStacQueryables
   static_stac_search.StaticStacSearch
   cop_marine.CopMarineSearch
   creodias_s3.CreodiasS3Search
   build_search_result.BuildSearchResult
   build_search_result.BuildPostSearchResult
   data_request_search.DataRequestSearch
   csw.CSWSearch
