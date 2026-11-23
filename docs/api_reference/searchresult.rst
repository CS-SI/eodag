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

Use ``fetch_next_page()`` to fetch one page at a time and retry a failed request
on the same result. Set ``raise_errors=True`` on the initial search to propagate
request errors. Without it, a failed request stops pagination.

.. autosummary::

   SearchResult.fetch_next_page
   SearchResult.next_page

Crunch
------

Use one of the following ``filter_*`` methods to filter search results using advanced criteria. These methods simplify
crunch plugins usage.

Or manually run :meth:`~eodag.api.search_result.SearchResult.crunch` to apply a given :class:`eodag.plugins.crunch.base.Crunch` plugin.

.. autosummary::

   SearchResult.filter_date
   SearchResult.filter_latest_intersect
   SearchResult.filter_latest_by_name
   SearchResult.filter_overlap
   SearchResult.filter_property
   SearchResult.filter_online
   SearchResult.crunch

Conversion
----------

.. autosummary::

   SearchResult.from_dict
   SearchResult.from_pystac
   SearchResult.as_dict
   SearchResult.as_pystac_object
   SearchResult.as_shapely_geometry_object
   SearchResult.as_wkt_object

Interface
---------

.. autosummary::

   SearchResult.__geo_interface__

.. autoclass:: SearchResult
   :members: crunch, filter_date, filter_latest_intersect, filter_latest_by_name, filter_overlap, filter_property,
             filter_online, from_dict, from_pystac, as_dict, as_pystac_object, as_shapely_geometry_object,
             as_wkt_object, fetch_next_page, next_page, __geo_interface__
