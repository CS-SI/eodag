.. _install:

Installation
============

EODAG is really simple to get installed on your platform:

.. code-block:: bash

    python -m pip install eodag

There are some tutorials on how to use eodag as a library. These tutorials are jupyter notebooks, and need
extra dependancies installation. To install them, type this on the command line (preferably in a virtualenv)::

    python -m pip install eodag[tutorials]

Then clone eodag repository::

    git clone https://bitbucket.org/geostorm/eodag.git

And then invoke jupyter notebook like this::

    jupyter notebook --notebook-dir=eodag/examples

It should open your navigator in the directory `eodag/examples` where you can view, run and tweak the tutorials.

.. note::

    If you already have a jupyter configuration in your home, the command above will override your default notebook directory,
    but not everything else. If you want to completely ignore your default configuration, consider passing the option
    `--config` with an arbitrary non-empty value like this::

        jupyter notebook --notebook-dir=eodag/examples --config=arbitrary

