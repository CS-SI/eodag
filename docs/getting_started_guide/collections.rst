.. collections:

Collections
===========

``eodag`` maintains a catalog of EO collections including some of their metadata. Each collection is
given an identifier (e.g. ``S2_MSI_L2A``) that should then be used by users to search for this kind
of product.

This catalog is saved as a YAML file that can be viewed `here <https://github.com/CS-SI/eodag/blob/develop/eodag/resources/collections.yml>`_.
The example below shows the catalog entry for the collection *Sentinel 2 Level-2A*.

.. code-block:: yaml

   S2_MSI_L2A:
     description: |
       The Level-2A product provides Bottom Of Atmosphere (BOA) reflectance images derived from the associated Level-1C
       products. Each Level-2A product is composed of 100x100 km2 tiles in cartographic geometry (UTM/WGS84 projection).
     instruments: ["MSI"]
     constellation: SENTINEL2
     platform: S2A,S2B
     processing:level: L2
     eodag:sensor_type: OPTICAL
     license: other
     title: SENTINEL2 Level-2A
     extent: {"spatial": {"bbox": [[-180.0, -90.0, 180.0, 90.0]]}, "temporal": {"interval": [["2018-03-26T00:00:00Z", null]]}}

This collection catalog can be obtained from the API:

.. code-block:: python

   from eodag import EODataAccessGateway
   dag = EODataAccessGateway()
   dag.list_collections()

Or from the CLI:

.. code-block:: console

   eodag list

The catalog is used in different ways by ``eodag``:

* Collections made available for a given provider (search/download) are listed in its configuration.
  This allows to unify the collection identifier among the providers.

  .. code-block:: console

     eodag search --conf peps_conf.yml -p S2_MSI_L2A
     eodag search --conf creodias_conf.yml -p S2_MSI_L2A

* Some of the metadata mapped can be used to search for products without specifying any identifier.
  In other terms, this catalog can be queried.
  When a search is made, the search criteria provided by the user are first used to search for the
  collection that best matches the criteria. The actual search is then performed with this collection.

  .. code-block:: console

     eodag search --sensor-type OPTICAL --processing-level L2

  .. code-block:: python

     from eodag import EODataAccessGateway
     search_criteria = {"eodag:sensor_type": "OPTICAL", "processing:level": "L2"}
     dag = EODataAccessGateway()
     dag.search(**search_criteria)

* The metadata stored in this file are sometimes added to the :attr:`properties` attribute to an
  :class:`~eodag.api.product._product.EOProduct`. It depends on whether the metadata are
  already mapped or not for the provider used to search for products.

The catalog is saved as a YAML file and distributed alongside ``eodag``.
Click on the link below to display its full content.

.. raw:: html

   <details>
   <summary><a>collections.yml</a></summary>

.. include:: ../../eodag/resources/collections.yml
   :start-line: 19
   :code: yaml

.. raw:: html

   </details>
   </br>

The following table lists the metadata parameters of the collections, and shows whether these collections are
available for providers or not.

Collections information (`CSV <../_static/collections_information.csv>`__)
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

.. raw:: html

   <p id="column_links"></p>
   <span id="table_0_span">

.. csv-table::
   :file: ../_static/collections_information.csv
   :header-rows: 1
   :stub-columns: 1
   :class: datatable

.. raw:: html

   </span>
