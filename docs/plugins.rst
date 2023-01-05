.. _plugins:

Plugins
=======

EODAG uses a two-level plugin system. *Plugin topics* are abstract interfaces for a specific functionality of EODAG
like *Search* or *Download*. EODAG providers are implementations of at least one plugin topic. The more plugin topics
are implemented by a provider, the more functionality of eodag are available for this provider.

Plugin Management
^^^^^^^^^^^^^^^^^

The plugin machinery is managed by one instance of :class:`~eodag.plugins.manager.PluginManager`. The instance manager knows
how to discover plugins at runtime, using `setuptools entry points mechanism <https://packaging.python.org/guides/creating-and-discovering-plugins/#using-package-metadata>`_.

Plugins Available
^^^^^^^^^^^^^^^^^

EODAG currently advertises 5 types of plugins: *Search*, *Download*, *Crunch*, *Authentication* and *Api*.

.. toctree::
   :maxdepth: 1

   plugins_reference/search
   plugins_reference/crunch
   plugins_reference/auth
   plugins_reference/download
   plugins_reference/api

The providers are implemented with a triplet of *Search/Authentication/Download* plugins or with an *Api* plugin:

+------------------+-------------------+--------------------------+----------------+
| Provider         | Search            | Authentication           | Download       |
+==================+===================+==========================+================+
| aws_eos          | PostJsonSearch    | AwsAuth                  | AwsDownload    |
+------------------+-------------------+--------------------------+----------------+
| theia            | QueryStringSearch | TokenAuth                | HTTPDownload   |
+------------------+-------------------+--------------------------+----------------+
| peps             | QueryStringSearch | GenericAuth              | HTTPDownload   |
+------------------+-------------------+--------------------------+----------------+
| sobloo           | QueryStringSearch | HTTPHeaderAuth           | HTTPDownload   |
+------------------+-------------------+--------------------------+----------------+
| creodias         | QueryStringSearch | KeycloakOIDCPasswordAuth | HTTPDownload   |
+------------------+-------------------+--------------------------+----------------+
| mundi            | QueryStringSearch | HTTPHeaderAuth           | S3RestDownload |
+------------------+-------------------+--------------------------+----------------+
| onda             | ODataV4Search     | GenericAuth              | HTTPDownload   |
+------------------+-------------------+--------------------------+----------------+
| astraea_eod      | StacSearch        | AwsAuth                  | AwsDownload    |
+------------------+-------------------+--------------------------+----------------+
| usgs_satapi_aws  | StacSearch        | AwsAuth                  | AwsDownload    |
+------------------+-------------------+--------------------------+----------------+
| earth_search     | StacSearch        | AwsAuth                  | AwsDownload    |
+------------------+-------------------+--------------------------+----------------+
| earth_search_cog | StacSearch        | None                     | HTTPDownload   |
+------------------+-------------------+--------------------------+----------------+
| earth_search_gcs | StacSearch        | AwsAuth                  | AwsDownload    |
+------------------+-------------------+--------------------------+----------------+
| usgs             | UsgsApi           | UsgsApi                  | UsgsApi        |
+------------------+-------------------+--------------------------+----------------+
| ecmwf            | EcmwfApi          | EcmwfApi                 | EcmwfApi       |
+------------------+-------------------+--------------------------+----------------+
| cop_ads          | CdsApi            | CdsApi                   | CdsApi         |
+------------------+-------------------+--------------------------+----------------+
| cop_cds          | CdsApi            | CdsApi                   | CdsApi         |
+------------------+-------------------+--------------------------+----------------+
| sara             | QueryStringSearch | GenericAuth              | HTTPDownload   |
+------------------+-------------------+--------------------------+----------------+

.. _creating_plugins:

Creating Plugins
^^^^^^^^^^^^^^^^

EODAG plugins can be separated from the core eodag package. They live in your Python site-packages as standalone Python
packages or modules, with eodag's specific entry points that will be looked at by the plugin manager to load plugins at
runtime. These entry points are: ``eodag.plugins.{topic}``, with possible values for ``topic`` being ``api``, ``search``,
``crunch``, ``auth`` and ``download``.

All you have to do to create eodag plugins is start a new Python project, add eodag as a dependancy to your project,
and then create the plugin type you want in Python module(s) by importing its base class from ``eodag.plugins.{topic}.base``
and subclassing it. Here is an example for an :class:`~eodag.plugins.apis.base.Api` plugin class located in a module
named ``your_package.your_module``:

.. code-block:: python

   from eodag.plugins.apis.base import Api

   class SampleApiPlugin(Api):

      def query(self):
         pass

      def download(self):
         pass

Then, in the `setup.py <https://setuptools.readthedocs.io/en/latest/userguide/quickstart.html#id2>`_ of your Python project,
add this:

.. code-block:: python

   setup(
      ...
      entry_points={
         ...
         'eodag.plugins.api': [
            'SampleApiPlugin = your_package.your_module:SampleApiPlugin'
         ],
         ...
      },
      ...
   )

See `what the PyPa explains <https://packaging.python.org/guides/creating-and-discovering-plugins/#using-package-metadata>`_ to better
understand this concept. In EODAG, the name you give to your plugin in the
`setup.py` script's entry point doesn't matter, but we prefer it to be the
same as the class name of the plugin. What matters is that the entry point
must be a class deriving from one of the 5 plugin topics supported. Be
particularly careful with consistency between the entry point name and the
super class of you plugin class. Here is a list of entry point names and the
plugin topic to which they map:

* 'eodag.plugins.api'      : :class:`~eodag.plugins.apis.base.Api`
* 'eodag.plugins.auth'     : :class:`~eodag.plugins.auth.base.Authentication`
* 'eodag.plugins.crunch'   : :class:`~eodag.plugins.crunch.base.Crunch`
* 'eodag.plugins.download' : :class:`~eodag.plugins.download.base.Download`
* 'eodag.plugins.search'   : :class:`~eodag.plugins.search.base.Search`

As an example of external plugin, you can have a look to
`eodag-sentinelsat <https://github.com/CS-SI/eodag-sentinelsat>`_.

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

An :class:`~eodag.api.product._product.EOProduct` has a :attr:`~eodag.api.product._product.EOProduct.properties` attribute
which is built based on how its metadata are set in the provider configuration. The following converters can be used to
transform the values collected from the provider:

.. automethod:: eodag.api.product.metadata_mapping.format_metadata

For example::

   search:
      ...
      metadata_mapping:
         publicationDate: '{$.data.timestamp#to_iso_utc_datetime_from_milliseconds}'
         ...
