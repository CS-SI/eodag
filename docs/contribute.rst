.. _contribute:

Contribute to EODAG development
===============================

If you intend to contribute to eodag source code:

.. code-block:: bash

    git clone https://github.com/CS-SI/eodag.git
    cd eodag
    python -m pip install -r requirements-dev.txt

To run the default test suite (which excludes end-to-end tests):

.. code-block:: bash

    tox

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

.. note::

    When contributing to tutorials, you will need to keep notebook outputs
    and save widget state. Otherwise outputs will not be visible in documentation.
