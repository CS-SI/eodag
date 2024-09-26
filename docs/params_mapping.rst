.. _params_mapping:

Parameters mapping
==================


Parameters mapping
^^^^^^^^^^^^^^^^^^

EODAG maps each provider's specific metadata parameters to a common model using
`OGC OpenSearch Extension for Earth Observation <http://docs.opengeospatial.org/is/13-026r9/13-026r9.html>`_.
Extra parameters having no equivalent in this model are mapped as is.

Depending on the provider, some parameters are queryable or not. This is configured in `providers.yml`:

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


Formatters
""""""""""

An :class:`~eodag.api.product._product.EOProduct` has a :attr:`~eodag.api.product._product.EOProduct.properties` attribute
which is built based on how its metadata are set in the provider configuration. For example::

   search:
      ...
      metadata_mapping:
         publicationDate: '{$.data.timestamp#to_iso_utc_datetime_from_milliseconds}'
         ...

The following converters can be used to transform the values collected from the provider:

.. autofunction:: eodag.api.product.metadata_mapping.format_metadata


Queryables
""""""""""

The :meth:`~eodag.api.core.EODataAccessGateway.list_queryables` method will help you to dynamically check which
parameters are queryable for a given provider or product type.
See `Python API User Guide / Queryables <https://eodag.readthedocs.io/en/latest/notebooks/api_user_guide/4_search.html#Queryables>`_
for more information and examples.

The following static tables list the parameters supported by providers, and if they are queryable or not.

OpenSearch parameters (`CSV <_static/params_mapping_opensearch.csv>`__)
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

.. role:: green
.. csv-table::
   :file: _static/params_mapping_opensearch.csv
   :header-rows: 1
   :stub-columns: 1
   :class: params

Provider/eodag specific parameters (`CSV <_static/params_mapping_extra.csv>`__)
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

.. role:: green
.. csv-table::
   :file: _static/params_mapping_extra.csv
   :header-rows: 1
   :stub-columns: 1
   :class: params
