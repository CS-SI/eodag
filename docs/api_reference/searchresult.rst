.. module:: eodag.api.search_result

============
SearchResult
============

The `SearchResult` class provides a convenient way to handle and manipulate search results obtained from the EODAG API.
It offers various methods to filter, transform, and interact with the search results, making it easier to work with geospatial data in different formats.

Constructor
-----------

.. autosummary::

   SearchResult

   .. members::

Pagination
----------

.. autosummary::

   SearchResult.next_page

Crunch
------

.. autosummary::

   SearchResult.crunch
   SearchResult.filter_date
   SearchResult.filter_latest_intersect
   SearchResult.filter_latest_by_name
   SearchResult.filter_overlap
   SearchResult.filter_property
   SearchResult.filter_online

Conversion
----------

.. autosummary::

   SearchResult.from_geojson
   SearchResult.as_geojson_object
   SearchResult.as_shapely_geometry_object
   SearchResult.as_wkt_object

Interface
---------

.. autosummary::

   SearchResult.__geo_interface__

.. autoclass:: SearchResult
   :members: crunch, filter_date, filter_latest_intersect, filter_latest_by_name, filter_overlap, filter_property,
             filter_online, from_geojson, as_geojson_object, as_shapely_geometry_object, as_wkt_object, next_page,
             __geo_interface__
