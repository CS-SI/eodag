.. image:: https://eodag.readthedocs.io/en/latest/_static/eodag_bycs.png
    :target: https://github.com/CS-SI/eodag

|

.. image:: https://badge.fury.io/py/eodag.svg
    :target: https://badge.fury.io/py/eodag

.. image:: https://img.shields.io/conda/vn/conda-forge/eodag
    :target: https://anaconda.org/conda-forge/eodag

.. image:: https://readthedocs.org/projects/eodag/badge/?version=latest&style=flat
    :target: https://eodag.readthedocs.io/en/latest/

.. image:: https://github.com/CS-SI/eodag/actions/workflows/test.yml/badge.svg
    :target: https://github.com/CS-SI/eodag/actions

.. image:: https://img.shields.io/github/issues/CS-SI/eodag.svg
    :target: https://github.com/CS-SI/eodag/issues

.. image:: https://mybinder.org/badge_logo.svg
    :target: https://mybinder.org/v2/git/https%3A%2F%2Fgithub.com%2FCS-SI%2Feodag.git/master?filepath=docs%2Fnotebooks%2Fintro_notebooks.ipynb

|

.. image:: https://img.shields.io/pypi/l/eodag.svg
    :target: https://pypi.org/project/eodag/

.. image:: https://img.shields.io/pypi/pyversions/eodag.svg
    :target: https://pypi.org/project/eodag/

|

..

    Checkout **EODAG Jupyterlab extension**: `eodag-labextension <https://github.com/CS-SI/eodag-labextension>`_!
    This will bring a fiendly UI to your notebook and help you search and browse for EO products using ``eodag``.

EODAG (Earth Observation Data Access Gateway) is a command line tool and a plugin-oriented Python framework for searching,
aggregating results and downloading remote sensed images while offering a unified API for data access regardless of the
data provider. The EODAG SDK is structured around three functions:

* List product types: list of supported products and their description

* Search products (by product type or uid) : searches products according to the search criteria provided

* Download products : download product “as is"

EODAG is developed in Python. It is structured according to a modular plugin architecture, easily extensible and able to
integrate new data providers. Three types of plugins compose the tool:

* Catalog search plugins, responsible for searching data (OpenSearch, CSW, ...), building paths, retrieving quicklook,
  combining results

* Download plugins, allowing to download and retrieve data locally (via FTP, HTTP, ..), always with the same directory
  organization

* Authentication plugins, which are used to authenticate the user on the external services used (JSON Token, Basic Auth, OAUTH, ...).

Since v2.0 EODAG can be run as `STAC client or server <https://eodag.readthedocs.io/en/latest/stac.html>`_.

Read `the documentation <https://eodag.readthedocs.io/en/latest/>`_ for more insights.

.. image:: https://raw.githubusercontent.com/CS-SI/eodag/develop/docs/_static/eodag_overview.png
   :alt: EODAG overview
   :class: no-scaled-link

Installation
============

EODAG is available on `PyPI <https://pypi.org/project/eodag/>`_:

.. code-block:: bash

   python -m pip install eodag

And with ``conda`` from the `conda-forge channel <https://anaconda.org/conda-forge/eodag>`_:

.. code-block:: bash

   conda install -c conda-forge eodag

Usage
=====

For downloading you will need to fill your credentials for the desired providers in your
`eodag user configuration file <https://eodag.readthedocs.io/en/latest/getting_started_guide/configure.html>`_.
The file will automatically be created with empty values on the first run.

Python API
----------

Example usage for interacting with the api in your Python code:

.. code-block:: python

    from eodag import EODataAccessGateway

    dag = EODataAccessGateway()

    search_results, total_count = dag.search(
        productType='S2_MSI_L1C',
        geom={'lonmin': 1, 'latmin': 43.5, 'lonmax': 2, 'latmax': 44}, # accepts WKT polygons, shapely.geometry, ...
        start='2021-01-01',
        end='2021-01-15'
    )

    product_paths = dag.download_all(search_results)


This will search for Sentinel 2 level-1C products on the default provider and return the found products first page and
an estimated total number of products matching the search criteria. And then it will download these products. Please
check the `Python API User Guide <https://eodag.readthedocs.io/en/latest/api_user_guide.html>`_ for more details.

STAC REST API
-------------

An eodag installation can be exposed through a STAC compliant REST api from the command line:

.. code-block:: bash

    $ eodag serve-rest --help
    Usage: eodag serve-rest [OPTIONS]

      Start eodag HTTP server

    Options:
      -f, --config PATH   File path to the user configuration file with its
                          credentials
      -d, --daemon TEXT   run in daemon mode
      -w, --world         run flask using IPv4 0.0.0.0 (all network interfaces),
                          otherwise bind to 127.0.0.1 (localhost). This maybe
                          necessary in systems that only run Flask  [default:
                          False]
      -p, --port INTEGER  The port on which to listen  [default: 5000]
      --debug             Run in debug mode (for development purpose)  [default:
                          False]
      --help              Show this message and exit.

    # run server
    $ eodag serve-rest

    # list available product types for ``peps`` provider:
    $ curl "http://127.0.0.1:5000/collections?provider=peps" | jq ".collections[].id"
    "S1_SAR_GRD"
    "S1_SAR_OCN"
    "S1_SAR_SLC"
    "S2_MSI_L1C"
    "S2_MSI_L2A"
    "S3_EFR"
    "S3_ERR"
    "S3_LAN"
    "S3_OLCI_L2LFR"
    "S3_OLCI_L2LRR"
    "S3_SLSTR_L1RBT"
    "S3_SLSTR_L2LST"

    # search for items
    $ curl "http://127.0.0.1:5000/search?collections=S2_MSI_L1C&bbox=0,43,1,44&datetime=2018-01-20/2018-01-25" \
    | jq ".context.matched"
    6

    # browse for items
    $ curl "http://127.0.0.1:5000/S2_MSI_L1C/country/FRA/year/2021/month/01/day/25/cloud_cover/10/items" \
    | jq ".context.matched"
    9

    # get download link
    $ curl "http://127.0.0.1:5000/S2_MSI_L1C/country/FRA/year/2021/month/01/day/25/cloud_cover/10/items" \
    | jq ".features[0].assets.downloadLink.href"
    "http://127.0.0.1:5000/S2_MSI_L1C/country/FRA/year/2021/month/01/day/25/cloud_cover/10/items/S2A_MSIL1C_20210125T105331_N0209_R051_T31UCR_20210125T130733/download"

    # download
    $ wget "http://127.0.0.1:5000/S2_MSI_L1C/country/FRA/year/2021/month/01/day/25/cloud_cover/10/items/S2A_MSIL1C_20210125T105331_N0209_R051_T31UCR_20210125T130733/download"


You can also browse over your STAC API server using `STAC Browser <https://github.com/radiantearth/stac-browser>`_.
Simply run:

.. code-block:: bash

    git clone https://github.com/CS-SI/eodag.git
    cd eodag
    docker-compose up
    # or for a more verbose logging:
    EODAG_LOGGING=3 docker-compose up

And browse http://127.0.0.1:5001:

.. image:: https://raw.githubusercontent.com/CS-SI/eodag/develop/docs/_static/stac_browser_example_600.png
   :target: https://raw.githubusercontent.com/CS-SI/eodag/develop/docs/_static/stac_browser_example.png
   :alt: STAC browser example
   :width: 600px


For more information, see `STAC REST API usage <https://eodag.readthedocs.io/en/latest/stac_rest.html>`_.

Command line interface
----------------------

Start playing with the CLI:

- To search for some products::

     eodag search --productType S2_MSI_L1C --box 1 43 2 44 --start 2021-03-01 --end 2021-03-31

  The request above searches for ``S2_MSI_L1C`` product types in a given bounding box, in March 2021. It saves the results in a GeoJSON file (``search_results.geojson`` by default).

  Results are paginated, you may want to get all pages at once with ``--all``, or search products having 20% of maximum coud cover with ``--cloudCover 20``. For more information on available options::

     eodag search --help

- To download the result of the previous call to search::

     eodag download --search-results search_results.geojson

- To download only the result quicklooks of the previous call to search::

     eodag download --quicklooks --search-results search_results.geojson

- To list all available product types and supported providers::

     eodag list

- To list available product types on a specified supported provider::

     eodag list -p sobloo

- To see all the available options and commands::

     eodag --help

- To print log messages, add ``-v`` to eodag master command. e.g. ``eodag -v list``. The more ``v`` given (up to 3), the more verbose the tool is. For a full verbose output, do for example: ``eodag -vvv list``

Contribute
==========

Have you spotted a typo in our documentation? Have you observed a bug while running EODAG?
Do you have a suggestion for a new feature?

Don't hesitate and open an issue or submit a pull request, contributions are most welcome!

For guidance on setting up a development environment and how to make a
contribution to eodag, see the `contributing guidelines`_.

.. _contributing guidelines: https://github.com/CS-SI/eodag/blob/develop/CONTRIBUTING.rst


License
=======

EODAG is licensed under Apache License v2.0.
See LICENSE file for details.


Authors
=======

EODAG has been created by `CS GROUP - France <https://www.csgroup.eu/>`_.


Credits
=======

EODAG is built on top of amazingly useful open source projects. See NOTICE file for details about those projects and
their licenses.
Thank you to all the authors of these projects !
