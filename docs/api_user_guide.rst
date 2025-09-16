.. _api_user_guide:

API User Guide
=====================

The API user guide introduces all the features offered by ``eodag`` through its API and
explains how they should be used. Each page is a `Jupyter notebook <https://jupyter.org/>`_ that can be viewed online,
run online thanks to `Binder <https://mybinder.readthedocs.io/en/latest/>`_,
or run locally after being downloaded (see how to :ref:`install_notebooks`).

.. toctree::
   :hidden:

   notebooks/api_user_guide/1_providers_products_available.ipynb
   notebooks/api_user_guide/2_configuration.ipynb
   notebooks/api_user_guide/3_search.ipynb
   notebooks/api_user_guide/4_queryables.ipynb
   notebooks/api_user_guide/5_serialize_deserialize.ipynb
   notebooks/api_user_guide/6_crunch.ipynb
   notebooks/api_user_guide/7_download.ipynb
   notebooks/api_user_guide/8_post_process.ipynb
   notebooks/tutos/tuto_stac_client.ipynb

.. grid:: 1 2 2 3
   :gutter: 4

   .. grid-item-card:: :octicon:`database;1.5em`  Providers & Products types
      :link: notebooks/api_user_guide/1_providers_products_available
      :link-type: doc
      :text-align: center
      :shadow: md

      Discover available data providers and explore the different product types accessible through the API.

   .. grid-item-card:: :octicon:`gear;1.5em`  Configuration
         :link: notebooks/api_user_guide/2_configuration
         :link-type: doc
         :text-align: center
         :shadow: md

         Learn how to configure your data providers, set their priorities, and configure logging to optimize your workflow.

   .. grid-item-card:: :octicon:`search;1.5em`  Search
         :link: notebooks/api_user_guide/3_search
         :link-type: doc
         :text-align: center
         :shadow: md

         Master advanced search techniques: pagination, filters, custom parameters, and error handling for efficient data discovery.

   .. grid-item-card:: :octicon:`list-unordered;1.5em`  Queryables
         :link: notebooks/api_user_guide/4_queryables
         :link-type: doc
         :text-align: center
         :shadow: md

         Explore available query parameters to refine your searches and discover new filtering criteria for better results.

   .. grid-item-card:: :octicon:`file-code;1.5em`  Serialize / Deserialize
         :link: notebooks/api_user_guide/5_serialize_deserialize
         :link-type: doc
         :text-align: center
         :shadow: md

         Efficiently manage serialization and deserialization of your search results to save and reuse them across sessions.

   .. grid-item-card:: :octicon:`filter;1.5em`  Crunch
         :link: notebooks/api_user_guide/6_crunch
         :link-type: doc
         :text-align: center
         :shadow: md

         Post-search filter your products using various criteria: temporal, geographical, properties, and online availability.

   .. grid-item-card:: :octicon:`download;1.5em`  Download
         :link: notebooks/api_user_guide/7_download
         :link-type: doc
         :text-align: center
         :shadow: md

         Download your products with progress bars, quicklooks management, and efficient assets handling.

   .. grid-item-card:: :octicon:`table;1.5em`  Post-processing
         :link: notebooks/api_user_guide/8_post_process
         :link-type: doc
         :text-align: center
         :shadow: md

         Post-process your data: downloaded file path management, Sentinel formats, and xarray conversion with eodag-cube.

   .. grid-item-card:: :octicon:`book;1.5em`  STAC Client Tutorial
         :link: notebooks/tutos/tuto_stac_client
         :link-type: doc
         :text-align: center
         :shadow: md

         Learn how to use EODAG as a STAC client to access data through STAC APIs and static catalogs.
