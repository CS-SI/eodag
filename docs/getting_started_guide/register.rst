.. _register:

Provider registration
=====================

The providers usually require their user to register to their service. As a result,
the users obtain a set of credentials (e.g. login/password, API key, etc.). These credentials
need to be provided to ``eodag`` (see :ref:`configure`). The list below explains how to register
to each provider supported by ``eodag``:

* `usgs`: create an account  `here <https://ers.cr.usgs.gov/register/>`__ and then `request an access <https://ers.cr.usgs.gov/profile/access>`_ to the `Machine-to-Machine (M2M) API <https://m2m.cr.usgs.gov/>`_.
  Product requests can be performed once access to the M2M API has been granted to you.

* `theia`: create an account `here <https://sso.theia-land.fr/theia/register/register.xhtml>`__

* `peps`: create an account `here <https://peps.cnes.fr/rocket/#/register>`__, then use your email as `username` in eodag credentials.

* `creodias`: create an account `here <https://portal.creodias.eu/register.php>`__

* `onda`: create an account `here: <https://www.onda-dias.eu/cms/>`__

* `mundi`: create an account `here <https://mundiwebservices.com>`__ (click on "login" and then go in the "register" tab).
  Then use as *apikey* the Web Token provided `here <https://mundiwebservices.com/account/profile>`__

* `ecmwf`: create an account `here <https://apps.ecmwf.int/registration/>`__.
  Then use *email* as *username* and *key* as *password* from `here <https://api.ecmwf.int/v1/key/>`__ in eodag credentials.
  EODAG can be used to request for public datasets as for operational archive. Please note that for public datasets you
  might need to accept a license (e.g. for `TIGGE <https://apps.ecmwf.int/datasets/data/tigge/licence/>`__)

* `cop_ads`: create an account `here <https://ads.atmosphere.copernicus.eu/user/register>`__.
  Then go to your profile and use from the section named "API key" the *UID* as *username* and *API Key* as *password* in eodag credentials.
  EODAG can be used to request for public datasets, you can browse them `here <https://ads.atmosphere.copernicus.eu/cdsapp#!/search?type=dataset>`__.

* `cop_cds`: create an account `here <https://cds.climate.copernicus.eu/user/register>`__.
  Then go to your profile and use from the section named "API key" use *UID* as *username* and *API Key* as *password* in eodag credentials.
  EODAG can be used to request for public datasets, you can browse them `here <https://cds.climate.copernicus.eu/cdsapp#!/search?type=dataset>`__.

* `sara`: create an account `here <https://copernicus.nci.org.au/sara.client/#/register>`__, then use your email as `username` in eodag credentials.

* `meteoblue`: eodag uses `dataset API <https://content.meteoblue.com/en/business-solutions/weather-apis/dataset-api>`_
  which requires the access level `Access Gold <https://content.meteoblue.com/en/business-solutions/weather-apis/pricing>`_.
  Contact `support@meteoblue.com <mailto:support@meteoblue.com>`_ to apply for a free API key trial.

* `cop_dataspace`: create an account `here <https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/auth?client_id=cdse-public&redirect_uri=https%3A%2F%2Fdataspace.copernicus.eu%2Fbrowser%2F&response_type=code&scope=openid>`__

* `planetary_computer`: most datasets are anonymously accessible, but a subscription key may be needed to increase `rate limits and access private datasets <https://planetarycomputer.microsoft.com/docs/concepts/sas/#rate-limits-and-access-restrictions>`_.
  Create an account `here <https://planetarycomputer.microsoft.com/account/request>`__, then view your keys by signing in with your Microsoft account `here <https://planetarycomputer.developer.azure-api.net/>`__.

* `aws_eos`: you need credentials for both EOS (search) and AWS (download):

  * Create an account on `EOS <https://auth.eos.com>`__

  * Get your EOS api key from `here <https://console.eos.com>`__

  * Create an account on `AWS <https://aws.amazon.com/>`__

  * Once the account is activated go to the `identity access management console <https://console.aws.amazon.com/iam/home#/home>`__

  * Click on user, then on your user name and then on security credentials.

  * In access keys, click on create access key.

  * Add these credentials to the user configuration file.

.. note::

    EOS free account is limited to 100 requests.

* `astraea_eod, earth_search, usgs_satapi_aws`: you need AWS credentials for download:

  * Create an account on `AWS <https://aws.amazon.com/>`__

  * Once the account is activated go to the `identity access management console <https://console.aws.amazon.com/iam/home#/home>`__

  * Click on user, then on your user name and then on security credentials.

  * In access keys, click on create access key.

  * Add these credentials to the user configuration file.

.. warning::

    A credit card number must be provided when creating an AWS account because fees apply
    after a given amount of downloaded data.

* `earth_search_gcs`: you need HMAC keys for Google Cloud Storage:

  * Sign in using a `google account <https://accounts.google.com/signin/v2/identifier>`__.

  * Get or create `HMAC keys <https://cloud.google.com/storage/docs/authentication/hmackeys>`__ for your user account
    on a project for interoperability API access from this
    `page <https://console.cloud.google.com/storage/settings;tab=interoperability>`__ (create a default project if
    none exists).

  * Add these credentials to the user configuration file.
