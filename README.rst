eodag
=====

Eodag is a command line tool and a plugin-oriented framework for searching, crunching and downloading remote sensed
images (mainly from satellite systems).

You can search and download satellite products:

* through the embedded cli:

    .. code-block:: bash

        eodag search --conf user.conf.yaml --bbox 1 43 2 44 --startDate 2018-01-01 --endDate 2018-01-31 --productType S2-L1C
        # With the shortcut arguments
        eodag search -f user.conf.yaml -b 1 43 2 44 -s 2018-01-01 -e 2018-01-31 -c 20 -p S2-L1C

* by interacting with the api in your Python scripts:

    .. code-block:: python

        from eodag import SatImagesAPI

        api = SatImagesAPI(user_conf_file_path='/path/to/user/conf.yaml')
        producttype = 'S2-L1C'
        footprint = {'lonmin': 1, 'latmin': 43.5, 'lonmax': 2, 'latmax': 44}
        start, end = '2018-01-01', '2018-01-31'
        for local_filename in api.download_all(api.search(producttype, footprint=footprint, startDate=start, endDate=end):
            print('Downloaded : {}'.format(local_filename))


.. note::

    .. role:: python(code)
       :language: python

    :python:`download_all` is a Python generator yielding paths to downloaded resources one by one to allow working on that
    path right away after download. If you want a list, you must cast it directly: :python:`list(api.download_all(...))`

If you wish to extend the supported productor systems instances, you can :

* configure an instance of known plugins => this only involves knowing how to write ``yaml`` documents (see ``resources/symtem_conf_default.yml``
  for examples of how to configure a system instance)

* develop plugins defining how to search products, transform search results and download them from a productor system
  which is not supported by eodag (see the ``plugins`` directory to see some examples of plugins).

Read `the documentation <https://bitbucket.org/geostorm/eodag>`_ for more insights.

Installation
============

.. code-block:: bash

    USER=<allowed-user>
    git clone https://${USER}@bitbucket.org/geostorm/eodag.git
    # Then open `eodag/eodag/resources/system_conf_default` and set the highest `priority` number to the preferred system
    # (default is eocloud)
    pip install eodag

Usage
=====

Command line interface
----------------------

Create a configuration file from the template provided with the repository, filling in your credentials as expected by
each system:

    .. code-block:: bash

        cp eodag/user_conf_template.yml my_conf.yml

Then you can start playing with it:

* To search for products and crunch the results of the search:

    .. code-block:: bash

        eodag search \
        --conf my_conf.yml \
        --bbox 1 43 2 44 \
        --startDate 2018-01-01 --endDate 2018-01-31 \
        --productType S2-L1C \
        --cruncher FilterLatestIntersect \
        --storage my_search.geojson

The request above search for product types `S2-L1C` and will crunch the result using cruncher `FilterLatestIntersect` and storing the overall
result to `my_search.geojson`.

You can pass arguments to a cruncher on the command line by doing this (example with using `FilterOverlap` cruncher which takes `minimum_overlap` as argument):

    .. code-block:: bash

        eodag search -f my_conf.yml -b 1 43 2 44 -s 2018-01-01 -e 2018-01-31 -p S2-L1C --cruncher FilterOverlap --cruncher-args FilterOverlap minimum_overlap 10

The request above means : "Give me all the products of type `S2-L1C`, use `FilterOverlap` to keep only those products that are contained in the bbox I gave you,
or whom spatial extent overlaps at least 10% (`minimum_overlap`) of the surface of this bbox"

* To download the result of a previous call to `search`:

    .. code-block:: bash

        eodag download --conf my_conf.yml --search-results my_search.geojson

* To list all available product types and supported systems:

    .. code-block:: bash

        eodag list

* To list available product types on a specified supported system:

    .. code-block:: bash

        eodag list -s eocloud

* To see all the available options and commands:

    .. code-block:: bash

        eodag --help

* To print log messages, add `-v` to `eodag` master command. e.g. `eodag -v list`. The more `v` given, the more verbose the tool is

How to get Amazon WS access keys
--------------------------------

* Create an account on AWS website: https://aws.amazon.com/fr/ (warning: A credit card number must be given because
    data become paying after a given amount of downloaded data).
* Once the account is activated go to the identity and access management console: https://console.aws.amazon.com/iam/home#/home
* Click on user, then on your user name and then on security credentials.
* In access keys, click on create access key.
* Add these credentials to the user conf file.



Supported systems
=================

* [X] `eocloud <https://finder.eocloud.eu/www/>`_
* [X] `peps <https://peps.cnes.fr/rocket/#/search?maxRecords=50&view=list>`_
* [X] `theia <https://theia.cnes.fr/atdistrib/rocket/#/home>`_
* [X] `theia for landsat <https://theia-landsat.cnes.fr/rocket/#/home>`_
* [X] `scihub <https://scihub.copernicus.eu/>`_
* [ ] Google cloud public datasets for `sentinel2 <https://cloud.google.com/storage/docs/public-datasets/sentinel-2>`_ and `landsat <https://cloud.google.com/storage/docs/public-datasets/landsat>`_
* [ ] Amazon S3 `Sentinel <http://sentinel-pds.s3-website.eu-central-1.amazonaws.com/>`_ and `Landsat <http://sentinel-pds.s3-website.eu-central-1.amazonaws.com/>`_ data access
* [ ] `codede <https://code-de.org/>`_
* [ ] `CEDA <http://catalogue.ceda.ac.uk/search/?search_term=sentinel&return_obj=ob&search_obj=ob>`_ partial mirror for sentinel-2 data
* [ ] `EUMETSAT <https://coda.eumetsat.int/#/home>`_ partial mirror to Copernicus data
* [ ] `Greek <https://sentinels.space.noa.gr/dhus/#/home>`_ partial mirror to Copernicus data
* [ ] `ASF <https://vertex.daac.asf.alaska.edu/>`_


Features to be implemented
==========================

* [X] search recursion for Resto search plugin: search a product type in many of the supported systems
* [X] crunch plugins
* [ ] opensearch search plugin
* [ ] configure an instance of `PICTO <https://www.picto-occitanie.fr/accueil>`_ to test another use case of CSW search