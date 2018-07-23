.. _tuto_bandmath_py2:

NDVI computation with eodag
---------------------------

In this tutorial, we compute a band math on a Sentinel-2 source, directly
by giving an extent with eodag. The area of interest is the center of
Toulouse.

.. code:: ipython2

    import matplotlib.pyplot as plt
    import ipyleaflet as ipyl
    import ipywidgets as ipyw
    
    from eodag.api.core import SatImagesAPI
    
    
    base_dir = '/projects/sdk'

We define an extent and set preferred provider for the product type S2
L1C, and make a search on the month of May:

.. code:: ipython2

    dag = SatImagesAPI(user_conf_file_path='%s/myconf.yml' % base_dir)
    
    product_type = 'S2_MSI_L1C'
    extent = {
        'lonmin': 1.306000,
        'lonmax': 1.551819,
        'latmin': 43.527642,
        'latmax': 43.662905
    }
    
    products = dag.search(product_type, 
                          startTimeFromAscendingNode='2018-05-01', 
                          completionTimeFromAscendingNode='2018-05-31', 
                          geometry=extent,
                          cloudCover=1)
    product = products[0]
    print(product.properties['title'])




.. parsed-literal::

    S2A_MSIL1C_20180521T105031_N0206_R051_T31TCJ_20180521T125745



The method **get\_data** allows to perform an operation directly on
bands without managing the download. We can see in green the "Prairie
des Filtres" on the left, and "Grand-Rond"-"Jardin des plantes" parks on
the right center. In red, the "Garonne".

.. code:: ipython2

    VIR = product.get_data(crs='epsg:4326', resolution=0.0001, band='B04', extent=(1.435905, 43.586857, 1.458907, 43.603827))
    NIR = product.get_data(crs='epsg:4326', resolution=0.0001, band='B08', extent=(1.435905, 43.586857, 1.458907, 43.603827))
    NDVI = (NIR - VIR * 1.) / (NIR + VIR)
    
    
    plt.imshow(NDVI, cmap='RdYlGn', aspect='auto')
    plt.savefig('%s/img/ndvi_toulouse.png' % base_dir)
