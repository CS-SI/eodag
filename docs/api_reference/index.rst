.. _api_reference:

API Reference
====================


The API Reference provides an overview of all public objects, functions and methods implemented in eodag.

.. toctree::
   :hidden:
   :maxdepth: 2

   core
   searchresult
   eoproduct
   assets
   utils
   exceptions
   types
   call_graphs


.. grid:: 1 2 2 3
   :gutter: 4

   .. grid-item-card:: EODataAccessGateway
      :link: core
      :link-type: doc
      :text-align: center
      :shadow: md

      The main entry point for accessing Earth observation data. Handles configuration, catalog access, search, filtering, and download operations.

   .. grid-item-card:: SearchResult
      :link: searchresult
      :link-type: doc
      :text-align: center
      :shadow: md

      Container for search results with filtering capabilities, conversion methods, and standardized interface for result manipulation.

   .. grid-item-card:: EOProduct
      :link: eoproduct
      :link-type: doc
      :text-align: center
      :shadow: md

      Represents individual Earth observation products with download capabilities, format conversion, and pixel-level data access.

   .. grid-item-card:: Assets
      :link: assets
      :link-type: doc
      :text-align: center
      :shadow: md

      Manage product assets including AssetsDict and Asset classes for handling multi-file products and pixel access operations.

   .. grid-item-card:: Utils
      :link: utils
      :link-type: doc
      :text-align: center
      :shadow: md

      Utility functions for logging, callbacks, text search, notebook integration, S3 operations, xarray support, and miscellaneous helpers.

   .. grid-item-card:: Exceptions
      :link: exceptions
      :link-type: doc
      :text-align: center
      :shadow: md

      Complete set of custom exceptions for error handling including authentication, download, configuration, and validation errors.

   .. grid-item-card:: Types
      :link: types
      :link-type: doc
      :text-align: center
      :shadow: md

      Type definitions, data models, and schema utilities for configuration management and type conversion between formats.

   .. grid-item-card:: Call Graphs
      :link: call_graphs
      :link-type: doc
      :text-align: center
      :shadow: md

      Visual representation of function call relationships and dependencies within the eodag codebase for development reference.
