Migration guide
----------------

Full changelog available in `Release history <changelog.html>`_.

v5.0.0
++++++

Order response mappings
~~~~~~~~~~~~~~~~~~~~~~~

In download plugin configurations, ``order_on_response``, ``order_status`` and
``order_status.on_success`` now distinguish two mappings:

* ``asset_mapping`` updates the ordered asset directly. It is singular and is not
  keyed by asset name. Use ``href`` instead of ``eodag:download_link`` and
  ``order:id`` instead of ``eodag:order_id``, including in placeholders such as
  ``{order:id}``.
* ``metadata_mapping`` only updates product properties, such as ``created``,
  ``published``, ``updated``, ``ecmwf:dataset`` and ``eodag:request_params``.

Both mappings are parsed together, so placeholders can reference fields from either
mapping. Keys beginning with ``_`` are parse-only helpers; they and unavailable
values are not stored. Order IDs are stored as strings.

Custom provider configurations must move asset order fields from
``metadata_mapping`` to ``asset_mapping``. Legacy order configuration semantics
are no longer supported.

For example::

    order_on_response:
      asset_mapping:
        order:id: $.json.jobID
        eodag:status_link: https://example.test/jobs/{order:id}
    order_status:
      metadata_mapping:
        created: $.json.created
      on_success:
        asset_mapping:
          href: $.json.asset.href

Asset order status
~~~~~~~~~~~~~~~~~~

Order state is stored only in the asset's ``order:status`` field, using
``orderable``, ``ordered``, ``succeeded`` or ``failed``. Raw provider status and
progress are no longer stored as ``eodag:order_status`` or ``eodag:order_percent``.
Use parse-only ``_order_status`` and ``_order_percent`` in order response mappings,
and update ``success`` / ``error`` matching to reference ``_order_status``.

An asset becomes ``failed`` when the provider reports an order error, rejects an
order with HTTP 400, or the successful order result cannot be parsed (including
an XML search returning zero or multiple results). Authentication, quota, timeout
and transient request errors do not mark an asset failed. Follow-up processing
must finish before the asset becomes ``succeeded``.

Failed assets are not ordered again automatically. Status polling can still
report the provider error; search again to obtain a fresh asset before retrying
the order. There is no compatibility conversion for legacy order configurations.

Product location proxies
~~~~~~~~~~~~~~~~~~~~~~~~

Reading or assigning ``EOProduct.location`` and ``EOProduct.remote_location`` now
emits ``DeprecationWarning``. Both return ``None`` instead of an empty string when
the ``download_link`` asset or its URL is missing. These properties no longer keep
independent product-level location state.

Use ``product.assets["download_link"]["href"]`` for the remote URL and
``product.assets["download_link"]["file:local_path"]`` for the downloaded filesystem
path. ``product.assets["download_link"].location`` returns the local path as a URI,
falling back to ``href``. Setting the deprecated ``location`` to a local URI writes
``file:local_path``; setting it to a remote URL updates ``href`` and clears the local
path. Setting ``remote_location`` updates ``href`` without clearing the local path.

Products without a ``download_link`` asset, including multi-asset downloads, have
no product-level location. Read local paths from their individual assets and use
the download method's returned path for the output directory. New saved results
preserve URLs and local paths in assets; v5 still converts the legacy
``eodag:download_link`` product property when importing old saved results.

v4.0.0a2
++++++++

Collections objects
~~~~~~~~~~~~~~~~~~~

:meth:`~eodag.api.core.EODataAccessGateway.list_collections` and
:meth:`~eodag.api.core.EODataAccessGateway.guess_collection` now return
:class:`~eodag.api.collection.CollectionsList` instances (lists of
:class:`~eodag.api.collection.Collection` objects) instead of list of dictionaries and list of strings respectively.

v4.0.0a1
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
  * - ``productInfo``
    - ``eodag:product_info``
  * - ``productPath``
    - ``eodag:product_path``
  * - ``requestParams``
    - ``eodag:request_params``
  * - ``searchLink``
    - ``eodag:search_link``
  * - ``tilePath``
    - ``eodag:tile_path``
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

Check latest `CLI User Guide <cli_user_guide.rst>`_ for complete guidelines.

.. list-table::
  :header-rows: 1

  * - v3.x.x Command and options
    - v4.x.x Command and options
  * - ``eodag search -p, --productType TEXT``
    - ``eodag search -c, --collection TEXT``
  * - ``eodag search --query provider=TEXT``
    - ``eodag search -p, --provider TEXT``
  * - ``eodag search -i, --instrument TEXT``
    - ``eodag search --instruments TEXT``
  * - ``eodag search -P, --platform TEXT``
    - ``eodag search --constellation TEXT``
  * - ``eodag search -t, --platformSerialIdentifier TEXT``
    - ``eodag search --platform TEXT``
  * - ``eodag search -c, --cloudCover INTEGER RANGE``
    - ``eodag search --cloud-cover INTEGER RANGE``
  * - ``eodag search -L, --processingLevel TEXT``
    - ``eodag search --processing-level TEXT``
  * - ``eodag search -S, --sensorType TEXT``
    - ``eodag search --sensor-type TEXT``
  * - ``eodag list -i, --instrument TEXT``
    - ``eodag list --instruments TEXT``
  * - ``eodag list -P, --platform TEXT``
    - ``eodag list --constellation TEXT``
  * - ``eodag list -t, --platformSerialIdentifier TEXT``
    - ``eodag list --platform TEXT``
  * - ``eodag list -L, --processingLevel TEXT``
    - ``eodag list --processing-level TEXT``
  * - ``eodag list -S, --sensorType TEXT``
    - ``eodag list --sensor-type TEXT``


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
<https://cs-si.github.io/eodag/eodag/resources/ext_collections.json>`_. See `API user guide /  Providers and products
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
