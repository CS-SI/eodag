.. _intro:

Introduction
============

EODAG (Earth Observation Data Access Gateway) is a command line tool and a plugin-oriented Python framework for searching,
aggregating results and downloading remote sensed images while offering a unified API for data access regardless of the
data provider. The EODAG SDK is structured around three functions:

    * List product types: list of supported products and their description

    * Search products (by product type) : searches products according to the search criteria provided

    * Download products : download product “as is"

EODAG is developed in Python. It is structured according to a modular plugin architecture, easily extensible and able to
integrate new data providers. Three types of plugins compose the tool:

    * Catalog search plugins, responsible for searching data (OpenSearch, CSW, ...), building paths, retrieving quicklook,
      combining results

    * Download plugins, allowing to download and retrieve data locally (via FTP, HTTP, ..), always with the same directory
      organization

    * Authentication plugins, which are used to authenticate the user on the external services used (JSON Token, Basic Auth, OAUTH, ...).

Available providers
-------------------

There are currently 6 available providers implemented on eodag:

* **airbus-ds**: Airbus DS catalog for the copernicus program
* **usgs**: U.S geological survey catalog for Landsat products
* **AmazonWS**: Amazon public bucket for Sentinel 2 products
* **theia-landsat**: French National Space Agency (CNES) catalog for Pleiades and Landsat products
* **theia**: French National Space Agency (CNES) catalog for Sentinel 2 products
* **peps**: French National Space Agency (CNES) catalog for Copernicus products (Sentinel 1, 2, 3)

.. note::

    For developers, there are 2 ways for adding support for a new provider:

    * By configuring existing plugins: a provider is an instance of already implemented plugins (search, download) =>
      this only involves knowing how to write ``yaml`` documents.

    * By developing new plugins (most of the time it will be search plugins) and configuring instances of these plugins
      (see the ``plugins`` directory to see some examples of plugins).

    At the moment, you are only able to do this from source (clone the repo, do your modification, then install your version of eodag).
    In the future, it will be easier to integrate new provider configurations, to plug-in new search/download/crunch implementations,
    and to configure the order of preference of providers for search.