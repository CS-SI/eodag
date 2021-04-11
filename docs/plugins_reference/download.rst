.. module:: eodag.plugins.download

================
Download Plugins
================

Download plugins must inherit the following class and implement :meth:`download`:

.. autoclass:: eodag.plugins.download.base.Download
   :members:

This table lists all the download plugins currently available:

.. autosummary::
   :toctree: generated/

   eodag.plugins.download.http.HTTPDownload
   eodag.plugins.download.aws.AwsDownload
   eodag.plugins.download.s3rest.S3RestDownload
