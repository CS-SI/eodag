.. _contribute:

Contribute
==========

Thank you for considering contributing to eodag!


Report issues
-------------

Issue tracker: https://github.com/CS-SI/eodag/issues

Please check that a similar issue does not already exist and
include the following information in your post:

-   Describe what you expected to happen.
-   If possible, include a `minimal reproducible example`_ to help us
    identify the issue. This also helps check that the issue is not with
    your own code.
-   Describe what actually happened. Include the full traceback if there
    was an exception.
-   List your Python and eodag versions. If possible, check if this
    issue is already fixed in the latest releases or the latest code in
    the repository.

.. _minimal reproducible example: https://stackoverflow.com/help/minimal-reproducible-example


Submit patches
--------------

If you intend to contribute to eodag source code:

.. code-block:: bash

    git clone https://github.com/CS-SI/eodag.git
    cd eodag
    python -m pip install -r requirements-dev.txt
    pre-commit install

We use ``pre-commit`` to run a suite of linters, formatters and pre-commit hooks (``black``, ``isort``, ``flake8``) to
ensure the code base is homogeneously formatted and easier to read. It's important that you install it, since we run
the exact same hooks in the Continuous Integration.

To run the default test suite (which excludes end-to-end tests):

.. code-block:: bash

    tox

To run the default test suite in parallel:

.. code-block:: bash

    tox -p

To only run end-to-end tests:

.. code-block:: bash

    tox -- tests/test_end_to_end.py

To run the entire tests (units, integration and end-to-end):

.. code-block:: bash

    tox -- tests eodag

.. note::

    * Running the `tox` command will also build the docs. As the documentation
      includes some notebooks (for the tutorials), the build process will need
      `pandoc <https://pandoc.org>`_ to succeed. If the build process fails for
      you, please `install <https://pandoc.org/installing.html>`_ pandoc and try
      again.

    * eodag is tested against python versions 3.7, 3.8, 3.9, 3.10 and 3.11. Ensure you have
      these versions installed before you run tox. You can use
      `pyenv <https://github.com/pyenv/pyenv>`_ to manage many different versions
      of python

Contribute to the docs
----------------------

The documentation of EODAG consists of:

* Files written with the `reStructuredText <https://docutils.sourceforge.io/rst.html>`_ markup language.
* `Jupyter Notebooks <https://jupyter-notebook.readthedocs.io/en/latest/index.html>`_, themselves being written in a mix of
  `Markdown markup language <https://jupyter-notebook.readthedocs.io/en/latest/examples/Notebook/Working%20With%20Markdown%20Cells.html>`_
  and Python code

`Sphinx <https://www.sphinx-doc.org/en/master/>`_ is used to create the website from these files.

`nbsphinx <https://nbsphinx.readthedocs.io/en/0.8.3/>`_ is a Sphinx extension that can parse Jupyter Notebooks. It can also execute notebooks.
The notebooks used to document EODAG are not executed by default (see the `conf.py` file), to avoid
searching for products and trying to download them (which would fail due to the lack of credentials).
However, executing notebooks is useful to check that they actually work fine. It is possible to
configure each a notebook so that `nbsphinx` executes it. The following setting has to be added to
a notebook's general metadata:

.. code-block:: json

   "nbsphinx": {
    "execute": "always"
   }

The notebooks listed below are **always executed** by `nbsphinx`:

* `<notebooks/api_user_guide/2_providers_products_available.ipynb>`_
* `<notebooks/api_user_guide/3_configuration.ipynb>`_
* `<notebooks/api_user_guide/6_crunch.ipynb>`_

For the other notebooks, their **cell output as long as their widget state** need so be saved.
If not, the outputs and the widgets (e.g. progress bar) won't be displayed in the online documentation.

.. tip::

   `sphinx-autobuild <https://pypi.org/project/sphinx-autobuild/>`_ can be installed to rebuild Sphinx documentation on changes, with live-reload in the browser.
   Run it from the repository root with ``sphinx-autobuild docs docs/_build/html/``

`Read the Docs <https://readthedocs.org/>`_ is a service that uses Sphinx to build a documentation website,
which it then hosts for free for open source projects, such as EODAG.

Release EODAG
-------------

Releases are made by tagging a commit on the master branch. EODAG version is then automatically updated
using `setuptools_scm`.To make a new release,

* Ensure you correctly updated `README.rst` and `CHANGES.rst` (and occasionally,
  also `NOTICE` - in case a new dependency is added).
* Check that the fallback version string in `pyproject.toml` (the variable `fallback_version`)
  is correctly updated to the new TAG
* Push your local master branch to remote.
* Tag the commit that represents the state of the release with a message. For example,
  for version 1.0, do this: `git tag -a v1.0 -m 'version 1.0'`
* Push the tags to github: `git push --tags`.

The documentation is managed by a webhook, and the latest documentation on readthedocs follows
the documentation present in `develop`. Therefore, there is nothing to do apart from updating
the `develop` branch to publish the latest documentation.
