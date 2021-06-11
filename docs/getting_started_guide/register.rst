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

* `peps`: create an account `here <https://peps.cnes.fr/rocket/#/register>`__

* `sobloo`: create an account `here <https://sobloo.eu/>`__ and get an API key

* `creodias`: create an account `here <https://portal.creodias.eu/register.php>`__

* `onda`: create an account `here: <https://www.onda-dias.eu/cms/>`__

* `mundi`: create an account `here <https://mundiwebservices.com>`__ (click on "login" and then go in the "register" tab).
  Then use as *apikey* the Web Token provided `here <https://mundiwebservices.com/account/profile>`__

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
