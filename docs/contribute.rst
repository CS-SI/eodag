.. _contribute:

Contribute to EODAG development
===============================

If you intend to contribute to eodag source code:

.. code-block:: bash

    git clone https://bitbucket.org/geostorm/eodag.git
    cd eodag
    python -m pip intall -r requirements-dev.txt

To run the default test suite (which excludes end-to-end tests):

.. code-block:: bash

    tox

.. note::

    You may encounter a Python `RuntimeWarning` saying that `numpy.dtype` size changed. If this is the case,
    you can suppress it by doing this on the command line before running the tests or eodag cli:
    `export PYTHONWARNINGS="ignore:numpy.dtype size changed"`

To only run end-to-end test:

.. code-block:: bash

    tox -- tests.test_end_to_end

To run the entire tests (units, integraton and end-to-end):

.. code-block:: bash

    tox -- tests eodag

.. note::

    Running the `tox` command will also build the docs. As The documentation
    includes some notebooks (for the turorials), the build process will need
    `pandoc <http://pandoc.org>`_ to succeed. If the build process fails for
    you, please `install <http://pandoc.org/installing.html>`_ pandoc and try
    again.