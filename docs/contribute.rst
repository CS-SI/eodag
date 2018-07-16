.. _contribute:

Contribute to EODAG development
===============================

If you intend to contribute to eodag source code:

.. code-block:: bash

    git clone https://bitbucket.org/geostorm/eodag.git
    cd eodag
    python -m pip intall -e .[dev,tutorials]

To run the default test suite (which excludes end-to-end tests):

.. code-block:: bash

    tox

To only run end-to-end test:

.. code-block:: bash

    tox -- tests.test_end_to_end

To run the entire tests (units, integraton and end-to-end):

.. code-block:: bash

    tox -- tests eodag