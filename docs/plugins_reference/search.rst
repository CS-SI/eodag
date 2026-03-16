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

   qssearch.querystringsearch.QueryStringSearch
   qssearch.odatav4search.ODataV4Search
   qssearch.postjsonsearch.PostJsonSearch
   qssearch.stacsearch.StacSearch
   qssearch.wekeosearch.WekeoSearch
   qssearch.geodessearch.GeodesSearch
   static_stac_search.StaticStacSearch
   stac_list_assets.StacListAssets
   cop_marine.CopMarineSearch
   cop_ghsl.CopGhslSearch
   creodias_s3.CreodiasS3Search
   build_search_result.ecmwfsearch.ECMWFSearch
   build_search_result.meteobluesearch.MeteoblueSearch
   build_search_result.wekeoecmwfsearch.WekeoECMWFSearch
   csw.CSWSearch
