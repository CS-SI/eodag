.. _api_user_guide:

API User Guide
==============

The API user guide introduces all the features offered by ``eodag`` through its API and
explains how they should be used. Each page is a `Jupyter notebook <https://jupyter.org/>`_ that can be viewed online,
run online thanks to `Binder <https://mybinder.readthedocs.io/en/latest/>`_,
or run locally after being downloaded (see how to :ref:`install_notebooks`).

.. note::

   You should be registered to *PEPS* to run the notebooks that download data.
   See :ref:`configure` and :ref:`register`.

.. warning::

   The `Download <notebooks/api_user_guide/download.ipynb>`_ notebook downloads a few
   EO products. These products are usually in the order of 700-900 Mo, make sure you have a
   decent internet connection if you plan to run the notebooks.

.. toctree::

   notebooks/api_user_guide/1_overview.ipynb
   notebooks/api_user_guide/2_providers_products_available.ipynb
   notebooks/api_user_guide/3_configuration.ipynb
   notebooks/api_user_guide/4_search.ipynb
   notebooks/api_user_guide/5_serialize_deserialize.ipynb
   notebooks/api_user_guide/6_crunch.ipynb
   notebooks/api_user_guide/7_download.ipynb
   notebooks/api_user_guide/8_post_process.ipynb
