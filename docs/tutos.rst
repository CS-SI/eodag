.. _tutos:

Tutorials
=========

The API/CLI user guides explain how ``eodag``'s features should be used. These tutorials show
how ``eodag`` can be used to achieve some specific tasks. They are `Jupyter Notebook <https://jupyter.org/>`_
that can be viewed online, run online thanks to `Binder <https://mybinder.readthedocs.io/en/latest/>`_,
or run locally after being downloaded (see how to :ref:`install_notebooks`).

.. note::

   Some tutorials require auxiliary data that can be directly downloaded from `Github <https://github.com/CS-SI/eodag/tree/master/docs/notebooks/tutos/auxdata>`_.

.. warning::

   The tutorials almost always involve downloading one ore several EO product(s).
   These products are usually in the order of 700-900 Mo, make sure you have a decent internet connection if you plan to run the notebooks.

.. warning::

   Some tutorials make use of additional softwares (e.g. `SNAP <https://step.esa.int/main/toolboxes/snap/>`_) for image processing.
   These processes can be long, intensive and generate outputs in the order of several Go.

   Please make sure that you use the right software version. They are mentioned at the beginning
   of each tutorial.

.. toctree::
   :hidden:
   :maxdepth: 2

   notebooks/tutos/tuto_search_location_tile.ipynb
   notebooks/tutos/tuto_cop_dem.ipynb
   notebooks/tutos/tuto_ecmwf.ipynb
   notebooks/tutos/tuto_cds.ipynb
   notebooks/tutos/tuto_wekeo.ipynb
   notebooks/tutos/tuto_meteoblue.ipynb
   notebooks/tutos/tuto_ship_detection.ipynb
   notebooks/tutos/tuto_burnt_areas_snappy.ipynb
   notebooks/tutos/tuto_dedt_lumi_roi.ipynb
   notebooks/tutos/tuto_fedeo_ceda.ipynb

.. grid:: 1 2 2 3
   :gutter: 4

   .. grid-item-card:: Search for products by tile
      :link: notebooks/tutos/tuto_search_location_tile
      :link-type: doc
      :text-align: center
      :shadow: md

      Learn how to search for products using location names or tile identifiers instead of coordinates.

   .. grid-item-card:: Get Copernicus DEM using EODAG
      :link: notebooks/tutos/tuto_cop_dem
      :link-type: doc
      :text-align: center
      :shadow: md

      Learn how to retrieve the Copernicus Digital Elevation Model (DEM) using EODAG.

   .. grid-item-card:: ECMWF API plugin for EODAG
      :link: notebooks/tutos/tuto_ecmwf
      :link-type: doc
      :text-align: center
      :shadow: md

      Access ECMWF data through the ECMWF API using the dedicated EODAG plugin.

   .. grid-item-card:: Copernicus Atmosphere using ECMWFSearch plugin
      :link: notebooks/tutos/tuto_cds
      :link-type: doc
      :text-align: center
      :shadow: md

      Access Copernicus Atmosphere data through the ECMWFSearch plugin using the CDS API.

   .. grid-item-card:: The wekeo provider in EODAG
      :link: notebooks/tutos/tuto_wekeo
      :link-type: doc
      :text-align: center
      :shadow: md

      Access WEkEO data through the WEkEO provider using the CDS API.

   .. grid-item-card:: Get forecast data from meteoblue using EODAG
      :link: notebooks/tutos/tuto_meteoblue
      :link-type: doc
      :text-align: center
      :shadow: md

      Access meteoblue forecast data using the dedicated EODAG plugin.

   .. grid-item-card:: Sentinel-1 processing for ship detection (SNAP)
      :link: notebooks/tutos/tuto_ship_detection
      :link-type: doc
      :text-align: center
      :shadow: md

      Detect ships in the Gulf of Trieste using Sentinel-1 SAR data.
      Learn how to retrieve, process, and analyze satellite data with ``eodag``.

   .. grid-item-card:: Sentinel-2 processing to get a burnt area map (Sen2Cor, SNAP, snappy)
      :link: notebooks/tutos/tuto_burnt_areas_snappy
      :link-type: doc
      :text-align: center
      :shadow: md

      Analyze the May 2018 wildfire in New Mexico using Sentinel-2 data.
      Recover a data stack, process it with SNAP, and generate a burned area mask with ``eodag``.

   .. grid-item-card:: DEDT Lumi through ECMWF Polytope API
      :link: notebooks/tutos/tuto_dedt_lumi_roi
      :link-type: doc
      :text-align: center
      :shadow: md

      Access DEDT Lumi data through the ECMWF Polytope API using the dedicated EODAG plugin.

   .. grid-item-card:: Accessing Fedeo data through CEDA API
      :link: notebooks/tutos/tuto_fedeo_ceda
      :link-type: doc
      :text-align: center
      :shadow: md

      Access Fedeo data through the CEDA API using the dedicated EODAG plugin.
