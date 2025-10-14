Migration guide
----------------

Full changelog available in `Release history <changelog.html>`_.

v4.0.0b1
++++++++

STAC-Formatted API and Results
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Migration from `OGC OpenSearch Extension for Earth Observation <https://docs.ogc.org/is/13-026r9/13-026r9.html>`_
to `SpatioTemporal Asset Catalog (STAC) <https://github.com/radiantearth/stac-spec>`_ for data representation.

This impacts both the API and CLI.

Renamed properties
^^^^^^^^^^^^^^^^^^

The list starts with common STAC properties, then lists STAC extensions properties, and finally EODAG-specific
properties.

.. list-table::
  :header-rows: 1

  * - v3.x.x property
    - v4.x.x property
  * - ``productType``
    - ``collection``
  * - ``startTimeFromAscendingNode``
    - ``start_datetime``
  * - ``completionTimeFromAscendingNode``
    - ``end_datetime``
  * - ``abstract``
    - ``description``
  * - ``accessConstraint``
    - ``license``
  * - ``keyword``
    - ``keywords``
  * - ``creationDate``
    - ``created``
  * - ``modificationDate``
    - ``updated``
  * - ``organisationName``
    - ``providers: [{"roles": ["producer"]}]``
  * - ``platform``
    - ``constellation``
  * - ``platformSerialIdentifier``
    - ``platform``
  * - ``instrument``
    - ``instruments[]``
  * - ``resolution``
    - ``gsd``
  * - ``cloudCover``
    - ``eo:cloud_cover``
  * - ``snowCover``
    - ``eo:snow_cover``
  * - ``tileIdentifier``
    - ``grid:code``
  * - ``gridSquare``
    - ``mgrs:grid_square``
  * - ``latitudeBand``
    - ``mgrs:latitude_band``
  * - ``utmZone``
    - ``mgrs:utm_zone``
  * - ``storageStatus``
    - ``order:status``
  * - ``processingLevel``
    - ``processing:level``
  * - ``acquisitionType``
    - ``product:acquisition_type``
  * - ``productType``
    - ``product:type`` or ``collection``
  * - ``timeliness``
    - ``product:timeliness``
  * - ``dopplerFrequency``
    - ``sar:frequency_band``
  * - ``polarisationChannels`` or ``polarizationChannels``
    - ``sar:polarizations[]``
  * - ``sensorMode``
    - ``sar:instrument_mode``
  * - ``swathIdentifier``
    - ``sar:instrument_mode`` or ``sar:beam_ids[] (geodes)``
  * - ``cycleNumber``
    - ``sat:orbit_cycle``
  * - ``orbitDirection``
    - ``sat:orbit_state``
  * - ``orbitNumber``
    - ``sat:absolute_orbit``
  * - ``relativeOrbitNumber``
    - ``sat:relative_orbit``
  * - ``doi``
    - ``sci:doi``
  * - ``illuminationAzimuthAngle``
    - ``view:sun_azimuth``
  * - ``illuminationElevationAngle``
    - ``view:sun_elevation``
  * - ``illuminationZenithAngle``
    - ``view:incidence_angle``
  * - ``productVersion``
    - ``version``
  * - ``defaultGeometry``
    - ``eodag:default_geometry``
  * - ``downloadLink``
    - ``eodag:download_link``
  * - ``mtdDownloadLink``
    - ``eodag:mtd_download_link``
  * - ``sensorType``
    - ``eodag:sensor_type``
  * - ``quicklook``
    - ``eodag:quicklook``
  * - ``thumbnail``
    - ``eodag:thumbnail``
  * - ``combinedOrderId``
    - ``eodag:combined_order_id``
  * - ``downloadId``
    - ``eodag:download_id``
  * - ``message``
    - ``eodag:order_message``
  * - ``orderId``
    - ``eodag:order_id``
  * - ``orderStatus``
    - ``eodag:order_status``
  * - ``orderStatusLink``
    - ``eodag:status_link``
  * - ``percent``
    - ``eodag:percent``
  * - ``requestParams``
    - ``eodag:request_params``
  * - ``searchLink``
    - ``eodag:search_link``
  * - ``providerProductType``
    - ``_collection`` or ``provider_collection``

Python API updates
^^^^^^^^^^^^^^^^^^

All product-types related classes and methods have been renamed with collections.

.. list-table::
  :header-rows: 1

  * - v3.x.x Python API
    - v4.x.x Python API
  * - ``EODataAccessGateway.available_providers(product_type=None, ...)``
    - :meth:`~eodag.api.core.EODataAccessGateway.available_providers` ``(collection=None, ...)``
  * - ``EODataAccessGateway.discover_product_types()``
    - :meth:`~eodag.api.core.EODataAccessGateway.discover_collections`
  * - ``EODataAccessGateway.fetch_product_types_list()``
    - :meth:`~eodag.api.core.EODataAccessGateway.fetch_collections_list`
  * - ``EODataAccessGateway.guess_product_type()``
    - :meth:`~eodag.api.core.EODataAccessGateway.guess_collection`
  * - ``EODataAccessGateway.list_product_types()``
    - :meth:`~eodag.api.core.EODataAccessGateway.list_collections`
  * - ``EODataAccessGateway.update_product_types_list()``
    - :meth:`~eodag.api.core.EODataAccessGateway.update_collections_list`
  * - ``EOProduct.product_type``
    - :attr:`~eodag.api.product._product.EOProduct.collection`

CLI updates
^^^^^^^^^^^

.. list-table::
  :header-rows: 1

  * - v3.x.x Command and options
    - v4.x.x Command and options
  * - ``eodag search -p, --productType TEXT``
    - ``eodag search -c, --collection TEXT``
  * - ``eodag search -i, --instruments TEXT``
    - ``eodag search -i, --instrument TEXT``

Environment variables renamed
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Check updated list of environment variables in `Getting started / Configure EODAG / environment variables
<getting_started_guide/configuration.html#core-configuration-using-environment-variables>`_.

.. list-table::
  :header-rows: 1

  * - v3.x.x environment variable
    - v4.x.x environment variable
  * - ``EODAG_PRODUCT_TYPES_CFG_FILE``
    - ``EODAG_COLLECTIONS_CFG_FILE``
  * - ``EODAG_EXT_PRODUCT_TYPES_CFG_FILE``
    - ``EODAG_EXT_COLLECTIONS_CFG_FILE``
  * - ``EODAG_STRICT_PRODUCT_TYPES``
    - ``EODAG_STRICT_COLLECTIONS``

Files renamed
^^^^^^^^^^^^^

.. list-table::
  :header-rows: 1

  * - v3.x.x file path
    - v4.x.x file path
  * - ``docs/_static/product_types_information.csv``
    - ``docs/_static/collections_information.csv``
  * - ``docs/_static/eodag_fetch_product_types.png``
    - ``docs/_static/eodag_fetch_collections.png``
  * - ``docs/add_product_type.rst``
    - ``docs/add_collection.rst``
  * - ``docs/getting_started_guide/product_types.rst``
    - ``docs/getting_started_guide/collections.rst``
  * - ``eodag/resources/product_types.yml``
    - ``eodag/resources/collections.yml``
  * - ``eodag/resources/ext_product_types.json``
    - ``eodag/resources/ext_collections.json``
  * - ``tests/resources/ext_product_types.json``
    - ``tests/resources/ext_collections.json``
  * - ``tests/resources/ext_product_types_free_text_search.json``
    - ``tests/resources/ext_collections_free_text_search.json``
  * - ``tests/resources/file_product_types_modes.yml``
    - ``tests/resources/file_collections_modes.yml``
  * - ``tests/resources/file_product_types_override.yml``
    - ``tests/resources/file_collections_override.yml``
  * - ``tests/resources/stac/product_type_queryables.json``
    - ``tests/resources/stac/collection_queryables.json``
  * - ``utils/product_types_information_to_csv.py``
    - ``utils/collections_information_to_csv.py``

External collections reference configuration file is now hosted as
`https://cs-si.github.io/eodag/eodag/resources/ext_collections.json
<https://cs-si.github.io/eodag/eodag/resources/ext_collections.jsons>`_. See `API user guide /  Providers and products
/ Collections discovery <notebooks/api_user_guide/1_providers_products_available.ipynb#Collections-discovery>`_ for more
information.

v3.0.0b3
++++++++

* :meth:`~eodag.api.core.EODataAccessGateway.download` / :class:`~eodag.types.download_args.DownloadConf` parameters
  ``outputs_prefix`` and ``outputs_extension`` renamed to ``output_dir`` and ``output_extension``.

v3.0.0b1
++++++++

* :meth:`~eodag.api.core.EODataAccessGateway.search` method now returns only a
  :class:`~eodag.api.search_result.SearchResult` instead of a 2 values tuple. It can optionally store the estimated
  total number of products in ``SearchResult.number_matched`` if the method is called with ``count=True``
  (``False`` by  default).

  * **eodag < 3.0.0b1 syntax:**

    .. code-block:: python

      search_results, number_matched = dag.search(productType="S2_MSI_L1C")

    |  Traceback (most recent call last):
    |    File "<stdin>", line 1, in <module>
    |  ValueError: too many values to unpack (expected 2)

  * **eodag >= 3.0.0b1 syntax:**

    .. code-block:: python

      search_results = dag.search(productType="S2_MSI_L1C")

* Packaging refactoring and new `optional dependencies
  <getting_started_guide/install.html#optional-dependencies>`_. EODAG default
  installs with a minimal set of dependencies.
  New sets of extra requirements are: ``eodag[all]``, ``eodag[all-providers]``, ``eodag[ecmwf]``, ``eodag[usgs]``,
  ``eodag[csw]``, ``eodag[server]``, ``eodag[stubs]``. Previous existing sets of extra requirements are also kept:
  ``eodag[notebook]``, ``eodag[tutorials]``, ``eodag[dev]``, ``eodag[docs]``.

  .. code-block:: sh

    # install eodag with all available providers supported
    pip install "eodag[all-providers]"

v2.0b1
++++++

- STAC API compliant REST server
- Common configuration for STAC providers

v1.0
++++

- Adds product type search functionality
- The cli arguments are now fully compliant with opensearch geo(bbox)/time extensions
