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
    :target: https://mybinder.org/v2/git/https%3A%2F%2Fgithub.com%2FCS-SI%2Feodag.git/master?filepath=examples%2Ftuto_basics.ipynb

|

.. image:: https://img.shields.io/pypi/l/eodag.svg
    :target: https://pypi.org/project/eodag/

.. image:: https://img.shields.io/pypi/pyversions/eodag.svg
    :target: https://pypi.org/project/eodag/

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

Since v2.0 EODAG can be run as `STAC client or server <https://eodag.readthedocs.io/en/latest/intro.html#stac-client-and-server>`_.

Read `the documentation <https://eodag.readthedocs.io/en/latest/>`_ for more insights.

.. image:: https://raw.githubusercontent.com/CS-SI/eodag/develop/docs/_static/eodag_overview.png
   :alt: EODAG overview
   :class: no-scaled-link

Installation
============

EODAG is on `PyPI <https://pypi.org/project/eodag/>`_:

.. code-block:: bash

    python -m pip install eodag


Usage
=====

For downloading you will need to fill your credentials for the desired providers in your
`eodag user configuration file <https://eodag.readthedocs.io/en/latest/intro.html#how-to-configure-authentication-for-available-providers>`_.
The file will automatically be created with empty values on the first run.

Python API
----------

Example usage for interacting with the api in your Python code:

.. code-block:: python

    from eodag import EODataAccessGateway

    dag = EODataAccessGateway()
    search_results, found_nb = dag.search(
        productType='S2_MSI_L1C',
        geom={'lonmin': 1, 'latmin': 43.5, 'lonmax': 2, 'latmax': 44}, # accepts WKT polygons, shapely.geometry, ...
        start='2021-01-01',
        end='2021-01-15'
    )
    product_paths = dag.download_all(search_results)


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


And browse http://127.0.0.1:5001:

.. image:: https://raw.githubusercontent.com/CS-SI/eodag/develop/docs/_static/stac_browser_example_600.png
   :target: https://raw.githubusercontent.com/CS-SI/eodag/develop/docs/_static/stac_browser_example.png
   :alt: STAC browser example
   :width: 600px


For more information, see `STAC REST interface usage <https://eodag.readthedocs.io/en/latest/use.html#stac-rest-interface>`_.

Command line interface
----------------------

Create a configuration file from the template `user_conf_template.yml` provided with the repository, filling
in your credentials as expected by each provider (note that this configuration file is required by now. However, this
will change in the future).

Then you can start playing with it:

* To search for products and crunch the results of the search::

        eodag search \
        --conf my_conf.yml \
        --box 1 43 2 44 \
        --start 2018-01-01 \
        --end 2018-01-31 \
        --cloudCover 20 \
        --productType S2_MSI_L1C \
        --all \
        --storage my_search.geojson

The request above searches for `S2_MSI_L1C` product types in a given bounding box, in January 2018. The command fetches internally all
the products that match these criteria. Without `--all`, it would only fetch the products found on the first result page.
It finally saves the results in a GeoJSON file.

You can pass arguments to a cruncher on the command line by doing this (example with using `FilterOverlap` cruncher
which takes `minimum_overlap` as argument)::

        eodag search -f my_conf.yml -b 1 43 2 44 -s 2018-01-01 -e 2018-01-31 -p S2_MSI_L1C --all \
                     --cruncher FilterOverlap \
                     --cruncher-args FilterOverlap minimum_overlap 10

The request above means : "Give me all the products of type `S2_MSI_L1C`, use `FilterOverlap` to keep only those products
that are contained in the bbox I gave you, or whose spatial extent overlaps at least 10% (`minimum_overlap`) of the surface
of this bbox"

* To download the result of a previous call to `search`::

        eodag download --conf my_conf.yml --search-results my_search.geojson

* To list all available product types and supported providers::

        eodag list

* To list available product types on a specified supported provider::

        eodag list -p sobloo

* To see all the available options and commands::

        eodag --help

* To print log messages, add `-v` to `eodag` master command. e.g. `eodag -v list`. The more `v` given (up to 3), the more
  verbose the tool is. For a full verbose output, do for example: ``eodag -vvv list``


Contribute
==========

For guidance on setting up a development environment and how to make a
contribution to eodag, see the `contributing guidelines`_.

.. _contributing guidelines: https://github.com/CS-SI/eodag/blob/develop/CONTRIBUTING.rst


LICENSE
=======

EODAG is licensed under Apache License v2.0.
See LICENSE file for details.


AUTHORS
=======

EODAG is developed by `CS GROUP - France <https://www.c-s.fr>`_.


CREDITS
=======

EODAG is built on top of amazingly useful open source projects. See NOTICE file for details about those projects and
their licenses.
Thank you to all the authors of these projects !
