.. _tutos:

Tutorials
=========

These tutorials are based on `Jupyter notebooks <http://jupyter.org/>`_ that you can either view online,
run online (thanks to `Binder <https://mybinder.readthedocs.io/en/latest/>`_) or run locally after downloading them.

.. note::
    * Each tutorial indicates at its beginning which dependencies/softwares/setup it requires to run correctly.

    * All the additional Python packages required to run the notebooks may be automatically installed with `pip install eodag[docs]`.

    * Some tutorials require auxiliary data that can be directly downloaded from `Github <https://github.com/CS-SI/eodag/tree/master/examples/auxdata>`_.

    * You will have to be registered to *PEPS* and *Sobloo* to run the notebooks. See :ref:`user-config-file`.

.. warning::
    * The tutorials almost always involve downloading one ore several EO product(s).
      These products are usually in the order of 700-900 Mo, make sure you have a decent internet connection if you plan to run the notebooks.

    * Some tutorials make use of additional softwares (e.g. `SNAP <https://step.esa.int/main/toolboxes/snap/>`_) for image processing.
      These processes can be long, intensive and generate outputs in the order of several Go.

This first series of tutorials gradually introduces you to the various capabilities of `eodag`:

.. toctree::
   :titlesonly:

   tutorials/tuto_basics.nblink
   tutorials/tuto_advanced.nblink
   tutorials/tuto_bandmath.nblink

This second series of tutorials shows how to include `eodag` in more involved scenarios that post-process EO products:

.. toctree::
   :titlesonly:

   tutorials/tuto_burnt_areas_gpt.nblink
   tutorials/tuto_burnt_areas_snappy.nblink
   tutorials/tuto_ship_detection.nblink

If you wish to run the notebooks you can find their download link below or alternatively a Binder
link (only for those that don't require any additional software) to run them directly online:

    * :download:`tuto_basics.ipynb <../examples/tuto_basics.ipynb>` :raw-html:`<a class="reference external image-reference" href="https://mybinder.org/v2/git/https%3A%2F%2Fgithub.com%2FCS-SI%2Feodag.git/master?filepath=examples%2Ftuto_basics.ipynb" rel="nofollow"><img src="https://mybinder.org/badge_logo.svg" type="image/svg+xml"></a>`

    * :download:`tuto_advanced.ipynb <../examples/tuto_advanced.ipynb>` :raw-html:`<a class="reference external image-reference" href="https://mybinder.org/v2/git/https%3A%2F%2Fgithub.com%2FCS-SI%2Feodag.git/master?filepath=examples%2Ftuto_advanced.ipynb" rel="nofollow"><img src="https://mybinder.org/badge_logo.svg" type="image/svg+xml"></a>`

    * :download:`tuto_bandmath.ipynb <../examples/tuto_bandmath.ipynb>` :raw-html:`<a class="reference external image-reference" href="https://mybinder.org/v2/git/https%3A%2F%2Fgithub.com%2FCS-SI%2Feodag.git/master?filepath=examples%2Ftuto_bandmath.ipynb" rel="nofollow"><img src="https://mybinder.org/badge_logo.svg" type="image/svg+xml"></a>`

    * :download:`tuto_burnt_areas_gpt.ipynb <../examples/tuto_burnt_areas_gpt.ipynb>`

    * :download:`tuto_burnt_areas_snappy.ipynb <../examples/tuto_burnt_areas_snappy.ipynb>`

    * :download:`tuto_ship_detection.ipynb <../examples/tuto_ship_detection.ipynb>`