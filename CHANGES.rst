===============
Release history
===============


v4.0.0a4 (2025-11-28)
=====================

Features
--------

* **core**: Providers representation classes (`#1902`_, `fa5f42b`_)

.. _#1902: https://github.com/CS-SI/eodag/pull/1902
.. _fa5f42b: https://github.com/CS-SI/eodag/commit/fa5f42b5ec0cbe172e4dd73db6906f9f7b583793


v4.0.0a3 (2025-11-27)
=====================

Bug Fixes
---------

* **core**: Handling of collections with aliases (`#1935`_, `274280a`_)

* **providers**: Geodes max_items_per_page down to 80 (`#1938`_, `abf8c71`_)

.. _#1935: https://github.com/CS-SI/eodag/pull/1935
.. _#1938: https://github.com/CS-SI/eodag/pull/1938

.. _274280a: https://github.com/CS-SI/eodag/commit/274280ae3b5df1fe7eac792d57192e633879dbcd
.. _abf8c71: https://github.com/CS-SI/eodag/commit/abf8c71bdbb7b3bcc27371b85f47261c489e3650

v4.0.0a2 (2025-11-19)
=====================

Features
--------

* **core**: Collections representation classes (`#1731`_, `4b57160`_)

* **core**: Search pagination using next_page (`#1745`_, `9abe670`_)

* **plugins**: Use original copernicus provider to list queryables of wekeo_ecmwf (`#1897`_,
  `0929a7c`_)

* **providers**: Add DEDT Marenostrum provider (`#1869`_, `650d21b`_)

* **providers**: Add DT_CLIMATE_ADAPTATION collection (`#1908`_, `cd84b88`_)

Bug Fixes
---------

* **core**: Skip None EOProduct.properties (`#1892`_, `41c2fc4`_)

* **core**: Sort queryables and ecmwf alias support (`#1894`_, `090c0bd`_)

* **plugins**: Add temporal resolution to ecmwf properties (`#1899`_, `219e669`_)

* **plugins**: Cop_marine search by id (`#1923`_, `0d42f00`_)

* **plugins**: Ecmwf geometries support (`#1924`_, `e996be9`_)

Continuous Integration
----------------------

* Better external collections summary in auto-update PR (`#1907`_, `43d9fb4`_)

* Fetch collections PR fix and refactor (`#1917`_, `0b88c50`_)

* Pre-commit replaced with faster prek (`#1914`_, `eb5dd5f`_)

Refactoring
-----------

* **collections**: CLMS and MetOp updates (`#1906`_, `9ebb872`_)

* **core**: Disable search pagination when less items got than expected (`#1920`_, `dfa18e7`_)

* **core**: Remove deprecatred legacy driver and get_data doc (`#1891`_, `2500af7`_)

* **core**: Whole world as default product geometry and shapely stubs (`#1915`_, `99df712`_)

* **providers**: Next_page_token_key added to confs (`#1921`_, `2bb99ba`_)

.. _#1730: https://github.com/CS-SI/eodag/pull/1730
.. _#1731: https://github.com/CS-SI/eodag/pull/1731
.. _#1745: https://github.com/CS-SI/eodag/pull/1745
.. _#1781: https://github.com/CS-SI/eodag/pull/1781
.. _#1789: https://github.com/CS-SI/eodag/pull/1789
.. _#1839: https://github.com/CS-SI/eodag/pull/1839
.. _#1840: https://github.com/CS-SI/eodag/pull/1840
.. _#1868: https://github.com/CS-SI/eodag/pull/1868
.. _#1869: https://github.com/CS-SI/eodag/pull/1869
.. _#1877: https://github.com/CS-SI/eodag/pull/1877
.. _#1880: https://github.com/CS-SI/eodag/pull/1880
.. _#1886: https://github.com/CS-SI/eodag/pull/1886
.. _#1888: https://github.com/CS-SI/eodag/pull/1888
.. _#1891: https://github.com/CS-SI/eodag/pull/1891
.. _#1892: https://github.com/CS-SI/eodag/pull/1892
.. _#1894: https://github.com/CS-SI/eodag/pull/1894
.. _#1897: https://github.com/CS-SI/eodag/pull/1897
.. _#1899: https://github.com/CS-SI/eodag/pull/1899
.. _#1906: https://github.com/CS-SI/eodag/pull/1906
.. _#1907: https://github.com/CS-SI/eodag/pull/1907
.. _#1908: https://github.com/CS-SI/eodag/pull/1908
.. _#1911: https://github.com/CS-SI/eodag/pull/1911
.. _#1914: https://github.com/CS-SI/eodag/pull/1914
.. _#1915: https://github.com/CS-SI/eodag/pull/1915
.. _#1917: https://github.com/CS-SI/eodag/pull/1917
.. _#1919: https://github.com/CS-SI/eodag/pull/1919
.. _#1920: https://github.com/CS-SI/eodag/pull/1920
.. _#1921: https://github.com/CS-SI/eodag/pull/1921
.. _#1923: https://github.com/CS-SI/eodag/pull/1923
.. _#1924: https://github.com/CS-SI/eodag/pull/1924
.. _090c0bd: https://github.com/CS-SI/eodag/commit/090c0bdee39041eb9b572112602be9477771a5fe
.. _0929a7c: https://github.com/CS-SI/eodag/commit/0929a7c7f883a5c5efcb87b903e2752a6efd789b
.. _0b88c50: https://github.com/CS-SI/eodag/commit/0b88c5041ec4d838cad64dbf864185b72325c791
.. _0d42f00: https://github.com/CS-SI/eodag/commit/0d42f00e9c237188c0ffc7de8aad3b5a0a37a6ae
.. _219e669: https://github.com/CS-SI/eodag/commit/219e669fa6e8bbbfa96357b21b964dd53c445233
.. _2500af7: https://github.com/CS-SI/eodag/commit/2500af7753cbbc1cfe6d315ea3247aebf6299859
.. _2bb99ba: https://github.com/CS-SI/eodag/commit/2bb99babf59ec2b7cf60a05148f20217ba6bfac9
.. _41c2fc4: https://github.com/CS-SI/eodag/commit/41c2fc4735df6b4498a5333dc13007ece279afce
.. _43d9fb4: https://github.com/CS-SI/eodag/commit/43d9fb442a8f33ab94873be251b230d1838d01c8
.. _4b57160: https://github.com/CS-SI/eodag/commit/4b571601b8a872265adc14c7fdb0be8e8566aa4c
.. _650d21b: https://github.com/CS-SI/eodag/commit/650d21b84e3c929eee7c1b100e6ee7ecfd0a70b8
.. _99df712: https://github.com/CS-SI/eodag/commit/99df71295a9a4c9f03bcb05cec814c4f50e43fb2
.. _9abe670: https://github.com/CS-SI/eodag/commit/9abe670945a70878ed7de5c53c46e5d5776e96c1
.. _9ebb872: https://github.com/CS-SI/eodag/commit/9ebb87297d464d06430dd5271c20b44e0df9b14c
.. _cd84b88: https://github.com/CS-SI/eodag/commit/cd84b88ff1bcb765f0b7ecd4d67fea1b06bc403e
.. _d4f8379: https://github.com/CS-SI/eodag/commit/d4f8379b90c02346506bdb53ded4c06ef128df31
.. _dfa18e7: https://github.com/CS-SI/eodag/commit/dfa18e7212094204000da269d039f05906dcb294
.. _e996be9: https://github.com/CS-SI/eodag/commit/e996be9ae1d7d94703452df736aed6ec8115a1f5
.. _eb5dd5f: https://github.com/CS-SI/eodag/commit/eb5dd5fb85ae17f02ac3abf8d96ff72b84358fea



v4.0.0a1 (2025-10-20)
=====================

Features
--------

* **core: STAC formatted properties** (`#1730`_, `743d7b5`_)

* **core**: Search validation (`#1877`_, `a157358`_)

Bug Fixes
---------

* Keep ext_product_types.json in v4 (`#1888`_, `d4f8379`_)

Continuous Integration
----------------------

* Run tests for v4 branch and associated PRs (`#1868`_, `a944aab`_)

Refactoring
-----------

* Remove deprecated code (`#1781`_, `09e14fe`_)

* Remove deprecated converters and plugins (`#1789`_, `edff5fe`_)

* Remove deprecated server-mode (`#1840`_, `266471b`_)

* **plugins**: Remove deprecated OAuth (`#1839`_, `3b749e2`_)

* **plugins**: Remove deprecated CreodiasS3Download (`#1886`_, `ea0a817`_)

.. _#1730: https://github.com/CS-SI/eodag/pull/1730
.. _#1781: https://github.com/CS-SI/eodag/pull/1781
.. _#1789: https://github.com/CS-SI/eodag/pull/1789
.. _#1839: https://github.com/CS-SI/eodag/pull/1839
.. _#1840: https://github.com/CS-SI/eodag/pull/1840
.. _#1868: https://github.com/CS-SI/eodag/pull/1868
.. _#1877: https://github.com/CS-SI/eodag/pull/1877
.. _#1886: https://github.com/CS-SI/eodag/pull/1886
.. _#1888: https://github.com/CS-SI/eodag/pull/1888
.. _09e14fe: https://github.com/CS-SI/eodag/commit/09e14fe91054bd3a67b572da47f283ea34309b9f
.. _266471b: https://github.com/CS-SI/eodag/commit/266471b676289ad532818986843478cac5765337
.. _3b749e2: https://github.com/CS-SI/eodag/commit/3b749e2b64f4c828f9562de7211df19ae7967736
.. _743d7b5: https://github.com/CS-SI/eodag/commit/743d7b5d25d50425de4c7f1c62c0922d7453afe2
.. _a157358: https://github.com/CS-SI/eodag/commit/a157358fa85e88b09ded3f05e02f463c05bd8cbd
.. _a944aab: https://github.com/CS-SI/eodag/commit/a944aab4675310576ba64d8bc0f634ceb95c3f4b
.. _d4f8379: https://github.com/CS-SI/eodag/commit/d4f8379b90c02346506bdb53ded4c06ef128df31
.. _ea0a817: https://github.com/CS-SI/eodag/commit/ea0a817674470685d4d5d83461c55e7ba0c52f79
.. _edff5fe: https://github.com/CS-SI/eodag/commit/edff5fe12aedf860d1d30392a7775f3d23e648db


v3.10.0 (2025-10-20)
====================

Features
--------

* **plugins**: Possibility to create presigned urls (`#1845`_, `d002c38`_)

Bug Fixes
---------

* **providers**: Added month/year mapping and default values for CMIP6_CLIMATE_PROJECT (`#1872`_,
  `dcdca60`_)

Build System
------------

* Pin pydantic < 2.12.0 to prevent sphinx failures (`#1873`_, `1b17b4a`_)

Refactoring
-----------

* **plugins**: Deprecate CreodiasS3Download (`#1884`_, `5f6966b`_)

.. _#1845: https://github.com/CS-SI/eodag/pull/1845
.. _#1872: https://github.com/CS-SI/eodag/pull/1872
.. _#1873: https://github.com/CS-SI/eodag/pull/1873
.. _#1884: https://github.com/CS-SI/eodag/pull/1884
.. _1b17b4a: https://github.com/CS-SI/eodag/commit/1b17b4af5f898ed608dd132e49477d28466f9451
.. _5f6966b: https://github.com/CS-SI/eodag/commit/5f6966bc52db1e19ad3f959bab41aca25804c3e5
.. _d002c38: https://github.com/CS-SI/eodag/commit/d002c38126f566f52903fb0e5012a22e771c3200
.. _dcdca60: https://github.com/CS-SI/eodag/commit/dcdca6012736f751418725312da736f61767ec36


v3.9.1 (2025-10-07)
===================

Bug Fixes
---------

* **plugins**: AwsAuth without credentials (`#1865`_, `ab04612`_)

* **providers**: Earth_search S2_MSI_L2A_COG assets href (`#1866`_, `f14ef6b`_)

* **providers**: Fix syntax error (`#1860`_, `d207f27`_)

* **providers**: PolarizationChannels mapping for STAC providers (`#1870`_, `819ecb2`_)

.. _#1860: https://github.com/CS-SI/eodag/pull/1860
.. _#1865: https://github.com/CS-SI/eodag/pull/1865
.. _#1866: https://github.com/CS-SI/eodag/pull/1866
.. _#1870: https://github.com/CS-SI/eodag/pull/1870
.. _819ecb2: https://github.com/CS-SI/eodag/commit/819ecb2127d7728236e32aadb1e605017c98cec6
.. _ab04612: https://github.com/CS-SI/eodag/commit/ab046125d1241adc164e8ffdec430b5d77d8193b
.. _d207f27: https://github.com/CS-SI/eodag/commit/d207f2701b472b8c6c75da5c63f0621736dedd8a
.. _f14ef6b: https://github.com/CS-SI/eodag/commit/f14ef6b1b11428f68bc1ff47e1b3081819e03d9a


v3.9.0 (2025-09-26)
===================

Features
--------

* **core**: Assets title normalized to key name (`#1826`_, `3662954`_)

* **providers**: Add CMIP6_CLIMATE_PROJECTIONS product type on cop_cds (`#1827`_, `308e0a9`_)

* **providers**: Available product types update for creodias, cop_dataspace and wekeo_main
  (`#1817`_, `04b0b55`_)

* **providers**: Send query and filter parameters as is for STAC providers (`#1828`_, `3b04096`_)

Bug Fixes
---------

* **core**: Update pattern of data roles in GenericDriver (`#1815`_, `c75351d`_)

* **providers**: CLMS_CORINE metadata mapping for wekeo (`#1846`_, `55b1ffe`_)

* **providers**: Harmonize orbitDirection properties (`#1836`_, `b428d61`_, `#1830`_, `57fecd0`_)

* **providers**: Harmonize polarizationChannels property (`#1831`_, `b85ef0f`_)

* **providers**: PlatformSerialIdentifier mapping for creodias/cop_dataspace (`#1848`_, `f890fbf`_)

* **providers**: S2_MSI_L2A_COG moved to earth_search (`#1841`_, `786c663`_)

Chores
------

* **cli,docs**: Deprecate STAC REST API server (`#1837`_, `083989e`_)

Documentation
-------------

* Documentation overhaul (`#1823`_, `df67693`_)

* Add tutorial for CCI data through fedeo_ceda (`#1832`_, `01b130a`_)

Refactoring
-----------

* **core**: Move dates utils functions to eodag.utils.dates (`#1844`_, `d2cd928`_)

* **core**: Use zipstream-ng instead of stream-zip (`#1805`_, `182cdc0`_)

* **plugins**: Dedt_lumi not-available data error message (`#1770`_, `bf8cbe1`_)

* **plugins**: Deprecate oauth plugin (`#1821`_, `1bdf8a9`_)

* **plugins**: Get_rio_env to AwsAuth (`#1838`_, `0ae4c17`_)

* **plugins**: Move aws authentication methods to AwsAuth plugin (`#1769`_, `1c072f8`_)

* **plugins**: Rename PostJsonSearchWithStacQueryables to WekeoSearch (`#1842`_, `4bfbd6d`_)

* **product-types**: S1C and S2C as available platformSerialIdentifier (`#1850`_, `7c532f4`_)

* **providers**: Use s3 alternate assets in usgs_satapi_aws (`#1851`_, `27b1ab2`_)

Testing
-------

* Add more tests to improve coverage (`#1791`_, `f7519f8`_)

.. _#1769: https://github.com/CS-SI/eodag/pull/1769
.. _#1770: https://github.com/CS-SI/eodag/pull/1770
.. _#1791: https://github.com/CS-SI/eodag/pull/1791
.. _#1805: https://github.com/CS-SI/eodag/pull/1805
.. _#1815: https://github.com/CS-SI/eodag/pull/1815
.. _#1817: https://github.com/CS-SI/eodag/pull/1817
.. _#1821: https://github.com/CS-SI/eodag/pull/1821
.. _#1823: https://github.com/CS-SI/eodag/pull/1823
.. _#1826: https://github.com/CS-SI/eodag/pull/1826
.. _#1827: https://github.com/CS-SI/eodag/pull/1827
.. _#1828: https://github.com/CS-SI/eodag/pull/1828
.. _#1830: https://github.com/CS-SI/eodag/pull/1830
.. _#1831: https://github.com/CS-SI/eodag/pull/1831
.. _#1832: https://github.com/CS-SI/eodag/pull/1832
.. _#1836: https://github.com/CS-SI/eodag/pull/1836
.. _#1837: https://github.com/CS-SI/eodag/pull/1837
.. _#1838: https://github.com/CS-SI/eodag/pull/1838
.. _#1841: https://github.com/CS-SI/eodag/pull/1841
.. _#1842: https://github.com/CS-SI/eodag/pull/1842
.. _#1844: https://github.com/CS-SI/eodag/pull/1844
.. _#1846: https://github.com/CS-SI/eodag/pull/1846
.. _#1848: https://github.com/CS-SI/eodag/pull/1848
.. _#1850: https://github.com/CS-SI/eodag/pull/1850
.. _#1851: https://github.com/CS-SI/eodag/pull/1851
.. _01b130a: https://github.com/CS-SI/eodag/commit/01b130a02a9c16fc3c76ee180bf56d1356380f82
.. _04b0b55: https://github.com/CS-SI/eodag/commit/04b0b5536b370a92843886ebf5135fac37172c18
.. _083989e: https://github.com/CS-SI/eodag/commit/083989e0d1be8878fa1da2c984c6025bc4a564f0
.. _0ae4c17: https://github.com/CS-SI/eodag/commit/0ae4c170fee95cfb2263c4f1b90a3219d502e819
.. _182cdc0: https://github.com/CS-SI/eodag/commit/182cdc0eb82e7e4ca9e073b12edf6c3e51952d39
.. _1bdf8a9: https://github.com/CS-SI/eodag/commit/1bdf8a9544717533f6ea85c7fc86f27b226a8f0f
.. _1c072f8: https://github.com/CS-SI/eodag/commit/1c072f8f857f24e08642c1cb6ddaff51fe26e52d
.. _27b1ab2: https://github.com/CS-SI/eodag/commit/27b1ab2174e9855323db26975ab347699f5d60cd
.. _308e0a9: https://github.com/CS-SI/eodag/commit/308e0a9884d4b2e3435922c89a23cc0aab1edab9
.. _3662954: https://github.com/CS-SI/eodag/commit/3662954cf31dd91dc79d740686e6557c9cbf7954
.. _3b04096: https://github.com/CS-SI/eodag/commit/3b04096ac6255f89c8eb8bb363a2b38ece1b02af
.. _4bfbd6d: https://github.com/CS-SI/eodag/commit/4bfbd6dfc11a08744935f8fdd4e3d9c321252d26
.. _55b1ffe: https://github.com/CS-SI/eodag/commit/55b1ffeae8b2ef03e5ecac35838675f9328cde90
.. _57fecd0: https://github.com/CS-SI/eodag/commit/57fecd07d32830ad12be3fb8074d5124c5797dc5
.. _786c663: https://github.com/CS-SI/eodag/commit/786c663414f42297e7ceeace2646446872160941
.. _7c532f4: https://github.com/CS-SI/eodag/commit/7c532f47fb3b17b4a39d379301134ac75f55253d
.. _b428d61: https://github.com/CS-SI/eodag/commit/b428d61405e2a24a59756016bade3788841c89dd
.. _b85ef0f: https://github.com/CS-SI/eodag/commit/b85ef0f360e805a61c2a7e9826a3cd7df4183315
.. _bf8cbe1: https://github.com/CS-SI/eodag/commit/bf8cbe1bd1ade032a1a7abdc17f3785a11fca5d9
.. _c75351d: https://github.com/CS-SI/eodag/commit/c75351d9b74ffa1cab3746a04637eb0de1a9f642
.. _d2cd928: https://github.com/CS-SI/eodag/commit/d2cd928e9e887e88db639e3ebb02d4e006c0f653
.. _df67693: https://github.com/CS-SI/eodag/commit/df67693099f72cbaf42e008f8b5b9c5af062e573
.. _f7519f8: https://github.com/CS-SI/eodag/commit/f7519f847af0253046d1329dead9d5a12b527923
.. _f890fbf: https://github.com/CS-SI/eodag/commit/f890fbfe85c514e5f6794ff7db875bfbf5798b98


v3.8.1 (2025-09-02)
===================

Bug Fixes
---------

* **core**: Guess_product_type using alias (`#1800`_, `99e6ab8`_)

* **plugins**: Filter using matching_url in SASAuth (`#1802`_, `c4e649c`_)

* **providers**: Instrument format for STAC providers (`#1803`_, `e1a56fd`_)

* **providers**: Ssl verify for fedeo_ceda (`#1801`_, `45b891a`_)

.. _#1800: https://github.com/CS-SI/eodag/pull/1800
.. _#1801: https://github.com/CS-SI/eodag/pull/1801
.. _#1802: https://github.com/CS-SI/eodag/pull/1802
.. _#1803: https://github.com/CS-SI/eodag/pull/1803
.. _45b891a: https://github.com/CS-SI/eodag/commit/45b891a6a527e0143eb23cfa1a9576cd74a56758
.. _99e6ab8: https://github.com/CS-SI/eodag/commit/99e6ab8fda3847bd8478bc8cc40688923ed13b49
.. _c4e649c: https://github.com/CS-SI/eodag/commit/c4e649cdadda539be517797d2668638c19b486c8
.. _e1a56fd: https://github.com/CS-SI/eodag/commit/e1a56fd0670d0aa4ee27cd5cc8a67b5fbea20be9


v3.8.0 (2025-08-27)
===================

Features
--------

* **providers**: New provider fedeo_ceda (`#1778`_, `4d9f091`_)

Bug Fixes
---------

* **providers**: Product types discovered properties format (`#1783`_, `7824f6a`_)

* **providers**: Remove deprecated product type (S2_MSI_L2AP) (`#1764`_, `7b1fb89`_)

* **providers**: Restore ssl verify for geodes (`#1780`_, `8b771f8`_)

* **server**: Remove duplicate host (`#1794`_, `fa22145`_)

Chores
------

* Deprecate unused code (`#1788`_, `2658e69`_)

Documentation
-------------

* Aws_eos logo added (`#1773`_, `af6d959`_)

Refactoring
-----------

* **core**: Whoosh removal (`#1741`_, `31f3c8a`_)

.. _#1741: https://github.com/CS-SI/eodag/pull/1741
.. _#1764: https://github.com/CS-SI/eodag/pull/1764
.. _#1773: https://github.com/CS-SI/eodag/pull/1773
.. _#1778: https://github.com/CS-SI/eodag/pull/1778
.. _#1780: https://github.com/CS-SI/eodag/pull/1780
.. _#1783: https://github.com/CS-SI/eodag/pull/1783
.. _#1788: https://github.com/CS-SI/eodag/pull/1788
.. _#1794: https://github.com/CS-SI/eodag/pull/1794
.. _2658e69: https://github.com/CS-SI/eodag/commit/2658e6983f64581f2364647993c4c0e6bc7bc841
.. _31f3c8a: https://github.com/CS-SI/eodag/commit/31f3c8a50b251cc2ad2d567fb6f1eb62937b5d43
.. _4d9f091: https://github.com/CS-SI/eodag/commit/4d9f09110c0fcc745d910b9c02e155aa1952b048
.. _7824f6a: https://github.com/CS-SI/eodag/commit/7824f6a1a3d3aa881532c5904f58acb73ebdca5f
.. _7b1fb89: https://github.com/CS-SI/eodag/commit/7b1fb89208537a360471a218d13b2f9865f282c4
.. _8b771f8: https://github.com/CS-SI/eodag/commit/8b771f801ef19e81297fc9fe273921702797dffc
.. _af6d959: https://github.com/CS-SI/eodag/commit/af6d959fec6fa009677ac429c70bb3004b066671
.. _fa22145: https://github.com/CS-SI/eodag/commit/fa22145056b62c8d399f254a3945e0c718834851


v3.7.0 (2025-07-31)
===================

Features
--------

* **plugins**: New search config for assets mapping (`#1711`_, `1281268`_)

* **providers**: Add 2 new MSG collections to provider ``eumetsat_ds`` (`#1742`_, `801c52c`_)

* **providers**: dedt_lumi search by geometry (`#1710`_, `efccdd0`_)

Bug Fixes
---------

* **core**: Logging issue on entrypoint loading error (`#1728`_, `6f8e6ad`_)

* **plugins**: metadata_mapping_from_product in search config (`#1737`_, `cdfe518`_)

* **providers**: Allow search by id for CLMS_CORINE with wekeo_main (`#1746`_, `bfe5e71`_)

* **providers**: Remove no-more-available theia provider (`#1736`_, `e81013b`_)

* **providers**: Update default version for CAMS_GLOBAL_EMISSIONS (`#1738`_, `81e4b90`_)

* **server**: Empty instruments mapping (`#1763`_, `11f2318`_)

* **utils**: Avoid repeated SSL context creation (`#1758`_, `f93645e`_)

Documentation
-------------

* Updated description, overview and ecosystem (`#1734`_, `ea929e4`_)

Performance Improvements
------------------------

* **plugins**: Optimize AwsDownload streaming (`#1740`_, `48f0e4c`_)

Refactoring
-----------

* Directly import urllib.parse methods (`#1761`_, `e4aca26`_)

.. _#1710: https://github.com/CS-SI/eodag/pull/1710
.. _#1711: https://github.com/CS-SI/eodag/pull/1711
.. _#1728: https://github.com/CS-SI/eodag/pull/1728
.. _#1734: https://github.com/CS-SI/eodag/pull/1734
.. _#1736: https://github.com/CS-SI/eodag/pull/1736
.. _#1737: https://github.com/CS-SI/eodag/pull/1737
.. _#1738: https://github.com/CS-SI/eodag/pull/1738
.. _#1740: https://github.com/CS-SI/eodag/pull/1740
.. _#1742: https://github.com/CS-SI/eodag/pull/1742
.. _#1746: https://github.com/CS-SI/eodag/pull/1746
.. _#1758: https://github.com/CS-SI/eodag/pull/1758
.. _#1761: https://github.com/CS-SI/eodag/pull/1761
.. _#1763: https://github.com/CS-SI/eodag/pull/1763
.. _11f2318: https://github.com/CS-SI/eodag/commit/11f2318a150982504226378110b853ca4aa644ce
.. _1281268: https://github.com/CS-SI/eodag/commit/1281268507c3a7338be9954b403a20d5156bc527
.. _48f0e4c: https://github.com/CS-SI/eodag/commit/48f0e4c8c82e80841b7b64bec60a251661a13d12
.. _6f8e6ad: https://github.com/CS-SI/eodag/commit/6f8e6ad683f786286cfb36e8e22c17cfb2daf125
.. _801c52c: https://github.com/CS-SI/eodag/commit/801c52c38124e6dfff1a5fdedeb0cbd269fc2478
.. _81e4b90: https://github.com/CS-SI/eodag/commit/81e4b903c5474894e87e6dcb9366fdfbb152398b
.. _bfe5e71: https://github.com/CS-SI/eodag/commit/bfe5e712087804d31fe7f057e5efbd1d2863fb36
.. _cdfe518: https://github.com/CS-SI/eodag/commit/cdfe518f2b392b700994f93d2c2d6cafdb46b81d
.. _e4aca26: https://github.com/CS-SI/eodag/commit/e4aca2672b156a6eb338e9e9a8277bc2895aa457
.. _e81013b: https://github.com/CS-SI/eodag/commit/e81013b262342a0621e2018a7d917145faaa2cc7
.. _ea929e4: https://github.com/CS-SI/eodag/commit/ea929e4339e976752bc61d1d305ad36ff1b78172
.. _efccdd0: https://github.com/CS-SI/eodag/commit/efccdd00fbd0880344fe294dba0f4790468fd9bc
.. _f93645e: https://github.com/CS-SI/eodag/commit/f93645ed4f09194d6c7f12a3c65b2ab3a8f9ad5a


v3.6.0 (2025-07-01)
===================

Features
--------

* **cli**: Commands chaining (`#1714`_, `754772b`_)

* **cli**: Download output directory (`#1716`_, `036b86b`_)

* **cli**: Download STAC items from their urls (`#1705`_, `5d598a9`_)

* **core**: Import stac items as SearchResult (`#1703`_, `1d49715`_)

* **providers**: Add new eurostat product types to dedl (`#1662`_, `b7192b1`_)

Bug Fixes
---------

* **core**: Do not download again unextracted products (`#1717`_, `29642e8`_)

* **queryables**: Improve date parameter parsing (`#1702`_, `9563d4b`_)

Documentation
-------------

* Cli and stac support update (`#1707`_, `c50aae1`_)

* Import_stac_items documentation update (`#1709`_, `7a04158`_)

.. _#1662: https://github.com/CS-SI/eodag/pull/1662
.. _#1702: https://github.com/CS-SI/eodag/pull/1702
.. _#1703: https://github.com/CS-SI/eodag/pull/1703
.. _#1705: https://github.com/CS-SI/eodag/pull/1705
.. _#1706: https://github.com/CS-SI/eodag/pull/1706
.. _#1707: https://github.com/CS-SI/eodag/pull/1707
.. _#1709: https://github.com/CS-SI/eodag/pull/1709
.. _#1714: https://github.com/CS-SI/eodag/pull/1714
.. _#1716: https://github.com/CS-SI/eodag/pull/1716
.. _#1717: https://github.com/CS-SI/eodag/pull/1717
.. _036b86b: https://github.com/CS-SI/eodag/commit/036b86bbefeed905c9962a7a4bf7bca8258246fb
.. _1d49715: https://github.com/CS-SI/eodag/commit/1d4971560e9b789dfe96ca09b2fcd5d88cb4e30a
.. _29642e8: https://github.com/CS-SI/eodag/commit/29642e87614b44ec3b544732ef6496ae8bf73087
.. _5d598a9: https://github.com/CS-SI/eodag/commit/5d598a9934d36390e7b6f1ef2d746f9a9030198d
.. _754772b: https://github.com/CS-SI/eodag/commit/754772b9e71700fb752cb632dfb66ef13cd2c743
.. _7a04158: https://github.com/CS-SI/eodag/commit/7a041583695f71811baf56e5616415df60750814
.. _9563d4b: https://github.com/CS-SI/eodag/commit/9563d4bccaea5a87805fff77863d14cb4b422fb7
.. _b7192b1: https://github.com/CS-SI/eodag/commit/b7192b14840d27a3558f4dc5dff0b99ea6c0d833
.. _c50aae1: https://github.com/CS-SI/eodag/commit/c50aae12b344d81f66fc20a9a930b7718e0b12b7
.. _e1db471: https://github.com/CS-SI/eodag/commit/e1db47199d47c4988eaece7628005727dba2985f


v3.5.1 (2025-06-23)
===================

Bug Fixes
---------

* **core**: Enable count with search iterator (`#1700`_, `bbcc7ba`_)

* **plugins**: Lru caching when fetching constraints with ECMWF (`#1698`_, `e23f47e`_)

Refactoring
-----------

* **core**: Register downloader using manager from search to EOProduct (`#1699`_, `fd0c149`_)

.. _#1698: https://github.com/CS-SI/eodag/pull/1698
.. _#1699: https://github.com/CS-SI/eodag/pull/1699
.. _#1700: https://github.com/CS-SI/eodag/pull/1700
.. _bbcc7ba: https://github.com/CS-SI/eodag/commit/bbcc7ba311fcf25a0231203035166276e704ec8e
.. _e23f47e: https://github.com/CS-SI/eodag/commit/e23f47ee97a50c0ba1d573801a17177c88f06eae
.. _fd0c149: https://github.com/CS-SI/eodag/commit/fd0c149277735a3ecdc11588e8ac8e166b591ae8


v3.5.0 (2025-06-20)
===================

Features
--------

* **core**: Add env variable to whitelist providers (`#1672`_, `b93c4c8`_)

* **core**: Add strict product types mode (`#1677`_, `5077fa5`_)

* **plugins**: Auth token expiration margin (`#1665`_, `ef5fc18`_)

* **server**: Added bbox filter support for collections search (`#1671`_, `5717f0d`_)

Bug Fixes
---------

* **core**: Always validate PluginConfig before loading (`#1690`_, `59ac437`_)

* **core**: Skip provider empty conf on init (`#1687`_, `0a4104e`_)

* **plugins**: Raise errors when metadata discovery is not allowed (`#1534`_, `855ffa3`_)

Build System
------------

* Update usgs to 0.3.6 (`#1688`_, `e63cfb1`_)

Continuous Integration
----------------------

* Use personal access token for deploy github action (`#1693`_, `ff777d7`_)

Documentation
-------------

* Dead-links and out-of-date param fix (`#1692`_, `445a20e`_)

.. _#1534: https://github.com/CS-SI/eodag/pull/1534
.. _#1665: https://github.com/CS-SI/eodag/pull/1665
.. _#1671: https://github.com/CS-SI/eodag/pull/1671
.. _#1672: https://github.com/CS-SI/eodag/pull/1672
.. _#1677: https://github.com/CS-SI/eodag/pull/1677
.. _#1687: https://github.com/CS-SI/eodag/pull/1687
.. _#1688: https://github.com/CS-SI/eodag/pull/1688
.. _#1690: https://github.com/CS-SI/eodag/pull/1690
.. _#1692: https://github.com/CS-SI/eodag/pull/1692
.. _#1693: https://github.com/CS-SI/eodag/pull/1693
.. _0a4104e: https://github.com/CS-SI/eodag/commit/0a4104e0518abc70e2133ca98472eea87d673a1c
.. _445a20e: https://github.com/CS-SI/eodag/commit/445a20e060730642e703615c73225c0df3cc84d0
.. _5077fa5: https://github.com/CS-SI/eodag/commit/5077fa591496811fb100c1e6b6a3e452cbdbe2a5
.. _5717f0d: https://github.com/CS-SI/eodag/commit/5717f0deddbf022f2c6d5207ade77de6afb0f9d5
.. _59ac437: https://github.com/CS-SI/eodag/commit/59ac437de01a8996d247b1f8239f332ed5dc5456
.. _855ffa3: https://github.com/CS-SI/eodag/commit/855ffa39fa9b914eb39cc20d6e5c2cbbc1b2097a
.. _b93c4c8: https://github.com/CS-SI/eodag/commit/b93c4c88f323af0eecb0950c90c6862ca9a7c3f4
.. _e63cfb1: https://github.com/CS-SI/eodag/commit/e63cfb19ca64a2ed65f500ae9678e117a2ea4cf8
.. _ef5fc18: https://github.com/CS-SI/eodag/commit/ef5fc188e515759c9227584b25805db75f537833
.. _ff777d7: https://github.com/CS-SI/eodag/commit/ff777d7a1e33f612c5227dba4fecfcec55ff18fc


v3.4.3 (2025-06-12)
===================

Bug Fixes
---------

* **core**: Queryables mismatch when list of possible values contains a single value (`#1666`_,
  `538331d`_)

* **plugins**: GenericAuth missing credentials handle (`#1678`_, `576a2ac`_)

* **plugins**: Openid_connect requests error handling (#1320) (`#1663`_, `9926083`_)

* **plugins**: Order retry (`#1676`_, `3602426`_)

* **providers**: Dedl mapping for CORINE collection (`#1661`_, `4c61b54`_)

* **providers**: Wekeo_main orderable products download (`#1670`_, `d573846`_)

Chores
------

* **deploy**: Remove deprecated common values (`154ea6d`_)

Documentation
-------------

* Configuration environment variables defaults (`#1681`_, `6e8eb6b`_)

* Updated contribution guidelines link in PR template (`#1667`_, `e5cd082`_)

Refactoring
-----------

* Typing fixes following mypy 1.16.0 (`#1673`_, `ece52c0`_)

.. _#1661: https://github.com/CS-SI/eodag/pull/1661
.. _#1663: https://github.com/CS-SI/eodag/pull/1663
.. _#1666: https://github.com/CS-SI/eodag/pull/1666
.. _#1667: https://github.com/CS-SI/eodag/pull/1667
.. _#1670: https://github.com/CS-SI/eodag/pull/1670
.. _#1673: https://github.com/CS-SI/eodag/pull/1673
.. _#1676: https://github.com/CS-SI/eodag/pull/1676
.. _#1678: https://github.com/CS-SI/eodag/pull/1678
.. _#1681: https://github.com/CS-SI/eodag/pull/1681
.. _154ea6d: https://github.com/CS-SI/eodag/commit/154ea6d035572e64c3a434bb41c095c9b4cc76b2
.. _3602426: https://github.com/CS-SI/eodag/commit/360242653ddc2a5c8587b37b3d91800459f4c243
.. _4c61b54: https://github.com/CS-SI/eodag/commit/4c61b540ee46a8ae70932d64e9d373653763eb16
.. _538331d: https://github.com/CS-SI/eodag/commit/538331d30085a814307173913ff831ca5a3397af
.. _576a2ac: https://github.com/CS-SI/eodag/commit/576a2ac95044d10367e91e5ef843fb33a921f5f5
.. _6e8eb6b: https://github.com/CS-SI/eodag/commit/6e8eb6b94eaad6294fea45d764a0e7c18a4e6823
.. _9926083: https://github.com/CS-SI/eodag/commit/99260837837c3b5f2eeac8b95dc2b2feae7a0390
.. _d573846: https://github.com/CS-SI/eodag/commit/d5738465930e08b24d562af3b7bc040464ff970a
.. _e5cd082: https://github.com/CS-SI/eodag/commit/e5cd082aa81eedb62cd48b7974362c99a6899d9c
.. _ece52c0: https://github.com/CS-SI/eodag/commit/ece52c07685e5df21cfda0b6ddc6a7416194406c


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

Features
--------

* **plugins**: Add queryables to cop_marine (`#1638`_, `bcc793e`_)

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


Features
--------

* **plugins**: :class:`~eodag.plugins.search.build_search_result.ECMWFSearch` search-by-id (`#1580`_, `f296c52`_)

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
* [v3.1.0b1] Updated `queryables <https://eodag.readthedocs.io/en/latest/notebooks/api_user_guide/4_queryables.html>`_
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
  <https://eodag.readthedocs.io/en/latest/notebooks/api_user_guide/8_post_process.html#Data-access-with-eodag-cube>`_
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

* Updated `queryables <https://eodag.readthedocs.io/en/latest/notebooks/api_user_guide/4_queryables.html>`_ mechanism
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
* **[docs]** `Queryables <https://eodag.readthedocs.io/en/latest/notebooks/api_user_guide/4_queryables.html>`_
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

* [v3.0.0b1] `search() <https://eodag.readthedocs.io/en/latest/notebooks/api_user_guide/3_search.html#search()>`_ method
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

* `search() <https://eodag.readthedocs.io/en/latest/notebooks/api_user_guide/3_search.html#search()>`_ method now
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
* `Search by id <https://eodag.readthedocs.io/en/stable/notebooks/api_user_guide/3_search.html#id-and-provider>`_ now
  uses :meth:`~eodag.api.core.EODataAccessGateway.search_all` and
  `crunch <https://eodag.readthedocs.io/en/stable/notebooks/api_user_guide/6_crunch.html#Filter-by-property>`_
  (:pull:`1099`).
* Free text search available for all fields when `guessing a product type
  <https://eodag.readthedocs.io/en/stable/notebooks/api_user_guide/6_crunch.html#Filter-by-property>`_ (:pull:`1070`),
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
* New `list_queryables <https://eodag.readthedocs.io/en/latest/notebooks/api_user_guide/3_search.html#Queryables>`_
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
  <https://eodag.readthedocs.io/en/latest/notebooks/api_user_guide/3_search.html#Guess-a-collection>`_ (:pull:`756`)
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
  <https://eodag.readthedocs.io/en/latest/getting_started_guide/collections.html#product-types-information-csv>`_
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
  <https://eodag.rtfd.io/en/latest/notebooks/api_user_guide/1_providers_products_available.html#Collections-discovery>`_
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
