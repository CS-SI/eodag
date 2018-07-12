.. _intro:

Introduction
============

EODAG (Earth Observation Data Access Gateway) is a command line tool and a plugin-oriented Python framework for searching,
crunching and downloading remote sensed images (mainly from satellite images providers).

You can search and download satellite products:

* through the embedded cli:

    .. code-block:: bash

        eodag search --conf user.conf.yaml \
                     --geometry 1 43 2 44 \
                     --startTimeFromAscendingNode 2018-01-01 \
                     --completionTimeFromAscendingNode 2018-01-31 \
                     --cloudCover 20 \
                     --productType S2_MSI_L1C
        # With the shortcut arguments
        eodag search -f user.conf.yaml -b 1 43 2 44 -s 2018-01-01 -e 2018-01-31 -c 20 -p S2-L1C

* by interacting with the api in your Python code:

    .. code-block:: python

        from eodag import SatImagesAPI

        dag = SatImagesAPI(user_conf_file_path='/path/to/user/conf.yaml')
        product_type = 'S2_MSI_L1C'
        footprint = {'lonmin': 1, 'latmin': 43.5, 'lonmax': 2, 'latmax': 44}
        start, end = '2018-01-01', '2018-01-31'
        search_results = dag.search(
            product_type,
            geometry=footprint,
            startTimeFromAscendingNode=start,
            completionTimeFromAscendingNode=end,
        )
        product_paths = dag.download_all(search_results)
        for path in product_paths:
            print('Downloaded : {}'.format(path))


There are 2 ways for adding support for a new provider :

* By configuring existing plugins: a provider is an instance of already implemented plugins (search, download) =>
  this only involves knowing how to write ``yaml`` documents (see `<eodag/resources/providers.yml>`_ for examples of how
  to configure a provider)

* By developing new plugins (most of the time it will be search plugins) and configuring instances of these plugins
  (see the ``plugins`` directory to see some examples of plugins).

Read `the documentation <https://bitbucket.org/geostorm/eodag>`_ for more insights.