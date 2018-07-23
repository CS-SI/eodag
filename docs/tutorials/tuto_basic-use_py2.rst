.. _tuto_basic-use_py2:

Eodag basic use tutorial
------------------------

This notebook presents the two basic features of eodag : search and
download.

.. code:: ipython2

    import os, fnmatch
    import json, geojson
    from datetime import date
    
    import ipyleaflet as ipyl
    import ipywidgets as ipyw
    from IPython.display import display, Image
    
    from eodag.api.core import SatImagesAPI
    
    
    base_dir = '/projects/sdk'

The first step is to initialize the session by creating an eodag
instance, with the configuration file that contains all providers
credentials (here called *myconf.yml*):

.. code:: ipython2

    dag = SatImagesAPI(user_conf_file_path='%s/myconf.yml' % base_dir)

We make a search on L1C Sentinel product types in Southern France:

.. code:: ipython2

    product_type = 'S2_MSI_L1C'
    extent = {
        'lonmin': -1.999512,
        'lonmax': 4.570313,
        'latmin': 42.763146,
        'latmax': 46.754917
    }
    
    products = dag.search(product_type, 
                          startTimeFromAscendingNode='2018-06-01', 
                          completionTimeFromAscendingNode=date.today().isoformat(), 
                          geometry=extent)
    
    dag.serialize(products, filename='%s/search_results.geojson' % base_dir)




.. parsed-literal::

    '/projects/sdk/search_results.geojson'



The result of the search is easily saved in a geojson file, and we can
check extents before downloading products with ipyleaflet API :

.. code:: ipython2

    emap, label = ipyl.Map(center=[43.6, 1.5], zoom=4), ipyw.Label(layout=ipyw.Layout(width='100%'))
    layer = ipyl.GeoJSON(data=products.as_geojson_object(), hover_style={'fillColor': 'yellow'})
    
    def hover_handler(event=None, id=None, properties=None):
        label.value = properties['title']
    
    layer.on_hover(hover_handler)
    emap.add_layer(layer)
    
    ipyw.VBox([emap, label])



.. parsed-literal::

    VkJveChjaGlsZHJlbj0oTWFwKGJhc2VtYXA9eyd1cmwnOiAnaHR0cHM6Ly97c30udGlsZS5vcGVuc3RyZWV0bWFwLm9yZy97en0ve3h9L3t5fS5wbmcnLCAnbWF4X3pvb20nOiAxOSwgJ2F0dHLigKY=



We can download from the eodag SearchResult object ``products``, (or
from the GeoJson previously created) :

.. code:: ipython2

    product = products[0]
    product_path = product.download()


.. parsed-literal::

    No handlers could be found for logger "eodag.plugins.download.http"
    407MKB [00:35, 11.7MKB/s] 
    Extracting files from /home/baptiste/data/S2B_MSIL1C_20180608T105649_N0206_R094_T30TYP_20180608T120643.zip:   0%|          | 0/108 [00:00<?, ?file/s][A
    Extracting files from /home/baptiste/data/S2B_MSIL1C_20180608T105649_N0206_R094_T30TYP_20180608T120643.zip:  13%|█▎        | 14/108 [00:00<00:01, 70.88file/s][A
    Extracting files from /home/baptiste/data/S2B_MSIL1C_20180608T105649_N0206_R094_T30TYP_20180608T120643.zip:  16%|█▌        | 17/108 [00:00<00:03, 26.17file/s][A
    Extracting files from /home/baptiste/data/S2B_MSIL1C_20180608T105649_N0206_R094_T30TYP_20180608T120643.zip:  18%|█▊        | 19/108 [00:00<00:04, 21.96file/s][A
    Extracting files from /home/baptiste/data/S2B_MSIL1C_20180608T105649_N0206_R094_T30TYP_20180608T120643.zip:  19%|█▉        | 21/108 [00:01<00:04, 19.48file/s][A
    Extracting files from /home/baptiste/data/S2B_MSIL1C_20180608T105649_N0206_R094_T30TYP_20180608T120643.zip:  21%|██▏       | 23/108 [00:01<00:04, 19.40file/s][A
    Extracting files from /home/baptiste/data/S2B_MSIL1C_20180608T105649_N0206_R094_T30TYP_20180608T120643.zip:  23%|██▎       | 25/108 [00:01<00:04, 17.89file/s][A
    Extracting files from /home/baptiste/data/S2B_MSIL1C_20180608T105649_N0206_R094_T30TYP_20180608T120643.zip:  25%|██▌       | 27/108 [00:01<00:04, 17.35file/s][A
    Extracting files from /home/baptiste/data/S2B_MSIL1C_20180608T105649_N0206_R094_T30TYP_20180608T120643.zip: 100%|██████████| 108/108 [00:01<00:00, 65.98file/s][A
