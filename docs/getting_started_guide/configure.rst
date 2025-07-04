.. _configure:

Configure EODAG
===============

Configuration in ``eodag`` plays an important role:

* To provide credentials (e.g. login/password, API key, etc.) required to download (and search sometimes) products with a provider
* To specify the search priority of a provider
* To indicate where to download products, whether to extract them or not, etc.
* To update a provider or add a new one

This page describes how to configure `eodag` both for interacting with its API or its command line interface.

Automatic pre-configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^

``eodag`` comes bundled with the pre-configuration of numerous providers. It knows how to search
for products in a provider's catalog, how to download products, etc. However, users are required
to complete this configuration with additional settings, such as provider credentials. Users can
also override pre-configured settings (e.g. the download folder).

YAML user configuration file
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The first time ``eodag`` is used after an install, a default YAML user configuration file is saved
in a local directory (``~/.config/eodag/eodag.yml`` on Linux).

This YAML file contains a template that shows how to complete the configuration of one or
more providers. It allows to either **override** an existing setting or **add** a missing
one (e.g. credentials). *PEPS*'s configuration template is shown below:

.. code-block:: yaml

   peps:
       priority: # Lower value means lower priority (Default: 1)
       search:  # Search parameters configuration
       download:
           extract:  # whether to extract the downloaded products (true or false).
           output_dir: # where to store downloaded products.
           dl_url_params:  # additional parameters to pass over to the download url as an url parameter
           delete_archive: # whether to delete the downloaded archives (true or false, Default: true).
       auth:
           credentials:
               username:
               password:

.. raw:: html

   <details>
   <summary><a>Click here to display the content of the whole file</a></summary>

.. include:: ../../eodag/resources/user_conf_template.yml
   :start-line: 17
   :code: yaml

.. raw:: html

   </details>

.. note::

   Please write settings values as plain text, without quotes to avoid ``PyYAML`` interpreting potential special
   characters. See https://pyyaml.org/wiki/PyYAMLDocumentation for more information.

|

Users can directly modify the default file, which is then loaded automatically:

* API: ``eodag.EODataAccessGateway()``
* CLI: ``eodag search -b 1 43 2 44 -s 2018-01-01 -e 2018-01-31 -p S2_MSI_L1C``

They can also choose to create their own configuration file(s)
and load them explicitely:

* API: ``eodag.EODataAccessGateway("my_config.yml")``
* CLI: ``eodag search -f my_config.yml -b 1 43 2 44 -s 2018-01-01 -e 2018-01-31 -p S2_MSI_L1C``

Alternatively, the environment variable ``EODAG_CFG_FILE`` can be used to set the path
to the configuration file. In that case it is also loaded automatically:

* API: ``eodag.EODataAccessGateway()``
* CLI: ``eodag search -b 1 43 2 44 -s 2018-01-01 -e 2018-01-31 -p S2_MSI_L1C``

.. warning::

   This file contains login information in clear text. Make sure you correctly
   configure access rules to it. It should be read/write-able only by the
   current user of eodag.

Environment variable configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Providers configuration using environment variables
"""""""""""""""""""""""""""""""""""""""""""""""""""

``eodag`` providers can also be configured with environment variables, which have **priority over**
the YAML user configuration file.

The name of the environment variables understood by ``eodag`` must follow the pattern
``EODAG__KEY1__KEY2__[...]__KEYN`` (note the double underscore between the keys).

See for instance the following configuration extracted from YAML file:

.. code-block:: yaml

   creodias:
       download:
           extract: True
           output_dir: /absolute/path/to/a/folder/
           delete_archive: False


The same configuration could be achieved by setting environment variables:

.. code-block:: bash

   export EODAG__CREODIAS__DOWNLOAD__EXTRACT=True
   export EODAG__CREODIAS__DOWNLOAD__OUTPUT_DIR=/absolute/path/to/a/folder/
   export EODAG__CREODIAS__DOWNLOAD__DELETE_ARCHIVE=False


Each configuration parameter can be set with an environment variable.

.. note::

   Setting credentials must be done according to the
   `provider's plugin <https://eodag.readthedocs.io/en/stable/plugins.html#plugins-available>`_ (auth | api):

   * Authentication plugin: ``EODAG__<PROVIDER>__AUTH__CREDENTIALS__<KEY>``

   * API plugin: ``EODAG__<PROVIDER>__API__CREDENTIALS__<KEY>``

   ``<KEY>`` should be replaced with the adapted credentials key (``USERNAME``, ``PASSWORD``, ``APIKEY``, ...) according
   to the provider configuration template in
   `the YAML user configuration file\
   <https://eodag.readthedocs.io/en/stable/getting_started_guide/configure.html#yaml-user-configuration-file>`_.


Core configuration using environment variables
""""""""""""""""""""""""""""""""""""""""""""""

Some EODAG core settings can be overriden using environment variables:

* ``EODAG_CFG_DIR`` customized configuration directory in place of `~/.config/eodag`.
* ``EODAG_CFG_FILE`` for defining the desired path to the `user configuration file\
  <https://eodag.readthedocs.io/en/stable/getting_started_guide/configure.html#yaml-user-configuration-file>`_
  in place of `~/.config/eodag/eodag.yml`.
* ``EODAG_LOCS_CFG_FILE`` for defining the desired path to the
  `locations <https://eodag.readthedocs.io/en/stable/notebooks/api_user_guide/4_search.html#Locations-search>`_
  configuration file in place of `~/.config/eodag/locations.yml`.
* ``EODAG_PROVIDERS_CFG_FILE`` for defining the desired path to the providers configuration file in place of
  `<python-site-packages>/eodag/resources/providers.yml`.
* ``EODAG_PRODUCT_TYPES_CFG_FILE`` for defining the desired path to the product types configuration file in place of
  `<python-site-packages>/eodag/resources/product_types.yml`.
* ``EODAG_EXT_PRODUCT_TYPES_CFG_FILE`` for defining the desired path to the `external product types configuration file\
  <https://eodag.readthedocs.io/en/stable/notebooks/api_user_guide/2_providers_products_available.html#Product-types-discovery>`_
  in place of https://cs-si.github.io/eodag/eodag/resources/ext_product_types.json.
  If the file is not readable, only user-modified providers will be fetched.
* ``EODAG_PROVIDERS_WHITELIST`` to restrict EODAG to only use a specific list of providers.

  If this environment variable is set (as a comma-separated list of provider names), EODAG will only load and use the specified providers.
  All other providers will be ignored, regardless of their presence in configuration files.

  This is useful for restricting EODAG to a subset of providers, for example in controlled or production environments.
* ``EODAG_STRICT_PRODUCT_TYPES`` to control how product types are listed.

  If this environment variable is set to a truthy value (such as ``1``, ``true``, ``yes``, or ``on``), EODAG will only list product types that are present in the main product types configuration file.
  Product types defined only in provider configurations (but not in the main product types configuration) will be ignored.
  If not set, EODAG will also include product types defined only in provider configurations, with minimal metadata.

  This is useful if you want to strictly control which product types are available, for example to ensure consistency across environments.

Example usage:

.. code-block:: bash

   export EODAG_PROVIDERS_WHITELIST=peps,creodias,theia
   export EODAG_STRICT_PRODUCT_TYPES=true

CLI configuration
^^^^^^^^^^^^^^^^^

The command options that require a configuration file (e.g. ``eodag download`` ) have an argument
(usually ``-f``) to provide the path to a YAML configuration file. If not specified,
the default configuration filepath is used. Settings defined by environment variables
are also taken into account.

API: Dynamic configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^

``eodag`` 's configuration can be altered directly from using Python. See this
`dedicated page <../notebooks/api_user_guide/3_configuration.ipynb>`_ in the Python API user guide.

Priority setting
^^^^^^^^^^^^^^^^

Some product types are available from multiple providers, for instance
*Sentinel 2 Level-1C* products. When a search is made for such product types,
``eodag`` would use its pre-configured preferred/prioritary provider, which is *PEPS*
currently.

To make a provider the preferred/prioritary one, its priority setting must be set to
an integer value that is higher than the priority of all the other providers.

.. note::

   *PEPS* is currently the default provider used when a search is made.
   To target another provider its priority must be increased.


.. warning::

   If the priority is set to a provider, and a search is made for a product type
   available in ``eodag``'s catalog with a provider that doesn't offer this product type,
   then the search will still be done. The provider used would be the one with the
   highest priority among those which offer this product type.

Download settings
^^^^^^^^^^^^^^^^^

Two useful download parameters can be set by a user:

* ``extract`` indicates whether the downloaded product archive should be automatically
  extracted or not. ``True`` by default.

*  ``output_dir`` indicates the absolute file path to `eodag`'s download folder.
   It is the temporary folder by default (e.g. ``/tmp`` on Linux).

* ``delete_archive`` indicates whether the downloaded product archive should be automatically
  deleted after extraction or not. ``True`` by default.

Credentials settings
^^^^^^^^^^^^^^^^^^^^

Credentials come into play at different stages for a provider. Most do not
require any credentials for a search to be made (a few require an API key).
Most, if not all of them, require credentials to be set to download products.

.. note::

   ``eodag`` tries to fail as early as possible if some credentials are missing to authenticate
   to a provider while trying to download a product. If the credentials are set, ``eodag`` will
   keep going. An :class:`~eodag.utils.exceptions.AuthenticationError` is raised if the
   authentication fails.

   Make sure to check that your credentials are correctly set and to keep them up to date.

Example
^^^^^^^

Edit your configuration file ``$HOME/.config/eodag/eodag.yml`` with the following content:

.. code-block:: yaml

   creodias:
       priority: 2
       download:
           extract: False
           output_dir: /home/user/eodagworkspace/
       auth:
           credentials:
               username: my_creodias_username
               password: my_creodias_password

It updates and completes the settings of the provider `creodias` by:

* Setting its priority to ``2``, which is higher than the default maximum priority (*PEPS* at 1).
  Products will then be searched through `creodias`'s catalog.

* The products downloaded should not be extracted automatically by ``eodag``.

* The products should be downloaded to the folder ``/home/user/eodagworkspace/``.

* Credentials (username and password) obtained from `creodias` are saved there, it will be used to authenticate to the
  provider.

This file can be used to download products with the API:

.. code-block:: python

   from eodag import EODataAccessGateway
   dag = EODataAccessGateway()
   products = dag.search(
      productType="S2_MSI_L1C",
      start="2018-01-01",
      end="2018-01-31",
      geom=(1, 43, 2, 44)
   )
   product_paths = dag.download_all(products)

Or with the CLI:

.. code-block:: console

   cd /home/user/eodagworkspace/
   eodag search -b 1 43 2 44 \
                -s 2018-01-01 \
                -e 2018-01-31 \
                -p S2_MSI_L1C \
                --storage my_search.geojson
   eodag download -f my_config.yml --search-results my_search.geojson

Authenticate using an OTP / One Time Password (Two-Factor authentication)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Use OTP through Python code
"""""""""""""""""""""""""""

``creodias`` needs a temporary 6-digits code to authenticate in addition of the ``username`` and ``password``. Check
`Creodias documentation\
<https://creodias.docs.cloudferro.com/en/latest/gettingstarted/Two-Factor-Authentication-for-Creodias-Site.html>`_
to see how to get this code once you are registered. This OTP code will only be valid for a few seconds, so you will
better set it dynamically in your python code instead of storing it statically in your user configuration file.

Set the OTP by updating ``creodias`` credentials for ``totp`` entry, using one of the two following configuration update
commands:

.. code-block:: python

   dag.providers_config["creodias"].auth.credentials["totp"] = "PLEASE_CHANGE_ME"

   # OR

   dag.update_providers_config(
      """
      creodias:
         auth:
            credentials:
               totp: PLEASE_CHANGE_ME
      """
   )

Then quickly authenticate as this OTP has a few seconds only lifetime. First authentication will retrieve a token that
will be stored and used if further authentication tries fail:

.. code-block:: python

   dag._plugins_manager.get_auth_plugin("creodias").authenticate()

Please note that authentication mechanism is already included in
`download methods <https://eodag.readthedocs.io/en/stable/notebooks/api_user_guide/8_download.html>`_ , so you could
also directly execute a download to retrieve the token while the OTP is still valid.

Use OTP through CLI
"""""""""""""""""""

To download through CLI a product on a provider that needs a One Time Password,  e.g. ``creodias``, first search on this
provider (increase the provider priotity to make eodag search on it):

.. code-block:: console

        EODAG__CREODIAS__PRIORITY=2 eodag search -b 1 43 2 44 -s 2018-01-01 -e 2018-01-31 -p S2_MSI_L1C --items 1

Then download using the OTP (``creodias`` needs it as ``totp`` parameter):

.. code-block:: console

        EODAG__CREODIAS__AUTH__CREDENTIALS__TOTP=PLEASE_CHANGE_ME eodag download --search-results search_results.geojson

If needed, check in the documentation how to
`use environment variables to configure EODAG <#environment-variable-configuration>`_.
