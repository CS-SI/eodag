.. _providers:

Featured providers
===================

``eodag`` connects you to a variety of Earth Observation (EO) data providers.
This section introduces the featured providers that are already integrated, so you can
easily start searching, accessing, and downloading products.

Some providers are completely open, while others require an account to access their data.
If credentials are needed, check the :doc:`registration guide <providers>` for details.

Note that ``eodag`` is not limited to the providers listed here.
If a desired provider is missing, you can add it yourself by configuring a new plugin.
See :doc:`how to add a new provider <add_provider>` for more details.

Description
^^^^^^^^^^^

Products from the following providers are made available through ``eodag``:

====================
Available Providers
====================

.. meta::
   :description: Comprehensive list of all supported data providers for Earth Observation data access
   :keywords: providers, data, earth observation, satellite, API

This section lists all supported data providers, grouped by organization or hosting entity.

.. contents::
   :depth: 2
   :local:
   :backlinks: none

----

**AWS / GCS EO catalogs**
-------------------------

.. admonition::  **Cloud-Native Earth Observation Data**
   :class: note

   These providers offer scalable access to satellite imagery through cloud infrastructure with global distribution.

**Earth Search**
~~~~~~~~~~~~~~~~

.. card:: ``earth_search``
   :class-card: card-border-primary shadow-sm
   :link: https://www.element84.com/earth-search/

   **Element84 STAC API on AWS**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

  **Setup Requirements:**

  * Create an account on `AWS <https://aws.amazon.com/>`__
  * Once the account is activated go to the `identity access management console <https://console.aws.amazon.com/iam/home#/home>`__
  * Click on user, then on your user name and then on security credentials.
  * In access keys, click on create access key.
  * Add these credentials to the user configuration file.

  .. warning:: **Billing Alert**

      A credit card number must be provided when creating an AWS account because fees apply
      after a given amount of downloaded data.

----

.. card:: ``earth_search_cog``
   :class-card: card-border-primary shadow-sm
   :link: https://www.element84.com/earth-search/

   **Element84 STAC API on AWS (COG access)**

   :octicon:`unlock;1em;sd-text-success` No account is required

----

.. card:: ``earth_search_gcs``
   :class-card: card-border-primary shadow-sm
   :link: https://cloud.google.com/storage/docs/public-datasets

   **Element84 Earth Search on Google Cloud Storage**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

  You need HMAC keys for Google Cloud Storage:

  * Sign in using a `google account <https://accounts.google.com/signin/v2/identifier>`__.
  * Get or create `HMAC keys <https://cloud.google.com/storage/docs/authentication/hmackeys>`__ for your user account
    on a project for interoperability API access from this
    `page <https://console.cloud.google.com/storage/settings;tab=interoperability>`__ (create a default project if
    none exists).
  * Add these credentials to the user configuration file.

----

**EOS**
~~~~~~~

.. card:: ``aws_eos``
   :class-card: card-border-primary shadow-sm
   :link: https://eos.com/

   **EOS Data Analytics search for Amazon public datasets**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

    You need credentials for both EOS Data Analytics (search) and AWS (download):

    * Create an account on `EOS <https://auth.eos.com>`__
    * Get your EOS api key from `here <https://api-connect.eos.com/user-dashboard/statistics>`__
    * Create an account on `AWS <https://aws.amazon.com/>`__
    * Once the account is activated go to the `identity access management console <https://console.aws.amazon.com/iam/home#/home>`__
    * Click on user, then on your user name and then on security credentials.
    * In access keys, click on create access key.
    * Add these credentials to the user configuration file:

      * ``search_auth.credentials.api_key``
      * ``download_auth.credentials.aws_access_key_id`` and ``download_auth.credentials.aws_secret_access_key`` or ``download_auth.credentials.aws_profile``

    .. note:: **Usage Limits**

        EOS free trial account is limited to 1000 requests, see also their `subscription plans <https://doc.eos.com/subscription/>`__.

----

**Copernicus**
--------------

.. admonition:: **European Space Programme**
   :class: note

   The Copernicus programme provides free and open access to Earth observation data from the Sentinel satellite constellation and climate services.

**Copernicus Data Stores**
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. card:: ``cop_ads``
   :class-card: card-border-primary shadow-sm
   :link: https://ads.atmosphere.copernicus.eu

   **Copernicus Atmosphere Data Store**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

    Go to the `ECMWF homepage <https://www.ecmwf.int/>`__ and create an account by clicking on *Log in* and then *Register*.

    Then log in and go to your user profile on `Atmosphere Data Store <https://ads.atmosphere.copernicus.eu/>`__ and
    use your *Personal Access Token* as ``apikey`` in eodag credentials.

    To download data you have to accept the `Licence to use Copernicus Products`. To accept the licence:

    * Go to `Datasets <https://ads.atmosphere.copernicus.eu/datasets>`__ while being logged in.
    * Open the details of a dataset and go to the download tab.
    * Scroll down and accept the licence in the section `Terms of use`.
    * You can check which licences you have accepted in your user profile.

----

.. card:: ``cop_cds``
   :class-card: card-border-primary shadow-sm
   :link: https://cds.climate.copernicus.eu

   **Copernicus Climate Data Store**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

    Go to the `ECMWF homepage <https://www.ecmwf.int/>`__ and create an account by clicking on *Log in* and then *Register*.
    Then log in and go to your user profile on `Climate Data Store <https://cds.climate.copernicus.eu/>`__ and use your
    *Personal Access Token* as ``apikey`` in eodag credentials.

    To download data, you also have to accept certain terms depending on the dataset. Some datasets have a specific licence
    whereas other licences are valid for a group of datasets.
    For example after accepting the `Licence to use Copernicus Products` you can use all `ERA5` datasets, to use the seasonal data from C3S you
    also have to accept the `Additional licence to use non European contributions`.

    To accept a licence:

    * Search for the dataset you want to download `here <https://cds.climate.copernicus.eu/datasets>`__ while being
      logged in.
    * Open the dataset details and go to the download tab.
    * Scroll down and accept the licence in the section `Terms of use`.
    * You can check which licences you have accepted in your user profile.

----

.. card:: ``cop_dataspace``
   :class-card: card-border-primary shadow-sm
   :link: https://dataspace.copernicus.eu/

   **Copernicus Data Space Ecosystem**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

    Create an account `here
    <https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/auth?client_id=cdse-public&redirect_uri=https%3A%2F%2Fdataspace.copernicus.eu%2Fbrowser%2F&response_type=code&scope=openid>`__

----

.. card:: ``cop_ewds``
   :class-card: card-border-primary shadow-sm
   :link: https://ewds.climate.copernicus.eu

   **CEMS Early Warning Data Store**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

    Go to the `ECMWF homepage <https://www.ecmwf.int/>`__ and create an account by clicking on *Log in* and then *Register*.
    Then log in and go to your user profile on `CEMS Early Warning Data Store <https://ewds.climate.copernicus.eu>`__ and use your
    *Personal Access Token* as ``apikey`` in eodag credentials.

    To download data, you also have to accept certain terms depending on the dataset. There are two different licences that have to be accepted
    to use the CEMS EWDS datasets. Accepting the `CEMS-FLOODS datasets licence` is necessary to use the `GLOFAS` and `EFAS` datasets,
    the `Licence to use Copernicus Products` is valid for the Fire danger datasets.

    To accept a licence:

    * Search for the dataset you want to download `here <https://ewds.climate.copernicus.eu/datasets>`__ while being
      logged in.
    * Open the dataset details and go to the download tab.
    * Scroll down and accept the licence in the section `Terms of use`.
    * You can check which licences you have accepted in your user profile.

----

.. card:: ``cop_marine``
   :class-card: card-border-primary shadow-sm
   :link: https://marine.copernicus.eu

   **Copernicus Marine Service**

   :octicon:`unlock;1em;sd-text-success` No account is required

----

**Sara**
~~~~~~~~~

.. card:: ``sara``
   :class-card: card-border-info shadow-sm
   :link: https://copernicus.nci.org.au

   **Sentinel Australasia Regional Access**

   Regional entry point providing localized access to Copernicus Sentinel products and datasets hosted for the Australasia region.

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

  Create an account `here <https://copernicus.nci.org.au/sara.client/#/register>`__, then use your email as ``username`` in
  eodag credentials.

----

**WEkEO**
~~~~~~~~~

.. card:: ``wekeo_cmems``
   :class-card: card-border-primary shadow-sm
   :link: https://www.wekeo.eu

   **Copernicus Marine (CMEMS) data from WEkEO**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

    The registration procedure is the same as for ``wekeo_main``.
    The licence that has to be accepted to access the Copernicus Marine data is:

    * ``Copernicus_Marine_Service_Product_License``

----

.. card:: ``wekeo_ecmwf``
   :class-card: card-border-primary shadow-sm
   :link: https://www.wekeo.eu/

   **WEkEO ECMWF data**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

    The registration procedure is the same as for ``wekeo_main``.

----

.. card:: ``wekeo_main``
   :class-card: card-border-primary shadow-sm
   :link: https://www.wekeo.eu/

   **WEkEO Copernicus Sentinel, DEM, and CLMS data**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

    You need an access token to authenticate and to accept terms and conditions with it:

    * Create an account on `WEkEO <https://www.wekeo.eu/register>`__
    * Add your WEkEO credentials (``username``, ``password``) to the user configuration file.
    * Depending on which data you want to retrieve, you will then need to accept terms and conditions (for once).
      To do this, follow the
      `tutorial guidelines <https://eodag.readthedocs.io/en/latest/notebooks/tutos/tuto_wekeo.html#Registration>`__
      or run the following commands in your terminal.

    * First, get a token from your base64-encoded credentials (replace USERNAME and PASSWORD with your credentials):

      .. code-block:: bash

          curl -X POST --data '{"username": "USERNAME", "password": "PASSWORD"}' \
          -H "Content-Type: application/json" \
          "https://gateway.prod.wekeo2.eu/hda-broker/gettoken"

      The WEkEO API will respond with a token:

      .. code-block:: bash

          { "access_token": "xxxxxxxx-yyyy-zzzz-xxxx-yyyyyyyyyyyy",
            "refresh_token": "xxxxxxxx-yyyy-zzzz-xxxx-yyyyyyyyyyyy",
            "scope":"openid",
            "id_token":"token",
            "token_type":"Bearer",
            "expires_in":3600
          }

    * Accept terms and conditions by running this command and replacing <access_token> and <licence_name>:

      .. code-block:: bash

          curl --request PUT \
              --header 'accept: application/json' \
              --header 'Authorization: Bearer <access_token>' \
              https://gateway.prod.wekeo2.eu/hda-broker/api/v1/termsaccepted/<licence_name>

    The licence name depends on which data you want to retrieve.
    To use all datasets available in WEkEO, the following licences have to be accepted:

    * EUMETSAT_Copernicus_Data_Licence
    * Copernicus_Land_Monitoring_Service_Data_Policy
    * Copernicus_Sentinel_License
    * Copernicus_ECMWF_License
    * Copernicus_DEM_Instance_COP-DEM-GLO-30-F_Global_30m
    * Copernicus_DEM_Instance_COP-DEM-GLO-90-F_Global_90m

----

**CREODIAS**
~~~~~~~~~~~~

.. card:: ``creodias``
   :class-card: card-border-primary shadow-sm
   :link: https://creodias.eu/

   **CloudFerro DIAS**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

    Create an account `here <https://portal.creodias.eu/register.php>`__, then use your ``username``, ``password`` in eodag
    credentials. You will also need `totp` in credentials, a temporary 6-digits OTP (One Time Password, see
    `Creodias documentation
    <https://creodias.docs.cloudferro.com/en/latest/gettingstarted/Two-Factor-Authentication-for-Creodias-Site.html>`__)
    to be able to authenticate and download. Check
    `Authenticate using an OTP
    <https://eodag.readthedocs.io/en/latest/getting_started_guide/configure.html#authenticate-using-an-otp-one-time-password-two-factor-authentication>`__
    to see how to proceed.

----

.. card:: ``creodias_s3``
   :class-card: card-border-primary shadow-sm
   :link: https://creodias.eu/

   **CloudFerro DIAS data through S3 protocol**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

    Create an account on `creodias <https://creodias.eu/>`__, then go to
    `keymanager <https://eodata-keymanager.creodias.eu/>`__ and click `Add credential` to generate the s3 access key and
    secret key. Add those credentials to the user configuration file (variables `aws_access_key_id` and
    `aws_secret_access_key`).

----

**CNES**
--------

.. admonition:: **French National Space Agency**
   :class: note

   CNES provides access to French satellite missions including SPOT, Pléiades, and specialized thematic data hubs.

.. card:: ``geodes``
   :class-card: card-border-primary shadow-sm
   :link: https://geodes.cnes.fr

   **French National Space Agency (CNES) Earth Observation portal**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

    Go to `https://geodes-portal.cnes.fr <https://geodes-portal.cnes.fr>`_, then login or create an account by
    clicking on ``Log in`` in the top-right corner. Once logged-in, create an API key in the user settings page, and used it
    as ``apikey`` in EODAG provider auth credentials.

----

.. card:: ``geodes_s3``
   :class-card: card-border-primary shadow-sm
   :link: https://geodes.cnes.fr

   **French National Space Agency (CNES) Earth Observation portal with internal s3 Datalake**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

    This provider is only available for CNES users. You need to be connected to the CNES network to access the data.
    Get credentials for internal Datalake and use them as ``aws_access_key_id``, ``aws_secret_access_key`` and
    ``aws_session_token`` EODAG credentials.

----

.. card:: ``hydroweb_next``
   :class-card: card-border-primary shadow-sm
   :link: https://hydroweb.next.theia-land.fr

   **hydroweb.next thematic hub for hydrology data access**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

    Go to `https://hydroweb.next.theia-land.fr <https://hydroweb.next.theia-land.fr>`_, then login or create an account by
    clicking on ``Log in`` in the top-right corner. Once logged-in, create an API key in the user settings page, and used it
    as ``apikey`` in EODAG provider auth credentials.

----

.. card:: ``peps``
   :class-card: card-border-primary shadow-sm
   :link: https://peps.cnes.fr/rocket/#/home

   **French National Space Agency (CNES) catalog for Sentinel products**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

    create an account `here <https://peps.cnes.fr/rocket/#/register>`__, then use your email as ``username`` in eodag
    credentials.

----

**Destination Earth**
---------------------

.. admonition:: **Digital Twin of Earth**
   :class: note

   Destination Earth initiative creates digital replicas of Earth systems for climate adaptation and environmental policy.

.. card:: ``dedl``
   :class-card: card-border-primary shadow-sm
   :link: https://hda.data.destination-earth.eu/ui

   **Destination Earth Data Lake (DEDL)**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

    You need a `DESP OpenID` account in order to authenticate.

    To create one go `here
    <https://hda.data.destination-earth.eu/ui>`__, then click on `Sign In`, select the identity provider `DESP OpenID` and
    then click `Authenticate`. Finally click on `Register` to create a new account.

----

.. card:: ``lumi``
   :class-card: card-border-primary shadow-sm
   :link: https://polytope.lumi.apps.dte.destination-earth.eu/openapi

   DestinE Digital Twin output on Lumi

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

    Create an account on `DestinE <https://platform.destine.eu/>`__, then use your ``username``, ``password`` in eodag
    credentials.

----

**ECMWF**
---------

.. admonition:: **Weather and Climate Data**
   :class: note

   European Centre for Medium-Range Weather Forecasts providing operational and research meteorological data.

.. card:: ``ecmwf``
   :class-card: card-border-primary shadow-sm
   :link: https://www.ecmwf.int/

   **European Centre for Medium-Range Weather Forecasts**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

    Create an account `here <https://www.ecmwf.int/user/login>`__.

    Then use *email* as ``username`` and *key* as ``password`` from `here <https://api.ecmwf.int/v1/key/>`__ in eodag credentials.
    EODAG can be used to request for public datasets as for operational archive. Please note that for public datasets you
    might need to accept a license (e.g. for `TIGGE <https://apps.ecmwf.int/datasets/data/tigge/licence/>`__)

----

**ESA**
-------

.. admonition:: **European Space Agency**
   :class: note

   European Space Agency providing access to climate monitoring and Earth observation missions.

.. card:: ``fedeo_ceda``
   :class-card: card-border-primary shadow-sm
   :link: https://climate.esa.int/en/


   **FedEO CEDA (Centre for Environmental Data Archival) through CEOS Federated Earth Observation missions access. The FedEO service periodically ingests the latest ESA CCI (Climate Change Initiative) Open Data Portal catalogue of all CCI datasets.**

   :octicon:`unlock;1em;sd-text-success` No account is required

----

**EUMETSAT**
------------

.. admonition:: **Meteorological Satellites**
   :class: note

   European Organisation for the Exploitation of Meteorological Satellites providing weather and climate data.

.. card:: ``eumetsat_ds``
   :class-card: card-border-primary shadow-sm
   :link: https://data.eumetsat.int

   **EUMETSAT Data Store (European Organisation for the Exploitation of Meteorological Satellites)**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

    Create an account `here <https://eoportal.eumetsat.int/userMgmt/register.faces>`__.

    Then use the consumer key as ``username`` and the consumer secret as ``password`` from `here
    <https://api.eumetsat.int/api-key/>`__ in eodag credentials.

----

**Meteoblue**
-------------

.. admonition:: **Weather Forecast Data**
   :class: note

   Professional weather forecast and historical weather data services with high-resolution models.

.. card:: ``meteoblue``
   :class-card: card-border-primary shadow-sm
   :link: https://content.meteoblue.com/en/business-solutions/weather-apis/dataset-api

   **Meteoblue forecast**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

    EODAG uses `dataset API <https://content.meteoblue.com/en/business-solutions/weather-apis/dataset-api>`_
    which requires the access level
    `Access Gold <https://content.meteoblue.com/en/business-solutions/weather-apis/pricing>`_.

    Contact `support@meteoblue.com <mailto:support@meteoblue.com>`_ to apply for a free API key trial.

----

**Planetary Computer**
----------------------

.. admonition:: **Microsoft Azure Platform**
   :class: note

   Microsoft's planetary-scale geospatial data platform with cloud computing and analysis capabilities.

.. card:: ``planetary_computer``
   :class-card: card-border-primary shadow-sm
   :link: https://planetarycomputer.microsoft.com/

   **Microsoft Planetary Computer**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

    Most datasets are anonymously accessible, but a subscription key may be needed to increase `rate limits and access
    private datasets <https://planetarycomputer.microsoft.com/docs/concepts/sas/#rate-limits-and-access-restrictions>`_.

    Create an account `here <https://planetarycomputer.microsoft.com/account/request>`__, then view your keys by signing in
    with your Microsoft account `here <https://planetarycomputer.developer.azure-api.net/>`__.

----

**USGS / Landsat**
------------------

.. admonition:: **U.S. Geological Survey**
   :class: note

   United States Geological Survey providing access to Landsat archive and other Earth observation programs.

.. card:: ``usgs``
   :class-card: card-border-primary shadow-sm
   :link: https://earthexplorer.usgs.gov/

   **U.S geological survey catalog for Landsat products**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

    Create an account  `here <https://ers.cr.usgs.gov/register/>`__, and
    `request an access <https://ers.cr.usgs.gov/profile/access>`_ to the
    `Machine-to-Machine (M2M) API <https://m2m.cr.usgs.gov/>`_.
    Then you will need to `generate an application token <https://ers.cr.usgs.gov/password/appgenerate>`_. Use it as
    ``password`` in eodag credentials, associated to your ``username``.

    Product requests can be performed once access to the M2M API has been granted to you.

----

.. card:: ``usgs_satapi_aws``
   :class-card: card-border-primary shadow-sm
   :link: https://landsatlook.usgs.gov/sat-api/

   **USGS Landsatlook SAT API**

.. dropdown:: Registration info
  :icon: lock
  :color: muted
  :class-container: dropdown-fade-in slim-dropdown

    You need AWS credentials for download:

    * Create an account on `AWS <https://aws.amazon.com/>`__
    * Once the account is activated go to the `identity access management console <https://console.aws.amazon.com/iam/home#/home>`__
    * Click on user, then on your user name and then on security credentials.
    * In access keys, click on create access key.
    * Add these credentials to the user configuration file.

    .. warning:: **Billing Alert**

        A credit card number must be provided when creating an AWS account because fees apply
        after a given amount of downloaded data.
