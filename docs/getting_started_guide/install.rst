.. _install:

Installation
============

EODAG is really simple to install with ``pip``:

.. code-block:: bash

   python -m pip install eodag

.. note::

   ``pyproj`` requires Cython or pip>=19.3. If the install of ``eodag`` fails, check your
   version of pip (Ubuntu 18.04 comes installed with pip 9.0.1).

Or with ``conda`` from the *conda-forge* channel:

.. code-block:: bash

   conda install -c conda-forge eodag

Optional dependencies
^^^^^^^^^^^^^^^^^^^^^

Since ``v3.0``, EODAG comes with a minimal set of dependencies. If you want more features, please install using one of
the following extras:

* ``eodag[all]``, includes everything that would be needed to run EODAG and associated tutorials with all features
* ``eodag[all-providers]``, includes dependencies required to have all providers available
* ``eodag[aws]``, includes dependencies for plugins using Amazon S3
* ``eodag[csw]``, includes dependencies for plugins using CSW
* ``eodag[ecmwf]``, includes dependencies for :class:`~eodag.plugins.apis.ecmwf.EcmwfApi` (`ecmwf` provider)
* ``eodag[usgs]``, includes dependencies for :class:`~eodag.plugins.apis.usgs.UsgsApi` (`usgs` provider)
* ``eodag[server]``, includes dependencies for server-mode

.. _install_notebooks:

Run the notebooks locally
^^^^^^^^^^^^^^^^^^^^^^^^^

The :ref:`api_user_guide` and the :ref:`tutos` consist of a series of `Jupyter notebooks <https://jupyter.org/>`_
that can be run locally:

1. Install the extras dependencies it requires by executing this command (preferably in a virtual environment)::

      python -m pip install "eodag[tutorials]"

2. Clone ``eodag`` 's repository with git::

      git clone https://github.com/CS-SI/eodag.git

3. Invoke jupyter::

      jupyter notebook

4. Browse to either ``docs/notebooks/api_user_guide`` or ``docs/notebooks/tutos`` and launch a notebook.
