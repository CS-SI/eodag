Release history
---------------

2.6.0 (2022-10-07)
++++++++++++++++++

* New `product types automatic discovery\
  <https://eodag.rtfd.io/en/latest/notebooks/api_user_guide/2_providers_products_available.html#Product-types-discovery>`_
  (:pull:`480`)(:pull:`467`)(:pull:`470`)(:pull:`471`)(:pull:`472`)(:pull:`473`)(:pull:`481`)(:pull:`486`)(:pull:`493`)
  (:pull:`491`)(:pull:`500`)
* New providers `cop_ads <https://ads.atmosphere.copernicus.eu>`_ and `cop_cds <https://cds.climate.copernicus.eu>`_
  for Copernicus Atmosphere and Climate Data Stores using :class:`~eodag.plugins.apis.cds.CdsApi` plugin, developed in
  the context of DOMINO-X (:pull:`504`)(:pull:`513`)
* :class:`~eodag.plugins.apis.usgs.UsgsApi` plugin fixed and updated (:pull:`489`)(:pull:`508`)
* Cache usage for ``jsonpath.parse()`` (:pull:`502`)
* Refactored download retry mechanism and more tests (:pull:`506`)
* Drop support of Python 3.6 (:pull:`505`)
* Various minor fixes and improvements (:pull:`469`)(:pull:`483`)(:pull:`484`)(:pull:`485`)(:pull:`490`)(:pull:`492`)
  (:pull:`494`)(:pull:`495`)(:pull:`496`)(:pull:`497`)(:pull:`510`)(:pull:`511`)(:pull:`514`)(:pull:`517`)

2.5.2 (2022-07-05)
++++++++++++++++++

* Fixes missing ``productPath`` property for some ``earth_search`` products (:pull:`480`)

2.5.1 (2022-06-27)
++++++++++++++++++

* Fixed broken :class:`~eodag.plugins.download.aws.AwsDownload` configuration for STAC providers (:pull:`475`)
* Set ``setuptools_scm`` max version for python3.6 (:pull:`477`)

2.5.0 (2022-06-07)
++++++++++++++++++

* `ecmwf <https://www.ecmwf.int/>`_ as new provider with new API plugin :class:`~eodag.plugins.apis.ecmwf.EcmwfApi`
  and `tutorial <https://eodag.readthedocs.io/en/latest/notebooks/tutos/tuto_ecmwf.html>`_, developed in the context
  of DOMINO-X (:pull:`452`)
* ``earth_search_gcs`` as new provider to download on
  `Google Cloud Storage public datasets <https://cloud.google.com/storage/docs/public-datasets>`_
  (:pull:`462`, thanks `@robert-werner <https://github.com/robert-werner>`_)
* STAC search on private servers needing authentication for earch (:pull:`443`)
* Do not list providers without credentials needing authentication for search (:pull:`442`)
* New packaging using `pyproject.toml` and `setup.cfg`, following `PEP 517 <https://peps.python.org/pep-0517/>`_
  recommendations and `setuptools build_meta <https://setuptools.pypa.io/en/latest/build_meta.html>`_ (:pull:`435`)
* `setuptools_scm` usage to have intermediate `dev` versions between releases (:pull:`431`)
* New options for :class:`~eodag.plugins.download.aws.AwsDownload` plugin: `requester_pays`, `base_uri`,
  and `ignore_assets` (:pull:`456`, thanks `@robert-werner <https://github.com/robert-werner>`_)
* :meth:`~eodag.api.search_result.SearchResult.filter_online` and additional convert methods added to
  :class:`~eodag.api.search_result.SearchResult` (:pull:`458`)(:pull:`450`)
* :class:`~eodag.plugins.authentication.token.TokenAuth` can now use headers and url formatting (:pull:`447`)
* All available metadata for `onda` provider is now retrieved (:pull:`440`)
* Various minor fixes and improvements (:pull:`430`)(:pull:`433`)(:pull:`434`)(:pull:`436`)(:pull:`438`)(:pull:`444`)
  (:pull:`448`)(:pull:`449`)(:pull:`451`)(:pull:`460`)(:pull:`464`)

2.4.0 (2022-03-09)
++++++++++++++++++

* STAC API POST requests and Query fragment handled in both
  :class:`~eodag.plugins.search.qssearch.StacSearch` client (:pull:`363`)(:pull:`367`) and server mode (:pull:`417`)
* Added ``downloaded_callback`` parameter to :meth:`~eodag.api.core.EODataAccessGateway.download_all` method
  allowing running a callback after each individual download (:pull:`381`)
* ``cloudCover`` parameter disabled for RADAR product types (:pull:`389`)
* Guess ``EOProduct.product_type`` from properties when missing (:pull:`380`)
* Keywords usage in product types configuration and guess mechanism (:pull:`372`)
* Automatic deletion of downloaded product zip after extraction (:pull:`358`)
* Crunchers are now directly attached to :class:`~eodag.api.search_result.SearchResult` (:pull:`359`)
* Import simplified for :class:`~eodag.api.product._product.EOProduct`, :class:`~eodag.api.search_result.SearchResult`,
  and `Crunchers <https://eodag.readthedocs.io/en/stable/plugins_reference/crunch.html>`_ (:pull:`356`)
* Added support for `python3.10` (:pull:`407`)
* Pytest usage instead of nosetest (:pull:`406`) and tests/coverage reports included in PR (:pull:`411`)(:pull:`416`)
* Various minor fixes and improvements (:pull:`355`)(:pull:`361`)(:pull:`366`)(:pull:`357`)(:pull:`371`)(:pull:`373`)
  (:pull:`374`)(:pull:`377`)(:pull:`379`)(:pull:`388`)(:pull:`394`)(:pull:`393`)(:pull:`405`)(:pull:`401`)(:pull:`398`)
  (:pull:`399`)(:pull:`419`)(:pull:`415`)(:pull:`410`)(:pull:`420`)

2.3.4 (2021-10-08)
++++++++++++++++++

* Link to the new eodag Jupyterlab extension: `eodag-labextension <https://github.com/CS-SI/eodag-labextension>`_
  (:pull:`352`)
* STAC client and server update to STAC 1.0.0 (:pull:`347`)
* Fixes :meth:`~eodag.api.product._product.EOProduct.get_quicklook` for onda provider
  (:pull:`344`, thanks `@drnextgis <https://github.com/drnextgis>`_)
* Fixed issue when downloading ``S2_MSI_L2A`` products from ``mundi`` (:pull:`350`)
* Various minor fixes and improvements (:pull:`340`)(:pull:`341`)(:pull:`345`)

2.3.3 (2021-08-11)
++++++++++++++++++

* Fixed issue when searching by id (:pull:`335`)
* Specified minimal `eodag-cube <https://github.com/CS-SI/eodag-cube>`_ version needed (:pull:`338`)
* Various minor fixes and improvements (:pull:`336`)(:pull:`337`)

2.3.2 (2021-07-29)
++++++++++++++++++

* Fixes duplicate logging in :meth:`~eodag.api.core.EODataAccessGateway.search_all` (:pull:`330`)
* Enable additional arguments like `productType` when searching by id (:pull:`329`)
* Prevent EOL auto changes on windows causing docker crashes (:pull:`324`)
* Configurable eodag logging in docker stac-server (:pull:`323`)
* Fixes missing `productType` in product properties when searching by id (:pull:`320`)
* Various minor fixes and improvements (:pull:`319`)(:pull:`321`)

2.3.1 (2021-07-09)
++++++++++++++++++

- Dockerfile update to be compatible with `stac-browser v2.0` (:pull:`314`)
- Adds new notebook extra dependency (:pull:`317`)
- EOProduct drivers definition update (:pull:`316`)

2.3.0 (2021-06-24)
++++++++++++++++++

- Removed Sentinel-3 products not available on peps any more (:pull:`304`, thanks `@tpfd <https://github.com/tpfd>`_)
- Prevent :meth:`~eodag.utils.notebook.NotebookWidgets.display_html` in ipython shell (:pull:`307`)
- Fixed plugins reload after having updated providers settings from user configuration (:pull:`306`)

2.3.0b1 (2021-06-11)
++++++++++++++++++++

- Re-structured and more complete documentation (:pull:`233`, and also :pull:`224`, :pull:`254`, :pull:`282`,
  :pull:`287`, :pull:`301`)
- Homogenized inconsistent paths returned by :meth:`~eodag.api.core.EODataAccessGateway.download` and
  :meth:`~eodag.api.core.EODataAccessGateway.download_all` methods (:pull:`244`)(:pull:`292`)
- Rewritten progress callback mechanism (:pull:`276`)(:pull:`285`)
- Sentinel products SAFE-format build for STAC AWS providers (:pull:`218`)
- New CLI optional `--quicklooks` flag in `eodag download` command (:pull:`279`,
  thanks `@ahuarte47 <https://github.com/ahuarte47>`_)
- New product types for Sentinel non-SAFE products (:pull:`228`)
- Creodias metadata mapping update (:pull:`294`)
- :meth:`~eodag.utils.logging.setup_logging` is now easier to import (:pull:`221`)
- :func:`~eodag.utils.logging.get_logging_verbose` function added (:pull:`283`)
- Documentation on how to request USGS M2M API access (:pull:`269`)
- User friendly parameters mapping documentation (:pull:`299`)
- Auto extract if extract is not set (:pull:`249`)
- Fixed how :meth:`~eodag.api.core.EODataAccessGateway.download_all` updates the passed list of products (:pull:`253`)
- Fixed user config file loading with settings of providers from ext plugin (:pull:`235`,
  thanks `@ahuarte47 <https://github.com/ahuarte47>`_)
- Improved and less strict handling of misconfigured user settings (:pull:`293`)(:pull:`296`)
- ISO 8601 formatted datetimes accepted by all providers (:pull:`257`)
- `GENERIC_PRODUCT_TYPE` not returned any more by :meth:`~eodag.api.core.EODataAccessGateway.list_product_types`
  (:pull:`261`)
- Warning displayed when searching with non preferred provider (:pull:`260`)
- Search kwargs used for guessing a product type not propagated any more (:pull:`248`)
- Deprecate :meth:`~eodag.api.core.EODataAccessGateway.load_stac_items`,
  :class:`~eodag.plugins.search.static_stac_search.StaticStacSearch` search plugin should be used instead (:pull:`225`)
- `ipywidgets` no more needed in :class:`~eodag.utils.notebook.NotebookWidgets` (:pull:`223`)
- Various minor fixes and improvements (:pull:`219`)(:pull:`246`)(:pull:`247`)(:pull:`258`)(:pull:`233`)(:pull:`273`)
  (:pull:`274`)(:pull:`280`)(:pull:`284`)(:pull:`288`)(:pull:`290`)(:pull:`295`)

2.2.0 (2021-03-26)
++++++++++++++++++

- New :meth:`~eodag.api.core.EODataAccessGateway.search_all` and
  :meth:`~eodag.api.core.EODataAccessGateway.search_iter_page` methods to simplify pagination handling (:pull:`190`)
- Docker-compose files for STAC API server with STAC-browser (:pull:`183`,
  thanks `@apparell <https://github.com/apparell>`_)
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
  `STAC client tutorial <https://eodag.readthedocs.io/en/latest/notebooks/tutos/tuto_stac_client.html>`_
- New tutorial for `Copernicus DEM <https://eodag.readthedocs.io/en/latest/notebooks/tutos/tuto_cop_dem.html>`_
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
