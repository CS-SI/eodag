.. _api_user_guide:

Python API User Guide
=====================

The Python API user guide introduces all the features offered by ``eodag`` through its API and
explains how they should be used. Each page is a `Jupyter notebook <https://jupyter.org/>`_ that can be viewed online,
run online thanks to `Binder <https://mybinder.readthedocs.io/en/latest/>`_,
or run locally after being downloaded (see how to :ref:`install_notebooks`).

.. note::

   You should be registered to *PEPS* to run the notebooks that download data.
   See :ref:`configure` and :ref:`register`.

.. warning::

   The `Download <notebooks/api_user_guide/8_download.ipynb>`_ notebook downloads a few
   EO products. These products are usually in the order of 700-900 Mo, make sure you have a
   decent internet connection if you plan to run the notebooks.

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

   .. grid-item-card:: Providers & Products
      :link: notebooks/api_user_guide/1_providers_products_available
      :link-type: doc
      :text-align: center
      :shadow: md

      Discover available data providers and explore the different types of Earth observation products accessible through the API.

   .. grid-item-card:: Configuration
      :link: notebooks/api_user_guide/2_configuration
      :link-type: doc
      :text-align: center
      :shadow: md

      Learn how to configure your data providers, set their priorities, and configure logging to optimize your workflow.

   .. grid-item-card:: Search
      :link: notebooks/api_user_guide/3_search
      :link-type: doc
      :text-align: center
      :shadow: md

      Master advanced search techniques: pagination, filters, custom parameters, and error handling for efficient data discovery.

   .. grid-item-card:: Queryables
      :link: notebooks/api_user_guide/4_queryables
      :link-type: doc
      :text-align: center
      :shadow: md

      Explore available query parameters to refine your searches and discover new filtering criteria for better results.

   .. grid-item-card:: Serialize / Deserialize
      :link: notebooks/api_user_guide/5_serialize_deserialize
      :link-type: doc
      :text-align: center
      :shadow: md

      Efficiently manage serialization and deserialization of your search results to save and reuse them across sessions.

   .. grid-item-card:: Crunch
      :link: notebooks/api_user_guide/6_crunch
      :link-type: doc
      :text-align: center
      :shadow: md

      Filter and analyze your products using various criteria: temporal, geographical, properties, and online availability.

   .. grid-item-card:: Download
      :link: notebooks/api_user_guide/7_download
      :link-type: doc
      :text-align: center
      :shadow: md

      Download your Earth observation products with progress bars, quicklooks management, and efficient asset handling.

   .. grid-item-card:: Post-processing
      :link: notebooks/api_user_guide/8_post_process
      :link-type: doc
      :text-align: center
      :shadow: md

      Process your data after download: file path management, Sentinel formats, and integration with eodag-cube.

   .. grid-item-card:: STAC Client Tutorial
      :link: notebooks/tutos/tuto_stac_client
      :link-type: doc
      :text-align: center
      :shadow: md

      Learn how to use STAC clients to access data catalogs through APIs and static catalog implementations.
