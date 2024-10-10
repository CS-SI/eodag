.. _add_provider:

Add a Provider
==============

``eodag`` provides a set of `plugins <plugins.rst>`_ which don't know anything about the
providers themselves, they just implement generic methods required to talk to different kinds of data catalog. For instance:

* :class:`~eodag.plugins.search.qssearch.QueryStringSearch`: Search plugin that implements a search protocol that relies on `query strings <https://en.wikipedia.org/wiki/Query_string>`_
* :class:`~eodag.plugins.authentication.header.HTTPHeaderAuth`: Authentication plugin that implements `HTTP authentication using headers <https://developer.mozilla.org/en-US/docs/Web/HTTP/Authentication>`_
* :class:`~eodag.plugins.download.http.HTTPDownload`: Download plugin that implements download over `HTTP protocol <https://en.wikipedia.org/wiki/Hypertext_Transfer_Protocol>`_

Dynamically add a new provider
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can dynamically add a new provider, from your python code using :meth:`~eodag.api.core.EODataAccessGateway.add_provider`
or :meth:`~eodag.api.core.EODataAccessGateway.update_providers_config` methods.
Check `Python API User Guide / Add-or-update-a-provider <notebooks/api_user_guide/3_configuration.ipynb#Add-or-update-a-provider>`_ for guidelines.

Configure a new provider
^^^^^^^^^^^^^^^^^^^^^^^^

The simplest way to add a new provider is to **use existing plugins**. This approach requires to
provide the new provider's configuration in a ``YAML`` format. The following example shows how to add a new STAC provider:

.. code-block::

   another_earth_search:
      search:
         type: StacSearch
         api_endpoint: https://earth-search.aws.element84.com/v1/search
         need_auth: false
      products:
         S2_MSI_L1C:
            productType: sentinel-2-l1c
         GENERIC_PRODUCT_TYPE:
            productType: '{productType}'
      download:
         type: AwsDownload
      auth:
         type: AwsAuth
         credentials:
            aws_access_key_id: PLEASE_CHANGE_ME
            aws_secret_access_key: PLEASE_CHANGE_ME

It configures the following existing plugins: :class:`~eodag.plugins.search.qssearch.StacSearch` (search),
:class:`~eodag.plugins.authentication.aws_auth.AwsAuth` (authentication) and :class:`~eodag.plugins.download.aws.AwsDownload` (download).

Each plugin configuration is inserted following the appropriate plugin topic key:

- ``search`` for `search plugins <plugins_reference/search.rst>`_
- ``download`` for `download plugins <plugins_reference/download.rst>`_
- ``auth``, ``search_auth``, or ``download_auth`` for `authentication plugins <plugins_reference/auth.rst>`_
- ``api`` for `api plugins <plugins_reference/api.rst>`_

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


Provider configuration
^^^^^^^^^^^^^^^^^^^^^^

The plugin structure is reflected in the internal providers configuration file. Here is a sample::

   provider_name:
      priority: 1
      products:
         # List of supported product types
         # This is a mapping containing all the information required by the search plugin class to perform its job.
         # The mapping is available in the config attribute of the search plugin as config['products']
         S2_MSI_L1C:
            a-config-key-needed-by-search-plugin-to-search-this-product-type: value
            another-config-key: another-value
            # Whether this product type is partially supported by this provider (the provider does not contain all the
            # products of this type)
            partial: True
         ...
      search:
         plugin: CustomSearchPluginClass
         api_endpoint: https://mandatory.config.key/
         a-key-conf-used-by-the-plugin-class-init-method: value
         another-random-key: random-value
         # A mapping between the search result of the provider and the eodag way of describing EO products (the keys are
         # the same as in the OpenSearch specification)
         metadata_mapping:
            ...
         ...
      download:
         plugin: CustomDownloadPlugin
         # Same as with search for random config keys as needed by the plugin class
         ...
      auth:
         plugin: CustomAuthPlugin
         # Same as with search for random config keys as needed by the plugin class
         ...

Note however, that for a provider which already has a Python library for accessing its products, the configuration
varies a little bit. It does not have the 'search' and 'download' keys. Instead, there is a single 'api' key like this::

   provider_name:
      ...
      api:
         plugin: ApiPluginClassName
         ...
