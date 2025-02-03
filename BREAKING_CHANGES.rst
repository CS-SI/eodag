Breaking changes
----------------

Full changelog available in `Release history <changelog.html>`_.

v3.0.0b3
++++++++

* :meth:`~eodag.api.core.EODataAccessGateway.download` / :class:`~eodag.types.download_args.DownloadConf` parameters
  ``outputs_prefix`` and ``outputs_extension`` renamed to ``output_dir`` and ``output_extension``.

v3.0.0b1
++++++++

* :meth:`~eodag.api.core.EODataAccessGateway.search` method now returns only a
  :class:`~eodag.api.search_result.SearchResult` instead of a 2 values tuple. It can optionally store the estimated
  total number of products in ``SearchResult.number_matched`` if the method is called with ``count=True``
  (``False`` by  default).

  * **eodag < 3.0.0b1 syntax:**

    .. code-block:: python

      search_results, number_matched = dag.search(productType="S2_MSI_L1C")

    |  Traceback (most recent call last):
    |    File "<stdin>", line 1, in <module>
    |  ValueError: too many values to unpack (expected 2)

  * **eodag >= 3.0.0b1 syntax:**

    .. code-block:: python

      search_results = dag.search(productType="S2_MSI_L1C")

* Packaging refactoring and new `optional dependencies
  <getting_started_guide/install.html#optional-dependencies>`_. EODAG default
  installs with a minimal set of dependencies.
  New sets of extra requirements are: ``eodag[all]``, ``eodag[all-providers]``, ``eodag[ecmwf]``, ``eodag[usgs]``,
  ``eodag[csw]``, ``eodag[server]``, ``eodag[stubs]``. Previous existing sets of extra requirements are also kept:
  ``eodag[notebook]``, ``eodag[tutorials]``, ``eodag[dev]``, ``eodag[docs]``.

  .. code-block:: sh

    # install eodag with all available providers supported
    pip install "eodag[all-providers]"

v2.0b1
++++++

- STAC API compliant REST server
- Common configuration for STAC providers

v1.0
++++

- Adds product type search functionality
- The cli arguments are now fully compliant with opensearch geo(bbox)/time extensions
