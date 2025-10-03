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
   queryables
   collection
   utils
   exceptions
   types
   call_graphs


.. grid:: 1 2 2 3
   :gutter: 4

   .. grid-item-card:: :octicon:`globe;1.5em`  EODataAccessGateway
      :link: core
      :link-type: doc
      :text-align: center
      :shadow: md

      The main entry point for accessing Earth observation data. Handles configuration, catalog access, search, filtering, and download operations.

   .. grid-item-card:: :octicon:`search;1.5em`  SearchResult
         :link: searchresult
         :link-type: doc
         :text-align: center
         :shadow: md

         Container for search results with filtering capabilities, conversion methods, and standardized interface for result manipulation.

   .. grid-item-card:: :octicon:`package;1.5em`  EOProduct
         :link: eoproduct
         :link-type: doc
         :text-align: center
         :shadow: md

         Represents individual Earth observation products with download capabilities, format conversion, and pixel-level data access.

   .. grid-item-card:: :octicon:`archive;1.5em`  Assets
         :link: assets
         :link-type: doc
         :text-align: center
         :shadow: md

         Manage product assets including AssetsDict and Asset classes for handling multi-file products and pixel access operations.

   .. grid-item-card:: :octicon:`book;1.5em`  Collection
         :link: collection
         :link-type: doc
         :text-align: center
         :shadow: md

         Represents individual collections of catalogs and their metadata in Pydantic models with capabilities to search and list queryables.

   .. grid-item-card:: :octicon:`database;1.5em`  Provider
         :link: provider
         :link-type: doc
         :text-align: center
         :shadow: md

         Provider management including ProvidersDict and Provider classes for handling multiple data sources and their configurations.

   .. grid-item-card:: :octicon:`list-unordered;1.5em`  Queryables
         :link: queryables
         :link-type: doc
         :text-align: center
         :shadow: md

         Pydantic model listing queryable parameters and their characteristics.

   .. grid-item-card:: :octicon:`tools;1.5em`  Utils
         :link: utils
         :link-type: doc
         :text-align: center
         :shadow: md

         Utility functions for logging, callbacks, text search, notebook integration, S3 operations, xarray support, and miscellaneous helpers.

   .. grid-item-card:: :octicon:`alert;1.5em`  Exceptions
         :link: exceptions
         :link-type: doc
         :text-align: center
         :shadow: md

         Complete set of custom exceptions for error handling including authentication, download, configuration, and validation errors.

   .. grid-item-card:: :octicon:`code;1.5em`  Types
         :link: types
         :link-type: doc
         :text-align: center
         :shadow: md

         Type definitions, data models, and schema utilities for configuration management and type conversion between formats.

   .. grid-item-card:: :octicon:`graph;1.5em`  Call Graphs
         :link: call_graphs
         :link-type: doc
         :text-align: center
         :shadow: md

         Visual representation of function call relationships and dependencies within the eodag codebase for development reference.
