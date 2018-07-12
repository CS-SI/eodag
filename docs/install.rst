.. _install:

Installation
============

.. code-block:: bash

    USER=<allowed-user>
    git clone https://${USER}@bitbucket.org/geostorm/eodag.git
    # Then open `eodag/eodag/resources/providers.yml` and set the highest `priority` number to the preferred provider
    # (default is airbus-ds). This only means all search will begin on that provider.
    python -m pip install eodag