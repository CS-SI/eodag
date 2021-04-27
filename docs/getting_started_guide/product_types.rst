.. _product_types:

EO product types
================

``eodag`` maintains a catalog of EO product types including some of their metadata. Each product type is
given an identifier (e.g. ``S2_MSI_L2A``) that should then be used by users to search for this kind
of product.

This catalog is saved as a YAML file that can be viewed `here <https://github.com/CS-SI/eodag/blob/develop/eodag/resources/product_types.yml>`_.
The example below shows the catalog entry for the product type *Sentinel 2 Level-2A*.

.. code-block:: yaml

   S2_MSI_L2A:
     abstract: |
       The Level-2A product provides Bottom Of Atmosphere (BOA) reflectance images derived from the associated Level-1C
       products. Each Level-2A product is composed of 100x100 km2 tiles in cartographic geometry (UTM/WGS84 projection).
     instrument: MSI
     platform: SENTINEL2
     platformSerialIdentifier: S2A,S2B
     processingLevel: L2
     sensorType: OPTICAL
     license: proprietary
     title: SENTINEL2 Level-2A
     missionStartDate: "2015-06-23T00:00:00Z"

This product type catalog can be obtained from the API:

.. code-block:: python

   from eodag import EODataAccessGateway
   dag = EODataAccessGateway()
   dag.list_product_types()

Or from the CLI:

.. code-block:: console

   eodag list

The catalog is used in different ways by ``eodag``:

* Product types made available for a given provider (search/download) are listed in its configuration.
  This allows to unify the product type identifier among the providers.

  .. code-block:: console

     eodag search --conf peps_conf.yml -p S2_MSI_L2A
     eodag search --conf sobloo_conf.yml -p S2_MSI_L2A

* Some of the metadata mapped can be used to search for products without specifying any identifier.
  In other terms, this catalog can be queried.
  When a search is made, the search criteria provided by the user are first used to search for the
  product type that best matches the criteria. The actual search is then performed with this product type.

  .. code-block:: console

     eodag search --sensorType OPTICAL --processingLevel L2

  .. code-block:: python

     from eodag import EODataAccessGateway
     dag = EODataAccessGateway()
     dag.search(sensorType="OPTICAL", processingLevel="L2")

* The metadata stored in this file are sometimes added to the :attr:`properties` attribute to an
  :class:`~eodag.api.product._product.EOProduct`. It depends on whether the metadata are
  already mapped or not for the provider used to search for products.

The catalog is saved as a YAML file and distributed alongside ``eodag``.
Click on the link below to display its full content.

.. raw:: html

   <details>
   <summary><a>product_types.yml</a></summary>

.. include:: ../../eodag/resources/product_types.yml
   :start-line: 19
   :code: yaml

.. raw:: html

   </details>
