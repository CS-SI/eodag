.. _side_projects:

Side projects
=============

EODAG-cube
----------

Data access functionalities have been split to a separate project to avoid conflicts with
unneeded libraries when using only EODAG basic functionalities. EODAG-cube is available
on `github <https://github.com/CS-SI/eodag-cube>`__ and `pypi <https://pypi.org/project/eodag-cube>`__.

EODAG-sentinelsat
-----------------

API plugin that enables to search and download EO products from catalogs implementing the
`SciHub / Copernicus Open Access Hub interface <https://scihub.copernicus.eu/userguide/WebHome>`_.
It is basically a wrapper around `sentinelsat <https://sentinelsat.readthedocs.io>`_, enabling it to be used with EODAG.
EODAG-sentinelsat is available on `github <https://github.com/CS-SI/eodag-sentinelsat>`__ and
`pypi <https://pypi.org/project/eodag-sentinelsat/>`__.

EODAG-labextension
------------------

Jupyterlab extension for searching and browsing remote sensed imagery directly from your notebook.

This extension is using the eodag library to efficiently search from various image providers.
It can transform search results to code cells into the active Python notebook to further process/visualize the dataset.

EODAG-labextension is available
on `github <https://github.com/CS-SI/eodag-labextension>`__ and `pypi <https://pypi.org/project/eodag-labextension>`__.
