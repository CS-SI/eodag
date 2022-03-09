.. module:: eodag.api.search_result

============
SearchResult
============

Constructor
-----------

.. autosummary::

   SearchResult

Crunch
------

.. autosummary::

   SearchResult.crunch
   SearchResult.filter_date
   SearchResult.filter_latest_intersect
   SearchResult.filter_latest_by_name
   SearchResult.filter_overlap
   SearchResult.filter_property

Conversion
----------

.. autosummary::

   SearchResult.from_geojson
   SearchResult.as_geojson_object

Interface
---------

.. autosummary::

   SearchResult.__geo_interface__

.. autoclass:: SearchResult
   :members: crunch, filter_date, filter_latest_intersect, filter_latest_by_name, filter_overlap, filter_property, from_geojson, as_geojson_object, __geo_interface__
