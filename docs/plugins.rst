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

+------------------------+------------------------------------+---------------------------------+------------------+
| Provider               | Search                             | Authentication                  | Download         |
+========================+====================================+=================================+==================+
| ``aws_eos``            | |PostJsonSearch|                   | |AwsAuth|                       | |AwsDownload|    |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``cop_ads``            | |ECMWFSearch|                      | |HTTPHeaderAuth|                | |HTTPDownload|   |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``cop_cds``            | |ECMWFSearch|                      | |HTTPHeaderAuth|                | |HTTPDownload|   |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``cop_ewds``           | |ECMWFSearch|                      | |HTTPHeaderAuth|                | |HTTPDownload|   |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``cop_dataspace``      | |QueryStringSearch|                | |KeycloakOIDCPasswordAuth|      | |HTTPDownload|   |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``cop_marine``         | |CopMarineSearch|                  | |AwsAuth|                       | |AwsDownload|    |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``creodias``           | |QueryStringSearch|                | |KeycloakOIDCPasswordAuth|      | |HTTPDownload|   |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``dedl``               | |StacSearch|                       | |OIDCTokenExchangeAuth|         | |HTTPDownload|   |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``dedt_lumi``          | |ECMWFSearch|                      | |OIDCAuthorizationCodeFlowAuth| | |HTTPDownload|   |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``earth_search``       | |StacSearch|                       | |AwsAuth|                       | |AwsDownload|    |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``earth_search_cog``   | |StacSearch|                       | ``None``                        | |HTTPDownload|   |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``earth_search_gcs``   | |StacSearch|                       | |AwsAuth|                       | |AwsDownload|    |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``ecmwf``              | |EcmwfApi|                         | |EcmwfApi|                      | |EcmwfApi|       |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``eumetsat_ds``        | |QueryStringSearch|                | |TokenAuth|                     | |HTTPDownload|   |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``geodes``             | |StacSearch|                       | |HTTPHeaderAuth|                | |HTTPDownload|   |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``geodes_s3``          | |StacListAssets|                   | |AwsAuth|                       | |AwsDownload|    |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``hydroweb_next``      | |StacSearch|                       | |HTTPHeaderAuth|                | |HTTPDownload|   |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``meteoblue``          | |MeteoblueSearch|                  | |HttpQueryStringAuth|           | |HTTPDownload|   |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``peps``               | |QueryStringSearch|                | |GenericAuth|                   | |HTTPDownload|   |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``planetary_computer`` | |StacSearch|                       | |SASAuth|                       | |HTTPDownload|   |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``usgs``               | |UsgsApi|                          | |UsgsApi|                       | |UsgsApi|        |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``usgs_satapi_aws``    | |StacSearch|                       | |AwsAuth|                       | |AwsDownload|    |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``theia``              | |QueryStringSearch|                | |TokenAuth|                     | |HTTPDownload|   |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``wekeo_ecmwf``        | |PostJsonSearch|                   | |TokenAuth|                     | |HTTPDownload|   |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``wekeo_cmems``        | |PostJsonSearch|                   | |TokenAuth|                     | |HTTPDownload|   |
+------------------------+------------------------------------+---------------------------------+------------------+
| ``wekeo_main``         | |PostJsonSearchWithStacQueryables| | |TokenAuth|                     | |HTTPDownload|   |
+------------------------+------------------------------------+---------------------------------+------------------+

.. |UsgsApi| replace:: :class:`~eodag.plugins.apis.usgs.UsgsApi`
.. |EcmwfApi| replace:: :class:`~eodag.plugins.apis.ecmwf.EcmwfApi`

.. |GenericAuth| replace:: :class:`~eodag.plugins.authentication.generic.GenericAuth`
.. |HTTPHeaderAuth| replace:: :class:`~eodag.plugins.authentication.header.HTTPHeaderAuth`
.. |AwsAuth| replace:: :class:`~eodag.plugins.authentication.aws_auth.AwsAuth`
.. |TokenAuth| replace:: :class:`~eodag.plugins.authentication.token.TokenAuth`
.. |OIDCAuthorizationCodeFlowAuth| replace:: :class:`~eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth`
.. |OIDCTokenExchangeAuth| replace:: :class:`~eodag.plugins.authentication.token_exchange.OIDCTokenExchangeAuth`
.. |KeycloakOIDCPasswordAuth| replace:: :class:`~eodag.plugins.authentication.keycloak.KeycloakOIDCPasswordAuth`
.. |HttpQueryStringAuth| replace:: :class:`~eodag.plugins.authentication.qsauth.HttpQueryStringAuth`
.. |SASAuth| replace:: :class:`~eodag.plugins.authentication.sas_auth.SASAuth`

.. |AwsDownload| replace:: :class:`~eodag.plugins.download.aws.AwsDownload`
.. |HTTPDownload| replace:: :class:`~eodag.plugins.download.http.HTTPDownload`
.. |CreodiasS3Download| replace:: :class:`~eodag.plugins.download.creodias_s3.CreodiasS3Download`

.. |QueryStringSearch| replace:: :class:`~eodag.plugins.search.qssearch.QueryStringSearch`
.. |ODataV4Search| replace:: :class:`~eodag.plugins.search.qssearch.ODataV4Search`
.. |PostJsonSearch| replace:: :class:`~eodag.plugins.search.qssearch.PostJsonSearch`
.. |StacSearch| replace:: :class:`~eodag.plugins.search.qssearch.StacSearch`
.. |PostJsonSearchWithStacQueryables| replace:: :class:`~eodag.plugins.search.qssearch.PostJsonSearchWithStacQueryables`
.. |ECMWFSearch| replace:: :class:`~eodag.plugins.search.build_search_result.ECMWFSearch`
.. |MeteoblueSearch| replace:: :class:`~eodag.plugins.search.build_search_result.MeteoblueSearch`
.. |WekeoECMWFSearch| replace:: :class:`~eodag.plugins.search.build_search_result.WekeoECMWFSearch`
.. |CreodiasS3Search| replace:: :class:`~eodag.plugins.search.creodias_s3.CreodiasS3Search`
.. |CopMarineSearch| replace:: :class:`~eodag.plugins.search.cop_marine.CopMarineSearch`
.. |StacListAssets| replace:: :class:`~eodag.plugins.search.stac_list_assets.StacListAssets`


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

Then, in the `configuration file <https://setuptools.readthedocs.io/en/latest/userguide/quickstart.html#id2>`_ of your Python project,
add this:


.. tabs::
   .. tab:: pyproject.toml
      .. code-block:: toml

         [project.entry-points."eodag.plugins.api"]
         SampleApiPlugin = "your_package.your_module:SampleApiPlugin"

   .. tab:: setup.py
      .. code-block:: python

         setup(
            # ...
            entry_points={
               'eodag.plugins.api': [
                  'SampleApiPlugin = your_package.your_module:SampleApiPlugin'
               ]
            }
         )

See `what the PyPa explains <https://packaging.python.org/guides/creating-and-discovering-plugins/#using-package-metadata>`_ to better
understand this concept. In EODAG, the name you give to your plugin in the
entry point doesn't matter, but we prefer it to be the same as the class
name of the plugin. What matters is that the entry point must be a class
deriving from one of the 5 plugin topics supported. Be particularly careful
with consistency between the entry point name and the super class of you
plugin class. Here is a list of entry point names and the plugin topic to
which they map:

* `eodag.plugins.api`            : :class:`~eodag.plugins.apis.base.Api`
* `eodag.plugins.authentication` : :class:`~eodag.plugins.authentication.base.Authentication`
* `eodag.plugins.crunch`         : :class:`~eodag.plugins.crunch.base.Crunch`
* `eodag.plugins.download`       : :class:`~eodag.plugins.download.base.Download`
* `eodag.plugins.search`         : :class:`~eodag.plugins.search.base.Search`


Read the :ref:`mock search plugin` section to get an example of how to build a search
plugin.

As an example of external plugin, you can have a look to
`eodag-sentinelsat <https://github.com/CS-SI/eodag-sentinelsat>`_.

.. _mock search plugin:

A sample mock search plugin
"""""""""""""""""""""""""""

In this section, we demonstrate the creation of custom search plugin. This plugin will
return a list of mocked EOProducts on search requests.

1. Create a folder called `eodag_search_mock`. It will be the name of our package.

2. Make an empty `__init.py__` file in the package folder.

3. Make a `mock_search.py` file and paste in it the following class
   definition.

   It is our search plugin. The `query()` function is the one called by EODAG when
   searching for products.

   .. code-block:: python

      # mock_search.py
      from typing import Any, List, Optional, Tuple
      from eodag.plugins.search import PreparedSearch
      from eodag.plugins.search.base import Search
      from eodag.api.product import EOProduct

      class MockSearch(Search):
      """Implement a Mock search plugin"""

      def query(
         self,
         prep: PreparedSearch = PreparedSearch(),
         **kwargs: Any,
      ) -> Tuple[List[EOProduct], Optional[int]]:
         """Generate EOProduct from the request"""
         return ([EOProduct(
            provider=self.provider,
            properties={
               **{
                  "id": f"mock_{kwargs.get('productType')}_{i}"
                  },
               **kwargs
            }
            ) for i in range(0, prep.items_per_page)],
            prep.items_per_page if prep.count else None
         )

4. Create a `pyproject.toml` file in the package folder and paste in it the following
   content.

   The `projects.entry-points` is crucial for EODAG to detect this new plugin.

   .. code-block:: toml

      [project]
      name = "eodag-search-mock"
      version = "0.0.1"
      description = "Mock Search plugin for EODAG"
      requires-python = ">=3.8"
      dependencies = [ "eodag" ]

      [project.entry-points."eodag.plugins.search"]
      MockSearch = "mock_search:MockSearch"

5. Your plugin is now ready. You need to install it for EODAG to be able to use it.

   .. code-block:: shell

      pip install eodag_search_mock


Plugin configuration
^^^^^^^^^^^^^^^^^^^^

.. autoclass:: eodag.config.PluginConfig
   :members:
   :member-order: bysource
   :undoc-members:
   :exclude-members: priority, product_type_config, yaml_loader, from_mapping, from_yaml, update, validate, yaml_dumper,
                     yaml_tag
