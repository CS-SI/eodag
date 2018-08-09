.. _use:

Command line interface
======================

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

    This file contains login information in clear text. Make sure you correctly configure access rules to it. It should
    be read/write-able only by the current user of eodag.

Then you can start playing with it:

* To search for products and crunch the results of the search::

        eodag search \
        --conf my_conf.yml \
        --geometry 1 43 2 44 \
        --startTimeFromAscendingNode 2018-01-01 --completionTimeFromAscendingNode 2018-01-31 \
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

* To download the result of a previous call to `search`::

        eodag download --conf my_conf.yml --search-results my_search.geojson

* To list all available product types and supported providers::

        eodag list

* To list available product types on a specified supported provider::

        eodag list -p airbus-ds

* To see all the available options and commands::

        eodag --help

* To print log messages, add `-v` to `eodag` master command. e.g. `eodag -v list`. The more `v` given (up to 3), the more
  verbose the tool is.

.. note::

    How to get Amazon Web Services access keys ?

    * Create an account on AWS website: https://aws.amazon.com/fr/ (warning: A credit card number must be given because data
      become paying after a given amount of downloaded data).
    * Once the account is activated go to the identity and access management console: https://console.aws.amazon.com/iam/home#/home
    * Click on user, then on your user name and then on security credentials.
    * In access keys, click on create access key.
    * Add these credentials to the user conf file.