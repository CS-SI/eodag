===============
Release history
===============


v3.4.2 (2025-05-15)
===================

Bug Fixes
---------

* **core**: Remove quotes around arrays in query param (`#1657`_, `b717e45`_)

* **plugins**: Adapt queryables additional_properties to providers config (`#1646`_, `cc6ecc9`_)

* **plugins**: Add alias to properties in cop_marine and EcmwfSearch plugins (`#1649`_, `ae93d5a`_)

* **plugins**: Ecmwfsearch orderable products search (`#1656`_, `a399a5b`_)

Continuous Integration
----------------------

* Automatic deployment (`#1655`_, `4fbdf8b`_)

.. _#1646: https://github.com/CS-SI/eodag/pull/1646
.. _#1649: https://github.com/CS-SI/eodag/pull/1649
.. _#1655: https://github.com/CS-SI/eodag/pull/1655
.. _#1656: https://github.com/CS-SI/eodag/pull/1656
.. _#1657: https://github.com/CS-SI/eodag/pull/1657
.. _4fbdf8b: https://github.com/CS-SI/eodag/commit/4fbdf8ba4d2cece05bede65e18438ecdc8029a69
.. _a399a5b: https://github.com/CS-SI/eodag/commit/a399a5b1d5457cdfcab355f8e2b4c440982ba65f
.. _ae93d5a: https://github.com/CS-SI/eodag/commit/ae93d5a6c58476dad2461d9dde663aa31356dff9
.. _b717e45: https://github.com/CS-SI/eodag/commit/b717e456fb23e59e9dfb6a99b5e30b697be73232
.. _cc6ecc9: https://github.com/CS-SI/eodag/commit/cc6ecc9979bfee420ff75cd919c3f90ae73689bb


v3.4.1 (2025-05-12)
===================

Bug Fixes
---------

* **plugins**: Missing datetime properties in ECMWFSearch result (`#1648`_, `9ac8d6a`_)

* **plugins**: Staticstacsearch text opener (`#1643`_, `71a51f1`_)

Documentation
-------------

* Fixed binder tutos links (`#1651`_, `5ec4421`_)

Testing
-------

* Update click>=8.2.0 exit status code (`#1650`_, `51a5f36`_)

.. _#1643: https://github.com/CS-SI/eodag/pull/1643
.. _#1648: https://github.com/CS-SI/eodag/pull/1648
.. _#1650: https://github.com/CS-SI/eodag/pull/1650
.. _#1651: https://github.com/CS-SI/eodag/pull/1651
.. _51a5f36: https://github.com/CS-SI/eodag/commit/51a5f3667b2cc0b706a7278494ee4e8bf1260210
.. _5ec4421: https://github.com/CS-SI/eodag/commit/5ec4421cf3c653e35005e4489a09cb2f22e44a9f
.. _71a51f1: https://github.com/CS-SI/eodag/commit/71a51f16ea370f542af3142fee25ec90c2a75ae3
.. _9ac8d6a: https://github.com/CS-SI/eodag/commit/9ac8d6a3f06ad1112c6dd3aeccb2f63eaa49c3c0


v3.4.0 (2025-04-30)
===================

Bug Fixes
---------

* **plugins**: Stac providers datetime queryables handling (`#1625`_, `9417fd9`_)

* **providers**: cop_ewds metadata mapping (`#1629`_, `30b5554`_)

Features
--------

* **plugins**: Add queryables to cop_marine (`#1638`_, `bcc793e`_)

Refactoring
-----------

* **core**: Use importlib.metadata instead of the deprecated pkg_resources (`#1631`_, `3675690`_, thanks `@avalentino <https://github.com/avalentino>`_)

.. _#1625: https://github.com/CS-SI/eodag/pull/1625
.. _#1629: https://github.com/CS-SI/eodag/pull/1629
.. _#1631: https://github.com/CS-SI/eodag/pull/1631
.. _#1638: https://github.com/CS-SI/eodag/pull/1638
.. _30b5554: https://github.com/CS-SI/eodag/commit/30b5554d96c58a0aca53849bd38db80902823bdf
.. _3675690: https://github.com/CS-SI/eodag/commit/3675690e04813de6b9402f0028277c091d0e51b0
.. _9417fd9: https://github.com/CS-SI/eodag/commit/9417fd90049ccfb8ee30f6eef7e497da2c1bea60
.. _bcc793e: https://github.com/CS-SI/eodag/commit/bcc793e83ae6c7fec3e282046e4516510e9015fb


v3.3.2 (2025-04-24)
===================

Bug Fixes
---------

* **providers**: Creodias and cop_dataspace products title mapping (`#1635`_, `850cb50`_)

Continuous Integration
----------------------

* Fixed changelog generation (`#1630`_, `3bd7a5c`_)

* Token usage for coverage report publishing (`#1633`_, `6a7e0d4`_)

* Update changelog generation (`#1627`_, `20e0ef7`_)

Refactoring
-----------

* **core**: Authentication for get_quicklook (`#1608`_, `40915e0`_)

.. _#1608: https://github.com/CS-SI/eodag/pull/1608
.. _#1627: https://github.com/CS-SI/eodag/pull/1627
.. _#1630: https://github.com/CS-SI/eodag/pull/1630
.. _#1633: https://github.com/CS-SI/eodag/pull/1633
.. _#1635: https://github.com/CS-SI/eodag/pull/1635
.. _20e0ef7: https://github.com/CS-SI/eodag/commit/20e0ef7d066b278ad2f068e1f65998c5549fdaf0
.. _3bd7a5c: https://github.com/CS-SI/eodag/commit/3bd7a5c486f28c104964d7ca11c222a5a4d9132f
.. _40915e0: https://github.com/CS-SI/eodag/commit/40915e031b4b5db2eda508fb71e5058d2a256bff
.. _6a7e0d4: https://github.com/CS-SI/eodag/commit/6a7e0d43883d862b06269dee4bff940b5112e018
.. _850cb50: https://github.com/CS-SI/eodag/commit/850cb5010058887277e19e59b2b7b3311fddd2a4


v3.3.1 (2025-04-17)
===================

Bug Fixes
---------

* **core**: Missing queryables from metadata-mapping (`#1614`_, `9789c0c`_)

* **core**: Provider queryables metadata (`#1613`_, `f1b066a`_)

* **core**: Reset errors between SearchResult instances (`#1607`_, `48b0779`_)

* **plugins**: Send client_id/client_secret with refresh_token in TokenAuth (`#1597`_, `9b626a9`_, thanks
  `@jgaucher-cs <https://github.com/jgaucher-cs>`_)

.. _#1597: https://github.com/CS-SI/eodag/pull/1597
.. _#1607: https://github.com/CS-SI/eodag/pull/1607
.. _#1613: https://github.com/CS-SI/eodag/pull/1613
.. _#1614: https://github.com/CS-SI/eodag/pull/1614
.. _48b0779: https://github.com/CS-SI/eodag/commit/48b07797b3a17c26e33f6f8ee2f51488a0829162
.. _9789c0c: https://github.com/CS-SI/eodag/commit/9789c0c4a52aa180422e1f0a0c2b8d86c373a0ee
.. _9b626a9: https://github.com/CS-SI/eodag/commit/9b626a91c7563d505632c830a98d18993ec95199
.. _f1b066a: https://github.com/CS-SI/eodag/commit/f1b066a8feffef3d1c20147776128793177fcfeb


v3.3.0 (2025-04-10)
===================

Bug Fixes
---------

* **core**: Ensure datetime format compliance with STAC specification (`#1573`_, `7e10e3a`_)

* **plugins**: Add datetime for ecmwf search (`#1572`_, `b785e7c`_)

* **plugins**: Check expiration time in token auth (`#1590`_, `15dbcb1`_)

* **providers**: ``geodes`` datetime search (`#1592`_, `87ade04`_)

* **providers**: Rename ``EO:CLMS:DAT:CORINE`` to ``EO:EEA:DAT:CORINE`` (`#1576`_, `2d3f6da`_)

Continuous Integration
----------------------

* Automatic changelog update (`#1601`_, `0625802`_)

Features
--------

* **plugins**: :class:`~eodag.plugins.search.build_search_result.ECMWFSearch` search-by-id (`#1580`_, `f296c52`_)

Testing
-------

* Fixed test for ecmwf dates (`#1588`_, `b6ca196`_)

.. _#1572: https://github.com/CS-SI/eodag/pull/1572
.. _#1573: https://github.com/CS-SI/eodag/pull/1573
.. _#1576: https://github.com/CS-SI/eodag/pull/1576
.. _#1580: https://github.com/CS-SI/eodag/pull/1580
.. _#1588: https://github.com/CS-SI/eodag/pull/1588
.. _#1590: https://github.com/CS-SI/eodag/pull/1590
.. _#1592: https://github.com/CS-SI/eodag/pull/1592
.. _#1599: https://github.com/CS-SI/eodag/pull/1599
.. _#1601: https://github.com/CS-SI/eodag/pull/1601
.. _#1603: https://github.com/CS-SI/eodag/pull/1603
.. _0625802: https://github.com/CS-SI/eodag/commit/0625802e62f5be02560f6b015c65d0643e7cb720
.. _15dbcb1: https://github.com/CS-SI/eodag/commit/15dbcb17b14becdce57087fdba5b60adeb4a7551
.. _2d3f6da: https://github.com/CS-SI/eodag/commit/2d3f6dac273cb70f55dfa9eb3c898266a4c93552
.. _548fded: https://github.com/CS-SI/eodag/commit/548fdedc7a30d488302a685c4c8361ba29c2068f
.. _6af7ce4: https://github.com/CS-SI/eodag/commit/6af7ce499d00c32af3754ce30ebcb8fc392638a9
.. _7e10e3a: https://github.com/CS-SI/eodag/commit/7e10e3aeb27220fd023f1cb00198ed2304ea3486
.. _87ade04: https://github.com/CS-SI/eodag/commit/87ade04922356eb78cf1798a8fb81bcea8057595
.. _b6ca196: https://github.com/CS-SI/eodag/commit/b6ca1968d60d6123e818f1eec06fc1fa386e465a
.. _b785e7c: https://github.com/CS-SI/eodag/commit/b785e7c15c8dc60efbe0f38ac4d6487d8917b1aa
.. _f296c52: https://github.com/CS-SI/eodag/commit/f296c526a803607e23c477a9da679b5f27e142dc


v3.2.0 (2025-04-01)
===================

Core features and fixes
-----------------------

* Fixes download of assets having keys with special characters (:pull:`1585`)

Providers and product types updates
-----------------------------------

* ``geodes`` API update (:pull:`1581`)
* Sanitize ``eumetsat_ds`` products title (:pull:`1582`)
* Updated default values for some ECMWF collections (:pull:`1575`)

Plugins new features and fixes
------------------------------

* Do not guess assets keys from their URL when inappropriate (:pull:`1584`)

Miscellaneous
-------------

* Various minor fixes and improvements (:pull:`1570`)(:pull:`1571`)
* External product types reference updates (:pull:`1567`)

v3.1.0 (2025-03-19)
===================

|:loudspeaker:| Major changes since last stable (`v3.0.1 <changelog.rst#v3-0-1-2024-11-06>`_)
---------------------------------------------------------------------------------------------

Core features and fixes
^^^^^^^^^^^^^^^^^^^^^^^

* [v3.1.0b2] Assets keys uniformization using drivers (:pull:`1488`)
* [v3.1.0b1] Updated `queryables <https://eodag.readthedocs.io/en/latest/notebooks/api_user_guide/5_queryables.html>`_
  mechanism and ecmwf-like plugins (:pull:`1397`)(:pull:`1427`)(:pull:`1462`)
* **[v3.1.0]** Customizable providers configuration file through ``EODAG_PRODUCT_TYPES_CFG_FILE`` environment
  variable (:pull:`1559`)
* [v3.1.0b1] Order and download polling times update (:pull:`1440`)

Providers and product types updates
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* **[v3.1.0]** Removed ``onda`` provider (:pull:`1564`)
* [v3.1.0b2] default search timeout to 20s (:pull:`1505`)

Plugins new features and fixes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* **[v3.1.0]** :class:`~eodag.plugins.search.build_search_result.ECMWFSearch`: simplified configuration (:pull:`1433`),
  fixed queryables issues (:pull:`1509`), mapped geometry metadata (:pull:`1555`)
* [v3.1.0b1] Removed default :class:`~eodag.plugins.download.http.HTTPDownload` zip extension (:pull:`1400`)
* [v3.1.0b1] Order and poll without downloading (:pull:`1437`)

Remaining changes since `v3.1.0b2 <changelog.rst#v3-1-0b2-2025-02-03>`_
-----------------------------------------------------------------------

Core features and fixes
^^^^^^^^^^^^^^^^^^^^^^^

* Keep queryables `required` attribute even with default values (:pull:`1521`)

Providers and product types updates
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* ``geodes``: recognize auth errors during download (:pull:`1562`), typo in ``geodes_s3`` user conf template
  (:pull:`1536`)
* ``wekeo_main`` metadata mapping update (:pull:`1549`) and COP-DEM product types update (:pull:`1516`)
* ``eumetsat_ds``: new MTG product types (:pull:`1513`), metadata mapping fix (:pull:`1502`), remove duplicate product
  types (:pull:`1514`)
* Add product types to ``dedl`` provider (:pull:`1515`)

Plugins new features and fixes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* :class:`~eodag.plugins.download.aws.AwsDownload`: zip partial download (:pull:`1561`), `InvalidRequest` handle
  (:pull:`1532`)
* Already authenticated user fix on openid authentication plugins (:pull:`1524`)
* Fixes missing file error on ``usgs`` authentication during attempts (:pull:`1550`)

Miscellaneous
^^^^^^^^^^^^^

* **[build]** remove dependencies max versions (:pull:`1519`)
* **[docs]** ``eodag-cube`` `Python API documentation
  <https://eodag.readthedocs.io/en/latest/notebooks/api_user_guide/9_post_process.html#Data-access-with-eodag-cube>`_
  (:pull:`1511`), ``usgs`` registration update (:pull:`1551`)
* Various minor fixes and improvements (:pull:`1502`)(:pull:`1540`)(:pull:`1541`)(:pull:`1547`)(:pull:`1552`)
  (:pull:`1566`)(:pull:`1568`)
* External product types reference updates (:pull:`1510`)(:pull:`1525`)(:pull:`1539`)(:pull:`1548`)(:pull:`1553`)
  (:pull:`1557`)(:pull:`1565`)

v3.1.0b2 (2025-02-03)
=====================

Core features and fixes
-----------------------

* Assets keys uniformization using drivers (:pull:`1488`)
* ``ssl_verify`` setting for ``get_quicklook`` (:pull:`1490`, thanks `@tromain <https://github.com/tromain>`_)
* Queryables merged by provider priority (:pull:`1431`)

Providers and product types updates
-----------------------------------

* ``geodes_s3`` as new provider (:pull:`1506`)
* default search timeout to 20s (:pull:`1505`)
* ``geodes`` ``relativeOrbitNumber`` property (:pull:`1499`) and numerical queryables fix (:pull:`1507`)

Miscellaneous
-------------

* **[docs]** Updated tutorials using ``eodag-cube`` (:pull:`1436`) and minor fixes (:pull:`1498`)(:pull:`1500`)
* **[style]** Typing update for generics (:pull:`1486`)
* Various minor fixes and improvements (:pull:`1471`)(:pull:`1472`)(:pull:`1473`)(:pull:`1475`)(:pull:`1477`)
  (:pull:`1479`)(:pull:`1480`)(:pull:`1483`)(:pull:`1492`)(:pull:`1503`)(:pull:`1504`)
* External product types reference updates (:pull:`1460`)(:pull:`1478`)(:pull:`1484`)(:pull:`1487`)(:pull:`1493`)
  (:pull:`1494`)

v3.1.0b1 (2025-01-13)
=====================

Core features and fixes
-----------------------

* Updated `queryables <https://eodag.readthedocs.io/en/latest/notebooks/api_user_guide/5_queryables.html>`_ mechanism
  and ecmwf-like plugins (:pull:`1397`)(:pull:`1427`)(:pull:`1462`)
* Order and download polling times update (:pull:`1440`)
* Do not retry downloading skipped products during download_all (:pull:`1465`)
* Renamed record files that were using previous mechanism (:pull:`1396`, thanks `@gasparakos\
  <https://github.com/gasparakos>`_)
* New ``to_lower()`` and ``to_upper()`` `parameters mapping\
  <https://eodag.readthedocs.io/en/latest/params_mapping.html#formatters>`_ methods (:pull:`1410`, thanks
  `@jgaucher-cs <https://github.com/jgaucher-cs>`_)

Providers and product types updates
-----------------------------------

* ``geodes`` updated ``id`` (:pull:`1441`) and ``tileIdentifier`` parameters (:pull:`1457`), and metadata mapping fix
  (:pull:`1468`)
* New MTG product types for ``eumetsat_ds`` (:pull:`1455`)
* ``FIRE_HISTORICAL`` on ``wekeo_ecmwf`` (:pull:`1392`)
* Various product types metadata-mapping and default values updates: for ``cop_ads`` and ``wekeo_ecmwf`` (:pull:`1389`),
  GLOFAS and EFAS product types (:pull:`1467`), ``EEA_DAILY_VI`` on ``wekeo_main`` (:pull:`1464`)

Plugins new features and fixes
------------------------------

* Removed default :class:`~eodag.plugins.download.http.HTTPDownload` zip extension (:pull:`1400`)
* Order and poll without downloading (:pull:`1437`)
* :class:`~eodag.plugins.authentication.token.TokenAuth` distinct headers for token retrieve and authentication
  (:pull:`1451`, thanks `@jgaucher-cs <https://github.com/jgaucher-cs>`_)
* Compare only offset-aware datetimes on openid authentication plugins (:pull:`1418`)
* Fixed ``creodias_s3`` search and download when no asset is available (:pull:`1425`)

Server mode
-----------

* Dedicated liveness endpoint added (:pull:`1353`)
* Processing level parsing fix in external STAC collections (:pull:`1429`)

Miscellaneous
-------------
* **[docs]** `Queryables <https://eodag.readthedocs.io/en/latest/notebooks/api_user_guide/5_queryables.html>`_
  documentation in a dedicated section (:pull:`1447`)
* Various minor fixes and improvements (:pull:`1390`)(:pull:`1403`)(:pull:`1411`)(:pull:`1415`)(:pull:`1419`)
  (:pull:`1428`)(:pull:`1430`)(:pull:`1434`)(:pull:`1445`)(:pull:`1448`)(:pull:`1458`)(:pull:`1466`)
* External product types reference updates (:pull:`1387`)(:pull:`1391`)(:pull:`1401`)(:pull:`1404`)(:pull:`1406`)
  (:pull:`1408`)(:pull:`1416`)(:pull:`1424`)(:pull:`1453`)(:pull:`1459`)

v3.0.1 (2024-11-06)
===================

Providers and product types updates
-----------------------------------

* ``geodes`` as new provider (:pull:`1357`)(:pull:`1363`)
* ``cop_ewds`` as new provider (:pull:`1331`)
* Removed ``astraea_eod`` provider (:pull:`1383`)
* Fixed ``S2_MSI_L1C`` search-by-id for ``earth_search`` (:pull:`1053`)
* MSG product types added (:pull:`1348`)
* Fixed order for some ``dedl`` product-types (:pull:`1358`)

Plugins new features and fixes
------------------------------

* Authenticate only when needed in :class:`~eodag.plugins.download.http.HTTPDownload` (:pull:`1370`)
* Various fixes for ``cop_marine`` (:pull:`1336`)(:pull:`1364`)
* OpenID token expiration fix and ``oidc_config_url`` usage (:pull:`1346`)
* Concurrent requests for ``wekeo_cmems`` product-types fetch (:pull:`1374`)
* Error is raised when :class:`~eodag.plugins.download.http.HTTPDownload` order fails (:pull:`1338`)

Miscellaneous
-------------
* **[build]** Add ``python3.13`` and drop ``python3.8`` support (:pull:`1344`)
* **[docs]** `Plugins <https://eodag.readthedocs.io/en/latest/plugins.html>`_ and `utils\
  <https://eodag.readthedocs.io/en/latest/api_reference/utils.html>`_ documention update (:pull:`1297`)
* **[docs]**  `conda optional dependencies\
  <https://eodag.readthedocs.io/en/latest/getting_started_guide/install.html#conda>`_  handling (:pull:`1343`)
* **[docs]**  Fixed ``auxdata`` reference in tutorials (:pull:`1372`, thanks `@emmanuel-ferdman\
  <https://github.com/emmanuel-ferdman>`_)
* **[ci]** Tests speedup using ``uv`` and ``tox-uv`` (:pull:`1347`)
* **[ci]** ``wekeo`` product types included in external product types reference (:pull:`1377`)
* Various minor fixes and improvements (:pull:`1298`)(:pull:`1335`)(:pull:`1340`)(:pull:`1341`)(:pull:`1351`)
  (:pull:`1367`)(:pull:`1365`)(:pull:`1368`)(:pull:`1379`)
* External product types reference updates (:pull:`1342`)(:pull:`1356`)(:pull:`1359`)(:pull:`1360`)(:pull:`1362`)
  (:pull:`1366`)(:pull:`1369`)(:pull:`1373`)(:pull:`1375`)(:pull:`1378`)(:pull:`1381`)(:pull:`1384`)

v3.0.0 (2024-10-10)
===================

|:warning:| Breaking changes since last stable (`v2.12.1 <changelog.rst#v2-12-1-2024-03-05>`_)
----------------------------------------------------------------------------------------------

* [v3.0.0b1] `search() <https://eodag.readthedocs.io/en/latest/notebooks/api_user_guide/4_search.html#search()>`_ method
  now returns only a :class:`~eodag.api.search_result.SearchResult` instead of a 2 values tuple (:pull:`1200`). It can
  optionally store the estimated total number of products in ``SearchResult.number_matched`` if the method is called
  with ``count=True`` (``False`` by  default).
* [v3.0.0b1] Packaging refactoring and new `optional dependencies
  <https://eodag.readthedocs.io/en/latest/getting_started_guide/install.html#optional-dependencies>`_ (:pull:`1108`)
  (:pull:`1219`). EODAG default installs with a minimal set of dependencies.
  New sets of extra requirements are: ``eodag[all]``, ``eodag[all-providers]``, ``eodag[ecmwf]``, ``eodag[usgs]``,
  ``eodag[csw]``, ``eodag[server]``. Previous existing sets of extra requirements are also kept:
  ``eodag[notebook]``, ``eodag[tutorials]``, ``eodag[dev]``, ``eodag[docs]``.
* [v3.0.0b3] :meth:`~eodag.api.core.EODataAccessGateway.download` / :class:`~eodag.types.download_args.DownloadConf`
  parameters ``outputs_prefix`` and ``outputs_extension`` renamed to ``output_dir`` and ``output_extension``
  (:pull:`1279`)

|:loudspeaker:| Major changes since last stable (`v2.12.1 <changelog.rst#v2-12-1-2024-03-05>`_)
-----------------------------------------------------------------------------------------------

Core features and fixes
^^^^^^^^^^^^^^^^^^^^^^^

* **[v3.0.0]** Sharable and multiple authentication plugins per provider (:pull:`1292`)(:pull:`1329`)(:pull:`1332`)
* [v3.0.0b3] New :meth:`~eodag.api.core.EODataAccessGateway.add_provider` method (:pull:`1260`)
* [v3.0.0b2] New :class:`~eodag.api.search_result.SearchResult` HTML representation for notebooks (:pull:`1243`)
* [v3.0.0b1] Search results sort feature (:pull:`943`)
* [v3.0.0b1] Providers groups (:pull:`1071`)
* [v3.0.0b1] Configurable download timeout (:pull:`1124`)

Providers and product types updates
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* **[v3.0.0]** Updated ``cop_ads`` and ``cop_cds`` to new cds api (:pull:`1284`)
* **[v3.0.0]** ``wekeo`` split into ``wekeo_main`` and ``wekeo_ecmwf`` providers (:pull:`1214`)
* [v3.0.0b1] `dedl <https://hda.data.destination-earth.eu/ui>`_ as new provider (:pull:`750`)
* [v3.0.0b1] `dedt_lumi <https://polytope.lumi.apps.dte.destination-earth.eu/openapi>`_ as new provider (:pull:`1119`)
  (:pull:`1126`), with authentication using destine credentials (:pull:`1127`)
* [v3.0.0b1] `cop_marine <https://marine.copernicus.eu/>`_ as new provider (:pull:`1131`)(:pull:`1224`)
* [v3.0.0b1] `eumetsat_ds <https://data.eumetsat.int/>`_ as new provider (:pull:`1060`), including `METOP` product types
  (:pull:`1143`)(:pull:`1189`)
* [v3.0.0b1] `OData` API usage for ``creodias`` & ``cop_dataspace`` (:pull:`1149`)

Plugins new features and fixes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* [v3.0.0b1] Standardized download output tree (:pull:`746`)
* [v3.0.0b1] ``flatten_top_dirs`` download plugins option set to true by default (:pull:`1220`)
* [v3.0.0b1] ``base_uri`` download plugins setting is not systematically mandatory any more (:pull:`1230`)
* [v3.0.0b1] Allow no auth for :class:`~eodag.plugins.download.http.HTTPDownload` download requests (:pull:`1196`)

Server mode
^^^^^^^^^^^

* [v3.0.0b1] Server-mode rework and cql2 support (:pull:`966`)
* [v3.0.0b1] Offline products order handling (:pull:`918`)
* **[v3.0.0]** Browsable catalogs removed (:pull:`1306`)

Miscellaneous
^^^^^^^^^^^^^

* **[v3.0.0b1 to v3.0.0][style]** type hints fixes and ``mypy`` in ``tox`` (:pull:`1052`)(:pull:`1253`)(:pull:`1269`)
  (:pull:`1326`)
* **[v3.0.0][docs]** Developer documentation update (:pull:`1327`)

Remaining changes since `v3.0.0b3 <changelog.rst#v3-0-0b3-2024-08-01>`_
-----------------------------------------------------------------------

Core features and fixes
^^^^^^^^^^^^^^^^^^^^^^^

* Improve search and authentication errors format (:pull:`1237`)

Providers and product types updates
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Handle ``cop_marine`` in-situ historical data (:pull:`1301`)
* Fixes for ``wekeo``: ``GRIDDED_GLACIERS_MASS_CHANGE`` order link (:pull:`1258`), yaml issue in provider config
  (:pull:`1315`)
* Fixes for ``wekeo_ecmwf``: ``hydrological_year`` usage (:pull:`1313`), fixed default dates (:pull:`1288`)

Plugins new features and fixes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Raise an error if no data available on :class:`~eodag.plugins.download.aws.AwsDownload` (:pull:`1257`)

Server mode
^^^^^^^^^^^

* Fixed *queryables* issues and parameters prefixes (:pull:`1318`)
* Send ``search_stac_items()`` in its own threadpool (:pull:`1323`)
* Fixed STAC collections metadata (:pull:`1278`)
* Updated logs format (:pull:`1238`)

Miscellaneous
^^^^^^^^^^^^^

* **[ci]** ``mypy`` in linting github action (:pull:`1326`), actions updates (:pull:`1310`)(:pull:`1314`)
* Various minor fixes and improvements (:pull:`1256`)(:pull:`1263`)(:pull:`1276`)(:pull:`1289`)(:pull:`1294`)
  (:pull:`1295`)(:pull:`1296`)(:pull:`1300`)(:pull:`1303`)(:pull:`1304`)(:pull:`1308`)(:pull:`1333`)
* External product types reference updates (:pull:`1290`)(:pull:`1316`)(:pull:`1322`)(:pull:`1334`)

v3.0.0b3 (2024-08-01)
=====================

|:warning:| Breaking changes
----------------------------

* :meth:`~eodag.api.core.EODataAccessGateway.download` / :class:`~eodag.types.download_args.DownloadConf` parameters
  ``outputs_prefix`` and ``outputs_extension`` renamed to ``output_dir`` and ``output_extension`` (:pull:`1279`)

Core features and fixes
-----------------------

* New :meth:`~eodag.api.core.EODataAccessGateway.add_provider` method (:pull:`1260`)
* Handle integers as ``locations`` shapefile attributes (:pull:`1280`)
* Renames some parameters and methods to snake_case (:pull:`1271`)
* Sorted discovered product types (:pull:`1250`)

Providers and product types updates
-----------------------------------

* Fixes ``usgs`` search by id (:pull:`1262`)
* Adds ``S1_SAR_GRD_COG`` and new odata query parameters for ``cop_dataspace`` (:pull:`1277`, thanks
  `@ninsbl <https://github.com/ninsbl>`_)
* Adds ``GRIDDED_GLACIERS_MASS_CHANGE`` on provider ``cop_cds`` (:pull:`1255`)
* Removes ``cacheable`` parameter for ``wekeo`` order requests (:pull:`1239`)

Plugins new features and fixes
------------------------------

* ``aws_session_token`` support in :class:`~eodag.plugins.authentication.aws_auth.AwsAuth` (:pull:`1267`)
* :class:`~eodag.plugins.download.http.HTTPDownload` asset ``HEAD`` check and ``ssl_verify`` (:pull:`1266`)
* Product types discovery disabled by default on :class:`~eodag.plugins.search.static_stac_search.StaticStacSearch`
  (:pull:`1259`)

Miscellaneous
-------------

* **[style]** type hints fixes and ``mypy`` in ``tox`` (:pull:`1253`)(:pull:`1269`)
* **[docs]** v3 breaking changes (:pull:`1281`), :meth:`~eodag.api.core.EODataAccessGateway.download` kwargs
  (:pull:`1282`), autosummary fixes (:pull:`1264`) and changelog update (:pull:`1254`)
* **[ci]** Github actions updates (:pull:`1249`)
* **[test]** Fixed end-to-end tests (:pull:`1236`)
* External product types reference updates (:pull:`1244`)(:pull:`1246`)(:pull:`1251`)

v3.0.0b2 (2024-06-29)
=====================

Core features and fixes
-----------------------

* New :class:`~eodag.api.search_result.SearchResult` HTML representation for notebooks (:pull:`1243`)

Plugins new features and fixes
------------------------------

* Fixed missing ``products`` configuration in ``Api`` plugin download (:pull:`1241`)
* Fixed ``pagination`` configuration to be not allways mandatory (:pull:`1240`)

Miscellaneous
-------------

* **[docs]** Custom mock search plugin example (:pull:`1242`)
* External product types reference updates (:pull:`1234`)

v3.0.0b1 (2024-06-24)
=====================

|:warning:| Breaking changes
----------------------------

* `search() <https://eodag.readthedocs.io/en/latest/notebooks/api_user_guide/4_search.html#search()>`_ method now
  returns only a :class:`~eodag.api.search_result.SearchResult` instead of a 2 values tuple (:pull:`1200`). It can
  optionally store the estimated total number of products in ``SearchResult.number_matched`` if the method is called
  with ``count=True`` (``False`` by  default).
* Packaging refactoring and new `optional dependencies
  <https://eodag.readthedocs.io/en/latest/getting_started_guide/install.html#optional-dependencies>`_ (:pull:`1108`)
  (:pull:`1219`). EODAG default installs with a minimal set of dependencies.
  New sets of extra requirements are: ``eodag[all]``, ``eodag[all-providers]``, ``eodag[ecmwf]``, ``eodag[usgs]``,
  ``eodag[csw]``, ``eodag[server]``. Previous existing sets of extra requirements are also kept:
  ``eodag[notebook]``, ``eodag[tutorials]``, ``eodag[dev]``, ``eodag[docs]``.

Core features and fixes
-----------------------

* Search results sort feature (:pull:`943`)
* Providers groups (:pull:`1071`)
* Configurable download timeout (:pull:`1124`)
* `Search by id <https://eodag.readthedocs.io/en/stable/notebooks/api_user_guide/4_search.html#id-and-provider>`_ now
  uses :meth:`~eodag.api.core.EODataAccessGateway.search_all` and
  `crunch <https://eodag.readthedocs.io/en/stable/notebooks/api_user_guide/7_crunch.html#Filter-by-property>`_
  (:pull:`1099`).
* Free text search available for all fields when `guessing a produc type
  <https://eodag.readthedocs.io/en/stable/notebooks/api_user_guide/7_crunch.html#Filter-by-property>`_ (:pull:`1070`),
  mission dates filtering support (:pull:`1222`)
* Configurable requests ``ssl_verify`` (:pull:`1045`)
* Download record hash independent from provider (:pull:`1023`)
* Fixed and refactored `queryables` (:pull:`1050`)(:pull:`1097`)(:pull:`1102`)(:pull:`1157`), authentication fix
  (:pull:`1194`), support for local constraints files (:pull:`1105`)
* Fixed `metadata mapping` in templates detection (:pull:`1139`), ``format_query_params()`` fixes (:pull:`1145`) and
  refactor (:pull:`1142`). Configurable assets filtering (:pull:`1033`).

Providers and product types updates
-----------------------------------

* `dedl <https://hda.data.destination-earth.eu/ui>`_ as new provider (:pull:`750`)
* `dedt_lumi <https://polytope.lumi.apps.dte.destination-earth.eu/openapi>`_ as new provider (:pull:`1119`)
  (:pull:`1126`), with authentication using destine credentials (:pull:`1127`)
* `cop_marine <https://marine.copernicus.eu/>`_ as new provider (:pull:`1131`)(:pull:`1224`)
* `eumetsat_ds <https://data.eumetsat.int/>`_ as new provider (:pull:`1060`), including `METOP` product types
  (:pull:`1143`)(:pull:`1189`)
* `OData` API usage for ``creodias`` & ``cop_dataspace`` (:pull:`1149`), fixes for empty geometries (:pull:`1186`),
  search datetime intervals (:pull:`1158`), and removed `discover_product_types` (:pull:`1112`)
* ``cop_ads`` and ``cop_cds`` now use :class:`~eodag.plugins.search.build_search_result.BuildSearchResult` and
  :class:`~eodag.plugins.download.http.HTTPDownload` instead of move ``CdsApi`` (:pull:`1029`), `EFAS` dates formatting
  (:pull:`1178`), ``area`` metadata mapping fix (:pull:`1225`)
* ``wekeo`` now uses `hda-broker 2.0` API (:pull:`1034`), lists queryables (:pull:`1104`), has fixed pagination
  (:pull:`1098`) and CLMS search by id (:pull:`1100`)
* Adjusted timeouts (:pull:`1163`)
* Opened time intervals supported for STAC providers (:pull:`1144`)
* New product types (:pull:`1164`)(:pull:`1227`), providers and product types configuration update (:pull:`1212`)

Plugins new features and fixes
------------------------------

* Standardized download output tree (:pull:`746`)
* Refactored search plugins methods to use ``PreparedSearch`` and ``RawSearchResult`` new classes (:pull:`1191`)
* Refresh token for :class:`~eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth` plugin
  (:pull:`1138`), tests (:pull:`1135`), and fix (:pull:`1232`)
* :class:`~eodag.plugins.authentication.header.HTTPHeaderAuth` accepts headers definition in credentials (:pull:`1215`)
* ``flatten_top_dirs`` download plugins option set to true by default (:pull:`1220`)
* ``base_uri`` download plugins setting is not systematically mandatory any more (:pull:`1230`)
* Re-login in :class:`~eodag.plugins.apis.usgs.UsgsApi` plugin on api file error (:pull:`1046`)
* Allow no auth for :class:`~eodag.plugins.download.http.HTTPDownload` download requests (:pull:`1196`)
* Refactorization of ``Api`` base plugin that now inherits from ``Search`` and ``Download`` (:pull:`1051`)
* ``orderLink`` support in `build_search_result.*` plugins (:pull:`1082`), and parsing fix (:pull:`1091`)
* Fixed resume interrupted assets download using :class:`~eodag.plugins.download.http.HTTPDownload` (:pull:`1017`)

Server mode
-----------

* Server-mode rework and cql2 support (:pull:`966`)
* Offline products order handling (:pull:`918`)
* External enhanced product types metadata (:pull:`1008`)(:pull:`1171`)(:pull:`1176`)(:pull:`1180`)(:pull:`1197`)
* Collections search using updated :meth:`~eodag.api.core.EODataAccessGateway.guess_product_type` (:pull:`909`)
* Providers groups (:pull:`1192`), and fixes for listing (:pull:`1187`) and items self links (:pull:`1090`)
* ``HEAD`` requests enabled (:pull:`1120`)
* LRU caching (:pull:`1073`)
* Additional item properties (:pull:`1170`)
* ``order`` and ``storage`` extensions usage (:pull:`1117`)
* ``bbox`` in queryables (:pull:`1185`), fixed some types missing (:pull:`1083`)
* Blacklist configution for assets alternate URLs (:pull:`1213`)
* ``id`` vs ``title`` in item metadata fix (:pull:`1193`)
* Error handling fixes (:pull:`1078`)(:pull:`1103`)(:pull:`1182`)
* Other server-mode fixes  (:pull:`1065`)(:pull:`1087`)(:pull:`1094`)(:pull:`1095`)(:pull:`1096`)(:pull:`1106`)
  (:pull:`1113`)(:pull:`1115`)(:pull:`1156`)(:pull:`1174`)(:pull:`1210`)(:pull:`1221`)(:pull:`1223`)

Miscellaneous
-------------

* **[build]** Updated requirements for ``uvicorn`` (:pull:`1152`), ``shapely`` (:pull:`1155`), ``orjson`` (:pull:`1150`)
  (:pull:`1079`)
* **[build]** Remove ``requests-ftp`` (:pull:`1085`)
* **[style]** type hints related fixes and refactoring (:pull:`1052`)
* **[docs]** sphinx theme updated and removed jquery (:pull:`1054`), newlines between badges fixes (:pull:`1109`), and
  other documentation fixes and updates (:pull:`1057`)(:pull:`1059`)(:pull:`1062`)(:pull:`1063`)(:pull:`1081`)
  (:pull:`1121`)(:pull:`1122`)
* **[ci]** Fetch product types Github action updates (:pull:`1202`)(:pull:`1205`)
* Various minor fixes and improvements (:pull:`1072`)(:pull:`1077`)(:pull:`1101`)(:pull:`1111`)(:pull:`1118`)
  (:pull:`1132`)(:pull:`1141`)(:pull:`1190`)
* External product types reference updates (:pull:`1027`)(:pull:`1028`)(:pull:`1086`)(:pull:`1093`)(:pull:`1107`)
  (:pull:`1110`)(:pull:`1114`)(:pull:`1136`)(:pull:`1137`)(:pull:`1140`)(:pull:`1146`)(:pull:`1151`)(:pull:`1153`)
  (:pull:`1160`)(:pull:`1165`)(:pull:`1203`)(:pull:`1204`)(:pull:`1206`)(:pull:`1207`)(:pull:`1208`)(:pull:`1229`)

v2.12.1 (2024-03-05)
====================

* `CdsApi` queryables fix (:pull:`1048`)

v2.12.0 (2024-02-19)
====================

* Individual product asset download methods (:pull:`932`)
* New environment variable `EODAG_CFG_DIR` available for custom configuration directory (:pull:`927`)
* New `list_queryables <https://eodag.readthedocs.io/en/latest/notebooks/api_user_guide/4_search.html#Queryables>`_
  method, available through python API and server mode, and using product-types constraints if available (:pull:`911`)
  (:pull:`917`)(:pull:`974`)(:pull:`977`)(:pull:`978`)(:pull:`981`)(:pull:`1005`)
* Removes limited RPC server (:pull:`1011`)
* Product types aliases (:pull:`905`)
* New provider `creodias_s3` (:pull:`986`)(:pull:`1002`)
* `earth_search` endpoint updated from v0 to v1 (:pull:`754`)
* `wekeo` endpoint updated to *wekeo2 wekeo-broker API* (:pull:`1010`)
* New product types added for `cop_ads` and `cop_cds` (:pull:`898`)
* Adds missing `tileIdentifier` and `quicklook` for `creodias`, `creodias_s3` and `cop_dataspace` (:pull:`957`)
  (:pull:`1014`)
* HTTP download with `CdsApi` (:pull:`946`)
* Download streaming available for :class:`~eodag.plugins.download.aws.AwsDownload` plugin (:pull:`997`)
* Lists STAC alternate assets in server mode (:pull:`961`)
* `_dc_qs` used in server-mode to store `CdsApi` search criteria (:pull:`958`)(:pull:`1000`)
* New eodag exception :class:`~eodag.utils.exceptions.TimeOutError` (:pull:`982`)
* Cast loaded environment variables type using config type-hints (:pull:`987`)
* Type hints fixes (:pull:`880`)(:pull:`983`)
* Requirements updates (:pull:`1020`)(:pull:`1021`)
* Various server mode fixes (:pull:`891`)(:pull:`895`)(:pull:`947`)(:pull:`992`)(:pull:`1001`)
* Various minor fixes and improvements (:pull:`934`)(:pull:`935`)(:pull:`936`)(:pull:`962`)(:pull:`969`)(:pull:`976`)
  (:pull:`980`)(:pull:`988`)(:pull:`991`)(:pull:`996`)(:pull:`1003`)(:pull:`1009`)(:pull:`1013`)(:pull:`1016`)
  (:pull:`1019`)(:pull:`1022`)(:pull:`1024`)(:pull:`1025`)

v2.11.0 (2023-11-20)
====================

* Fallback mechanism for search (:pull:`753`)(:pull:`807`)
* `creodias` and `cop_dataspace` configuration update (from `OData` to `OpenSearch`) (:pull:`866`)(:pull:`883`)
  (:pull:`894`)(:pull:`915`)(:pull:`929`)
* Removes `mundi` provider (:pull:`890`)
* Copernicus DEM product types available through creodias (:pull:`882`)
* `wekeo` driver update and new product types (:pull:`798`)(:pull:`840`)(:pull:`856`)(:pull:`902`)
* Allows `provider` search parameter to directly search on it (:pull:`790`)
* Refresh token usage in `KeycloakOIDCPasswordAuth` (`creodias` and `cop_dataspace`) (:pull:`921`)
* Per-provider search timeout (:pull:`841`)
* New `EODAG_PROVIDERS_CFG_FILE` environment variable for custom provider configuration setting (:pull:`836`)
* Many server-mode updates and fixes: `queryables` endpoints (:pull:`795`), built-in Swagger doc update (:pull:`846`),
  exceptions handling (:pull:`794`)(:pull:`806`)(:pull:`812`)(:pull:`829`),
  provider setting (:pull:`808`) and returned information (:pull:`884`)(:pull:`879`), multithreaded requests (:pull:`843`),
  opened time intervals fixes (:pull:`837`), search-by-ids fix (:pull:`822`), intersects parameter fixes (:pull:`796`)
  (:pull:`797`)
* Adds support for Python 3.12 (:pull:`892`) and removes support for Python 3.7 (:pull:`903`)
* Fixes plugin manager rebuild (solves preferred provider issues) (:pull:`919`)
* Reformatted logs (:pull:`842`)(:pull:`885`)
* Adds static type information (:pull:`863`)
* Various minor fixes and improvements (:pull:`759`)(:pull:`788`)(:pull:`791`)(:pull:`793`)(:pull:`802`)(:pull:`804`)
  (:pull:`805`)(:pull:`813`)(:pull:`818`)(:pull:`819`)(:pull:`821`)(:pull:`824`)(:pull:`825`)(:pull:`828`)(:pull:`830`)
  (:pull:`832`)(:pull:`835`)(:pull:`838`)(:pull:`844`)(:pull:`867`)(:pull:`868`)(:pull:`872`)(:pull:`877`)(:pull:`878`)
  (:pull:`881`)(:pull:`893`)(:pull:`899`)(:pull:`913`)(:pull:`920`)(:pull:`925`)(:pull:`926`)

v2.11.0b1 (2023-07-28)
======================

* `wekeo <https://www.wekeo.eu>`_ as new provider (:pull:`772`)
* Server-mode Flask to FastAPI (:pull:`701`)
* Server-mode download streaming (:pull:`742`)
* Updated creodias authentication mechanism to Creodias-new (:pull:`763`)
* Helm Chart (:pull:`739`)
* Server-mode search by (multiples) id(s) (:pull:`776`)
* Fixed server-mode parallel requests (:pull:`741`)
* Keep origin assets in the stac server response (:pull:`681`)
* Enable single-link download for STAC providers (:pull:`757`)
* Fixes missing provider in STAC download link (:pull:`774`)
* Better documentation for `guess_product_type()\
  <https://eodag.readthedocs.io/en/latest/notebooks/api_user_guide/4_search.html#Guess-a-product-type>`_ (:pull:`756`)
* Fixed issue with docker image user directory (:pull:`764`)
* Various minor fixes and improvements (:pull:`720`)(:pull:`717`)(:pull:`722`)(:pull:`723`)(:pull:`724`)(:pull:`727`)
  (:pull:`729`)(:pull:`731`)(:pull:`737`)(:pull:`738`)(:pull:`743`)(:pull:`744`)(:pull:`745`)(:pull:`749`)(:pull:`751`)
  (:pull:`762`)(:pull:`771`)(:pull:`775`)(:pull:`777`)

v2.10.0 (2023-04-18)
====================

* `hydroweb_next` (`hydroweb.next <https://hydroweb.next.theia-land.fr>`_), thematic hub for hydrology data access,
  as new provider (:pull:`711`)
* Search by tile standardized using ``tileIdentifier`` new query parameter and metadata (:pull:`713`)
* Server mode STAC API version updated to `1.0.0-rc.3` (:pull:`697`)
* Better catalogs title and description in server mode (:pull:`710`)
* Server mode advanced tests (:pull:`708`), and fixes for catalogs dates filtering (:pull:`706`), catalogs cloud-cover
  filtering (:pull:`705`), missing `sensorType` error for discovered product types (:pull:`699`), broken links through
  STAC search endpoint (:pull:`698`)
* Added links to `eodag-server <https://hub.docker.com/r/csspace/eodag-server>`_ image on Dockerhub (:pull:`715`)
* EODAG server installation update in docker image (:pull:`700`) and sigterm fix (:pull:`702`)
* STAC browser docker image update (:pull:`704`)
* Various minor fixes and improvements (:pull:`693`)(:pull:`694`)(:pull:`695`)(:pull:`696`)(:pull:`703`)(:pull:`707`)
  (:pull:`712`)(:pull:`714`)

v2.9.2 (2023-03-31)
===================

* `planetary_computer`, `Microsoft Planetary Computer <https://planetarycomputer.microsoft.com/>`_  as new provider
  (:pull:`659`)
* Fetch product types optimization (:pull:`683`)
* Fixes external product types update for unknown provider (:pull:`682`)
* Default dates and refactor for `CdsApi` and :class:`~eodag.plugins.apis.ecmwf.EcmwfApi` (:pull:`672`)(:pull:`678`)(:pull:`679`)
* `peps` `storageStatus` update (:pull:`677`)
* Customized and faster `deepcopy` (:pull:`664`)
* Various minor fixes and improvements (:pull:`665`)(:pull:`666`)(:pull:`667`)(:pull:`668`)(:pull:`669`)(:pull:`670`)
  (:pull:`675`)(:pull:`688`)(:pull:`690`)(:pull:`691`)

v2.9.1 (2023-02-27)
===================

* ``cop_dataspace``, `Copernicus Data Space <https://dataspace.copernicus.eu>`_  as new provider (:pull:`658`)
* EODAG specific `User-Agent` appended to requests headers (:pull:`656`)
* ``Sentinel-5P`` and other product types updates for ``creodias``, ``mundi`` and ``onda`` (:pull:`657`)
* Handle missing geometries through new ``defaultGeometry`` :class:`~eodag.api.product._product.EOProduct` property
  (:pull:`653`)
* ``mundi`` `GeoRSS` geometries handling (:pull:`654`)
* Fixes search errors handling (:pull:`660`)
* Various minor fixes and improvements (:pull:`649`)(:pull:`652`)

v2.9.0 (2023-02-16)
===================

* Optimizes search time mixing count and search requests when possible (:pull:`632`)
* Optimizes search time with rewritten ``JSONPath.parse`` usage now based on a
  `common_metadata_mapping_path` (:pull:`626`)
* ``creodias`` API update, from resto to OData (:pull:`623`)(:pull:`639`)
* Optimizes and updates ``onda`` search (:pull:`616`)(:pull:`636`)
* Fixes OFFLINE products order mechanism for ``mundi`` provider (:pull:`645`)
* Download progress bar adjustable refresh time (:pull:`643`)
* Simplify ``OData`` metadata mapping using pre-mapping (:pull:`622`)
* Fixes download error for single-asset products on STAC providers (:pull:`634`)
* Tests execution optimized (:pull:`631`)
* Various minor fixes and improvements (:pull:`612`)(:pull:`619`)(:pull:`620`)(:pull:`621`)(:pull:`624`)(:pull:`625`)
  (:pull:`629`)(:pull:`630`)(:pull:`635`)(:pull:`638`)(:pull:`640`)(:pull:`641`)(:pull:`642`)(:pull:`644`)(:pull:`646`)
  (:pull:`647`)

v2.8.0 (2023-01-17)
===================

* `meteoblue <https://content.meteoblue.com/en/business-solutions/weather-apis/dataset-api>`_ as new forecast provider,
  in the context of DOMINO-X (:pull:`604`)
* `SARA <https://copernicus.nci.org.au/sara.client>`_ (Sentinel Australasia Regional Access) as new provider
  (:pull:`578`, thanks `@catchSheep <https://github.com/catchSheep>`_)(:pull:`602`)
* Removes unavailable ```sobloo``` provider (:pull:`607`)
* Landsat collection-1 data no more available on `usgs` (:pull:`601`)
* `Product types catalog\
  <https://eodag.readthedocs.io/en/latest/getting_started_guide/product_types.html#product-types-information-csv>`_
  more visible in documentation (:pull:`603`)
* Metadata mapping `to_geo_interface()` renamed to `to_geojson()`
  (`d7565a4 <https://github.com/CS-SI/eodag/pull/604/commits/d7565a4984d356aca20310a87c02692cb879427e>`_)
* Added support for `python3.11` (:pull:`552`)
* Improved http asset size discovery in :class:`~eodag.plugins.download.http.HTTPDownload` (:pull:`566`)
* Various minor fixes and improvements (:pull:`572`)(:pull:`574`)(:pull:`576`)(:pull:`579`)(:pull:`580`)(:pull:`582`)
  (:pull:`586`)(:pull:`588`)(:pull:`589`)(:pull:`590`)(:pull:`592`)(:pull:`593`)(:pull:`595`)(:pull:`597`)(:pull:`598`)
  (:pull:`599`)(:pull:`609`)(:pull:`610`)

v2.7.0 (2022-11-29)
===================

* Fetch external product types before searching for an unkown product type (:pull:`559`)
* Handle local assets in :class:`~eodag.plugins.download.http.HTTPDownload` plugin (:pull:`561`)
* Fetch external product types only for given provider if one is specified (:pull:`557`)
* Fixed request error handling during :meth:`~eodag.api.core.EODataAccessGateway.search_all` (:pull:`554`)
* Various minor fixes and improvements (:pull:`555`)(:pull:`558`)(:pull:`562`)

v2.6.2 (2022-11-15)
===================

* Added new methods to get assets filename from header (:pull:`542`)
* All local files URI formats are now supported (:pull:`545`)
* More tests (:pull:`539`)(:pull:`549`)
* Various minor fixes and improvements (:pull:`535`)(:pull:`540`)(:pull:`541`)(:pull:`543`)(:pull:`544`)(:pull:`553`)

v2.6.1 (2022-10-19)
===================

* Swagger UI now needs to be manually run when using python API (:pull:`529`)
* Removed `cloudCover` restriction in product types discovery (:pull:`530`)
* Some `sensorType` values changed in product types settings to align to `OpenSearch extension for Earth Observation\
  <http://docs.opengeospatial.org/is/13-026r9/13-026r9.html>`_ (:pull:`528`)
* Fixed CSS glitch in `online documentation parameters tables\
  <https://eodag.rtfd.io/en/stable/add_provider.html#parameters-mapping>`_ (:pull:`527`)
* Fixed S3 bucket extraction (:pull:`524`)
* Various minor fixes and improvements (:pull:`522`)(:pull:`523`)(:pull:`525`)(:pull:`526`)

v2.6.0 (2022-10-07)
===================

* New `product types automatic discovery\
  <https://eodag.rtfd.io/en/latest/notebooks/api_user_guide/2_providers_products_available.html#Product-types-discovery>`_
  (:pull:`480`)(:pull:`467`)(:pull:`470`)(:pull:`471`)(:pull:`472`)(:pull:`473`)(:pull:`481`)(:pull:`486`)(:pull:`493`)
  (:pull:`491`)(:pull:`500`)
* New providers `cop_ads <https://ads.atmosphere.copernicus.eu>`_ and `cop_cds <https://cds.climate.copernicus.eu>`_
  for Copernicus Atmosphere and Climate Data Stores using `CdsApi` plugin, developed in
  the context of DOMINO-X (:pull:`504`)(:pull:`513`)
* :class:`~eodag.plugins.apis.usgs.UsgsApi` plugin fixed and updated (:pull:`489`)(:pull:`508`)
* Cache usage for ``jsonpath.parse()`` (:pull:`502`)
* Refactored download retry mechanism and more tests (:pull:`506`)
* Drop support of Python 3.6 (:pull:`505`)
* Various minor fixes and improvements (:pull:`469`)(:pull:`483`)(:pull:`484`)(:pull:`485`)(:pull:`490`)(:pull:`492`)
  (:pull:`494`)(:pull:`495`)(:pull:`496`)(:pull:`497`)(:pull:`510`)(:pull:`511`)(:pull:`514`)(:pull:`517`)

v2.5.2 (2022-07-05)
===================

* Fixes missing ``productPath`` property for some ``earth_search`` products (:pull:`480`)

v2.5.1 (2022-06-27)
===================

* Fixed broken :class:`~eodag.plugins.download.aws.AwsDownload` configuration for STAC providers (:pull:`475`)
* Set ``setuptools_scm`` max version for python3.6 (:pull:`477`)

v2.5.0 (2022-06-07)
===================

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

v2.4.0 (2022-03-09)
===================

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

v2.3.4 (2021-10-08)
===================

* Link to the new eodag Jupyterlab extension: `eodag-labextension <https://github.com/CS-SI/eodag-labextension>`_
  (:pull:`352`)
* STAC client and server update to STAC 1.0.0 (:pull:`347`)
* Fixes :meth:`~eodag.api.product._product.EOProduct.get_quicklook` for onda provider
  (:pull:`344`, thanks `@drnextgis <https://github.com/drnextgis>`_)
* Fixed issue when downloading ``S2_MSI_L2A`` products from ``mundi`` (:pull:`350`)
* Various minor fixes and improvements (:pull:`340`)(:pull:`341`)(:pull:`345`)

v2.3.3 (2021-08-11)
===================

* Fixed issue when searching by id (:pull:`335`)
* Specified minimal `eodag-cube <https://github.com/CS-SI/eodag-cube>`_ version needed (:pull:`338`)
* Various minor fixes and improvements (:pull:`336`)(:pull:`337`)

v2.3.2 (2021-07-29)
===================

* Fixes duplicate logging in :meth:`~eodag.api.core.EODataAccessGateway.search_all` (:pull:`330`)
* Enable additional arguments like `productType` when searching by id (:pull:`329`)
* Prevent EOL auto changes on windows causing docker crashes (:pull:`324`)
* Configurable eodag logging in docker stac-server (:pull:`323`)
* Fixes missing `productType` in product properties when searching by id (:pull:`320`)
* Various minor fixes and improvements (:pull:`319`)(:pull:`321`)

v2.3.1 (2021-07-09)
===================

- Dockerfile update to be compatible with `stac-browser v2.0` (:pull:`314`)
- Adds new notebook extra dependency (:pull:`317`)
- EOProduct drivers definition update (:pull:`316`)

v2.3.0 (2021-06-24)
===================

- Removed Sentinel-3 products not available on peps any more (:pull:`304`, thanks `@tpfd <https://github.com/tpfd>`_)
- Prevent :meth:`~eodag.utils.notebook.NotebookWidgets.display_html` in ipython shell (:pull:`307`)
- Fixed plugins reload after having updated providers settings from user configuration (:pull:`306`)

v2.3.0b1 (2021-06-11)
=====================

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

v2.2.0 (2021-03-26)
===================

- New :meth:`~eodag.api.core.EODataAccessGateway.search_all` and
  :meth:`~eodag.api.core.EODataAccessGateway.search_iter_page` methods to simplify pagination handling (:pull:`190`)
- Docker-compose files for STAC API server with STAC-browser (:pull:`183`,
  thanks `@apparell <https://github.com/apparell>`_)
- Fixed USGS plugin which now uses M2M API (:pull:`209`)
- Windows support added in Continuous Integration (:pull:`192`)
- Fixes issue with automatically load configution from EODAG external plugins, fixes :issue:`184`
- More explicit signature for :meth:`~eodag.utils.logging.setup_logging`, fixes :issue:`197`
- Various minor fixes

v2.1.1 (2021-03-18)
===================

- Continuous Integration performed with GitHub actions
- Providers config automatically loaded from EODAG external plugins, fixes :issue:`172`
- Various minor fixes

v2.1.0 (2021-03-09)
===================

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
- Locations must now be passed to :meth:`~eodag.api.core.EODataAccessGateway.search` method as a dictionary
- Metadata mapping update and uniformization, fixes :issue:`154`
- Raise a :class:`ValueError` when a location search doesn't match any record and add a new ``locations``
  parameter to :meth:`~eodag.api.core.EODataAccessGateway.search`.
- Drop support of Python 3.5

v2.0.1 (2021-02-05)
===================

- Fixes issue when rebuilding index on NFS, see :issue:`151`
- Tests can be run in parallel mode, fixes :issue:`103`

v2.0 (2021-01-28)
=================

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

v2.0b2 (2020-12-18)
===================

- New method :meth:`~eodag.api.core.EODataAccessGateway.deserialize_and_register`, fixes :issue:`140`
- Load static stac catalogs as :class:`~eodag.api.search_result.SearchResult`
- Search on unknown product types using ``GENERIC_PRODUCT_TYPE``
- ``get_data``, drivers and rpc server moved to `eodag-cube <https://github.com/CS-SI/eodag-cube>`_
- Removed fixed dependencies, fixes :issue:`82`
- Use locations conf template by default

v2.0b1 (2020-11-17)
===================

- STAC API compliant REST server
- Common configuration for STAC providers
- astraea_eod as new STAC provider
- Search by geometry / bbox / location name, fixes :issue:`49`
- removed Python 2.7 support

v1.6.0 (2020-08-24)
===================

- Warning: last release including Python 2.7 support

v1.6.0rc2 (2020-08-11)
======================

- Queryable parameters configuration update for peps
- Fixed re-download error after original zip deletion, fixes :issue:`142`
- Fixed python-dateutil version conflict, fixes :issue:`141`
- Default user configuration file usage in CLI mode
- Fixed error when provider returns geometry as bbox with negative coords, fixes :issue:`143`

v1.6.0rc0 (2020-06-18)
======================

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

v1.5.2 (2020-05-06)
===================

- Fix CLI download_all missing plugin configuration, fixes :issue:`134`

v1.5.1 (2020-04-08)
===================

- ``productionStatus`` parameter renamed to ``storageStatus``,
  see `Parameters Mapping documentation <https://eodag.readthedocs.io/en/latest/intro.html#parameters-mapping>`_

v1.5.0 (2020-04-08)
===================

- ``productionStatus`` parameter standardization over providers
- Not-available products download management, using ``wait``/``timeout``
  :meth:`~eodag.api.core.EODataAccessGateway.download`
  optional parameters, fixes :issue:`125`
- More explicit authentication errors messages
- Update search endoint for aws_s3_sentinel2_l1c and add RequestPayer option usage,
  fixes :issue:`131`

v1.4.2 (2020-03-04)
===================

- Skip badly configured providers in user configuration, see :issue:`129`

v1.4.1 (2020-02-25)
===================

- Warning message if an unknow provider is found in user configuration file,
  fixes :issue:`129`

v1.4.0 (2020-02-24)
===================

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

v1.3.6 (2020-01-24)
===================

- USGS plugin corrections, fixes :issue:`73`
- Fixed py27 encodeurl in querystring
- End-to-end tests update, fixes :issue:`119`
- Default eodag conf used in end-to-end tests, fixes :issue:`98`
- Fixed :meth:`~eodag.api.core.EODataAccessGateway.download_all` method :issue:`118`

v1.3.5 (2020-01-07)
===================

- Removed tqdm_notebook warning, fixes :issue:`117`
- Removed traceback from geom intersection warning, fixes :issue:`114`
- Documentation update for provider priorities and parametters mapping
- New test for readme/pypi syntax

v1.3.4 (2019-12-12)
===================

- Use sobloo official api endpoint, fixes :issue:`115`
- New badges in readme and CS logo
- Set owslib version to 0.18.0 (py27 support dropped)

v1.3.3 (2019-10-11)
===================

- Fixes product configuration for theia provider :issue:`113`

v1.3.2 (2019-09-27)
===================

- Fixes pagination configuration for sobloo provider :issue:`111`

v1.3.1 (2019-09-27)
===================

- Added calls graphs in documentation
- Tutorial notebooks fixes :issue:`109`,
  :issue:`110`
- Download unit display fix :issue:`108`
- Fix date format with sobloo provider :issue:`107`

v1.3.0 (2019-09-06)
===================

- Add parameters mapping in documentation
- Add new queryable parameters for sobloo :issue:`105`
- Fix custom search
- Fix sobloo cloudCoverage query :issue:`106`

v1.2.3 (2019-08-26)
===================

- Binder basic tuto Binder badge only

v1.2.2 (2019-08-23)
===================

- Binder basic tuto working

v1.2.1 (2019-08-23)
===================

- Add binder links

v1.2.0 (2019-08-22)
===================

- Add download_all support by plugins
- Fix GeoJSON rounding issue with new geojson lib

v1.1.3 (2019-08-05)
===================

- Tutorial fix

v1.1.2 (2019-08-05)
===================

- Fix dependency version issue (Jinja2)
- Tutorials fixes and enhancements

v1.1.1 (2019-07-26)
===================

- Updates documentation for custom field

v1.1.0 (2019-07-23)
===================

- Adds custom fields for query string search
- Adapts to new download interface for sobloo

v1.0.1 (2019-04-30)
===================

- Fixes :issue:`97`
- Fixes :issue:`96`

v1.0 (2019-04-26)
=================

- Adds product type search functionality
- Extends the list of search parameters with ``instrument``, ``platform``, ``platformSerialIdentifier``,
  ``processingLevel`` and ``sensorType``
- The cli arguments are now fully compliant with opensearch geo(bbox)/time extensions
- Adds functionality to search products by their ID
- Exposes search products by ID functionality on REST interface
- Exposes get quicklook functionality on REST interface
- Fixes a bug occuring when ``outputs_prefix`` config parameter is not set in user config

v0.7.2 (2019-03-26)
===================

- Fixes bug due to the new version of PyYaml
- Updates documentation and tutorial
- Automatically generates a user configuration file in ``~/.config/eodag/eodag.yml``. This path is overridable by the
  ``EODAG_CFG_FILE`` environment variable.


v0.7.1 (2019-03-01)
===================

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


v0.7.0 (2018-12-04)
===================

- Creates Creodias, Mundi, Onda and Wekeo drivers
- Every provider configuration parameter is now overridable by the user configuration
- Provider configuration is now overridable by environment variables following the pattern:
  EODAG__<PROVIDER>__<CONFIG_PARAMETER> (special prefix + double underscore between configuration keys + configuration
  parameters uppercase with simple underscores preserved). There is no limit to the how fine the override can go
- New authentication plugins (keycloak with openid)


v0.6.3 (2018-09-24)
===================

- Silences rasterio's NotGeoreferencedWarning warning when sentinel2_l1c driver tries to determine the address of a
  requested band on the disk
- Changes the `DEFAULT_PROJ` constant in `eodag.utils` from a `pyproj.Proj` instance to `rasterio.crs.CRS` instance

v0.6.2 (2018-09-24)
===================

- Updates catalog url for airbus-ds provider
- Removes authentication for airbus-ds provider on catalog search

v0.6.1 (2018-09-19)
===================

- Enhance error message for missing credentials
- Enable EOProduct to remember its remote address for subsequent downloads

v0.6.0 (2018-08-09)
===================

- Add support of a new product type: PLD_BUNDLE provided by theia-landsat
- Create a new authentication plugin to perform headless OpenID connect authorisation
  code flow
- Refactor the class name of the core api (from SatImagesAPI to EODataAccessGateway)
- Set peps platform as the default provider
- Set product archive depth for peps provider to 2 (after extracting a product from peps,
  the product is nested one level inside a top level directory where it was extracted)

v0.5.0 (2018-08-02)
===================

- Make progress bar for download optional and customizable
- Fix bugs in FilterOverlap cruncher

v0.4.0 (2018-07-26)
===================

- Enable quicklook retrieval interface for EOProduct

v0.3.0 (2018-07-23)
===================

- Add docs for tutorials
- Configure project for CI/CD on Bitbucket pipelines


v0.2.0 (2018-07-17)
===================

- Prepare project for release as open source and publication on PyPI
- The get_data functionality now returns an xarray.DataArray instead of numpy.ndarray
- Sentinel 2 L1C product type driver for get_data functionality now supports products
  stored on Amazon S3
- Add tutorials


v0.1.0 (2018-06-20)
===================

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


v0.0.1 (2018-06-15)
===================

- Starting to be stable for internal use
- Basic functionality implemented (search, download, crunch, get_data)
