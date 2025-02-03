.. module:: eodag.utils
   :no-index:

=====
Utils
=====

Logging
-------

.. automodule:: eodag.utils.logging
   :members:

Callbacks
---------

.. autoclass:: eodag.utils.DownloadedCallback
   :special-members: __call__
.. autofunction:: eodag.utils.ProgressCallback

Notebook
--------

.. automodule:: eodag.utils.notebook
   :members:

S3
----

.. automodule:: eodag.utils.s3
   :members:

Misc
----

.. automodule:: eodag.utils
   :members:
   :exclude-members: DownloadedCallback, ProgressCallback, NotebookProgressCallback, get_progress_callback
