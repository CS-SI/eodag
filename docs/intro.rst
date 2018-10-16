.. _intro:

Introduction
============

Nowadays, we observe a rise in publicly accessible Earth Observation (EO) data.
Together with it, there is more and more EO data providers, each potentially having
a different data access policy. This difference is visible at various levels:
in the data discovery (CSW, OpenSearch more or less custom, etc.), in the
product access (object storage, downloads, direct file system access, etc.), in
the storage structure and in the authentication mechanisms (OAUTH, JWT, basic
auth,...). All these different technologies add a knowledge overhead on a user
(end-user or application developer) wishing to take advantage of these
data. EODAG was designed to solve this problem.

EODAG (Earth Observation Data Access Gateway) is a command line tool and a
plugin-oriented Python framework for searching, aggregating results and
downloading remote sensed images while offering a unified API for data access
regardless of the data provider. The EODAG SDK is structured around three
functions:

    * List product types: list of supported products and their description

    * Search products (by product type) : searches products according to the
      search criteria provided

    * Download products : download product “as is"

EODAG is developed in Python. It is structured according to a modular plugin
architecture, easily extensible and able to integrate new data providers. Three
types of plugins compose the tool:

    * Catalog search plugins, responsible for searching data (OpenSearch, CSW, ...),
      building paths, retrieving quicklook, combining results

    * Download plugins, allowing to download and retrieve data locally (via FTP, HTTP, ..),
      always with the same directory organization

    * Authentication plugins, which are used to authenticate the user on the
      external services used (JSON Token, Basic Auth, OAUTH, ...).

Available providers
-------------------

There are currently 6 available providers implemented on eodag:

* `airbus-ds <https://sobloo.eu/>`_: Airbus DS catalog for the copernicus program

* `USGS <https://earthexplorer.usgs.gov/>`_: U.S geological survey catalog for Landsat products

* `AmazonWS <http://sentinel-pds.s3-website.eu-central-1.amazonaws.com/>`_: Amazon public bucket for Sentinel 2 products

* `theia-landsat <https://theia-landsat.cnes.fr/rocket/#/home>`_: French National Space Agency (CNES) catalog for Pleiades and Landsat products

* `theia <https://theia.cnes.fr/atdistrib/rocket/>`_: French National Space Agency (CNES) catalog for Sentinel 2 products

* `peps <https://peps.cnes.fr/rocket/#/home>`_: French National Space Agency (CNES) catalog for Copernicus (Sentinel 1, 2, 3) products

.. note::

    For developers, there are 2 ways for adding support for a new provider:

    * By configuring existing plugins: a provider is an instance of already
      implemented plugins (search, download) => this only involves knowing how
      to write ``yaml`` documents.

    * By developing new plugins (most of the time it will be search plugins)
      and configuring instances of these plugins.

    See :ref:`creating_plugins` for more details on how to extend eodag.

.. _user-config-file:

How to configure authentication for available providers
-------------------------------------------------------

Create a configuration file containing your credentials for each provider.  You can download
:download:`this template <../user_conf_template.yml>`, which has the following layout:

.. code-block:: yaml

    outputs_prefix: # The path of the root directory for all your downloads
    extract:    # whether to extract products downloaded as archives (true or false)
    peps:
        credentials:
            username:
            password:
    theia:
        credentials:
            ident:
            pass:
    theia-landsat:
        credentials:
            username:
            password:
    USGS:
        credentials:
            username:
            password:
    AmazonWS:
        credentials:
            aws_access_key_id:
            aws_secret_access_key:
    airbus-ds:
        credentials:
            apikey:

.. warning::

    This file contains login information in clear text. Make sure you correctly
    configure access rules to it. It should be read/write-able only by the
    current user of eodag.

Fill this configuration file with the credentials you obtained from each
provider.

For USGS, create an account here: https://ers.cr.usgs.gov/register/

For theia-landsat and theia, you only need to register once here: https://sso.theia-land.fr/theia/register/register.xhtml

For peps, create an account here: https://peps.cnes.fr/rocket/#/register

For AmazonWS:

    * Create an account on AWS website: https://aws.amazon.com/fr/ (warning:
      A credit card number must be given because fees apply after a given
      amount of downloaded data).
    * Once the account is activated go to the identity and access management console: https://console.aws.amazon.com/iam/home#/home
    * Click on user, then on your user name and then on security credentials.
    * In access keys, click on create access key.
    * Add these credentials to the user conf file.

For airbus-ds, create an account here for an api key: https://auth.sobloo.eu/auth/realms/IDP/protocol/openid-connect/auth?client_id=dias&redirect_uri=https%3A%2F%2Fsobloo.eu%2Fsites%2Fall%2Fthemes%2Fdias%2Ftemplates%2Fsso%2Fpopup-signin.html&response_type=id_token%20token&scope=openid&state=176305cc793f40fda565e2260b851d4c&nonce=234b2d571bb4447db8d3385f565255f7&display=popup

