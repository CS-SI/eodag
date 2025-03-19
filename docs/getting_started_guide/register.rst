.. _register:

Provider registration
=====================

The providers usually require their user to register to their service. As a result,
the users obtain a set of credentials (e.g. login/password, API key, etc.). These credentials
need to be provided to ``eodag`` (see :ref:`configure`). The list below explains how to register
to each provider supported by ``eodag``:

[AWS] ``earth_search``, ``usgs_satapi_aws``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
You need AWS credentials for download:

* Create an account on `AWS <https://aws.amazon.com/>`__
* Once the account is activated go to the `identity access management console <https://console.aws.amazon.com/iam/home#/home>`__
* Click on user, then on your user name and then on security credentials.
* In access keys, click on create access key.
* Add these credentials to the user configuration file.

.. warning::

    A credit card number must be provided when creating an AWS account because fees apply
    after a given amount of downloaded data.

``aws_eos``
^^^^^^^^^^^
You need credentials for both EOS (search) and AWS (download):

* Create an account on `EOS <https://auth.eos.com>`__
* Get your EOS api key from `here <https://api-connect.eos.com/user-dashboard/statistics>`__
* Create an account on `AWS <https://aws.amazon.com/>`__
* Once the account is activated go to the `identity access management console <https://console.aws.amazon.com/iam/home#/home>`__
* Click on user, then on your user name and then on security credentials.
* In access keys, click on create access key.
* Add these credentials to the user configuration file:

  * ``search_auth.credentials.api_key``
  * ``download_auth.credentials.aws_access_key_id`` and ``download_auth.credentials.aws_secret_access_key`` or ``download_auth.credentials.aws_profile``

.. note::

    EOS free account is limited to 100 requests.

``cop_ads``
^^^^^^^^^^^
Go to the `ECMWF homepage <https://www.ecmwf.int/>`__ and create an account by clicking on *Log in* and then *Register*.

Then log in and go to your user profile on `Atmosphere Data Store <https://ads.atmosphere.copernicus.eu/>`__ and
use your *Personal Access Token* as ``apikey`` in eodag credentials.

To download data you have to accept the `Licence to use Copernicus Products`. To accept the licence:

* Go to `Datasets <https://ads.atmosphere.copernicus.eu/datasets>`__ while being logged in.
* Open the details of a dataset and go to the download tab.
* Scroll down and accept the licence in the section `Terms of use`.
* You can check which licences you have accepted in your user profile.

``cop_cds``
^^^^^^^^^^^
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

``cop_dataspace``
^^^^^^^^^^^^^^^^^
Create an account `here
<https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/auth?client_id=cdse-public&redirect_uri=https%3A%2F%2Fdataspace.copernicus.eu%2Fbrowser%2F&response_type=code&scope=openid>`__

``cop_ewds``
^^^^^^^^^^^^
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

``cop_marine``
^^^^^^^^^^^^^^
No account is required

``creodias``
^^^^^^^^^^^^
Create an account `here <https://portal.creodias.eu/register.php>`__, then use your ``username``, ``password`` in eodag
credentials. You will also need `totp` in credentials, a temporary 6-digits OTP (One Time Password, see
`Creodias documentation
<https://creodias.docs.cloudferro.com/en/latest/gettingstarted/Two-Factor-Authentication-for-Creodias-Site.html>`__)
to be able to authenticate and download. Check
`Authenticate using an OTP
<https://eodag.readthedocs.io/en/latest/getting_started_guide/configure.html#authenticate-using-an-otp-one-time-password-two-factor-authentication>`__
to see how to proceed.

``creodias_s3``
^^^^^^^^^^^^^^^
Create an account on `creodias <https://creodias.eu/>`__, then go to
`keymanager <https://eodata-keymanager.creodias.eu/>`__ and click `Add credential` to generate the s3 access key and
secret key. Add those credentials to the user configuration file (variables `aws_access_key_id` and
`aws_secret_access_key`).

``dedl``
^^^^^^^^
You need a `DESP OpenID` account in order to authenticate.

To create one go `here
<https://hda.data.destination-earth.eu/ui>`__, then click on `Sign In`, select the identity provider `DESP OpenID` and
then click `Authenticate`. Finally click on `Register` to create a new account.

``dedt_lumi``
^^^^^^^^^^^^^
Create an account on `DestinE <https://platform.destine.eu/>`__, then use your ``username``, ``password`` in eodag
credentials.

``earth_search_gcs``
^^^^^^^^^^^^^^^^^^^^
you need HMAC keys for Google Cloud Storage:

* Sign in using a `google account <https://accounts.google.com/signin/v2/identifier>`__.
* Get or create `HMAC keys <https://cloud.google.com/storage/docs/authentication/hmackeys>`__ for your user account
  on a project for interoperability API access from this
  `page <https://console.cloud.google.com/storage/settings;tab=interoperability>`__ (create a default project if
  none exists).
* Add these credentials to the user configuration file.

``earth_search_cog``
^^^^^^^^^^^^^^^^^^^^
No authentication needed.

``ecmwf``
^^^^^^^^^
Create an account `here <https://apps.ecmwf.int/registration/>`__.

Then use *email* as ``username`` and *key* as ``password`` from `here <https://api.ecmwf.int/v1/key/>`__ in eodag credentials.
EODAG can be used to request for public datasets as for operational archive. Please note that for public datasets you
might need to accept a license (e.g. for `TIGGE <https://apps.ecmwf.int/datasets/data/tigge/licence/>`__)

``eumetsat_ds``
^^^^^^^^^^^^^^^
Create an account `here <https://eoportal.eumetsat.int/userMgmt/register.faces>`__.

Then use the consumer key as ``username`` and the consumer secret as ``password`` from `here
<https://api.eumetsat.int/api-key/>`__ in eodag credentials.

``geodes``
^^^^^^^^^^
Go to `https://geodes-portal.cnes.fr <https://geodes-portal.cnes.fr>`_, then login or create an account by
clicking on ``Log in`` in the top-right corner. Once logged-in, create an API key in the user settings page, and used it
as ``apikey`` in EODAG provider auth credentials.

``geodes_s3``
^^^^^^^^^^^^^
This provider is only available for CNES users. You need to be connected to the CNES network to access the data.
Get credentials for internal Datalake and use them as ``aws_access_key_id``, ``aws_secret_access_key`` and
``aws_session_token`` EODAG credentials.

``hydroweb_next``
^^^^^^^^^^^^^^^^^
Go to `https://hydroweb.next.theia-land.fr <https://hydroweb.next.theia-land.fr>`_, then login or create an account by
clicking on ``Log in`` in the top-right corner. Once logged-in, create an API key in the user settings page, and used it
as ``apikey`` in EODAG provider auth credentials.

``meteoblue``
^^^^^^^^^^^^^
EODAG uses `dataset API <https://content.meteoblue.com/en/business-solutions/weather-apis/dataset-api>`_
which requires the access level
`Access Gold <https://content.meteoblue.com/en/business-solutions/weather-apis/pricing>`_.

Contact `support@meteoblue.com <mailto:support@meteoblue.com>`_ to apply for a free API key trial.

``peps``
^^^^^^^^
create an account `here <https://peps.cnes.fr/rocket/#/register>`__, then use your email as ``username`` in eodag
credentials.

``planetary_computer``
^^^^^^^^^^^^^^^^^^^^^^
Most datasets are anonymously accessible, but a subscription key may be needed to increase `rate limits and access
private datasets <https://planetarycomputer.microsoft.com/docs/concepts/sas/#rate-limits-and-access-restrictions>`_.

Create an account `here <https://planetarycomputer.microsoft.com/account/request>`__, then view your keys by signing in
with your Microsoft account `here <https://planetarycomputer.developer.azure-api.net/>`__.

``sara``
^^^^^^^^
Create an account `here <https://copernicus.nci.org.au/sara.client/#/register>`__, then use your email as ``username`` in
eodag credentials.

``theia``
^^^^^^^^^
Create an account `here <https://sso.theia-land.fr/theia/register/register.xhtml>`__

``usgs``
^^^^^^^^
Create an account  `here <https://ers.cr.usgs.gov/register/>`__, and
`request an access <https://ers.cr.usgs.gov/profile/access>`_ to the
`Machine-to-Machine (M2M) API <https://m2m.cr.usgs.gov/>`_.
Then you will need to `generate an application token <https://ers.cr.usgs.gov/password/appgenerate>`_. Use it as
``password`` in eodag credentials, associated to your ``username``.

Product requests can be performed once access to the M2M API has been granted to you.

``wekeo_cmems``
^^^^^^^^^^^^^^^
The registration procedure is the same as for ``wekeo_main``. The licence that has to be accepted to access the
Copernicus Marine data is ``Copernicus_Marine_Service_Product_License``.

``wekeo_ecmwf``
^^^^^^^^^^^^^^^
The registration procedure is the same as for `wekeo_main <getting_started_guide/register.rst#wekeo_main>`_.

``wekeo_main``
^^^^^^^^^^^^^^
You need an access token to authenticate and to accept terms and conditions with it:

* Create an account on `WEkEO <https://www.wekeo.eu/register>`__
* Add your WEkEO credentials (``username``, ``password``) to the user configuration file.
* Depending on which data you want to retrieve, you will then need to accept terms and conditions (for once). To do this, follow the
  `tutorial guidelines <https://eodag.readthedocs.io/en/latest/notebooks/tutos/tuto_wekeo.html#Registration>`__
  or run the following commands in your terminal.
* First, get a token from your base64-encoded credentials (replace USERNAME and PASSWORD with your credentials):

  .. code-block:: bash

    curl -X POST --data '{"username": "USERNAME", "password": "PASSWORD"}' -H "Content-Type: application/json" "https://gateway.prod.wekeo2.eu/hda-broker/gettoken"

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

    curl --request PUT --header 'accept: application/json' --header 'Authorization: Bearer <access_token>' https://gateway.prod.wekeo2.eu/hda-broker/api/v1/termsaccepted/<licence_name>

  The licence name depends on which data you want to retrieve. To use all datasets available in wekeo, the following licences have to be accepted:

  * EUMETSAT_Copernicus_Data_Licence
  * Copernicus_Land_Monitoring_Service_Data_Policy
  * Copernicus_Sentinel_License
  * Copernicus_ECMWF_License
  * Copernicus_DEM_Instance_COP-DEM-GLO-30-F_Global_30m
  * Copernicus_DEM_Instance_COP-DEM-GLO-90-F_Global_90m
