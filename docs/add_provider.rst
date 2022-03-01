.. _add_provider:

Add a Provider
==============

``eodag`` provides a set of `plugins <plugins.rst>`_ which don't know anything about the
providers themselves, they just implement generic methods required to talk to different kinds of data catalog. For instance:

* :class:`~eodag.plugins.search.qssearch.QueryStringSearch`: Search plugin that implements a search protocol that relies on `query strings <https://en.wikipedia.org/wiki/Query_string>`_
* :class:`~eodag.plugins.authentication.header.HTTPHeaderAuth`: Authentication plugin that implements `HTTP authentication using headers <https://developer.mozilla.org/en-US/docs/Web/HTTP/Authentication>`_
* :class:`~eodag.plugins.download.http.HTTPDownload`: Download plugin that implements download over `HTTP protocol <https://en.wikipedia.org/wiki/Hypertext_Transfer_Protocol>`_

Configure a new provider
^^^^^^^^^^^^^^^^^^^^^^^^

The simplest way to add a new provider is to **configure existing plugins**. This approach requires to
provide the new provider's configuration in a ``YAML`` format. The following example, extracted from
the `STAC client page <notebooks/tutos/tuto_stac_client.ipynb#stac-api>`_, shows how to add a new STAC provider:

.. code-block::

   tamn:
      search:
         type: StacSearch
         api_endpoint: https://tamn.snapplanet.io/search
      products:
         S2_MSI_L1C:
               productType: S2
         GENERIC_PRODUCT_TYPE:
               productType: '{productType}'
      download:
         type: AwsDownload
         base_uri: https://tamn.snapplanet.io
         flatten_top_dirs: True
      auth:
         type: AwsAuth
         credentials:
               aws_access_key_id: PLEASE_CHANGE_ME
               aws_secret_access_key: PLEASE_CHANGE_ME

It configures the following existing plugins: :class:`~eodag.plugins.search.qssearch.StacSearch` (search),
:class:`~eodag.plugins.authentication.aws_auth.AwsAuth` (authentication) and :class:`~eodag.plugins.download.aws.AwsDownload` (download).

Of course, it is also necessary to know how to configure these plugins (which parameters they take, what values they can have, etc.).
You can get some inspiration from the *Providers pre-configuration* section by analysing how ``eodag`` configures the providers it comes installed with.

Add more plugins
^^^^^^^^^^^^^^^^

``eodag`` is a plugin-oriented framework which means it can be easily extended. If the plugins it offers are not sufficient for your
own needs (i.e. getting data from a provider not supported by ``eodag``), you should then write your own plugins (possibly by extending one of provided by ``eodag``)
and configure them. What you are the most likely to be willing to do is either to develop a new `Search <plugins_reference/search.rst>`_ plugin or an
`Api <plugins_reference/api.rst>`_ plugin (e.g. to create an interface with another program).

`eodag-sentinelsat <https://github.com/CS-SI/eodag-sentinelsat>`_ is a good example of an Api plugin. It creates an interface with the
`sentinalsat <https://github.com/sentinelsat/sentinelsat>`_ library to search and download products from `SciHub <https://scihub.copernicus.eu/>`_.

See more details about how to create a new plugin in :ref:`this dedicated section <creating_plugins>`.

Providers pre-configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^

All the providers are pre-configured in ``eodag`` in a YAML file.
Click on the link below to display its full content.

.. raw:: html

   <details>
   <summary><a>providers.yml</a></summary>

.. include:: ../eodag/resources/providers.yml
   :start-line: 17
   :code: yaml

.. raw:: html

   </details>

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

The following tables list the parameters supported by providers, and if they are queryable or not.

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
