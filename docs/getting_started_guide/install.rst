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
  (`== eodag[all-providers,csw,server,tutorials]`)
* ``eodag[all-providers]``, includes dependencies required to have all providers available (`== eodag[ecmwf,usgs]`)
* ``eodag[csw]``, includes dependencies for plugins using CSW
* ``eodag[ecmwf]``, includes dependencies for :class:`~eodag.plugins.apis.ecmwf.EcmwfApi` (`ecmwf` provider)
* ``eodag[usgs]``, includes dependencies for :class:`~eodag.plugins.apis.usgs.UsgsApi` (`usgs` provider)
* ``eodag[server]``, includes dependencies for server-mode

Also available:

* ``eodag[notebook]``, includes notebook adapted progress bars
* ``eodag[tutorials]``, includes dependencies to run notebooks (`eodag[ecmwf,notebook]`, visualisation and
  jupyter-related stuff)
* ``eodag[stubs]``, includes dependencies stubs
* ``eodag[dev]``, includes dependencies required for contributing (`eodag[all-providers,csw,server,stubs]`, testing
  and linting tools)
* ``eodag[docs]``, includes dependencies required to build documentation

Conda
"""""

Conda does not support for the moment `optional groups of dependencies (conda/conda#7502)
<https://github.com/conda/conda/issues/7502>`_. To separate *server-mode* dependencies from the default installation,
we made 2 distinct packages on conda-forge:

* `eodag <https://anaconda.org/conda-forge/eodag>`_ equivalent to ``eodag[all-providers,csw]``
* `eodag-server <https://anaconda.org/conda-forge/eodag-server>`_ equivalent to ``eodag[all-providers,csw,server]``

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
