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

    * Running the `tox` command will also build the docs. As The documentation
      includes some notebooks (for the turorials), the build process will need
      `pandoc <http://pandoc.org>`_ to succeed. If the build process fails for
      you, please `install <http://pandoc.org/installing.html>`_ pandoc and try
      again.

    * When contributing to tutorials, you will need to keep notebook outputs
      and save widget state. Otherwise outputs will not be visible in documentation.

    * eodag is tested against python versions 3.6, 3.7, 3.8 and 3.9. Ensure you have
      these versions installed before you run tox. You can use
      `pyenv <https://github.com/pyenv/pyenv>`_ to manage many different versions
      of python

Releases are made by tagging a commit on the master branch. To make a new release,

    * Ensure you correctly updated `README.rst` and `CHANGES.rst` (and occasionally,
      also `NOTICE` - in case a new dependency is added).
    * Check that the version string in `eodag/__meta__.py` (the variable `__version__`)
      is correctly updated
    * Push your local master branch to remote.
    * Tag the commit that represents the state of the release with a message. For example,
      for version 1.0, do this: `git tag -a v1.0 -m 'version 1.0'`
    * Push the tags to github: `git push --tags`.

The documentation is managed by a webhook, and the latest documentation on readthedocs follows
the documentation present in `master`. Therefore, there is nothing to do apart from updating
the `master` branch to publish the latest documentation.
