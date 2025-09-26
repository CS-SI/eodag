.. module:: eodag.utils
   :no-index:

=====
Utils
=====

This section provides an overview of the utility functions and classes available in the `eodag` library.
These utilities are designed to assist with various tasks such as logging, handling callbacks, performing free text searches, working with Jupyter notebooks, interacting with S3 storage, and processing xarray data.
Each subsection below details the specific utilities and their usage.

Logging
-------

.. automodule:: eodag.utils.logging
   :members:

Callbacks
---------

.. autoclass:: eodag.utils.DownloadedCallback
   :special-members: __call__
.. autofunction:: eodag.utils.ProgressCallback

Dates
-----

.. automodule:: eodag.utils.dates
   :members:

Free text search
----------------

.. autofunction:: eodag.utils.free_text_search.compile_free_text_query

Notebook
--------

.. automodule:: eodag.utils.notebook
   :members:

S3
----

.. automodule:: eodag.utils.s3
   :members:

xarray
------

.. warning::

   These functions will only be available with `eodag-cube <https://github.com/CS-SI/eodag-cube>`__ installed.

.. automodule:: eodag_cube.utils.xarray
   :members:

Misc
----

.. automodule:: eodag.utils
   :members:
   :exclude-members: DownloadedCallback, ProgressCallback, NotebookProgressCallback, get_progress_callback
