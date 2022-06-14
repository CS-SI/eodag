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

.. _install_notebooks:

Run the notebooks locally
^^^^^^^^^^^^^^^^^^^^^^^^^

The :ref:`api_user_guide` and the :ref:`tutos` consist of a series of `Jupyter notebooks <https://jupyter.org/>`_
that can be run locally:

1. Install the extras dependencies it requires by executing this command (preferably in a virtual environment)::

      python -m pip install eodag[tutorials]

2. Clone ``eodag`` 's repository with git::

      git clone https://github.com/CS-SI/eodag.git

3. Invoke jupyter::

      jupyter notebook

4. Browse to either ``docs/notebooks/api_user_guide`` or ``docs/notebooks/tutos`` and launch a notebook.
