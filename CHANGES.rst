Release history
---------------

1.3.6 (2020-01-24)
++++++++++++++++++

- USGS plugin corrections, fixes `#73 <https://bitbucket.org/geostorm/eodag/issues/73>`_
- Fixed py27 encodeurl in querystring
- End-to-end tests update, fixes `#119 <https://bitbucket.org/geostorm/eodag/issues/119>`_
- Default eodag conf used in end-to-end tests, fixes `#98 <https://bitbucket.org/geostorm/eodag/issues/98>`_
- Fixed download_all method `#118 <https://bitbucket.org/geostorm/eodag/issues/118>`_

1.3.5 (2020-01-07)
++++++++++++++++++

- Removed tqdm_notebook warning, fixes `#117 <https://bitbucket.org/geostorm/eodag/issues/117>`_
- Removed traceback from geom intersection warning, fixes `#114 <https://bitbucket.org/geostorm/eodag/issues/114>`_
- Documentation update for provider priorities and parametters mapping
- New test for readme/pypi syntax

1.3.4 (2019-12-12)
++++++++++++++++++

- Use sobloo official api endpoint, fixes `#115 <https://bitbucket.org/geostorm/eodag/issues/115>`_
- New badges in readme and CS logo
- Set owslib version to 0.18.0 (py27 support dropped)

1.3.3 (2019-10-11)
++++++++++++++++++

- Fixes product configuration for theia provider `#113 <https://bitbucket.org/geostorm/eodag/issues/113>`_

1.3.2 (2019-09-27)
++++++++++++++++++

- Fixes pagination configuration for sobloo provider `#111 <https://bitbucket.org/geostorm/eodag/issues/111>`_

1.3.1 (2019-09-27)
++++++++++++++++++

- Added calls graphs in documentation
- Tutorial notebooks fixes `#109 <https://bitbucket.org/geostorm/eodag/issues/109>`_, `#110 <https://bitbucket.org/geostorm/eodag/issues/110>`_
- Download unit display fix `#108 <https://bitbucket.org/geostorm/eodag/issues/108>`_
- Fix date format with sobloo provider `#107 <https://bitbucket.org/geostorm/eodag/issues/107>`_

1.3.0 (2019-09-06)
++++++++++++++++++

- Add parameters mapping in documentation
- Add new queryable parameters for sobloo `#105 <https://bitbucket.org/geostorm/eodag/issues/105>`_
- Fix custom search
- Fix sobloo cloudCoverage query `#106 <https://bitbucket.org/geostorm/eodag/issues/106>`_

1.2.3 (2019-08-26)
++++++++++++++++++

- Binder basic tuto Binder badge only

1.2.2 (2019-08-23)
++++++++++++++++++

- Binder basic tuto working

1.2.1 (2019-08-23)
++++++++++++++++++

- Add binder links

1.2.0 (2019-08-22)
++++++++++++++++++

- Add download_all support by plugins
- Fix GeoJSON rounding issue with new geojson lib

1.1.3 (2019-08-05)
++++++++++++++++++

- Tutorial fix

1.1.2 (2019-08-05)
++++++++++++++++++

- Fix dependency version issue (Jinja2)
- Tutorials fixes and enhancements

1.1.1 (2019-07-26)
++++++++++++++++++

- Updates documentation for custom field

1.1.0 (2019-07-23)
++++++++++++++++++

- Adds custom fields for query string search
- Adapts to new download interface for sobloo

1.0.1 (2019-04-30)
++++++++++++++++++

- Fixes `#97 <https://bitbucket.org/geostorm/eodag/issues/97/conversion-to-provider-product-type-is-not>`_
- Fixes `#96 <https://bitbucket.org/geostorm/eodag/issues/96/eodag-does-not-handle-well-the-switch-in>`_

1.0 (2019-04-26)
++++++++++++++++

- Adds product type search functionality
- Extends the list of search parameters with ``instrument``, ``platform``, ``platformSerialIdentifier``, ``processingLevel`` and ``sensorType``
- The cli arguments are now fully compliant with opensearch geo(bbox)/time extensions
- Adds functionality to search products by their ID
- Exposes search products by ID functionality on REST interface
- Exposes get quicklook functionality on REST interface
- Fixes a bug occuring when ``outputs_prefix`` config parameter is not set in user config

0.7.2 (2019-03-26)
++++++++++++++++++

- Fixes bug due to the new version of PyYaml
- Updates documentation and tutorial
- Automatically generates a user configuration file in ``~/.config/eodag/eodag.yml``. This path is overridable by the
  ``EODAG_CFG_FILE`` environment variable.


0.7.1 (2019-03-01)
++++++++++++++++++

- Creates a http rest server interface to eodag
- Switches separator of conversion functions in search parameters: the separator switches from "$" to "#"
- In the providers configuration file, an operator can now specify a conversion to be applied to metadata when
  extracting them from provider search response. See the providers.yml file (sobloo provider, specification of
  startTimeFromAscendingNode extraction) for an example usage of this feature
- The RestoSearch plugin is dismissed and merged with its parent to allow better generalization of the
  QueryStringSearch plugin.
- Simplifies the way eodag search for product types on the providers: the partial_support mechanism is removed
- The search interface is modified to return a 2-tuple, the first item being the result and the second the total
  number of items satisfying the request
- The EOProduct properties now excludes all metadata that were either not mapped or not available (mapped in the
  provider metadata_mapping but not present in the provider response). This lowers the size of the number of elements
  needed to be transferred as response to http requests for the embedded http server
- Two new cli args are added: --page and --items to precise which page is to be requested on the provider (default 1)
  and how many results to retrieve (default 20)


0.7.0 (2018-12-04)
++++++++++++++++++

- Creates Creodias, Mundi, Onda and Wekeo drivers
- Every provider configuration parameter is now overridable by the user configuration
- Provider configuration is now overridable by environment variables following the pattern:
  EODAG__<PROVIDER>__<CONFIG_PARAMETER> (special prefix + double underscore between configuration keys + configuration
  parameters uppercase with simple underscores preserved). There is no limit to the how fine the override can go
- New authentication plugins (keycloak with openid)


0.6.3 (2018-09-24)
++++++++++++++++++

- Silences rasterio's NotGeoreferencedWarning warning when sentinel2_l1c driver tries to determine the address of a
  requested band on the disk
- Changes the `DEFAULT_PROJ` constant in `eodag.utils` from a `pyproj.Proj` instance to `rasterio.crs.CRS` instance

0.6.2 (2018-09-24)
++++++++++++++++++

- Updates catalog url for airbus-ds provider
- Removes authentication for airbus-ds provider on catalog search

0.6.1 (2018-09-19)
++++++++++++++++++

- Enhance error message for missing credentials
- Enable EOProduct to remember its remote address for subsequent downloads

0.6.0 (2018-08-09)
++++++++++++++++++

- Add support of a new product type: PLD_BUNDLE provided by theia-landsat
- Create a new authentication plugin to perform headless OpenID connect authorisation
  code flow
- Refactor the class name of the core api (from SatImagesAPI to EODataAccessGateway)
- Set peps platform as the default provider
- Set product archive depth for peps provider to 2 (after extracting a product from peps,
  the product is nested one level inside a top level directory where it was extracted)

0.5.0 (2018-08-02)
++++++++++++++++++

- Make progress bar for download optional and customizable
- Fix bugs in FilterOverlap cruncher

0.4.0 (2018-07-26)
++++++++++++++++++

- Enable quicklook retrieval interface for EOProduct

0.3.0 (2018-07-23)
++++++++++++++++++

- Add docs for tutorials
- Configure project for CI/CD on Bitbucket pipelines


0.2.0 (2018-07-17)
++++++++++++++++++

- Prepare project for release as open source and publication on PyPI
- The get_data functionality now returns an xarray.DataArray instead of numpy.ndarray
- Sentinel 2 L1C product type driver for get_data functionality now supports products
  stored on Amazon S3
- Add tutorials


0.1.0 (2018-06-20)
++++++++++++++++++

- Handle different organisation of files in downloaded zip files
- Add HTTPHeaderAuth authentication plugin
- Map product metadata in providers configuration file through xpath and jsonpath
- Add an interface for sorting multiple SearchResult by geographic extent
- Index Dataset drivers (for the get_data functionality) by eodag product types
- Refactor plugin manager
- Enable SearchResult to provide a list-like interface
- Download is now resilient to download plugins failures
- Update EOProduct API
- Create ArlasSearch search plugin
- Some bug fixes


0.0.1 (2018-06-15)
++++++++++++++++++

- Starting to be stable for internal use
- Basic functionality implemented (search, download, crunch, get_data)
