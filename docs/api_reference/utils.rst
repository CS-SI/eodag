.. module:: eodag.utils
   :no-index:

=====
Utils
=====

This section provides an overview of the utility functions and classes available in the `eodag` library.
These utilities are designed to assist with various tasks such as logging, handling callbacks, performing free text searches, working with Jupyter notebooks, interacting with S3 storage, and processing xarray data.
Each subsection below details the specific utilities and their usage.

Logging
-------

.. automodule:: eodag.utils.logging
   :members:

Callbacks
---------

.. autoclass:: eodag.utils.DownloadedCallback
   :special-members: __call__
.. autofunction:: eodag.utils.ProgressCallback

Dates
-----

.. automodule:: eodag.utils.dates
   :members:

Free text search
----------------

.. autofunction:: eodag.utils.free_text_search.compile_free_text_query

Notebook
--------

.. automodule:: eodag.utils.notebook
   :members:

S3
----

.. automodule:: eodag.utils.s3
   :members:

xarray
------

.. warning::

   These functions will only be available with `eodag-cube <https://github.com/CS-SI/eodag-cube>`__ installed.

.. automodule:: eodag_cube.utils.xarray
   :members:

Misc
----

.. automodule:: eodag.utils
   :members:
   :exclude-members: DownloadedCallback, ProgressCallback, NotebookProgressCallback, get_progress_callback,
      DEFAULT_PROJ, GENERIC_COLLECTION, GENERIC_STAC_PROVIDER, STAC_SEARCH_PLUGINS, USER_AGENT,
      HTTP_REQ_TIMEOUT, DEFAULT_SEARCH_TIMEOUT, DEFAULT_STREAM_REQUESTS_TIMEOUT, REQ_RETRY_TOTAL,
      REQ_RETRY_BACKOFF_FACTOR, REQ_RETRY_STATUS_FORCELIST, DEFAULT_DOWNLOAD_WAIT, DEFAULT_DOWNLOAD_TIMEOUT,
      JSONPATH_MATCH, WORKABLE_JSONPATH_MATCH, ARRAY_FIELD_MATCH, DEFAULT_PAGE, DEFAULT_LIMIT,
      DEFAULT_MAX_LIMIT, DEFAULT_MISSION_START_DATE, DEFAULT_SHAPELY_GEOMETRY,
      DEFAULT_TOKEN_EXPIRATION_MARGIN, KNOWN_NEXT_PAGE_TOKEN_KEYS, ONLINE_STATUS, STAC_VERSION

Constants: Core
---------------

.. autodata:: eodag.utils.GENERIC_COLLECTION
.. autodata:: eodag.utils.GENERIC_STAC_PROVIDER
.. autodata:: eodag.utils.STAC_SEARCH_PLUGINS
.. autodata:: eodag.utils.STAC_VERSION

Constants: HTTP requests
------------------------

.. autodata:: eodag.utils.USER_AGENT
.. autodata:: eodag.utils.HTTP_REQ_TIMEOUT
.. autodata:: eodag.utils.DEFAULT_SEARCH_TIMEOUT
.. autodata:: eodag.utils.DEFAULT_STREAM_REQUESTS_TIMEOUT
.. autodata:: eodag.utils.REQ_RETRY_TOTAL
.. autodata:: eodag.utils.REQ_RETRY_BACKOFF_FACTOR
.. autodata:: eodag.utils.REQ_RETRY_STATUS_FORCELIST
.. autodata:: eodag.utils.DEFAULT_DOWNLOAD_WAIT
.. autodata:: eodag.utils.DEFAULT_DOWNLOAD_TIMEOUT
.. autodata:: eodag.utils.DEFAULT_TOKEN_EXPIRATION_MARGIN

Constants: Pagination
---------------------

.. autodata:: eodag.utils.DEFAULT_PAGE
.. autodata:: eodag.utils.DEFAULT_LIMIT
.. autodata:: eodag.utils.DEFAULT_MAX_LIMIT
.. autodata:: eodag.utils.KNOWN_NEXT_PAGE_TOKEN_KEYS

Constants: Metadata-mapping / default values
--------------------------------------------

.. autodata:: eodag.utils.DEFAULT_PROJ
.. autodata:: eodag.utils.DEFAULT_MISSION_START_DATE
.. autodata:: eodag.utils.DEFAULT_SHAPELY_GEOMETRY
.. autodata:: eodag.utils.ONLINE_STATUS

Constants: Metadata-mapping / JSONPath regex
--------------------------------------------

.. autodata:: eodag.utils.JSONPATH_MATCH
.. autodata:: eodag.utils.WORKABLE_JSONPATH_MATCH
.. autodata:: eodag.utils.ARRAY_FIELD_MATCH
