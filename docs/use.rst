.. _use:

Command line interface
======================

Make sure you correctly followed instructions on :ref:`user-config-file`.

Then you can start playing with it:

* To search for products and crunch the results of the search::

        eodag search \
        --conf my_conf.yml \
        --box 1 43 2 44 \
        --start 2018-01-01 --end 2018-01-31 \
        --productType S2_MSI_L1C \
        --cruncher FilterLatestIntersect \
        --storage my_search.geojson

The request above search for product types `S2_MSI_L1C` and will crunch the result using cruncher `FilterLatestIntersect`
and storing the overall result to `my_search.geojson`.

You can pass arguments to a cruncher on the command line by doing this (example with using `FilterOverlap` cruncher
which takes `minimum_overlap` as argument)::

        eodag search -f my_conf.yml -b 1 43 2 44 -s 2018-01-01 -e 2018-01-31 -p S2_MSI_L1C \
                     --cruncher FilterOverlap \
                     --cruncher-args FilterOverlap minimum_overlap 10

The request above means : "Give me all the products of type `S2_MSI_L1C`, use `FilterOverlap` to keep only those products
that are contained in the bbox I gave you, or whom spatial extent overlaps at least 10% (`minimum_overlap`) of the surface
of this bbox"

You can use `eaodag search` with custom parameters. Custom parameters will be used as is in the query string search sent
to the provider. For instance, if you want to add foo=1 and bar=2 to the previous query::

        eodag search -f my_conf.yml -b 1 43 2 44 -s 2018-01-01 -e 2018-01-31 -p S2_MSI_L1C \
                     --cruncher FilterOverlap \
                     --cruncher-args FilterOverlap minimum_overlap 1 \
                     --custom "foo=1&bar=2"

* To download the result of a previous call to `search`::

        eodag download --conf my_conf.yml --search-results my_search.geojson

* To list all available product types and supported providers::

        eodag list

* To list available product types on a specified supported provider::

        eodag list -p sobloo

* To see all the available options and commands::

        eodag --help

* To print log messages, add `-v` to `eodag` master command. e.g. `eodag -v list`. The more `v` given (up to 3), the more
  verbose the tool is.


HTTP Rest Interface
===================

EODAG has a REST API implementing OpenSearch Geo interface. To run the server, do::

    eodag serve-rest -f <configuration-file>

Below is the content of the help message of this command::

    # eodag serve-rest --help
    Usage: eodag serve-rest [OPTIONS]

      Start eodag HTTP server

    Options:
      -f, --config PATH   File path to the user configuration file with its
                          credentials  [required]
      -d, --daemon        run in daemon mode  [default: False]
      -w, --world         run flask using IPv4 0.0.0.0 (all network interfaces),
                          otherwise bind to 127.0.0.1 (localhost). This maybe
                          necessary in systems that only run Flask  [default:
                          False]
      -p, --port INTEGER  The port on which to listen  [default: 5000]
      --debug             Run in debug mode (for development purpose)  [default:
                          False]
      --help              Show this message and exit.

Searching
---------

After you have launched the server, navigate to its home page. For example, for a local
development server launched with `eodag serve-rest -f <config> --debug`, go to
http://127.0.0.1:5000/. You will see a documentation of the interface.

The supported operations are:

* List product types::

    # All supported product types
    http://127.0.0.1:5000/product-types
    # <provider> only supported product types
    http://127.0.0.1:5000/product-types/<provider>

* Search product::

    http://127.0.0.1:5000/<product_type>/?param=value

The supported request parameters are:

* `box`: the search bounding box defined by: min_lon,min_lat,max_lon,max_lat.
* `dtstart`: the start date
* `dtend`: the end date
* `cloudCover`: cloud cover

Example URL::

    http://127.0.0.1:5000/S2_MSI_L1C/?box=0,43,1,44

Filtering
---------

The service provides ability to filter search results by the crunchers available
to EODAG. To activate a filter, add the `filter` request parameter.

Available filters and their matching EODAG cruncher are:

* `latestIntersect` -> FilterLatestIntersect
* `latestByName` -> FilterLatestByName
* `overlap` -> FilterOverlap

Some filters may require additional configuration parameters
which can be set as request parameters.
For example, overlap filter requires adding a `minimum_overlap` parameter to the request.

Example URL::

    http://127.0.0.1:5000/S2_MSI_L1C/?box=0,43,1,44&filter=overlap&minimum_overlap=0
