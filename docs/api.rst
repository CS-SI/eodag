.. _api:

.. module:: eodag.api.core

Python API
==========

Core
----

.. autoclass:: eodag.api.core.EODataAccessGateway
   :members:
   :undoc-members:

.. module:: eodag.api.product

Representation Of Earth Observation Products
--------------------------------------------

The EOProduct object
^^^^^^^^^^^^^^^^^^^^

.. autoclass:: eodag.api.product._product.EOProduct
   :members:
   :show-inheritance:
   :undoc-members:

An :class:`~eodag.api.product._product.EOProduct` has a :attr:`~eodag.api.product._product.EOProduct.properties` attribute
which is built using one of the two following methods, depending on the configuration of the provider for which it is
constructed (these methods are therefore to be used primarily in search plugins).

.. automodule:: eodag.api.product.metadata_mapping
   :members:

.. module:: eodag.api.product.drivers

Data access drivers
^^^^^^^^^^^^^^^^^^^

Only minimal driver comes with eodag. For more drivers, install `EODAG-cube <https://github.com/CS-SI/eodag-cube>`_.

.. autoclass:: eodag.api.product.drivers.base.DatasetDriver
   :members:
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.api.product.drivers.base.NoDriver
   :show-inheritance:
   :undoc-members:

.. module:: eodag.api.search_result

Representation Of Search Results
--------------------------------

.. autoclass:: eodag.api.search_result.SearchResult
   :members:
   :undoc-members:

.. module:: eodag.plugins

Plugins
-------

EODAG uses a two-level plugin system. *Plugin topics* are abstract interfaces for a specific functionality of EODAG
like *Search* or *Download*. EODAG providers are implementations of at least one plugin topic. The more plugin topics
are implemented by a provider, the more functionality of eodag are available for this provider.

This organisation is reflected in the internal providers configuration file. Here is a sample::

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
            # See https://eodag.readthedocs.io/en/latest/api.html#eodag.utils.metadata_mapping.get_metadata_path
            ...
      download:
         plugin: CustomDownloadPlugin
         # Same as with search for random config keys as needed by the plugin class
         ...
      auth:
         plugin: CustomAuthPlugin
         # Same as with search for random config keys as needed by the plugin class
         ...

Note however, that for a provider which already have a Python library for accessing its products, the configuration
vary a little bit. It does not have the 'search' and 'download' keys. Instead, there is a single 'api' key like this::

   provider_name:
      ...
      api:
         plugin: ApiPluginClassName
         ...

Plugin Management
^^^^^^^^^^^^^^^^^

The plugin machinery is managed by one instance of :class:`~eodag.plugins.manager.PluginManager`.

.. autoclass:: eodag.plugins.manager.PluginManager
   :members:
   :show-inheritance:

The instance manager knows how to discover plugins at runtime, using
`setuptools entry points mechanism <https://packaging.python.org/guides/creating-and-discovering-plugins/#using-package-metadata>`_.
See :ref:`creating_plugins`.

Plugin Types
^^^^^^^^^^^^

EODAG currently advertises 5 types of plugins: *Search*, *Download*, *Crunch*, *Authentication* and *Api*.

.. autoclass:: eodag.plugins.base.PluginTopic
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.search.base.Search
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.download.base.Download
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.crunch.base.Crunch
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.authentication.base.Authentication
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.apis.base.Api
   :show-inheritance:
   :undoc-members:

.. module:: eodag.plugins.search

Search Plugins
^^^^^^^^^^^^^^

.. autoclass:: eodag.plugins.search.csw.CSWSearch
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.search.qssearch.QueryStringSearch
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.search.qssearch.AwsSearch
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.search.qssearch.ODataV4Search
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.search.qssearch.PostJsonSearch
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.search.qssearch.StacSearch
   :show-inheritance:
   :undoc-members:

.. module:: eodag.plugins.download

Download Plugins
^^^^^^^^^^^^^^^^

.. autoclass:: eodag.plugins.download.http.HTTPDownload
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.download.aws.AwsDownload
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.download.s3rest.S3RestDownload
   :show-inheritance:
   :undoc-members:

.. module:: eodag.plugins.crunch

Crunch Plugins
^^^^^^^^^^^^^^

.. autoclass:: eodag.plugins.crunch.filter_date.FilterDate
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.crunch.filter_latest_intersect.FilterLatestIntersect
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.crunch.filter_latest_tpl_name.FilterLatestByName
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.crunch.filter_overlap.FilterOverlap
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.crunch.filter_property.FilterProperty
   :show-inheritance:
   :undoc-members:

.. module:: eodag.plugins.authentication

Authentication Plugins
^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: eodag.plugins.authentication.generic.GenericAuth
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.authentication.token.TokenAuth
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.authentication.header.HTTPHeaderAuth
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.authentication.oauth.OAuth
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth
   :show-inheritance:
   :undoc-members:

.. autoclass:: eodag.plugins.authentication.keycloak.KeycloakOIDCPasswordAuth
   :show-inheritance:
   :undoc-members:

.. module:: eodag.plugins.apis

External Apis Plugins
^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: eodag.plugins.apis.usgs.UsgsApi
   :show-inheritance:
   :undoc-members:

.. _creating_plugins:

Creating EODAG plugins
^^^^^^^^^^^^^^^^^^^^^^

EODAG plugins can be separated from the core eodag package. They live in your Python site-packages as standalone Python
packages or modules, with eodag's specific entry points that will be looked at by the plugin manager to load plugins at
runtime. These entry points are: `eodag.plugins.{topic}`, with possible values for `topic` being `api`, `search`,
`crunch`, `auth` and `download`.

All you have to do to create eodag plugins is start a new Python project, add eodag as a dependancy to your project,
and then create the plugin type you want in Python module(s) by importing its base class from `eodag.plugins.{topic}.base`
and subclassing it. Here is an example for an :class:`~eodag.plugins.apis.base.Api` plugin class located in a module
named `your_package.your_module`:

.. code-block:: python

   from eodag.plugins.apis.base import Api

   class SampleApiPlugin(Api):

      def query(self):
         pass

      def download(self):
         pass

Then, in the `setup.py <http://setuptools.readthedocs.io/en/latest/setuptools.html#basic-use>`_ of your Python project,
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

See `This <https://packaging.python.org/guides/creating-and-discovering-plugins/#using-package-metadata>`_ to better
understand this concept. In `eodag`, the name you give to your plugin in the
`setup.py` script's entry point does'nt matter, but we prefer it to be the
same as the class name of the plugin. What matters is that the entry point
must be a class deriving from one of the 5 plugin topics supported. Be
particularly careful with consistency between the entry point name and the
super class of you plugin class. Here is a list of entry point names and the
plugin topic to which they map:

* 'eodag.plugins.api'      : :class:`~eodag.plugins.apis.base.Api`
* 'eodag.plugins.auth'     : :class:`~eodag.plugins.auth.Authentication`
* 'eodag.plugins.crunch'   : :class:`~eodag.plugins.crunch.Crunch`
* 'eodag.plugins.download' : :class:`~eodag.plugins.download.Download`
* 'eodag.plugins.search'   : :class:`~eodag.plugins.search.base.Search`


Providers configuration
^^^^^^^^^^^^^^^^^^^^^^^

.. automodule:: eodag.config
   :members:
   :undoc-members:


Utils
-----

.. automodule:: eodag.utils
   :members:
   :show-inheritance:
   :undoc-members:

.. automodule:: eodag.utils.exceptions
   :members:
   :show-inheritance:
   :undoc-members:

.. automodule:: eodag.utils.import_system
   :members:
   :show-inheritance:
   :undoc-members:

.. automodule:: eodag.utils.logging
   :members:
   :show-inheritance:
   :undoc-members:


Call graphs
-----------

* `Main API calls graph <_static/eodag_main_calls_graph.svg>`_
* `Advanced calls graph (main API + search and authentication plugins) <_static/eodag_advanced_calls_graph.svg>`_

These call graphs are generated using *graphviz* and `Pyan3 <https://github.com/davidfraser/pyan>`_

.. code-block:: bash

   cd eodag_working_copy/eodag
   # main api
   pyan3 `find ./api -name "*.py"` \
   --uses --colored --grouped-alt --nested-groups --annotated --dot --dot-rankdir=LR \
   >/tmp/eodag_main_calls_graph.dot
   dot -Tsvg /tmp/eodag_main_calls_graph.dot >../docs/_static/eodag_main_calls_graph.svg
   # advanced api
   pyan3 `find ./api ./plugins/search/ ./plugins/authentication/ -name "*.py"` \
   --uses --colored --grouped-alt --nested-groups --annotated --dot --dot-rankdir=LR \
   >/tmp/eodag_advanced_calls_graph.dot
   dot -Tsvg /tmp/eodag_advanced_calls_graph.dot >../docs/_static/eodag_advanced_calls_graph.svg
