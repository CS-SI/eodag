.. _cli_user_guide:

CLI User Guide
==============

Make sure you correctly followed instructions on :ref:`configure` and :ref:`register`.

Then you can start playing with it:

* Run ``eodag --help`` to display all the available options and commands:

.. code-block:: console

        Usage: eodag [OPTIONS] COMMAND [ARGS]...

        Earth Observation Data Access Gateway: work on EO products from any
        provider

        Options:
        -v, --verbose  Control the verbosity of the logs. For maximum verbosity,
                        type -vvv
        --help         Show this message and exit.

        Commands:
        deploy-wsgi-app  Configure the settings of the HTTP web app (the
                        providers...
        download         Download a list of products from a serialized search...
        list             List supported product types
        search           Search satellite images by their product types,...
        serve-rest       Start eodag HTTP server
        serve-rpc        Start eodag rpc server
        version          Print eodag version and exit

* Each command has its own help, see for instance the help of the ``list`` command with ``eodag list --help``:

.. code-block:: console

        Usage: eodag list [OPTIONS]

        List supported product types

        Options:
        -p, --provider TEXT             List product types supported by this
                                        provider
        -i, --instrument TEXT           List product types originating from this
                                        instrument
        -P, --platform TEXT             List product types originating from this
                                        platform
        -t, --platformSerialIdentifier TEXT
                                        List product types originating from the
                                        satellite identified by this keyword
        -L, --processingLevel TEXT      List product types of processing level
        -S, --sensorType TEXT           List product types originating from this
                                        type of sensor
        --help                          Show this message and exit.

* By default the command line interface of eodag is set to the minimum verbosity level. You can print more
  log messages by adding ``-v`` to eodag master command. The more ``v`` given (up to 3), the more verbose the tool is.
  This feature comes in handy when you want to inspect an error or an unexpected behaviour. 4 different verbosity levels
  are offered to you:

.. code-block:: console

        eodag list
        eodag -v list
        eodag -vv list
        eodag -vvv list

* To search for products and crunch the results of the search:

.. code-block:: console

        eodag search \
        --conf my_conf.yml \
        --box 1 43 2 44 \
        --start 2018-01-01 --end 2018-01-31 \
        --productType S2_MSI_L1C \
        --all \
        --storage my_search.geojson

The request above searches for `S2_MSI_L1C` product types in a given bounding box, in January 2018. The command fetches internally all
the products that match these criteria. Without ``--all``, it would only fetch the products found on the first result page.
It finally saves the results in a GeoJSON file.

You can pass arguments to a cruncher on the command line by doing this (example with using ``FilterOverlap`` cruncher
which takes ``minimum_overlap`` as argument):

.. code-block:: console

        eodag search -f my_conf.yml -b 1 43 2 44 -s 2018-01-01 -e 2018-01-31 -p S2_MSI_L1C --all \
                     --cruncher FilterOverlap \
                     --cruncher-args FilterOverlap minimum_overlap 10

The request above means : "Give me all the products of type `S2_MSI_L1C`, use ``FilterOverlap`` to keep only those products
that are contained in the bbox I gave you, or whose spatial extent overlaps at least 10% (``minimum_overlap``) of the surface
of this bbox"

You can use ``eaodag search`` with custom parameters. Custom parameters will be used as is in the query string search sent
to the provider. For instance, if you want to add foo=1 and bar=2 to the previous query:

.. code-block:: console

        eodag search -f my_conf.yml -b 1 43 2 44 -s 2018-01-01 -e 2018-01-31 -p S2_MSI_L1C \
                     --cruncher FilterOverlap \
                     --cruncher-args FilterOverlap minimum_overlap 1 \
                     --custom "foo=1&bar=2"

* To download the result of a previous call to ``search``:

.. code-block:: console

        eodag download --conf my_conf.yml --search-results my_search.geojson

* To list all available product types and supported providers:

.. code-block:: console

        eodag list

* To list available product types on a specified supported provider:

.. code-block:: console

        eodag list -p sobloo
