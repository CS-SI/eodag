.. _tutos:

Tutorials
=========

The API/CLI user guides explain how ``eodag``'s features should be used. These tutorials show
how ``eodag`` can be used to achieve some specific tasks. They are `Jupyter Notebook <https://jupyter.org/>`_
that can be viewed online, run online thanks to `Binder <https://mybinder.readthedocs.io/en/latest/>`_,
or run locally after being downloaded (see how to :ref:`install_notebooks`).

.. note::

   Some tutorials require auxiliary data that can be directly downloaded from `Github <https://github.com/CS-SI/eodag/tree/master/examples/auxdata>`_.

.. warning::

   The tutorials almost always involve downloading one ore several EO product(s).
   These products are usually in the order of 700-900 Mo, make sure you have a decent internet connection if you plan to run the notebooks.

.. warning::

   Some tutorials make use of additional softwares (e.g. `SNAP <https://step.esa.int/main/toolboxes/snap/>`_) for image processing.
   These processes can be long, intensive and generate outputs in the order of several Go.

   Please make sure that you use the right software version. They are mentioned at the beginning
   of each tutorial.

.. toctree::

   notebooks/tutos/tuto_search_location_tile.ipynb
   notebooks/tutos/tuto_cop_dem.ipynb
   notebooks/tutos/tuto_ecmwf.ipynb
   notebooks/tutos/tuto_cds.ipynb
   notebooks/tutos/tuto_meteoblue.ipynb
   notebooks/tutos/tuto_ship_detection.ipynb
   notebooks/tutos/tuto_burnt_areas_snappy.ipynb
