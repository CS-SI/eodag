Release history
---------------

2.2.1 (XXXX-XX-XX)
++++++++++++++++++

- Re-structure and complete the documentation.
- Build SAFE format for Sentinel products from AWS STAC API providers, fixes :issue:`171`
- Deprecate :meth:`~eodag.api.core.EODataAccessGateway.load_stac_items`, use the
  :class:`~eodag.plugins.search.static_stac_search.StaticStacSearch` search plugin instead

2.2.0 (2021-03-26)
++++++++++++++++++

- New :meth:`~eodag.api.core.EODataAccessGateway.search_all` and
  :meth:`~eodag.api.core.EODataAccessGateway.search_iter_page` methods to simplify pagination handling (:pull:`190`)
- Docker-compose files for STAC API server with STAC-browser (:pull:`183`)
- Fixed USGS plugin which now uses M2M API (:pull:`209`)
- Windows support added in Continuous Integration (:pull:`192`)
- Fixes issue with automatically load configution from EODAG external plugins, fixes :issue:`184`
- More explicit signature for :meth:`~eodag.utils.logging.setup_logging`, fixes :issue:`197`
- Various minor fixes

2.1.1 (2021-03-18)
++++++++++++++++++

- Continuous Integration performed with GitHub actions
- Providers config automatically loaded from EODAG external plugins, fixes :issue:`172`
- Various minor fixes

2.1.0 (2021-03-09)
++++++++++++++++++

- `earth_search <https://www.element84.com/earth-search>`_ and
  `usgs_satapi_aws <https://landsatlook.usgs.gov/sat-api>`_ as new providers
- Updated :class:`~eodag.plugins.download.http.HTTPDownload` plugin, handling products with multiple assets
- New plugin :class:`~eodag.plugins.authentication.aws_auth.AwsAuth`, enables AWS authentication using no-sign-request,
  profile, ``~/.aws/*``
- New search plugin :class:`~eodag.plugins.search.static_stac_search.StaticStacSearch` and updated
  `STAC client tutorial <https://eodag.readthedocs.io/en/latest/tutorials/tuto_stac_client.html>`_
- New tutorial for `Copernicus DEM <https://eodag.readthedocs.io/en/latest/tutorials/tuto_cop_dem.html>`_
- Remove ``unidecode`` dependency
- Start/end dates passed to sobloo are now in UTC, and make it clear that search dates must be in UTC
- Locations must now be passed to :meth:`~eodag.api.core.EODataAccessGateway.search` method as a dictionnary
- Metadata mapping update and uniformization, fixes :issue:`154`
- Raise a :class:`ValueError` when a location search doesn't match any record and add a new ``locations``
  parameter to :meth:`~eodag.api.core.EODataAccessGateway.search`.
- Drop support of Python 3.5

2.0.1 (2021-02-05)
++++++++++++++++++

- Fixes issue when rebuilding index on NFS, see :issue:`151`
- Tests can be run in parallel mode, fixes :issue:`103`

2.0 (2021-01-28)
++++++++++++++++

- Add a new provider dynamically
- Allow to dynamically set download options, fixes :issue:`145` and :issue:`112`
- New tutorials for STAC and search by geometry, fixes :issue:`139`
- New crunches :class:`~eodag.plugins.crunch.filter_date.FilterDate`,
  :class:`~eodag.plugins.crunch.filter_property.FilterProperty` and updated
  :class:`~eodag.plugins.crunch.filter_overlap.FilterOverlap`, fixes :issue:`137`
- Use ``jsonpath-ng`` instead of ``jsonpath-rw`` and ``pyjq``, ``pyshp`` instead of ``fiona``
- Better wrong or missing credentials handling
- Add warning for the total number of results returned by theia
- Support regex query from locations configuration
- sort_by_extent renamed to group_by_extent
- Documentation and tutorials update
- Various minor fixes, code refactorization, and tests update

2.0b2 (2020-12-18)
++++++++++++++++++

- New method :meth:`~eodag.api.core.EODataAccessGateway.deserialize_and_register`, fixes :issue:`140`
- Load static stac catalogs as :class:`~eodag.api.search_result.SearchResult`
- Search on unknown product types using ``GENERIC_PRODUCT_TYPE``
- ``get_data``, drivers and rpc server moved to `eodag-cube <https://github.com/CS-SI/eodag-cube>`_
- Removed fixed dependencies, fixes :issue:`82`
- Use locations conf template by default

2.0b1 (2020-11-17)
++++++++++++++++++

- STAC API compliant REST server
- Common configuration for STAC providers
- astraea_eod as new STAC provider
- Search by geometry / bbox / location name, fixes :issue:`49`
- removed Python 2.7 support

1.6.0 (2020-08-24)
++++++++++++++++++

- Warning: last release including Python 2.7 support

1.6.0rc2 (2020-08-11)
+++++++++++++++++++++

- Queryable parameters configuration update for peps
- Fixed re-download error after original zip deletion, fixes :issue:`142`
- Fixed python-dateutil version conflict, fixes :issue:`141`
- Default user configuration file usage in CLI mode
- Fixed error when provider returns geometry as bbox with negative coords, fixes :issue:`143`

1.6.0rc0 (2020-06-18)
+++++++++++++++++++++

- Github set as default version control repository hosting service for source code and issues
- New provider for AWS: aws_eos (S2_MSI_L1C/L2A, S1_SAR_GRD, L8, CBERS-4, MODIS, NAIP), replaces aws_s3_sentinel2_l1c
- Build SAFE products for AWS Sentinel data
- New theia product types for S2, SPOT, VENUS, OSO
- New search plugin for POST requests (PostJsonSearch)
- Metadata auto discovery (for product properties and search parameter), replaces custom parameter
- Search configuration can be tweaked for each provider product type
- Fixed Lansat-8 search for onda, fixes :issue:`135`
- Advanced tutorial notebook, fixes :issue:`130`
- Various minor fixes, code refactorization, and tests update

1.5.2 (2020-05-06)
++++++++++++++++++

- Fix CLI download_all missing plugin configuration, fixes :issue:`134`

1.5.1 (2020-04-08)
++++++++++++++++++

- ``productionStatus`` parameter renamed to ``storageStatus``,
  see `Parameters Mapping documentation <https://eodag.readthedocs.io/en/latest/intro.html#parameters-mapping>`_

1.5.0 (2020-04-08)
++++++++++++++++++

- ``productionStatus`` parameter standardization over providers
- Not-available products download management, using ``wait``/``timeout``
  :meth:`~eodag.api.core.EODataAccessGateway.download`
  optional parameters, fixes :issue:`125`
- More explicit authentication errors messages
- Update search endoint for aws_s3_sentinel2_l1c and add RequestPayer option usage,
  fixes :issue:`131`

1.4.2 (2020-03-04)
++++++++++++++++++

- Skip badly configured providers in user configuration, see :issue:`129`

1.4.1 (2020-02-25)
++++++++++++++++++

- Warning message if an unknow provider is found in user configuration file,
  fixes :issue:`129`

1.4.0 (2020-02-24)
++++++++++++++++++

- Add to query the parameters set in the provider product type definition
- New :class:`~eodag.plugins.download.s3rest.S3RestDownload` plugin for mundi, fixes :issue:`127`
- S3_OLCI_L2LFR support for mundi, see :issue:`124`
- S2_MSI_L2A support for peps, see :issue:`124`
- Theia-landsat provider moved to theia, fixes :issue:`95`
- Fixed onda query quoting issues, fixes :issue:`128`
- Mundi, creodias and onda added to end-to-end tests
- Gdal install instructions and missing auxdata in ship_detection tutorial
- Sobloo and creodias quicklooks fix
- Eodag logo added and other minor changes to documentation

1.3.6 (2020-01-24)
++++++++++++++++++

- USGS plugin corrections, fixes :issue:`73`
- Fixed py27 encodeurl in querystring
- End-to-end tests update, fixes :issue:`119`
- Default eodag conf used in end-to-end tests, fixes :issue:`98`
- Fixed :meth:`~eodag.api.core.EODataAccessGateway.download_all` method :issue:`118`

1.3.5 (2020-01-07)
++++++++++++++++++

- Removed tqdm_notebook warning, fixes :issue:`117`
- Removed traceback from geom intersection warning, fixes :issue:`114`
- Documentation update for provider priorities and parametters mapping
- New test for readme/pypi syntax

1.3.4 (2019-12-12)
++++++++++++++++++

- Use sobloo official api endpoint, fixes :issue:`115`
- New badges in readme and CS logo
- Set owslib version to 0.18.0 (py27 support dropped)

1.3.3 (2019-10-11)
++++++++++++++++++

- Fixes product configuration for theia provider :issue:`113`

1.3.2 (2019-09-27)
++++++++++++++++++

- Fixes pagination configuration for sobloo provider :issue:`111`

1.3.1 (2019-09-27)
++++++++++++++++++

- Added calls graphs in documentation
- Tutorial notebooks fixes :issue:`109`,
  :issue:`110`
- Download unit display fix :issue:`108`
- Fix date format with sobloo provider :issue:`107`

1.3.0 (2019-09-06)
++++++++++++++++++

- Add parameters mapping in documentation
- Add new queryable parameters for sobloo :issue:`105`
- Fix custom search
- Fix sobloo cloudCoverage query :issue:`106`

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

- Fixes :issue:`97`
- Fixes :issue:`96`

1.0 (2019-04-26)
++++++++++++++++

- Adds product type search functionality
- Extends the list of search parameters with ``instrument``, ``platform``, ``platformSerialIdentifier``,
  ``processingLevel`` and ``sensorType``
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
