.. _params_mapping:

Parameters mapping
==================

`eodag` interacts with various data providers, each having its own way of naming and structuring
metadata parameters. To provide a unified interface for users, `eodag` maps these provider metadata parameters to a common model.

Parameters mapping
^^^^^^^^^^^^^^^^^^

EODAG maps each provider's specific metadata parameters to a common model using
`OGC OpenSearch Extension for Earth Observation <http://docs.opengeospatial.org/is/13-026r9/13-026r9.html>`_.
Extra parameters having no equivalent in this model are mapped as is.

Depending on the provider, some parameters are queryable or not. This is configured in each configuration file located in the ``eodag/resources/providers/`` directory.

* If a parameter metadata-mapping is a list, the first element will help constructing the query \
  (using `format() <https://docs.python.org/fr/3/library/string.html#string.Formatter.format>`_), and the 2nd will \
  help extracting its values from the query result (using `jsonpath <https://github.com/h2non/jsonpath-ng>`_)
* If a parameter metadata-mapping is a string, it will not be queryable and this string will help extracting its \
  values from the query result (using `jsonpath <https://github.com/h2non/jsonpath-ng>`_).

.. code-block::

   some_provider:
      search:
         metadata_mapping:
            queryableParameter:
               - 'this_is_query_string={queryableParameter}'
               - '$.jsonpath.in.result.to.parameter'
            nonQueryableParameter: '$.jsonpath.in.result.to.another_parameter'

Asset mappings
""""""""""""""

Search ``metadata_mapping`` builds product properties. Download URLs and order
state belong to assets, created by ``assets_mapping``. For example:

.. code-block:: yaml

   search:
      assets_mapping:
         download_link:
            href: $.properties.downloadUrl
            order:status: orderable
            eodag:order_link: $.properties.orderUrl

Each search asset mapping is parsed independently. Product metadata fields are
not implicit template variables: extract any values needed by an asset into
that asset's mapping. Keys beginning with ``_`` are temporary helpers and are
removed before assets are exposed. Literal JSON braces in templates must be
escaped as ``{{`` and ``}}``. For example:

.. code-block:: yaml

   search:
      assets_mapping:
         download_link:
            _id: $.id
            _qs: $.request
            eodag:order_link: 'https://example.test/order?{{"id": "{_id}", "request": {_qs#to_geojson}}}'
            order:status: orderable

Order response mappings
"""""""""""""""""""""""

Download configurations use singular ``asset_mapping`` in ``order_on_response``,
``order_status`` and ``order_status.on_success``. Unlike search
``assets_mapping``, it is not keyed by asset name: it updates the asset being
ordered. ``metadata_mapping`` updates only product properties.

.. code-block:: yaml

   download:
      order_on_response:
         asset_mapping:
            order:id: $.json.id
            eodag:status_link: 'https://example.test/jobs/{order:id}'
      order_status:
         asset_mapping:
            _order_status: $.json.status
            _order_percent: $.json.progress
         metadata_mapping:
            updated: $.json.updated
         success:
            _order_status: completed
         error:
            _order_status: rejected
         on_success:
            asset_mapping:
               href: $.json.downloadUrl

Asset and product mappings for an order response are parsed together, so
placeholders can reference either mapping. Helpers beginning with ``_`` and
unavailable values are not saved. Use ``_order_status`` for raw provider status
matching and ``_order_percent`` for progress logging, not persisted
``eodag:order_status`` or ``eodag:order_percent`` fields. EODAG manages the asset's
``order:status`` using ``orderable``, ``ordered``, ``succeeded`` and ``failed``.
``order:id`` is stored as a string. Legacy order configurations using
``metadata_mapping`` for asset fields, ``eodag:download_link`` or
``eodag:order_id`` must be migrated; they are not converted automatically.


Formatters
""""""""""

An :class:`~eodag.api.product._product.EOProduct` has a :attr:`~eodag.api.product._product.EOProduct.properties` attribute
which is built based on how its metadata are set in the provider configuration. For example::

   search:
      ...
      metadata_mapping:
         publicationDate: '{$.data.timestamp#to_iso_utc_datetime_from_milliseconds}'
         ...

Converters can be chained using ``#``. They are applied from left to right, passing
each result directly to the next converter. Chaining works both when building
search queries and when extracting metadata from JSON or XML results. For example:

.. code-block:: yaml

   platform:
      - '{{"platformSerialIdentifier": "{platform#replace_str(r"^sentinel-1([a-c])$", r"\1")#to_upper}"}}'
      - '{$.properties.metadata.platformSerialIdentifier#to_lower#replace_str(r"^([a-c])$", r"sentinel-1\1")}'

This maps ``sentinel-1a`` to ``A`` for a search and ``A`` back to ``sentinel-1a``
in returned metadata, likewise for ``b`` and ``c``. A ``#`` inside converter
arguments is treated as part of the argument, not as a chain separator. If a
value is ``None``, the remaining converters are skipped.

The following converters can be used to transform the values collected from the provider:

.. autofunction:: eodag.api.product.metadata_mapping.format_metadata


Queryables
""""""""""

The :meth:`~eodag.api.core.EODataAccessGateway.list_queryables` method will help you to dynamically check which
parameters are queryable for a given provider or collection.
See `Python API User Guide / Queryables <notebooks/api_user_guide/4_queryables.ipynb>`_
for more information and examples.
