eodag
=====

Eodag is a command line tool and a plugin-oriented framework for searching, crunching and downloading remote sensed
images (mainly from satellite systems).

You can search and download satellite products:

* through the embedded cli:

    .. code-block:: bash

        eodag --conf user.conf.yaml --bbox 1 43 2 44 --startDate 2018-01-01 --endDate 2018-01-31 --productType SLC
        # With the shortcut arguments
        eodag -f user.conf.yaml -b 1 43 2 44 -s 2018-01-01 -e 2018-01-31 -c 20 -p SLC

* by interacting with the api in your Python scripts:

    .. code-block:: python

        from eodag import SatImagesAPI

        api = SatImagesAPI(user_conf_file_path='/path/to/user/conf.yaml')
        producttype = 'SLC'
        footprint = {'lonmin': 1, 'latmin': 43.5, 'lonmax': 2, 'latmax': 44}
        start, end = '2018-01-01', '2018-01-31'
        for local_filename in api.download_all(api.search(producttype, footprint=footprint, startDate=start, endDate=end):
            print('Downloaded : {}'.format(local_filename))


If you wish to extend the supported productor systems instances, you can :

* configure an instance of known plugins => this only involves knowing how to write ``yaml`` documents (see ``resources/symtem_conf_default.yml``
  for examples of how to configure a system instance)

* develop plugins defining how to search products, transform search results and download them from a productor system
  which is not supported by eodag (see the ``plugins`` directory to see some examples of plugins).

Read `the documentation <https://bitbucket.org/geostorm/eodag>`_ for more insights.

Installation
============

.. code-block:: bash

    git clone https://aoyono@bitbucket.org/geostorm/eodag.git
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

    .. code-block:: bash

        eodag --conf my_conf.yml --bbox 1 43 2 44 --startDate 2018-01-01 --endDate 2018-01-31 --productType SLC

To see all the available options:

    .. code-block:: bash

        eodag --help

Here is a list of supported arguments and options:

+----+---------------+---------------------------+---------------------------------------------------------------------------------------------------------+
| -b | -\-bbox       | <FLOAT FLOAT FLOAT FLOAT> | Search for a product on a bounding box, providing its minlon, minlat, maxlon and maxlat (in this order) |
+----+---------------+---------------------------+---------------------------------------------------------------------------------------------------------+
| -s | -\-startDat   |           TEXT            | Maximum age of the product (in ISO8601 format: yyyy-MM-ddThh:mm:ss.SSSZ)                                |
+----+---------------+---------------------------+---------------------------------------------------------------------------------------------------------+
| -e | -\-endDate    |           TEXT            | Minimum age of the product (in ISO8601 format: yyyy-MM-ddThh:mm:ss.SSSZ)                                |
+----+---------------+---------------------------+---------------------------------------------------------------------------------------------------------+
| -p | -\-productType|           TEXT            | The product type to search                                                                              |
+----+---------------+---------------------------+---------------------------------------------------------------------------------------------------------+
| -c | -\-maxCloud   |           INT             | Maximum cloud cover percentage needed for the product                                                   |
+----+---------------+---------------------------+---------------------------------------------------------------------------------------------------------+
| -v | -\-verbose    |                           | Control the verbosity of the logs. For maximum verbosity, type -vvv                                     |
+----+---------------+---------------------------+---------------------------------------------------------------------------------------------------------+
| -f | -\-conf       |           PATH            | File path to the user configuration file with its credentials                                           |
+----+---------------+---------------------------+---------------------------------------------------------------------------------------------------------+
|    | -\-help       |                           | Show help message and exit.                                                                             |
+----+---------------+---------------------------+---------------------------------------------------------------------------------------------------------+

Features to be implemented
==========================

* [X] search recursion for Resto search plugin: search a product type in many of the supported systems
* [X] crunch plugins
* [ ] opensearch search plugin
* [ ] configure an instance of `PICTO <https://www.picto-occitanie.fr/accueil>`_ to test another use case of CSW search