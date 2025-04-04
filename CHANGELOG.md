# CHANGELOG


## v3.2.1 (2025-04-04)

### Bug Fixes

- **core**: Ensure datetime format compliance with STAC specification
  ([#1573](https://github.com/CS-SI/eodag/pull/1573),
  [`7e10e3a`](https://github.com/CS-SI/eodag/commit/7e10e3aeb27220fd023f1cb00198ed2304ea3486))

- **plugins**: Add datetime for ecmwf search ([#1572](https://github.com/CS-SI/eodag/pull/1572),
  [`b785e7c`](https://github.com/CS-SI/eodag/commit/b785e7c15c8dc60efbe0f38ac4d6487d8917b1aa))

- **providers**: Rename EO:CLMS:DAT:CORINE to EO:EEA:DAT:CORINE
  ([#1576](https://github.com/CS-SI/eodag/pull/1576),
  [`2d3f6da`](https://github.com/CS-SI/eodag/commit/2d3f6dac273cb70f55dfa9eb3c898266a4c93552))

### Testing

- Fixed test for ecmwf dates ([#1588](https://github.com/CS-SI/eodag/pull/1588),
  [`b6ca196`](https://github.com/CS-SI/eodag/commit/b6ca1968d60d6123e818f1eec06fc1fa386e465a))


## v3.2.0 (2025-04-01)

### Bug Fixes

- Update external product types reference ([#1567](https://github.com/CS-SI/eodag/pull/1567),
  [`cacdee3`](https://github.com/CS-SI/eodag/commit/cacdee35f9cb42166168a2e5af91997bac072d07))

- **core**: Download asset with special chars ([#1585](https://github.com/CS-SI/eodag/pull/1585),
  [`f8f92d5`](https://github.com/CS-SI/eodag/commit/f8f92d568f990c74f3f299ca172ca417af0856bb))

- **plugins**: Awsdownload with asset and ignore_assets
  ([#1571](https://github.com/CS-SI/eodag/pull/1571),
  [`44ca6ff`](https://github.com/CS-SI/eodag/commit/44ca6ff43264827e50356414fb130f2fec8d8e57))

- **providers**: Default values for some ECMWF collections
  ([#1575](https://github.com/CS-SI/eodag/pull/1575),
  [`dc22c2e`](https://github.com/CS-SI/eodag/commit/dc22c2e449b648b628d1dbbde3fc290be4f0b4a2))

- **providers**: Geodes API update ([#1581](https://github.com/CS-SI/eodag/pull/1581),
  [`dfb7a0f`](https://github.com/CS-SI/eodag/commit/dfb7a0fb36d3e8225757248616f4399835c837df))

- **providers**: Sanitize eumetsat_ds titles ([#1582](https://github.com/CS-SI/eodag/pull/1582),
  [`28c0bd0`](https://github.com/CS-SI/eodag/commit/28c0bd0b3fc8cdf96ff5c199773f00658c2c8bfb))

### Build System

- Bump version ([#1586](https://github.com/CS-SI/eodag/pull/1586),
  [`9fea9ae`](https://github.com/CS-SI/eodag/commit/9fea9aece99f7d5ffa06ca21d68942ebf02202e4))

### Continuous Integration

- Action-semantic-pull-request ([#1570](https://github.com/CS-SI/eodag/pull/1570),
  [`80cf170`](https://github.com/CS-SI/eodag/commit/80cf1708389849b26abc45d932276a59c6faacf4))

### Features

- **plugins**: Do not guess keys from href when inappropriate
  ([#1584](https://github.com/CS-SI/eodag/pull/1584),
  [`beb6c1f`](https://github.com/CS-SI/eodag/commit/beb6c1f7095b7f1401e3c7964b0d8e5964cf9cc4))


## v3.1.0 (2025-03-19)

### Bug Fixes

- Convert_to_bounds for multipolygons ([#1503](https://github.com/CS-SI/eodag/pull/1503),
  [`1aa6a98`](https://github.com/CS-SI/eodag/commit/1aa6a98648c12e27bfb1bea936c03e855a7db0b2))

- Remove inappropriate archive ([#1448](https://github.com/CS-SI/eodag/pull/1448),
  [`d4fffce`](https://github.com/CS-SI/eodag/commit/d4fffce9823ec078c557a222aaf9407ba7406bad))

- Update external product types reference ([#1387](https://github.com/CS-SI/eodag/pull/1387),
  [`2473ac1`](https://github.com/CS-SI/eodag/commit/2473ac169a3d05f04f83d4f227c2fb63689ae2d6))

- Update external product types reference ([#1391](https://github.com/CS-SI/eodag/pull/1391),
  [`175e167`](https://github.com/CS-SI/eodag/commit/175e167d429556d9a5914312d6ae54336bb8a2ae))

- Update external product types reference ([#1401](https://github.com/CS-SI/eodag/pull/1401),
  [`7ee6c7f`](https://github.com/CS-SI/eodag/commit/7ee6c7f853e6789fa6addeccbef9016d96c4799a))

- Update external product types reference ([#1404](https://github.com/CS-SI/eodag/pull/1404),
  [`eeb8d3b`](https://github.com/CS-SI/eodag/commit/eeb8d3b01c42fbd4d97aef28d3410e257378281a))

- Update external product types reference ([#1406](https://github.com/CS-SI/eodag/pull/1406),
  [`ae88aa9`](https://github.com/CS-SI/eodag/commit/ae88aa951a5cd4840d8a735a20181c3bf64ffdde))

- Update external product types reference ([#1408](https://github.com/CS-SI/eodag/pull/1408),
  [`70e156b`](https://github.com/CS-SI/eodag/commit/70e156b8959adf170833b01e06a91ab9d6e29c6c))

- Update external product types reference ([#1416](https://github.com/CS-SI/eodag/pull/1416),
  [`77cd724`](https://github.com/CS-SI/eodag/commit/77cd7240aecb8829e8867302392ee5faebd3372d))

- Update external product types reference ([#1424](https://github.com/CS-SI/eodag/pull/1424),
  [`2fc3f27`](https://github.com/CS-SI/eodag/commit/2fc3f278ee6f4843f8aea66122f96bd8ccd97fba))

- Update external product types reference ([#1453](https://github.com/CS-SI/eodag/pull/1453),
  [`7924f7f`](https://github.com/CS-SI/eodag/commit/7924f7f9bef81a15aff3de6c78c2b93fe96228a7))

- Update external product types reference ([#1459](https://github.com/CS-SI/eodag/pull/1459),
  [`6564ce6`](https://github.com/CS-SI/eodag/commit/6564ce68dd39f24a6b2db62b6b50cd24cb72552c))

- Update external product types reference ([#1460](https://github.com/CS-SI/eodag/pull/1460),
  [`4233b05`](https://github.com/CS-SI/eodag/commit/4233b05b1f9ed5de5c4d0bb8d9ea4610f711c3b9))

- Update external product types reference ([#1478](https://github.com/CS-SI/eodag/pull/1478),
  [`689471c`](https://github.com/CS-SI/eodag/commit/689471c44a19be2bc495cde09c45038e36d06fe2))

- Update external product types reference ([#1484](https://github.com/CS-SI/eodag/pull/1484),
  [`045a849`](https://github.com/CS-SI/eodag/commit/045a8492cb8f24aaa39eb9c68def97833e2efd35))

- Update external product types reference ([#1487](https://github.com/CS-SI/eodag/pull/1487),
  [`7341337`](https://github.com/CS-SI/eodag/commit/7341337b76ef9023d370dd191c7ee2a638552c88))

- Update external product types reference ([#1493](https://github.com/CS-SI/eodag/pull/1493),
  [`b7ae557`](https://github.com/CS-SI/eodag/commit/b7ae55777753554516c0bf42422db3274bbd5eb1))

- Update external product types reference ([#1494](https://github.com/CS-SI/eodag/pull/1494),
  [`0ff477d`](https://github.com/CS-SI/eodag/commit/0ff477d7a685896fa9d5dc2280fe925b1c269cf5))

- Update external product types reference ([#1510](https://github.com/CS-SI/eodag/pull/1510),
  [`c5805cf`](https://github.com/CS-SI/eodag/commit/c5805cffe3798db35c78bb2e6b4478d057fca11c))

- Update external product types reference ([#1525](https://github.com/CS-SI/eodag/pull/1525),
  [`b7cc06e`](https://github.com/CS-SI/eodag/commit/b7cc06e19025e5bbf14e28a0975f1749e21e9be3))

- Update external product types reference ([#1539](https://github.com/CS-SI/eodag/pull/1539),
  [`2a8e683`](https://github.com/CS-SI/eodag/commit/2a8e683aedde62a610a499f04fed101bdae230e0))

- Update external product types reference ([#1548](https://github.com/CS-SI/eodag/pull/1548),
  [`0715f05`](https://github.com/CS-SI/eodag/commit/0715f05176a56cd754170c4471970830b5b31472))

- Update external product types reference ([#1553](https://github.com/CS-SI/eodag/pull/1553),
  [`4d6f726`](https://github.com/CS-SI/eodag/commit/4d6f726aa9a9e0d492eccdf7d88f498404c2c021))

- Update external product types reference ([#1557](https://github.com/CS-SI/eodag/pull/1557),
  [`67f653d`](https://github.com/CS-SI/eodag/commit/67f653deb272109dae563f5cc513ca696561bf2c))

- Update external product types reference ([#1565](https://github.com/CS-SI/eodag/pull/1565),
  [`0293c5f`](https://github.com/CS-SI/eodag/commit/0293c5f1ccdf93786db37f6b9932fe7d74db6cbf))

- **build**: Do not cache apt update in server dockerfile
  ([#1430](https://github.com/CS-SI/eodag/pull/1430),
  [`b871978`](https://github.com/CS-SI/eodag/commit/b871978c5374fe3d1d3372cf4a0dbbaf4be6d099))

- **cli**: Handle import error of eodag.rest module
  ([#1415](https://github.com/CS-SI/eodag/pull/1415),
  [`d1e649e`](https://github.com/CS-SI/eodag/commit/d1e649e084f784600c2fceb09a684576206615c5))

- **cop_marine**: Search_by_id for products without date in id
  ([#1471](https://github.com/CS-SI/eodag/pull/1471),
  [`c08c053`](https://github.com/CS-SI/eodag/commit/c08c0537a5ed873439db25f6fb50b52d9b4c552c))

- **core**: Do not retry skipped products during download_all
  ([#1465](https://github.com/CS-SI/eodag/pull/1465),
  [`938c23e`](https://github.com/CS-SI/eodag/commit/938c23ee366ea4363873ab9be107744a24a6bd25))

- **core**: Handle exceptions occuring on failed index write
  ([#1428](https://github.com/CS-SI/eodag/pull/1428),
  [`076a0f8`](https://github.com/CS-SI/eodag/commit/076a0f8efe1a1406817bdaa1ffcb446cfded9d56))

- **core**: Metadata mapping for date parameter ([#1480](https://github.com/CS-SI/eodag/pull/1480),
  [`8e47f11`](https://github.com/CS-SI/eodag/commit/8e47f11656a7d5e7e3dcc5e94f05ac31b457a71d))

- **core**: Polling times and typing update ([#1440](https://github.com/CS-SI/eodag/pull/1440),
  [`3c2fcc7`](https://github.com/CS-SI/eodag/commit/3c2fcc704ba577725af86335fe0bbf5b15ac9739))

- **core**: Rename old record file ([#1396](https://github.com/CS-SI/eodag/pull/1396),
  [`a5e1620`](https://github.com/CS-SI/eodag/commit/a5e16201b59b6234bdce58353dd8b85ca00f6c65))

- **core**: Ssl_verify setting for get_quicklook ([#1490](https://github.com/CS-SI/eodag/pull/1490),
  [`b247f5c`](https://github.com/CS-SI/eodag/commit/b247f5c9f1a0573cce408c48ff07b9fd50916671))

- **crunch**: Skip missing key in filter_property
  ([#1466](https://github.com/CS-SI/eodag/pull/1466),
  [`17c23a4`](https://github.com/CS-SI/eodag/commit/17c23a44f72429c0ec931db16eeaf10cc916bf3d))

- **EcmwfSearch**: Map geometry metadata ([#1555](https://github.com/CS-SI/eodag/pull/1555),
  [`ddde27a`](https://github.com/CS-SI/eodag/commit/ddde27a3313855d7e1afa391b6aef4b84a846bb6))

- **geodes**: Added relativeOrbitNumber property ([#1499](https://github.com/CS-SI/eodag/pull/1499),
  [`4d03a1a`](https://github.com/CS-SI/eodag/commit/4d03a1a1be55d04c9ef9e769e64348ba1726a574))

- **geodes**: Unquote searched numerical values ([#1507](https://github.com/CS-SI/eodag/pull/1507),
  [`d50b378`](https://github.com/CS-SI/eodag/commit/d50b378f8de6ad328cdfae694ba76a9dfbdb3d09))

- **oidc**: Do not fail when trying to authenticate an already authenticated user
  ([#1524](https://github.com/CS-SI/eodag/pull/1524),
  [`baeafb4`](https://github.com/CS-SI/eodag/commit/baeafb4d331f782dcbfd8e16cd6ec7242f6e687f))

- **openid_connect**: Compare only offset-aware datetimes
  ([#1418](https://github.com/CS-SI/eodag/pull/1418),
  [`f3556af`](https://github.com/CS-SI/eodag/commit/f3556af4a41b40a850cd938e0f9f4a635f6f8b16))

- **plugins**: Aws rio_env s3_endpoint ([#1504](https://github.com/CS-SI/eodag/pull/1504),
  [`e2846dd`](https://github.com/CS-SI/eodag/commit/e2846ddd130ffd5ddb8bd1b0b5a45bc71d92c2cb))

- **plugins**: Creodias_s3 search and download when no asset
  ([#1425](https://github.com/CS-SI/eodag/pull/1425),
  [`aa3bb3c`](https://github.com/CS-SI/eodag/commit/aa3bb3c47a6517fc056fe1c09de26de7b62973b7))

- **plugins**: Distinct headers for token retrieve and authentication
  ([#1451](https://github.com/CS-SI/eodag/pull/1451),
  [`0f20c0a`](https://github.com/CS-SI/eodag/commit/0f20c0a7b85b165c31eeb4ab558ddfff8b479f94))

- **plugins**: Ecmwfsearch strip_quotes implementation for dicts
  ([#1483](https://github.com/CS-SI/eodag/pull/1483),
  [`2dbab73`](https://github.com/CS-SI/eodag/commit/2dbab735019e3b56278caa2abc84baacd3523e71))

- **plugins**: Filenotfounderror on usgs auth attempt failure
  ([#1550](https://github.com/CS-SI/eodag/pull/1550),
  [`2efa9e9`](https://github.com/CS-SI/eodag/commit/2efa9e903023db01ce0176fe1328e9fd4116482c))

- **plugins**: Handle InvalidRequest in AwsDownload
  ([#1532](https://github.com/CS-SI/eodag/pull/1532),
  [`7c47474`](https://github.com/CS-SI/eodag/commit/7c47474d7932f0c824ab3b3dae94f4a041368adf))

- **plugins**: Httpdownload conflicting files ([#1479](https://github.com/CS-SI/eodag/pull/1479),
  [`f069ccb`](https://github.com/CS-SI/eodag/commit/f069ccbb64c53ef594047cde5e5e52a236595813))

- **plugins**: Raise error on failed empty stream_zip
  ([#1475](https://github.com/CS-SI/eodag/pull/1475),
  [`f82f016`](https://github.com/CS-SI/eodag/commit/f82f016bac64911445b3beaa95f7fac7c47509bf))

- **plugins**: Remove default HTTPDownload zip extension
  ([#1400](https://github.com/CS-SI/eodag/pull/1400),
  [`07a38ac`](https://github.com/CS-SI/eodag/commit/07a38ace5ee8fd6c759e9325a475ec54ac92e113))

- **plugins**: Remove default queryables form value
  ([#1473](https://github.com/CS-SI/eodag/pull/1473),
  [`45c1aa7`](https://github.com/CS-SI/eodag/commit/45c1aa778974a915660cbed3233529e854edb94e))

- **plugins**: Small bugs in ecmwf queryables ([#1509](https://github.com/CS-SI/eodag/pull/1509),
  [`e71ca9c`](https://github.com/CS-SI/eodag/commit/e71ca9cfe531b396ad042c9050f043ea84ba8e7a))

- **plugins**: Urlopen timeout handling ([#1547](https://github.com/CS-SI/eodag/pull/1547),
  [`643cb3c`](https://github.com/CS-SI/eodag/commit/643cb3c0e6228ebf83ba01bf38a80b05162a7ab4))

- **plugins**: Validation error if 400 error during order
  ([#1390](https://github.com/CS-SI/eodag/pull/1390),
  [`a0da7e4`](https://github.com/CS-SI/eodag/commit/a0da7e412a1f7946f56190153624b7516403835d))

- **product-types**: Default license from proprietary to other
  ([#1492](https://github.com/CS-SI/eodag/pull/1492),
  [`35949ce`](https://github.com/CS-SI/eodag/commit/35949cefd3a871297fd85ae8de64448ed0949cc6))

- **providers**: Cop_ads and wekeo_ecmwf metadata mapping
  ([#1389](https://github.com/CS-SI/eodag/pull/1389),
  [`277b63b`](https://github.com/CS-SI/eodag/commit/277b63b7b9e69104e92ae0cc4bf7b055d5d4b642))

- **providers**: Default search timeout to 20s ([#1505](https://github.com/CS-SI/eodag/pull/1505),
  [`52a69f6`](https://github.com/CS-SI/eodag/commit/52a69f6026f6faf6dde82f06033f93658306e80e))

- **providers**: Default values and dates for GLOFAS and EFAS product types
  ([#1467](https://github.com/CS-SI/eodag/pull/1467),
  [`419956b`](https://github.com/CS-SI/eodag/commit/419956b422a96a3aa4f92962aa19143f46ac61e6))

- **providers**: Fire_historical on wekeo_ecmwf ([#1392](https://github.com/CS-SI/eodag/pull/1392),
  [`3f0f2cd`](https://github.com/CS-SI/eodag/commit/3f0f2cd2d54301b004fc8958cd369d93941d4c2a))

- **providers**: Geodes id property ([#1441](https://github.com/CS-SI/eodag/pull/1441),
  [`132ff00`](https://github.com/CS-SI/eodag/commit/132ff0000d874992fab84de4abeb602f254d7264))

- **providers**: Geodes metadata mapping ([#1468](https://github.com/CS-SI/eodag/pull/1468),
  [`67039bc`](https://github.com/CS-SI/eodag/commit/67039bca881c54649e628f466157579bdc47de79))

- **providers**: Geodes tileIdentifier ([#1457](https://github.com/CS-SI/eodag/pull/1457),
  [`6229ca6`](https://github.com/CS-SI/eodag/commit/6229ca6c7e716be5b48c26df9504bb0ca7adaea5))

- **providers**: Metadata mapping for EEA_DAILY_VI with wekeo_main
  ([#1464](https://github.com/CS-SI/eodag/pull/1464),
  [`b21735a`](https://github.com/CS-SI/eodag/commit/b21735af3aeaa616c3396a0f9ee177a807319e82))

- **providers**: Queryables fixes for some product-types
  ([#1462](https://github.com/CS-SI/eodag/pull/1462),
  [`6d51c12`](https://github.com/CS-SI/eodag/commit/6d51c12ba6f6e9166833f8dfc85f9e1612b60ec3))

- **providers**: Recognize geodes auth errors during download
  ([#1562](https://github.com/CS-SI/eodag/pull/1562),
  [`d325727`](https://github.com/CS-SI/eodag/commit/d325727bf6728d117876684104ba60a4d0fc3cc2))

- **providers**: Remove eumetsat_ds duplicate product types
  ([#1514](https://github.com/CS-SI/eodag/pull/1514),
  [`e3be09a`](https://github.com/CS-SI/eodag/commit/e3be09aaa2817e902a81a0accde424b04c3b7d9d))

Co-authored-by: anesson-cs <113022843+anesson-cs@users.noreply.github.com>

- **providers**: Remove onda provider ([#1564](https://github.com/CS-SI/eodag/pull/1564),
  [`a9234e4`](https://github.com/CS-SI/eodag/commit/a9234e4f72df7d8ab064a32e1db5376c0c45801b))

- **providers**: Remove unnecessary metadata mappings for eumtesat_ds
  ([#1502](https://github.com/CS-SI/eodag/pull/1502),
  [`8facb6d`](https://github.com/CS-SI/eodag/commit/8facb6d9a76c234233bfeee802d2316873f8f965))

- **providers**: Typo in geodes_s3 user conf template
  ([#1536](https://github.com/CS-SI/eodag/pull/1536),
  [`697b5c8`](https://github.com/CS-SI/eodag/commit/697b5c851f7f15ccb48c9e749061314118f26e3b))

- **providers**: Update wekeo config for COP-DEM produc types
  ([#1516](https://github.com/CS-SI/eodag/pull/1516),
  [`d38035f`](https://github.com/CS-SI/eodag/commit/d38035f63dc9a57136a5f4f295f77af0870914d2))

- **providers**: Wekeo_main metadata mapping ([#1549](https://github.com/CS-SI/eodag/pull/1549),
  [`0a66ed9`](https://github.com/CS-SI/eodag/commit/0a66ed938e37f141b25ed5c3ad9e44ef8ec05fa1))

- **server**: Add default datetime in dedt_lumi generated items
  ([#1472](https://github.com/CS-SI/eodag/pull/1472),
  [`20c5cbf`](https://github.com/CS-SI/eodag/commit/20c5cbfe64076e8e92c5f71536a777ebea8a1568))

- **server**: Geodes property parsing ([#1477](https://github.com/CS-SI/eodag/pull/1477),
  [`270e752`](https://github.com/CS-SI/eodag/commit/270e75200d3dea75e28f84005bd2bcdafe8ba6b2))

- **server**: Load processing level as string in external stac collection
  ([#1429](https://github.com/CS-SI/eodag/pull/1429),
  [`90f0545`](https://github.com/CS-SI/eodag/commit/90f0545a6d40e2682818d5d2e59b2d7fb42bf11e))

- **wekeo-ecmwf**: Correct queryables ([#1427](https://github.com/CS-SI/eodag/pull/1427),
  [`7658679`](https://github.com/CS-SI/eodag/commit/7658679d2494edc42f83facb23ee4c3f1d1c7df6))

### Build System

- Add missing cryptography requirement ([#1419](https://github.com/CS-SI/eodag/pull/1419),
  [`fe753c4`](https://github.com/CS-SI/eodag/commit/fe753c4a303db775e10121f8944cd1658b4b768b))

- Bump release ([#1508](https://github.com/CS-SI/eodag/pull/1508),
  [`cfc4bca`](https://github.com/CS-SI/eodag/commit/cfc4bca17c330be3f91f96b67bf867e37c402272))

- Bump version ([#1469](https://github.com/CS-SI/eodag/pull/1469),
  [`b108c32`](https://github.com/CS-SI/eodag/commit/b108c32c6263f5752a345d224a71e16072591774))

- Bump version ([#1568](https://github.com/CS-SI/eodag/pull/1568),
  [`9b387f8`](https://github.com/CS-SI/eodag/commit/9b387f8f9cc66cd1456ffcdbe4651dc96c35506c))

- Do not install usgs from git repo ([#1569](https://github.com/CS-SI/eodag/pull/1569),
  [`13d3a73`](https://github.com/CS-SI/eodag/commit/13d3a7323616b0007108bd3b865e4a220f8880bc))

- Prevent pydantic v2.10.0 usage ([#1411](https://github.com/CS-SI/eodag/pull/1411),
  [`1b3f312`](https://github.com/CS-SI/eodag/commit/1b3f312c386356431f705a9fac56b1581ef4aada))

- Remove dependencies max versions ([#1519](https://github.com/CS-SI/eodag/pull/1519),
  [`74490a2`](https://github.com/CS-SI/eodag/commit/74490a2bf3baa8c6be94964e60f6d4323d5bc596))

- Usgs last version from git repo ([#1552](https://github.com/CS-SI/eodag/pull/1552),
  [`2bc623f`](https://github.com/CS-SI/eodag/commit/2bc623f65dd4b2d07a687c40b7d8843a1678b51f))

### Documentation

- Adding product types ([#1434](https://github.com/CS-SI/eodag/pull/1434),
  [`2b94fd0`](https://github.com/CS-SI/eodag/commit/2b94fd045ca720efc7fd0f8d54817f231b4972a7))

- Eodag-cube api ref ([#1511](https://github.com/CS-SI/eodag/pull/1511),
  [`f5b4015`](https://github.com/CS-SI/eodag/commit/f5b4015e976685972c823c4d992ab685b39d9b3a))

- Move queryables doc to a new notebook ([#1447](https://github.com/CS-SI/eodag/pull/1447),
  [`0d90d9e`](https://github.com/CS-SI/eodag/commit/0d90d9e40345cfaaf6733f0215b7e1d873e2be12))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Remove beta from ads and cds links ([#1541](https://github.com/CS-SI/eodag/pull/1541),
  [`3a9ac6e`](https://github.com/CS-SI/eodag/commit/3a9ac6e4666257b643e9bd544c8b4ec8d1fa7b5f))

- Remove onda logo ([#1566](https://github.com/CS-SI/eodag/pull/1566),
  [`cd50894`](https://github.com/CS-SI/eodag/commit/cd50894671f098b90dd056f27b368003ea56e5e4))

- Titles fixes in Breaking Changes ([#1498](https://github.com/CS-SI/eodag/pull/1498),
  [`908c372`](https://github.com/CS-SI/eodag/commit/908c3724092331611479f660b844093b50d7f67f))

- Typo in geodes register link ([#1500](https://github.com/CS-SI/eodag/pull/1500),
  [`687d3f4`](https://github.com/CS-SI/eodag/commit/687d3f435a152eb54019d04cbc985439649f6b04))

- Update tutorials using eodag-cube ([#1436](https://github.com/CS-SI/eodag/pull/1436),
  [`8331bd1`](https://github.com/CS-SI/eodag/commit/8331bd19a9311a81c18547ace32dd4a0bbc43846))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Usgs registration update ([#1551](https://github.com/CS-SI/eodag/pull/1551),
  [`53a53c8`](https://github.com/CS-SI/eodag/commit/53a53c8c2dce182fb00e9780a3e0e2ccea30b0a6))

### Features

- **AwsDownload**: Zip partial download from s3 ([#1561](https://github.com/CS-SI/eodag/pull/1561),
  [`c59e264`](https://github.com/CS-SI/eodag/commit/c59e2649a3c5f18d4debd034b4c7d11947acd6e6))

- **core**: Add EODAG_PRODUCT_TYPES_CFG_FILE env var
  ([#1559](https://github.com/CS-SI/eodag/pull/1559),
  [`fd5ac0e`](https://github.com/CS-SI/eodag/commit/fd5ac0e7a63c1bb2eaa7b3ae6ee69f2760f758aa))

- **core**: Add to_lower and to_upper parameters mapping
  ([#1410](https://github.com/CS-SI/eodag/pull/1410),
  [`fb599d4`](https://github.com/CS-SI/eodag/commit/fb599d4d1385c7fdcea1c5d3f4457c6437208160))

- **core**: Merge queryables by provider priority
  ([#1431](https://github.com/CS-SI/eodag/pull/1431),
  [`2c7e575`](https://github.com/CS-SI/eodag/commit/2c7e575421a815121f97332a273177e6ec124444))

- **core**: Queryables mechanism and ecmwf plugins updates
  ([#1397](https://github.com/CS-SI/eodag/pull/1397),
  [`d709297`](https://github.com/CS-SI/eodag/commit/d709297eaff2aa642d454d871cac54c65bc70c2f))

Co-authored-by: Aubin Lambaré <aubin.lambare@csgroup.eu>

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- **eumetsat_ds**: New MTG product types ([#1513](https://github.com/CS-SI/eodag/pull/1513),
  [`a3e2572`](https://github.com/CS-SI/eodag/commit/a3e25729a80e044f0745f537a8e07716a7a25a81))

- **plugins**: Order and poll without downloading
  ([#1437](https://github.com/CS-SI/eodag/pull/1437),
  [`7e502af`](https://github.com/CS-SI/eodag/commit/7e502af83d68b83045a59358dc48200af9ad21ab))

- **providers**: Add product types to dedl provider
  ([#1515](https://github.com/CS-SI/eodag/pull/1515),
  [`d549c5a`](https://github.com/CS-SI/eodag/commit/d549c5ace03685f6528fbe69a34f845842ecae98))

- **providers**: Geodes_s3 as new provider ([#1506](https://github.com/CS-SI/eodag/pull/1506),
  [`23e1e54`](https://github.com/CS-SI/eodag/commit/23e1e54cbd42af5c72a2e96ab2e5a8cfa2f65388))

- **providers**: New mtg datasets in eumetsat_ds ([#1455](https://github.com/CS-SI/eodag/pull/1455),
  [`6dc0509`](https://github.com/CS-SI/eodag/commit/6dc050952154450cb0c121b7f8ce3fe731e12274))

Co-authored-by: jlahovnik <julia.lahovnik@csgroup.eu>

- **queryables**: Keep required even with default values
  ([#1521](https://github.com/CS-SI/eodag/pull/1521),
  [`248990a`](https://github.com/CS-SI/eodag/commit/248990abf57214a70e853006b784934e7f2f7037))

- **server**: Add dedicated liveness endpoint ([#1353](https://github.com/CS-SI/eodag/pull/1353),
  [`94d16b5`](https://github.com/CS-SI/eodag/commit/94d16b5d197cfa8d5a958eb8e0436f9180bf16f8))

- **utils**: Update mimetypes definition ([#1445](https://github.com/CS-SI/eodag/pull/1445),
  [`c44a5b8`](https://github.com/CS-SI/eodag/commit/c44a5b8efc1a45c376155c4289cc6f47360ea088))

### Refactoring

- Aws auth typing and generic types ([#1486](https://github.com/CS-SI/eodag/pull/1486),
  [`7bfe7fb`](https://github.com/CS-SI/eodag/commit/7bfe7fbaac144b8e63e2b20657026ee1c86e245d))

- Typing fixes following mypy 1.14.0 ([#1458](https://github.com/CS-SI/eodag/pull/1458),
  [`7a51598`](https://github.com/CS-SI/eodag/commit/7a515985291fbafbbcdabc3babfe90e1f828568c))

- **core**: Drivers from eodag-cube to core ([#1488](https://github.com/CS-SI/eodag/pull/1488),
  [`59bf497`](https://github.com/CS-SI/eodag/commit/59bf4970f38590e1a3c1a55b46cb9d757e3a2145))

- **core**: Replace pkg_resources.resource_filename and version using importlib
  ([#1540](https://github.com/CS-SI/eodag/pull/1540),
  [`c9be6ab`](https://github.com/CS-SI/eodag/commit/c9be6ab0460b88e30c166eb7e5b9b01cf34762fd))

- **ecmwf**: Simplify ECMWFSearch configuration ([#1433](https://github.com/CS-SI/eodag/pull/1433),
  [`df3c233`](https://github.com/CS-SI/eodag/commit/df3c233cc42832e75432d5d517944cea030f72e7))

### Testing

- Renamed old formatted record file ([#1403](https://github.com/CS-SI/eodag/pull/1403),
  [`279dad6`](https://github.com/CS-SI/eodag/commit/279dad6968c9925bb03592eae00358eacb7a7193))


## v3.0.1 (2024-11-06)

### Bug Fixes

- Cop_marine - handling of ids with points ([#1364](https://github.com/CS-SI/eodag/pull/1364),
  [`441cefa`](https://github.com/CS-SI/eodag/commit/441cefac33c8d93ee4ae8d596732fe24618faaf8))

- Update external product types reference ([#1342](https://github.com/CS-SI/eodag/pull/1342),
  [`4785e8a`](https://github.com/CS-SI/eodag/commit/4785e8a128a70d3f07bd57ed6333a66db10a91a4))

- Update external product types reference ([#1356](https://github.com/CS-SI/eodag/pull/1356),
  [`c4393b5`](https://github.com/CS-SI/eodag/commit/c4393b56ac5f8ad6101367ed67a969ff39a1edc1))

- Update external product types reference ([#1359](https://github.com/CS-SI/eodag/pull/1359),
  [`e482098`](https://github.com/CS-SI/eodag/commit/e482098bc146f610604fcf6e112cbe4cf6a79c0f))

- Update external product types reference ([#1360](https://github.com/CS-SI/eodag/pull/1360),
  [`127b346`](https://github.com/CS-SI/eodag/commit/127b346ee024c7e23884f5887a8c9d9e1b41b0c9))

- Update external product types reference ([#1362](https://github.com/CS-SI/eodag/pull/1362),
  [`1737390`](https://github.com/CS-SI/eodag/commit/1737390b3b9df60321e50cf4f4a9b46ca8f31506))

- Update external product types reference ([#1366](https://github.com/CS-SI/eodag/pull/1366),
  [`127e035`](https://github.com/CS-SI/eodag/commit/127e035620f1c2f97c6f7d0d7d7d7dd973ab9340))

- Update external product types reference ([#1369](https://github.com/CS-SI/eodag/pull/1369),
  [`3ebb060`](https://github.com/CS-SI/eodag/commit/3ebb060803399ff75fcd0dd0223039a5d2f46c06))

- Update external product types reference ([#1373](https://github.com/CS-SI/eodag/pull/1373),
  [`b471693`](https://github.com/CS-SI/eodag/commit/b471693a08c7ed3c7c2c12449a8d29bc09352ba6))

- Update external product types reference ([#1375](https://github.com/CS-SI/eodag/pull/1375),
  [`1888f5f`](https://github.com/CS-SI/eodag/commit/1888f5fc9f75301a836e1a8c15a29bea7bef167a))

- Update external product types reference ([#1378](https://github.com/CS-SI/eodag/pull/1378),
  [`3a2babe`](https://github.com/CS-SI/eodag/commit/3a2babe5453fbbc41c5625e31d9628fd9275577f))

- Update external product types reference ([#1381](https://github.com/CS-SI/eodag/pull/1381),
  [`9fe7fb2`](https://github.com/CS-SI/eodag/commit/9fe7fb25ca8afe79095633d66b8d7320c2efe383))

- Update external product types reference ([#1384](https://github.com/CS-SI/eodag/pull/1384),
  [`9a31d66`](https://github.com/CS-SI/eodag/commit/9a31d66f2d7d17068c545cf104c9ab7194b3ce5e))

- **plugins**: Auth only when needed during http download
  ([#1370](https://github.com/CS-SI/eodag/pull/1370),
  [`6b6d64c`](https://github.com/CS-SI/eodag/commit/6b6d64cdab94495eec0d72e4af8adb955b841d8a))

- **plugins**: Better error handling for cop_marine
  ([#1336](https://github.com/CS-SI/eodag/pull/1336),
  [`72b14f0`](https://github.com/CS-SI/eodag/commit/72b14f05974d12b754e03f700854e5292634f3a7))

- **plugins**: Oidc_config_url usage and expired token fix
  ([#1346](https://github.com/CS-SI/eodag/pull/1346),
  [`5c96977`](https://github.com/CS-SI/eodag/commit/5c96977764972e0aa22075b897043cfbb3a5d07e))

- **plugins**: Onda and no matching settings auth plugins
  ([#1340](https://github.com/CS-SI/eodag/pull/1340),
  [`55bea37`](https://github.com/CS-SI/eodag/commit/55bea37d849167757a794cd0423f1217f694f399))

- **plugins**: Raise error when http download order fails
  ([#1338](https://github.com/CS-SI/eodag/pull/1338),
  [`86baf25`](https://github.com/CS-SI/eodag/commit/86baf25476cfd86fffb9d820ce48cbb7221c1315))

- **providers**: Geodes conf fixes ([#1363](https://github.com/CS-SI/eodag/pull/1363),
  [`10923f0`](https://github.com/CS-SI/eodag/commit/10923f000ede40a4bd826c2df71007a7b7d273ac))

- **providers**: Missing orderable metadata mapping for some dedl product-types
  ([#1358](https://github.com/CS-SI/eodag/pull/1358),
  [`90da4f0`](https://github.com/CS-SI/eodag/commit/90da4f09fa98a43419b50ddcf19f3155b2c849e8))

- **providers**: Remove astraea_eod provider ([#1383](https://github.com/CS-SI/eodag/pull/1383),
  [`d2fc110`](https://github.com/CS-SI/eodag/commit/d2fc1100c700fe1819e7cb2190ca4b3cf16dd1fa))

- **providers**: Remove two_passes_id_search config param
  ([#1298](https://github.com/CS-SI/eodag/pull/1298),
  [`27f41ae`](https://github.com/CS-SI/eodag/commit/27f41aed5ecb3499649aed1f3b4211ae1bee7a1b))

- **providers**: S2_msi_l1c search-by-id for earth_search
  ([#1053](https://github.com/CS-SI/eodag/pull/1053),
  [`05f1142`](https://github.com/CS-SI/eodag/commit/05f114281a3b7b2f56da5b1bc8a5f918e2ed23bd))

- **providers**: Small errors in wekeo metadata mappings
  ([#1335](https://github.com/CS-SI/eodag/pull/1335),
  [`7252ad5`](https://github.com/CS-SI/eodag/commit/7252ad5e7759d518a78e79a6d894446a9dc4ddd2))

- **utils**: Include response text in RequestError
  ([#1341](https://github.com/CS-SI/eodag/pull/1341),
  [`9b6f422`](https://github.com/CS-SI/eodag/commit/9b6f4221139e79878b4cd212f3d0d937cf26cdae))

### Build System

- Add python3.13 and drop python3.8 support ([#1344](https://github.com/CS-SI/eodag/pull/1344),
  [`fdd3dce`](https://github.com/CS-SI/eodag/commit/fdd3dce8d74e91218d1392bc8bb4298d1e7ca5c8))

- Bump version ([#1386](https://github.com/CS-SI/eodag/pull/1386),
  [`80547b5`](https://github.com/CS-SI/eodag/commit/80547b5912a3bc94dd54534c85571763ebce4286))

- Tests speedup using uv and tox-uv ([#1347](https://github.com/CS-SI/eodag/pull/1347),
  [`7bf602f`](https://github.com/CS-SI/eodag/commit/7bf602fc9c3cc9badf2862ad1237c1daef2c754e))

### Continuous Integration

- Fetch wekeo product types ([#1377](https://github.com/CS-SI/eodag/pull/1377),
  [`2043582`](https://github.com/CS-SI/eodag/commit/2043582f60cfe67462323eed374a0965cd5f1911))

- Fetch-product-types diff formatting ([#1351](https://github.com/CS-SI/eodag/pull/1351),
  [`348e066`](https://github.com/CS-SI/eodag/commit/348e066156d7078c7da5c36c9829f7885c8ef34f))

### Documentation

- Conda optional deps ([#1343](https://github.com/CS-SI/eodag/pull/1343),
  [`7adc615`](https://github.com/CS-SI/eodag/commit/7adc6156451eba3e14c0a1fab7c3e7679ef45683))

- Fixes tutos auxdata reference
  ([`072b93e`](https://github.com/CS-SI/eodag/commit/072b93e48d71a153a22f537f8b60daaea1d49c7a))

- Plugins and utils documention update ([#1297](https://github.com/CS-SI/eodag/pull/1297),
  [`cdee784`](https://github.com/CS-SI/eodag/commit/cdee784fa2d227c8e908610422140188df4ed142))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Updated wekeo tutorial ([#1367](https://github.com/CS-SI/eodag/pull/1367),
  [`024a916`](https://github.com/CS-SI/eodag/commit/024a9169e163861e027f1cf2b4c7e6434c97c56e))

### Features

- **plugins**: Concurrent reqs for wekeo_cmems product-types fetch
  ([#1374](https://github.com/CS-SI/eodag/pull/1374),
  [`7aa0309`](https://github.com/CS-SI/eodag/commit/7aa0309d3ef356abaf51ca3335ceb489a8ea9e43))

- **providers**: Add MSG product types ([#1348](https://github.com/CS-SI/eodag/pull/1348),
  [`f65e582`](https://github.com/CS-SI/eodag/commit/f65e5823801754cc64d460d612e407e732fb74eb))

- **providers**: Cop_ewds as new provider ([#1331](https://github.com/CS-SI/eodag/pull/1331),
  [`28d9ae7`](https://github.com/CS-SI/eodag/commit/28d9ae7aa9f69a290f92de86814b9ac39be0fe49))

- **providers**: Geodes as new provider ([#1357](https://github.com/CS-SI/eodag/pull/1357),
  [`ad57a81`](https://github.com/CS-SI/eodag/commit/ad57a811eaa87e34143a8fda7bcc8d8afd5563ed))

### Refactoring

- **core**: Shorter fetched product types logs ([#1379](https://github.com/CS-SI/eodag/pull/1379),
  [`4e7645e`](https://github.com/CS-SI/eodag/commit/4e7645e0888b396e551885a0d62eef08e2afb684))

### Testing

- Force deps upgrade on install in tox ([#1368](https://github.com/CS-SI/eodag/pull/1368),
  [`e20c12b`](https://github.com/CS-SI/eodag/commit/e20c12b42f491f562056ab8884d1ffb8f18dd8af))


## v3.0.0 (2024-10-10)

### Bug Fixes

- Allow str type for resolution param ([#1102](https://github.com/CS-SI/eodag/pull/1102),
  [`7d87255`](https://github.com/CS-SI/eodag/commit/7d87255f833df7cafc30ce5f223ef39c1960542c))

- Catch product.location resolve errors during download
  ([#1118](https://github.com/CS-SI/eodag/pull/1118),
  [`bd79ff7`](https://github.com/CS-SI/eodag/commit/bd79ff731b9abf637af37aa488e527f44f4e5821))

- Clms search by id on wekeo ([#1100](https://github.com/CS-SI/eodag/pull/1100),
  [`5b9caa5`](https://github.com/CS-SI/eodag/commit/5b9caa5bf8c0dec8c22756fcd6a8662506cb84f6))

- Completed progress_callback with unknown total ([#1072](https://github.com/CS-SI/eodag/pull/1072),
  [`db83859`](https://github.com/CS-SI/eodag/commit/db83859f9565ff101ead03fde8b85995fc3d8af8))

- Correct external stac collection id reference ([#1171](https://github.com/CS-SI/eodag/pull/1171),
  [`76fadda`](https://github.com/CS-SI/eodag/commit/76fadda0844db2eb407632a375d93e9b9a7eec46))

- Efas dates formatting on cop_cds ([#1178](https://github.com/CS-SI/eodag/pull/1178),
  [`dbc1b57`](https://github.com/CS-SI/eodag/commit/dbc1b577d0d1a213879a6064f010ae42863dc84e))

- Enable eodag-cube assets import ([#1077](https://github.com/CS-SI/eodag/pull/1077),
  [`a27c188`](https://github.com/CS-SI/eodag/commit/a27c188c33be6115caac3237f4e699afc60943c1))

- Eumetsat_ds METOP search by id ([#1189](https://github.com/CS-SI/eodag/pull/1189),
  [`56068d7`](https://github.com/CS-SI/eodag/commit/56068d75c3c6c58e140e1b174fe8311863c7987c))

- Format_query_params in PostJsonSearch ([#1145](https://github.com/CS-SI/eodag/pull/1145),
  [`9764ac8`](https://github.com/CS-SI/eodag/commit/9764ac8d83ed81bd47d53df59a6dc3893ff55ec2))

- Handle creodias and cop_dataspace empty geometries
  ([#1186](https://github.com/CS-SI/eodag/pull/1186),
  [`69b5443`](https://github.com/CS-SI/eodag/commit/69b5443866b16d29c5e511f3cd430adfdb7364bd))

- Handle empty response from provider ([#1132](https://github.com/CS-SI/eodag/pull/1132),
  [`22b7e1f`](https://github.com/CS-SI/eodag/commit/22b7e1f72147f8aa14f9193a9819d49be30eb535))

- Improve stac collection links generation ([#1174](https://github.com/CS-SI/eodag/pull/1174),
  [`f915932`](https://github.com/CS-SI/eodag/commit/f915932e6341de392a2d701d33ee4ec798beca5b))

Co-authored-by: LAMBARE Aubin <aubin.lambare@csgroup.eu>

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Keep order in unique items lists ([#1296](https://github.com/CS-SI/eodag/pull/1296),
  [`db61d9c`](https://github.com/CS-SI/eodag/commit/db61d9c2640bb8a3195d671b742214f4c3e02d33))

- Move DEFAULT_MISSION_START_DATE to utils ([#1111](https://github.com/CS-SI/eodag/pull/1111),
  [`b71183e`](https://github.com/CS-SI/eodag/commit/b71183ebcf57a751a8081a1445e84a19fad29f43))

- Orderlink in build_search plugins ([#1082](https://github.com/CS-SI/eodag/pull/1082),
  [`1513d9c`](https://github.com/CS-SI/eodag/commit/1513d9c623210aac53b65cfef9f8024117d0bdf7))

- Orderlink parsing using updated templates metadata-mapping
  ([#1091](https://github.com/CS-SI/eodag/pull/1091),
  [`4286d13`](https://github.com/CS-SI/eodag/commit/4286d132c8500c968a82445c2e3509216c4a1e65))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Orjson requirement ([#1150](https://github.com/CS-SI/eodag/pull/1150),
  [`a2c8b01`](https://github.com/CS-SI/eodag/commit/a2c8b01656f373a05eedfafdcabe01fd68b3a21f))

- Prodcut types fetch update ([#1202](https://github.com/CS-SI/eodag/pull/1202),
  [`9028c4b`](https://github.com/CS-SI/eodag/commit/9028c4b52c09810b7b74d1a62873734abd071af3))

- Providers and product-types conf update ([#1212](https://github.com/CS-SI/eodag/pull/1212),
  [`e73c12e`](https://github.com/CS-SI/eodag/commit/e73c12e906318c95d0b7e912ce82f44c90091128))

- Queryables fixes + small refactor ([#1050](https://github.com/CS-SI/eodag/pull/1050),
  [`a8522fd`](https://github.com/CS-SI/eodag/commit/a8522fd96835becbcf2eecba4cbb5aaac492301e))

- Re-login in UsgsApi plugin on api file error ([#1046](https://github.com/CS-SI/eodag/pull/1046),
  [`2ef1ad1`](https://github.com/CS-SI/eodag/commit/2ef1ad1bbf78482abf284c3dc90449fc43afca41))

- Removes creodias discover_product_types ([#1112](https://github.com/CS-SI/eodag/pull/1112),
  [`81732a8`](https://github.com/CS-SI/eodag/commit/81732a834f414ad73c6b5654ec0226a14a9d4220))

- Response with 4xx or 5xx is false ([#1078](https://github.com/CS-SI/eodag/pull/1078),
  [`d513572`](https://github.com/CS-SI/eodag/commit/d513572bafbdd45344b8b24c69acc8940e2175ef))

- Search fallback error logging ([#1101](https://github.com/CS-SI/eodag/pull/1101),
  [`9d04c9b`](https://github.com/CS-SI/eodag/commit/9d04c9bd9757f469db0f010b457c5a90ef31ccae))

- Server-mode imports handling in cli ([#1113](https://github.com/CS-SI/eodag/pull/1113),
  [`c9a324b`](https://github.com/CS-SI/eodag/commit/c9a324ba000655bd69b64ea1cf8db91f20a6e015))

- Server-mode search param formatting and error message
  ([#1103](https://github.com/CS-SI/eodag/pull/1103),
  [`0dc0ba0`](https://github.com/CS-SI/eodag/commit/0dc0ba05eb4db2b5298e8de50d702e33ceae4aee))

- Shared rest functions without server extra ([#1115](https://github.com/CS-SI/eodag/pull/1115),
  [`ad46243`](https://github.com/CS-SI/eodag/commit/ad46243a9591d2d27ea9f3c681d80bbac53e55ed))

- Single product type discovery ([#1190](https://github.com/CS-SI/eodag/pull/1190),
  [`8360a41`](https://github.com/CS-SI/eodag/commit/8360a418c93b787ce399932df8f4979626962765))

- Sorted keys in gh action fetch product types diff
  ([#1205](https://github.com/CS-SI/eodag/pull/1205),
  [`298f941`](https://github.com/CS-SI/eodag/commit/298f941abfb9bc89f7636884039c034c5465f316))

- Type hints related fixes and refactoring ([#1052](https://github.com/CS-SI/eodag/pull/1052),
  [`d1df25e`](https://github.com/CS-SI/eodag/commit/d1df25ec4c7b97eb4b4543c6e8f919121919967c))

- Update external product types reference ([#1086](https://github.com/CS-SI/eodag/pull/1086),
  [`8090f54`](https://github.com/CS-SI/eodag/commit/8090f547134c55e26528a3756491c3d4af5e9cc4))

- Update external product types reference ([#1093](https://github.com/CS-SI/eodag/pull/1093),
  [`baf2298`](https://github.com/CS-SI/eodag/commit/baf2298a7c7ef7b4f423cef48df01901db1b8d35))

- Update external product types reference ([#1107](https://github.com/CS-SI/eodag/pull/1107),
  [`ed3ab95`](https://github.com/CS-SI/eodag/commit/ed3ab95dbdc27acd42bd6af65d7ca7eba0de5acd))

- Update external product types reference ([#1110](https://github.com/CS-SI/eodag/pull/1110),
  [`6606607`](https://github.com/CS-SI/eodag/commit/66066070f68e7a558ec34ac4ba46d64c7376ff31))

- Update external product types reference ([#1114](https://github.com/CS-SI/eodag/pull/1114),
  [`b2c6a50`](https://github.com/CS-SI/eodag/commit/b2c6a50cde181ad0a642340baebe9fbf14a6c60b))

- Update external product types reference ([#1136](https://github.com/CS-SI/eodag/pull/1136),
  [`975c7cd`](https://github.com/CS-SI/eodag/commit/975c7cddbe15dddfa4f06341252af1d4b63bd251))

- Update external product types reference ([#1137](https://github.com/CS-SI/eodag/pull/1137),
  [`a943c6c`](https://github.com/CS-SI/eodag/commit/a943c6c099e488a926c2cc2e305f8b53299bb180))

- Update external product types reference ([#1140](https://github.com/CS-SI/eodag/pull/1140),
  [`3b8ca8d`](https://github.com/CS-SI/eodag/commit/3b8ca8d191dc98479dd2be3a9e53ec79d6c0be32))

- Update external product types reference ([#1146](https://github.com/CS-SI/eodag/pull/1146),
  [`eb9a6f0`](https://github.com/CS-SI/eodag/commit/eb9a6f04359c64d28255a81775b42713b4abfad7))

- Update external product types reference ([#1151](https://github.com/CS-SI/eodag/pull/1151),
  [`f343411`](https://github.com/CS-SI/eodag/commit/f34341140fcd82e81176fe5eb92d760031e65c44))

- Update external product types reference ([#1153](https://github.com/CS-SI/eodag/pull/1153),
  [`df8c944`](https://github.com/CS-SI/eodag/commit/df8c94465cf7ca2d1852842dc707dbacaa075e56))

- Update external product types reference ([#1160](https://github.com/CS-SI/eodag/pull/1160),
  [`0a6208a`](https://github.com/CS-SI/eodag/commit/0a6208a6e306461fca3f66c1653a41ffda54dfb6))

- Update external product types reference ([#1165](https://github.com/CS-SI/eodag/pull/1165),
  [`06c4678`](https://github.com/CS-SI/eodag/commit/06c4678d1cf18bb16c7d61b21c0255542acf6f33))

- Update external product types reference ([#1203](https://github.com/CS-SI/eodag/pull/1203),
  [`8868ee5`](https://github.com/CS-SI/eodag/commit/8868ee57deb90c0b72ebd021c6033b2dbd28a193))

- Update external product types reference ([#1204](https://github.com/CS-SI/eodag/pull/1204),
  [`fb729b1`](https://github.com/CS-SI/eodag/commit/fb729b1b95b16b90ccd58a7bc3fb19480620b996))

- Update external product types reference ([#1206](https://github.com/CS-SI/eodag/pull/1206),
  [`8cf240e`](https://github.com/CS-SI/eodag/commit/8cf240ecadc7632de5eadc7f19524856db8105f0))

- Update external product types reference ([#1207](https://github.com/CS-SI/eodag/pull/1207),
  [`3efcf4c`](https://github.com/CS-SI/eodag/commit/3efcf4ca6238c96788d130ddf2faed840158063a))

- Update external product types reference ([#1208](https://github.com/CS-SI/eodag/pull/1208),
  [`e76f4a8`](https://github.com/CS-SI/eodag/commit/e76f4a823aa6607fbb4541fee78bf57138d1e504))

- Update external product types reference ([#1210](https://github.com/CS-SI/eodag/pull/1210),
  [`e577b27`](https://github.com/CS-SI/eodag/commit/e577b2754e9a4fde81d29fe84c4e9b1c8f97f585))

- Update external product types reference ([#1223](https://github.com/CS-SI/eodag/pull/1223),
  [`0d454f9`](https://github.com/CS-SI/eodag/commit/0d454f9718b5449b9693c184517728c0dd070083))

- Update external product types reference ([#1229](https://github.com/CS-SI/eodag/pull/1229),
  [`8f633df`](https://github.com/CS-SI/eodag/commit/8f633dff0d05f12579c9f7f1df5ddb6919bd656a))

- Update external product types reference ([#1234](https://github.com/CS-SI/eodag/pull/1234),
  [`b3af807`](https://github.com/CS-SI/eodag/commit/b3af807a732ae753d049d41f8181af0b32bbfe03))

- Update external product types reference ([#1244](https://github.com/CS-SI/eodag/pull/1244),
  [`0afcc97`](https://github.com/CS-SI/eodag/commit/0afcc97f30661217d96b4aae4a35ccb2bc63b6cf))

Co-authored-by: github-actions[bot] <github-actions[bot]@users.noreply.github.com>

- Update external product types reference ([#1246](https://github.com/CS-SI/eodag/pull/1246),
  [`568ae07`](https://github.com/CS-SI/eodag/commit/568ae07bfa176f1e68b59c1775f2fb3e39df93b9))

- Update external product types reference ([#1251](https://github.com/CS-SI/eodag/pull/1251),
  [`cf2f643`](https://github.com/CS-SI/eodag/commit/cf2f643b18d6cff0d2472e7436bb5d92536b75b0))

- Update external product types reference ([#1290](https://github.com/CS-SI/eodag/pull/1290),
  [`30c3c4a`](https://github.com/CS-SI/eodag/commit/30c3c4a6eb7cffc18586984e3ed3dbc33deb3fc7))

- Update external product types reference ([#1316](https://github.com/CS-SI/eodag/pull/1316),
  [`0deebef`](https://github.com/CS-SI/eodag/commit/0deebefa2631c0649e990e813b67e54150637eda))

- Update external product types reference ([#1322](https://github.com/CS-SI/eodag/pull/1322),
  [`c42cf9c`](https://github.com/CS-SI/eodag/commit/c42cf9c9ddeeeb8fb10757c04823f527406e9862))

- Update external product types reference ([#1334](https://github.com/CS-SI/eodag/pull/1334),
  [`216612f`](https://github.com/CS-SI/eodag/commit/216612f52440a273cf4fb9f9e7bb893c85e5d2bf))

- Update templates detection in metadata-mapping ([#1139](https://github.com/CS-SI/eodag/pull/1139),
  [`8fe2f86`](https://github.com/CS-SI/eodag/commit/8fe2f86f7bed28802c50eaa49499a66bbf86812a))

- Use id instead of title in item id metadata ([#1193](https://github.com/CS-SI/eodag/pull/1193),
  [`5f1b707`](https://github.com/CS-SI/eodag/commit/5f1b7070fea53513309d4719326b29428527f7d3))

- Wekeo pagination ([#1098](https://github.com/CS-SI/eodag/pull/1098),
  [`3506dfb`](https://github.com/CS-SI/eodag/commit/3506dfbdfa6520c18d9a94fdcd361cf77b59a97c))

- **build**: Update shapely to fix issues with numpy 2.1
  ([#1303](https://github.com/CS-SI/eodag/pull/1303),
  [`f373d7b`](https://github.com/CS-SI/eodag/commit/f373d7b08c77b78293737ff742499bc91b123826))

- **core**: Better compare matching_url with orderLink when OFFLINE
  ([#1332](https://github.com/CS-SI/eodag/pull/1332),
  [`d24377f`](https://github.com/CS-SI/eodag/commit/d24377f36b8defd8e2ef78dd42ee8c451464e9c3))

- **core**: Do not use git lfs ([#1333](https://github.com/CS-SI/eodag/pull/1333),
  [`ea72351`](https://github.com/CS-SI/eodag/commit/ea723511ee51834d8578f1c9d52b33fa86f31efc))

- **core**: Download authentication without downloadLink
  ([#1329](https://github.com/CS-SI/eodag/pull/1329),
  [`8174a1e`](https://github.com/CS-SI/eodag/commit/8174a1ea8079ae0aec604a9517342fce7055595a))

- **core**: Missing _search_by_id warning ([#1294](https://github.com/CS-SI/eodag/pull/1294),
  [`3316c4f`](https://github.com/CS-SI/eodag/commit/3316c4fcff8790e27316112a25ebabf2a5f88021))

- **plugins**: Add ssl_verify where necessary and remove where unnecessary
  ([#1289](https://github.com/CS-SI/eodag/pull/1289),
  [`0af86ad`](https://github.com/CS-SI/eodag/commit/0af86add7bae03489cff4a14a60d885c1b8aa4ec))

- **plugins**: Aws_session_token support in aws_auth
  ([#1267](https://github.com/CS-SI/eodag/pull/1267),
  [`47ed8bb`](https://github.com/CS-SI/eodag/commit/47ed8bbd74c757d3d498b49132dc2d32f8ac6b38))

- **plugins**: Build_search_result end_date preprocessing
  ([#1304](https://github.com/CS-SI/eodag/pull/1304),
  [`672fded`](https://github.com/CS-SI/eodag/commit/672fdede8451931769333423f67d1183b86062ca))

- **plugins**: Copmarine dates check ([#1224](https://github.com/CS-SI/eodag/pull/1224),
  [`87f69d3`](https://github.com/CS-SI/eodag/commit/87f69d309a7445b558e01ff49d6e21bd801e7f43))

- **plugins**: Http asset HEAD check and ssl_verify
  ([#1266](https://github.com/CS-SI/eodag/pull/1266),
  [`feef2bf`](https://github.com/CS-SI/eodag/commit/feef2bfdab8d86b94645ce87de8de6c961982460))

- **plugins**: Missing products conf in api plugin download
  ([#1241](https://github.com/CS-SI/eodag/pull/1241),
  [`8bb11c4`](https://github.com/CS-SI/eodag/commit/8bb11c4173c5585d52779b1a0c2c91051d9de639))

- **plugins**: Pagination is not globally mandatory
  ([#1240](https://github.com/CS-SI/eodag/pull/1240),
  [`cda35ec`](https://github.com/CS-SI/eodag/commit/cda35ecda90edb10fe82e50633f2a8886b1528d1))

- **plugins**: Product types discovery disabled by default on StaticStacSearch
  ([#1259](https://github.com/CS-SI/eodag/pull/1259),
  [`1e42221`](https://github.com/CS-SI/eodag/commit/1e422214aa717c3a050d255c3dd81f4871480522))

- **plugins**: Qssearch without productType ([#1295](https://github.com/CS-SI/eodag/pull/1295),
  [`f274d4a`](https://github.com/CS-SI/eodag/commit/f274d4adb60d5337e1dfd1b62dfe6d18c6ad61db))

- **plugins**: Raise error if no data available on AwsDownload
  ([#1257](https://github.com/CS-SI/eodag/pull/1257),
  [`dc24261`](https://github.com/CS-SI/eodag/commit/dc24261ac6accfbd60b38de0825262c250a29a65))

Co-authored-by: Nicola Dalpasso <nicola.dalpasso@csgroup.de>

- **plugins**: Skip product types discovery on parsing errors
  ([#1300](https://github.com/CS-SI/eodag/pull/1300),
  [`1948645`](https://github.com/CS-SI/eodag/commit/19486454af9784ea80313d7ace6357601a47ddee))

- **plugins**: Stored oidc token conflicts ([#1232](https://github.com/CS-SI/eodag/pull/1232),
  [`4ff098f`](https://github.com/CS-SI/eodag/commit/4ff098fa3b9204809744e50bbba86cbaa08ae092))

- **provider**: Wekeo_ecmwf default dates ([#1288](https://github.com/CS-SI/eodag/pull/1288),
  [`f4b7a67`](https://github.com/CS-SI/eodag/commit/f4b7a67ad974b122ddc89ea6ff315248c9468169))

- **providers**: Area metadata mapping for CAMS_EU_AIR_QUALITY_FORECAST
  ([#1225](https://github.com/CS-SI/eodag/pull/1225),
  [`8539f18`](https://github.com/CS-SI/eodag/commit/8539f18cb1314d9b4e4ec56b3e83ac6a08e46488))

- **providers**: Handle cop_marine in situ historical data
  ([#1301](https://github.com/CS-SI/eodag/pull/1301),
  [`b3c0263`](https://github.com/CS-SI/eodag/commit/b3c0263863e976639e0355395f5e132836c625f1))

- **providers**: Remove cacheable param for wekeo order
  ([#1239](https://github.com/CS-SI/eodag/pull/1239),
  [`d29137d`](https://github.com/CS-SI/eodag/commit/d29137de503d099615839d79c34799b7290284e7))

- **providers**: Typos in dedl provider config ([#1308](https://github.com/CS-SI/eodag/pull/1308),
  [`cecc9d8`](https://github.com/CS-SI/eodag/commit/cecc9d81cc260b46bd88d2ba0e18497c9f62e9f4))

- **providers**: Usage of hydrological_year in wekeo_ecmwf
  ([#1313](https://github.com/CS-SI/eodag/pull/1313),
  [`6088572`](https://github.com/CS-SI/eodag/commit/6088572458c7fbcd315483187d35df231361cfd7))

- **providers**: Usgs search by id ([#1262](https://github.com/CS-SI/eodag/pull/1262),
  [`7f1b989`](https://github.com/CS-SI/eodag/commit/7f1b989f75fcaebc9db3a218ed28696959b33ee1))

- **queryables**: Missing search plugin auth ([#1194](https://github.com/CS-SI/eodag/pull/1194),
  [`72ca3d7`](https://github.com/CS-SI/eodag/commit/72ca3d7dd63b4db66dd513f0479dc50b58708511))

- **server**: Add datetime in collections cache hash
  ([#1256](https://github.com/CS-SI/eodag/pull/1256),
  [`2e12639`](https://github.com/CS-SI/eodag/commit/2e126398a399e83542ad3a557f5aba43da4681eb))

Co-authored-by: Nicola Dalpasso <nicola.dalpasso@csgroup.de>

- **server**: Add provider in self link of item ([#1090](https://github.com/CS-SI/eodag/pull/1090),
  [`2c0e690`](https://github.com/CS-SI/eodag/commit/2c0e69045f7edeee7a63f29eff9601a19933707c))

- **server**: Append external collections metadata to product_types config
  ([#1197](https://github.com/CS-SI/eodag/pull/1197),
  [`203665d`](https://github.com/CS-SI/eodag/commit/203665ddf68268b299782a98d75db15d747558dc))

- **server**: Avoid multiplication of providers ([#1187](https://github.com/CS-SI/eodag/pull/1187),
  [`8f0eacf`](https://github.com/CS-SI/eodag/commit/8f0eacf8ae6df513396cf033a93450316c778629))

- **server**: Correct STAC collection generation ([#1278](https://github.com/CS-SI/eodag/pull/1278),
  [`2a318e7`](https://github.com/CS-SI/eodag/commit/2a318e7ca5c696296a0ab9b68a5343a28ed10f77))

- **server**: Get proxy info in next POST search URL
  ([#1106](https://github.com/CS-SI/eodag/pull/1106),
  [`0196e96`](https://github.com/CS-SI/eodag/commit/0196e96e4a8463d8692c4aabbf80752adc152409))

- **server**: Invalid characters in download urls
  ([#1276](https://github.com/CS-SI/eodag/pull/1276),
  [`0e511e7`](https://github.com/CS-SI/eodag/commit/0e511e763f3fda98c0aea4b64f3091582e572d18))

- **server**: Landing page and collections metadata update
  ([#1221](https://github.com/CS-SI/eodag/pull/1221),
  [`bc932d6`](https://github.com/CS-SI/eodag/commit/bc932d60f2b0fc4df4c4e4dc0b1bb390427c5be2))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- **server**: Merge providers by group & use groups in item links
  ([#1192](https://github.com/CS-SI/eodag/pull/1192),
  [`ea12faa`](https://github.com/CS-SI/eodag/commit/ea12faadae5d7e02977fe3824c7c405f8ecb23ab))

- **server**: Merge providers from external STAC collection
  ([#1176](https://github.com/CS-SI/eodag/pull/1176),
  [`2c5a0e0`](https://github.com/CS-SI/eodag/commit/2c5a0e07593f15a264e8658e3bd91e4768f3865e))

- **server**: Next page bbox is a list ([#1095](https://github.com/CS-SI/eodag/pull/1095),
  [`e6743bb`](https://github.com/CS-SI/eodag/commit/e6743bb5eea1936fb7e1fa7a53a4a62948952baa))

- **server**: Nonetype error in download with api plugin
  ([#1087](https://github.com/CS-SI/eodag/pull/1087),
  [`44172e0`](https://github.com/CS-SI/eodag/commit/44172e0d23c14cad53c4b8a038d99ea827646f96))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- **server**: Queryable issues and parameters prefixes
  ([#1318](https://github.com/CS-SI/eodag/pull/1318),
  [`cbe3238`](https://github.com/CS-SI/eodag/commit/cbe32384ccfcfafbee0e4e2a988408feac3bd832))

- **server**: Remove catalogs ([#1306](https://github.com/CS-SI/eodag/pull/1306),
  [`1d3070f`](https://github.com/CS-SI/eodag/commit/1d3070f0aca2f34e091d46195694175889ee0e78))

- **server**: Replace 400 with 404 when collection or item not found
  ([#1182](https://github.com/CS-SI/eodag/pull/1182),
  [`c5534d1`](https://github.com/CS-SI/eodag/commit/c5534d170ac87c064c4616331457f1003523d887))

- **server**: Send search_stac_items in its own threadpool
  ([#1323](https://github.com/CS-SI/eodag/pull/1323),
  [`eb54b16`](https://github.com/CS-SI/eodag/commit/eb54b1684a02c2e15f65b92729c5505decd7da98))

- **server**: Single asset download with ignore_assets plugin setting
  ([#1199](https://github.com/CS-SI/eodag/pull/1199),
  [`fe356ec`](https://github.com/CS-SI/eodag/commit/fe356ec1df6c10d17051873a55b13df42a4d9d1e))

- **server**: Stac ext collection keywords mapping
  ([#1180](https://github.com/CS-SI/eodag/pull/1180),
  [`4358ae6`](https://github.com/CS-SI/eodag/commit/4358ae622fce7b33bad5b6746290d6866cf3e4c1))

- **server**: Type missing on some queryables ([#1083](https://github.com/CS-SI/eodag/pull/1083),
  [`0440f20`](https://github.com/CS-SI/eodag/commit/0440f2082cd74f5a21822455580cd2a81415d665))

- **wekeo**: Correct order link for GRIDDED_GLACIERS_MASS_CHANGE
  ([#1258](https://github.com/CS-SI/eodag/pull/1258),
  [`050c371`](https://github.com/CS-SI/eodag/commit/050c3711d1a8f6584f098335f1b9a60ef34759d6))

- **wekeo**: Yml anchor issue in provider config ([#1315](https://github.com/CS-SI/eodag/pull/1315),
  [`4b35e1d`](https://github.com/CS-SI/eodag/commit/4b35e1d8eeeae5a2cc291f46aa0fbf02b98b972e))

### Build System

- Bump version ([#1218](https://github.com/CS-SI/eodag/pull/1218),
  [`1e0e577`](https://github.com/CS-SI/eodag/commit/1e0e577096bef0f6c3b532aa51c843a33cabe933))

- Bump version ([#1245](https://github.com/CS-SI/eodag/pull/1245),
  [`95a2f31`](https://github.com/CS-SI/eodag/commit/95a2f31f19921cf3a693c50d5ec5cdcf95f26b3f))

- Bump version ([#1283](https://github.com/CS-SI/eodag/pull/1283),
  [`5065a00`](https://github.com/CS-SI/eodag/commit/5065a005f4b20d0ca7abc9d296fd696ec017a564))

- Bump version ([#1330](https://github.com/CS-SI/eodag/pull/1330),
  [`14a2ca8`](https://github.com/CS-SI/eodag/commit/14a2ca8506f1a305cd34993e26458788c3129601))

- Install boto3 by default ([#1219](https://github.com/CS-SI/eodag/pull/1219),
  [`ccf150d`](https://github.com/CS-SI/eodag/commit/ccf150d08cdc882d8ae02e66b003d9c23e790aeb))

- Orjson pinned for windows py312 ([#1079](https://github.com/CS-SI/eodag/pull/1079),
  [`930ada1`](https://github.com/CS-SI/eodag/commit/930ada121a2e24ec90fbca7c4b099e024ad2b681))

- Refactor and new optional dependencies ([#1108](https://github.com/CS-SI/eodag/pull/1108),
  [`3ebcffd`](https://github.com/CS-SI/eodag/commit/3ebcffd20dddb912d095e954a31efee7ca7931e9))

- Specify shapely min version ([#1155](https://github.com/CS-SI/eodag/pull/1155),
  [`af5e548`](https://github.com/CS-SI/eodag/commit/af5e54849215055791f184d3b211bf464f6ec132))

- Uvicorn extras fix ([#1152](https://github.com/CS-SI/eodag/pull/1152),
  [`50a451f`](https://github.com/CS-SI/eodag/commit/50a451fabfbd6529acd3b95cd1a8230ac1ada904))

- **deps**: Bump actions/download-artifact from 3 to 4
  ([#1310](https://github.com/CS-SI/eodag/pull/1310),
  [`6c46430`](https://github.com/CS-SI/eodag/commit/6c46430c96ee052554e092e0b0ee19afc3a2009e))

- **deps**: Update upload-artifact action v4 ([#1314](https://github.com/CS-SI/eodag/pull/1314),
  [`eb0e34e`](https://github.com/CS-SI/eodag/commit/eb0e34ec14a7a77b653d23a63626fb900dfcb071))

### Continuous Integration

- Github actions updates ([#1249](https://github.com/CS-SI/eodag/pull/1249),
  [`e0ce87b`](https://github.com/CS-SI/eodag/commit/e0ce87bb6dae07730d169b7f53568e8bd912a8d4))

- Mypy in linting github action ([#1326](https://github.com/CS-SI/eodag/pull/1326),
  [`3061402`](https://github.com/CS-SI/eodag/commit/3061402971d6faf72978d390707cc247d22bcee8))

Co-authored-by: Julia Lahovnik <julia.lahovnik@csgroup.eu>

### Documentation

- Add missing url in sara provider configuration ([#1062](https://github.com/CS-SI/eodag/pull/1062),
  [`b2c1467`](https://github.com/CS-SI/eodag/commit/b2c1467fa2b84dfa7c617a6726b3e3c61d479593))

- Add wekeo_cmems provider in index and plugins documentation pages
  ([#1081](https://github.com/CS-SI/eodag/pull/1081),
  [`e0774f9`](https://github.com/CS-SI/eodag/commit/e0774f992e77774625df910fc3f8ba549fb85b96))

- Changelog update ([#1254](https://github.com/CS-SI/eodag/pull/1254),
  [`f457527`](https://github.com/CS-SI/eodag/commit/f4575270895d897b44b1ccc399884476dc754cd5))

- Developer documentation update ([#1327](https://github.com/CS-SI/eodag/pull/1327),
  [`0d7ff3c`](https://github.com/CS-SI/eodag/commit/0d7ff3cf9fb348fd2c6d7cc40d9307791fb3325d))

- Download methods ([#1282](https://github.com/CS-SI/eodag/pull/1282),
  [`1e7247f`](https://github.com/CS-SI/eodag/commit/1e7247fb749ce0b69fb5ee59591b4b24b2d72140))

- Mock search plugin section ([#1242](https://github.com/CS-SI/eodag/pull/1242),
  [`e21c5d7`](https://github.com/CS-SI/eodag/commit/e21c5d75ae068e4ce1985be8561b4450b11871bf))

- Prevent newline between README badges ([#1109](https://github.com/CS-SI/eodag/pull/1109),
  [`e619c88`](https://github.com/CS-SI/eodag/commit/e619c88de826047b8f46f4485ca5537a58e60678))

- Providers.yml comments for sticky scroll ([#1059](https://github.com/CS-SI/eodag/pull/1059),
  [`b49dfce`](https://github.com/CS-SI/eodag/commit/b49dfceb9eaffdbb14bfea9c00929ed5ea71cccd))

- Remove current module from summarized items ([#1264](https://github.com/CS-SI/eodag/pull/1264),
  [`f7efdd0`](https://github.com/CS-SI/eodag/commit/f7efdd09236091864c16b46822730cf1b97317c9))

- Remove unneeded code and files
  ([`211bdfd`](https://github.com/CS-SI/eodag/commit/211bdfdd48ac3bd8e9607c98b3d582aa39636be0))

- Restored readme logo ([#1057](https://github.com/CS-SI/eodag/pull/1057),
  [`1a23ff3`](https://github.com/CS-SI/eodag/commit/1a23ff314acaee053c6454e36c8a7d6a8466ba36))

- Rtd copyright 2024 ([#1121](https://github.com/CS-SI/eodag/pull/1121),
  [`5f88b80`](https://github.com/CS-SI/eodag/commit/5f88b808f37197d871943c431c2d7ed3cd6b5181))

- Search dates documentation ([#1063](https://github.com/CS-SI/eodag/pull/1063),
  [`a65bae4`](https://github.com/CS-SI/eodag/commit/a65bae4fed6a92e5fd729db863fc97386977c501))

- Update CS GROUP name ([#1122](https://github.com/CS-SI/eodag/pull/1122),
  [`bc1953a`](https://github.com/CS-SI/eodag/commit/bc1953ab88bee1cff638872ead8239a4ac4433f2))

- Update layout
  ([`faa2a50`](https://github.com/CS-SI/eodag/commit/faa2a50269f2bbec7d62e113e49b08d1e588b831))

- Update sphinx theme and remove jquery
  ([`13c177b`](https://github.com/CS-SI/eodag/commit/13c177bb5d2caaf7e88f0d01d06d541a61237749))

- V3 breaking changes ([#1281](https://github.com/CS-SI/eodag/pull/1281),
  [`fe3bf6d`](https://github.com/CS-SI/eodag/commit/fe3bf6de4a01330315b2f0a65ab1df9f971ab68f))

### Features

- Add cop_marine provider ([#1131](https://github.com/CS-SI/eodag/pull/1131),
  [`19e0d05`](https://github.com/CS-SI/eodag/commit/19e0d05fea41921d431b3a46eed83b875c8ac6e3))

Co-authored-by: Julia Lahovnik <julia.lahovnik@csgroup.eu>

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Add METOP product types for eumetsat_ds ([#1143](https://github.com/CS-SI/eodag/pull/1143),
  [`3543a40`](https://github.com/CS-SI/eodag/commit/3543a40873c344242aec3cc9b719b9f1bf033462))

- Add new product types ([#1164](https://github.com/CS-SI/eodag/pull/1164),
  [`b507413`](https://github.com/CS-SI/eodag/commit/b507413aa272f36a724fe1d09a4b54ae495bdeb0))

Co-authored-by: LAMBARE Aubin <aubin.lambare@csgroup.eu>

- Add provider dedl ([#750](https://github.com/CS-SI/eodag/pull/750),
  [`2fc91a9`](https://github.com/CS-SI/eodag/commit/2fc91a9fde63fc221fb23ddceb58aeaac170ecab))

Co-authored-by: LAMBARE Aubin <aubin.lambare@csgroup.eu>

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

Co-authored-by: Nicola Dalpasso <nicola.dalpasso@csgroup.de>

- Add provider eumetsat_ds ([#1060](https://github.com/CS-SI/eodag/pull/1060),
  [`05697ac`](https://github.com/CS-SI/eodag/commit/05697ac048f76b1a66b42951dfd61bcc7cd76581))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Add refresh token to `OIDCAuthorizationCodeFlowAuth` plugin
  ([#1138](https://github.com/CS-SI/eodag/pull/1138),
  [`8822525`](https://github.com/CS-SI/eodag/commit/88225254349299bfa4773c9083424e0b6df0ea34))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Adjust timeout to match the provider's one ([#1163](https://github.com/CS-SI/eodag/pull/1163),
  [`80f9403`](https://github.com/CS-SI/eodag/commit/80f9403cf52c7446dd495539d551060fe54c92fc))

- Allow local constraints files ([#1105](https://github.com/CS-SI/eodag/pull/1105),
  [`59ccd8b`](https://github.com/CS-SI/eodag/commit/59ccd8b563ce9914488ab0d5f52965fd09692cde))

- Allow no auth for download requests ([#1196](https://github.com/CS-SI/eodag/pull/1196),
  [`d8aefa9`](https://github.com/CS-SI/eodag/commit/d8aefa9f27238618b16bb65965c3dd794b0d1123))

- Configurable download timeout ([#1124](https://github.com/CS-SI/eodag/pull/1124),
  [`a29e7a7`](https://github.com/CS-SI/eodag/commit/a29e7a744de8085868192952e675aa685a87b1d3))

- Configurable requests ssl_verify ([#1045](https://github.com/CS-SI/eodag/pull/1045),
  [`fe76492`](https://github.com/CS-SI/eodag/commit/fe76492b7d336271d78b0a980792638580257e7f))

- Dedt_lumi provider ([#1119](https://github.com/CS-SI/eodag/pull/1119),
  [`9729aa4`](https://github.com/CS-SI/eodag/commit/9729aa4e5a52c1d692527fcac61d0ac7934bd481))

Co-authored-by: Julia Lahovnik <julia.lahovnik@csgroup.eu>

Co-authored-by: LAMBARE Aubin <aubin.lambare@csgroup.eu>

- Extend freetext search to all filters ([#1070](https://github.com/CS-SI/eodag/pull/1070),
  [`ac53539`](https://github.com/CS-SI/eodag/commit/ac53539c4aed0c580fb80e0d2c2036af60e1aeca))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- External enhanced product types metadata ([#1008](https://github.com/CS-SI/eodag/pull/1008),
  [`be8f361`](https://github.com/CS-SI/eodag/commit/be8f361153d017dd06e048dfc63fcfce278319c6))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Get queryables for wekeo with a constraints file
  ([#1104](https://github.com/CS-SI/eodag/pull/1104),
  [`3bcdd79`](https://github.com/CS-SI/eodag/commit/3bcdd7933cf1d42b4616c9c71aba65c564448018))

- Handle integers as shapefile attributes ([#1280](https://github.com/CS-SI/eodag/pull/1280),
  [`73d8f11`](https://github.com/CS-SI/eodag/commit/73d8f11b9a74d7929a0df9d0aa68658ff61d8de4))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Httpheaderauth accepts headers def in credentials
  ([#1215](https://github.com/CS-SI/eodag/pull/1215),
  [`3309501`](https://github.com/CS-SI/eodag/commit/3309501ac8391d09a4151dff4113dccaa6fa5d36))

- Match intersection of the datetime interval on search
  ([#1158](https://github.com/CS-SI/eodag/pull/1158),
  [`0454652`](https://github.com/CS-SI/eodag/commit/04546522890d49f922f2870d4811a1cd18dd5eea))

Co-authored-by: Aubin Lambare <aubin.lambare@csgroup.eu>

- Provider groups ([#1071](https://github.com/CS-SI/eodag/pull/1071),
  [`7523dcf`](https://github.com/CS-SI/eodag/commit/7523dcf3ad98066fd4328c23cf674331be32b1f7))

- Support opened time intervals for STAC providers
  ([#1144](https://github.com/CS-SI/eodag/pull/1144),
  [`be370c7`](https://github.com/CS-SI/eodag/commit/be370c745bc736536b076e37baad43e906cf49c4))

- Use OData API for creodias & cop_dataspace ([#1149](https://github.com/CS-SI/eodag/pull/1149),
  [`bb95da0`](https://github.com/CS-SI/eodag/commit/bb95da00eb6f1b62920ff6d41c54fee5e0d46370))

Co-authored-by: Aubin Lambare <aubin.lambare@csgroup.eu>

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Wekeo updated to hda-broker 2.0 ([#1034](https://github.com/CS-SI/eodag/pull/1034),
  [`8132c6c`](https://github.com/CS-SI/eodag/commit/8132c6c1f26b777e49c828ea803cee746d0eb102))

- **cop_dataspace**: Adds S1_SAR_GRD_COG and new odata query parameters
  ([#1277](https://github.com/CS-SI/eodag/pull/1277),
  [`97b7b6f`](https://github.com/CS-SI/eodag/commit/97b7b6f881714b4c40029a174c2539085cd50868))

- **core**: Add_provider method ([#1260](https://github.com/CS-SI/eodag/pull/1260),
  [`513bfe0`](https://github.com/CS-SI/eodag/commit/513bfe0fd417f6ea7fd33e68562048722696b7a0))

- **core**: Datetime filters in guess_product_types
  ([#1222](https://github.com/CS-SI/eodag/pull/1222),
  [`1e37edc`](https://github.com/CS-SI/eodag/commit/1e37edccf2c266768884076d0178dc0d71c7434d))

- **core**: Improve search and authentication errors format
  ([#1237](https://github.com/CS-SI/eodag/pull/1237),
  [`9a7b44c`](https://github.com/CS-SI/eodag/commit/9a7b44c12a3e12c998a8fbc60a765e8ee6b474f5))

Co-authored-by: Nicola Dalpasso <nicola.dalpasso@csgroup.de>

- **core**: Search optional count and return only SearchResult
  ([#1200](https://github.com/CS-SI/eodag/pull/1200),
  [`9c0d7e7`](https://github.com/CS-SI/eodag/commit/9c0d7e7b2f2c3bcbeac6f6b710e3efd03ed78379))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- **core**: Searchresult HTML representation ([#1243](https://github.com/CS-SI/eodag/pull/1243),
  [`ddb3c6f`](https://github.com/CS-SI/eodag/commit/ddb3c6fa1e19c2aee7abbb998c44ed0542d7f627))

- **core**: Shared and multiple auth per provider
  ([#1292](https://github.com/CS-SI/eodag/pull/1292),
  [`d148e50`](https://github.com/CS-SI/eodag/commit/d148e50926ad4c29a2a338a74e1751ef21d8b5f1))

- **core**: Sorted discovered product types ([#1250](https://github.com/CS-SI/eodag/pull/1250),
  [`641dfdf`](https://github.com/CS-SI/eodag/commit/641dfdf3f755b5be6e01e78e3c594cadf5687070))

- **dedt_lumi**: Add parameter levelist & default time to 0000
  ([#1126](https://github.com/CS-SI/eodag/pull/1126),
  [`b54f8d5`](https://github.com/CS-SI/eodag/commit/b54f8d566be4747c411f6683c9d27b4a4368eae6))

- **dedt_lumi**: Authenticate with destine credentials
  ([#1127](https://github.com/CS-SI/eodag/pull/1127),
  [`52a4bfa`](https://github.com/CS-SI/eodag/commit/52a4bfa70b06771c61f9b9bb40fa408401d18079))

- **plugins**: Flatten_top_dirs true by default ([#1220](https://github.com/CS-SI/eodag/pull/1220),
  [`888e7c4`](https://github.com/CS-SI/eodag/commit/888e7c49620a92e848cb4b4e32dc39a3db6be108))

- **providers**: Add GRIDDED_GLACIERS_MASS_CHANGE on provider cop_cds
  ([#1255](https://github.com/CS-SI/eodag/pull/1255),
  [`a456422`](https://github.com/CS-SI/eodag/commit/a456422efb7f912bfc50c1c1e62342eca95b3edb))

- **providers**: Add METOP_HIRSL1 and SATELLITE_FIRE_BURNED_AREA datasets
  ([#1227](https://github.com/CS-SI/eodag/pull/1227),
  [`03306fa`](https://github.com/CS-SI/eodag/commit/03306fa3a4485c9bb05108a9210de226d1abf8f2))

- **providers**: Wekeo split to wekeo_main and wekeo_ecmwf
  ([#1214](https://github.com/CS-SI/eodag/pull/1214),
  [`e864f53`](https://github.com/CS-SI/eodag/commit/e864f5313b7da2b6e8964b58d2df455c55e47250))

- **server**: Add bbox queryables ([#1185](https://github.com/CS-SI/eodag/pull/1185),
  [`17e68c2`](https://github.com/CS-SI/eodag/commit/17e68c2a45700ff8ab1d3de156d629dbf9a080a5))

- **server**: Add blacklist config for assets alt URLs
  ([#1213](https://github.com/CS-SI/eodag/pull/1213),
  [`53e2756`](https://github.com/CS-SI/eodag/commit/53e2756c611262eff1f703874b83ca25478bb18f))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- **server**: Caching LRU ([#1073](https://github.com/CS-SI/eodag/pull/1073),
  [`60338b6`](https://github.com/CS-SI/eodag/commit/60338b6dd766c79d82c569170359210cbcad4cc4))

- **server**: Enable HEAD requests ([#1120](https://github.com/CS-SI/eodag/pull/1120),
  [`8dde659`](https://github.com/CS-SI/eodag/commit/8dde65983b16cc4d3cb4865c805d647e2728831b))

- **server**: Order and storage extensions usage ([#1117](https://github.com/CS-SI/eodag/pull/1117),
  [`ff84295`](https://github.com/CS-SI/eodag/commit/ff84295c8d80a8f711b0f518726df19cb24ff701))

### Refactoring

- Api base plugin inherits from Search and Download
  ([#1051](https://github.com/CS-SI/eodag/pull/1051),
  [`2937f61`](https://github.com/CS-SI/eodag/commit/2937f61124df06991f869a16798a0659c86cf705))

- Constraints fetch using fetch_json method ([#1157](https://github.com/CS-SI/eodag/pull/1157),
  [`1294ddd`](https://github.com/CS-SI/eodag/commit/1294dddaecebf87312e368e1111f21aee6b016ac))

- Metadata.mapping format_query_params update ([#1142](https://github.com/CS-SI/eodag/pull/1142),
  [`e47bd3e`](https://github.com/CS-SI/eodag/commit/e47bd3e7c29bf1df787fe82d811e49e2eac16458))

- Move CdsApi to BuildSearchResult and HTTPDownload
  ([#1029](https://github.com/CS-SI/eodag/pull/1029),
  [`b3e40f6`](https://github.com/CS-SI/eodag/commit/b3e40f6dccf92562902a067593ac8996f8f3e618))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Output_dir and output_extension parameters ([#1279](https://github.com/CS-SI/eodag/pull/1279),
  [`8586d37`](https://github.com/CS-SI/eodag/commit/8586d37ef28c031f80fe4665782da8aa08f96e00))

- Preparedsearch and RawSearchResult usage ([#1191](https://github.com/CS-SI/eodag/pull/1191),
  [`2c37db3`](https://github.com/CS-SI/eodag/commit/2c37db30b5cd2e908bf3231f589debac7def11be))

- Remove not needed anymore requests-ftp ([#1085](https://github.com/CS-SI/eodag/pull/1085),
  [`32b26dc`](https://github.com/CS-SI/eodag/commit/32b26dc2fd84e68157ed50c261463390a514a44e))

- Search all and crunch for _search_by_id ([#1099](https://github.com/CS-SI/eodag/pull/1099),
  [`aba8f47`](https://github.com/CS-SI/eodag/commit/aba8f47051d292cfd77ae42fcab7d204e9c2dabc))

- Tokenauth credentials check ([#1141](https://github.com/CS-SI/eodag/pull/1141),
  [`dda2150`](https://github.com/CS-SI/eodag/commit/dda21504db894b1e95acfb88f67033f22a322892))

- Type hints fixes ([#1253](https://github.com/CS-SI/eodag/pull/1253),
  [`1c91533`](https://github.com/CS-SI/eodag/commit/1c915335fcf7a9070c2991f230309f454d74f1bf))

- Type hints fixes and mypy in tox ([#1269](https://github.com/CS-SI/eodag/pull/1269),
  [`6055d7b`](https://github.com/CS-SI/eodag/commit/6055d7b2246f46f6f7122bb1dc8c08cc6119bc4f))

- **core**: Git lfs and constraints update for DT datasets
  ([#1263](https://github.com/CS-SI/eodag/pull/1263),
  [`073a910`](https://github.com/CS-SI/eodag/commit/073a9103cb50954a8f4c9d4eb4e17390e466256b))

- **core**: Rename some parameters and methods to snake_case
  ([#1271](https://github.com/CS-SI/eodag/pull/1271),
  [`3e5834f`](https://github.com/CS-SI/eodag/commit/3e5834f1995ba7129aaad3c3742e38bbde2b927c))

- **docs**: Sphinx-autodoc-typehints usage ([#1066](https://github.com/CS-SI/eodag/pull/1066),
  [`c54f68b`](https://github.com/CS-SI/eodag/commit/c54f68b9935c005b58396cea85999e7bb0676c35))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- **plugins**: Optional base_uri ([#1230](https://github.com/CS-SI/eodag/pull/1230),
  [`5a72caa`](https://github.com/CS-SI/eodag/commit/5a72caa3d422fd39ea68696df4055c004fa22a2e))

- **provider**: New cds api ([#1284](https://github.com/CS-SI/eodag/pull/1284),
  [`948b82b`](https://github.com/CS-SI/eodag/commit/948b82b4fd1df9fc3078c99c1b04c34c3290fc65))

- **server**: Logs format ([#1238](https://github.com/CS-SI/eodag/pull/1238),
  [`c8733ce`](https://github.com/CS-SI/eodag/commit/c8733ce3c026417eaa318a498c752381053a1fd7))

### Testing

- `oidcauthorizationcodeflowauth` plugin ([#1135](https://github.com/CS-SI/eodag/pull/1135),
  [`919f46d`](https://github.com/CS-SI/eodag/commit/919f46df4527efe6963d5cc4c33e8971a65249b9))

- Fieldinfo repr with pydantic >= 2.7.0 ([#1097](https://github.com/CS-SI/eodag/pull/1097),
  [`c99e3be`](https://github.com/CS-SI/eodag/commit/c99e3bec15a3a8964dd39d5e6152a49d8152515e))

- Fix end-to-end tests ([#1236](https://github.com/CS-SI/eodag/pull/1236),
  [`90aa258`](https://github.com/CS-SI/eodag/commit/90aa258ed9c1caf5d6fce3ec79f6dcfce8ed50ae))


## v2.12.1 (2024-03-05)

### Bug Fixes

- Remove metadata_mapping from CdsApi queryables ([#1048](https://github.com/CS-SI/eodag/pull/1048),
  [`ee6306b`](https://github.com/CS-SI/eodag/commit/ee6306b13f9a8a930e7ebb6b35af59f6799f2472))

- Update external product types reference ([#1027](https://github.com/CS-SI/eodag/pull/1027),
  [`2ed579c`](https://github.com/CS-SI/eodag/commit/2ed579c55521978ff07e8e9fefed095b24101d1f))

- Update external product types reference ([#1028](https://github.com/CS-SI/eodag/pull/1028),
  [`6e25b8a`](https://github.com/CS-SI/eodag/commit/6e25b8ac1fe3e9b997dff9e6c1ada5854b57adf1))

### Build System

- Bump version to v2.12.1
  ([`ef764e9`](https://github.com/CS-SI/eodag/commit/ef764e95effdd796a06ffd28ef22b6c777b72326))

### Features

- Add sorting feature in library mode ([#943](https://github.com/CS-SI/eodag/pull/943),
  [`dd9a2ef`](https://github.com/CS-SI/eodag/commit/dd9a2ef78e042e131af8dc731024b618752a52ad))

- Configurable assets filtering ([#1033](https://github.com/CS-SI/eodag/pull/1033),
  [`d4d6bdf`](https://github.com/CS-SI/eodag/commit/d4d6bdf136a0d5a8e0cc0e8e03ddbb0b6a6e494d))

- Generate record hash from product_type + id ([#1023](https://github.com/CS-SI/eodag/pull/1023),
  [`c8189af`](https://github.com/CS-SI/eodag/commit/c8189af1c9f9f68ed793d9eadfba62028ae6d8d1))

- Resume interrupted assets download using HTTPDownload
  ([#1017](https://github.com/CS-SI/eodag/pull/1017),
  [`b800cac`](https://github.com/CS-SI/eodag/commit/b800cacb931478fa73798d3bf88553c4de655296))

- Standardize output tree ([#746](https://github.com/CS-SI/eodag/pull/746),
  [`fbf81ca`](https://github.com/CS-SI/eodag/commit/fbf81ca8ae4eb064f31c88da19dd1a7b0100a281))


## v2.12.0 (2024-02-19)

### Bug Fixes

- Add missing stac properties + fix typo ([#947](https://github.com/CS-SI/eodag/pull/947),
  [`6823a97`](https://github.com/CS-SI/eodag/commit/6823a976319611d99d7358236f63266573c28aca))

- Astraea_eod product-type specific metadata-mapping
  ([#980](https://github.com/CS-SI/eodag/pull/980),
  [`85498a9`](https://github.com/CS-SI/eodag/commit/85498a93c3a0aa5e4e27fb135685000254ec65aa))

- Cast loaded env vars type using config type-hints
  ([#987](https://github.com/CS-SI/eodag/pull/987),
  [`270f673`](https://github.com/CS-SI/eodag/commit/270f673d0a33cb3012ed1f61e02a0e444892299d))

- Common queryables ([#977](https://github.com/CS-SI/eodag/pull/977),
  [`bf9b8e9`](https://github.com/CS-SI/eodag/commit/bf9b8e948f0912aa9aaea3f1317041736ebd5fa6))

- Creodias and cop_dataspace quicklook ([#957](https://github.com/CS-SI/eodag/pull/957),
  [`300a2f8`](https://github.com/CS-SI/eodag/commit/300a2f8c3f5a5b80064b31865c8929c6d4604e48))

- Download of single asset with aws download and ignore assets not working
  ([#991](https://github.com/CS-SI/eodag/pull/991),
  [`80394d2`](https://github.com/CS-SI/eodag/commit/80394d20c0a68eb8ca6a59b373ce126081442356))

- Lib and server mode queryables ([#974](https://github.com/CS-SI/eodag/pull/974),
  [`4061b78`](https://github.com/CS-SI/eodag/commit/4061b78f61f798a123dd4efc79fa5ba3718a71e3))

- Missing tileIdentifier for creodias and cop_dataspace
  ([#1014](https://github.com/CS-SI/eodag/pull/1014),
  [`f8cfc68`](https://github.com/CS-SI/eodag/commit/f8cfc68a5d966eb1ce5a11cd1b58c354aad3205d))

- Remove rpc server ([#1011](https://github.com/CS-SI/eodag/pull/1011),
  [`ce74f22`](https://github.com/CS-SI/eodag/commit/ce74f222f6d9f646f9d35321072db2b18d7ea24f))

- Removed deprecated server context extension ([#891](https://github.com/CS-SI/eodag/pull/891),
  [`b6dd367`](https://github.com/CS-SI/eodag/commit/b6dd367341798de4202147376887c394c2794207))

- S2_msi_l2a removed for peps ([#969](https://github.com/CS-SI/eodag/pull/969),
  [`9b95224`](https://github.com/CS-SI/eodag/commit/9b952243e3164f430e9799d082d18e049d54b6cb))

- Stacsearch default assets ([#935](https://github.com/CS-SI/eodag/pull/935),
  [`9c1a67c`](https://github.com/CS-SI/eodag/commit/9c1a67c1cce787536771dc3c063e41d1c749c9f9))

- Update external product types reference ([#1009](https://github.com/CS-SI/eodag/pull/1009),
  [`f18edab`](https://github.com/CS-SI/eodag/commit/f18edab149dc8868d7ebff5131397d09e225776d))

- Update external product types reference ([#1013](https://github.com/CS-SI/eodag/pull/1013),
  [`44d725e`](https://github.com/CS-SI/eodag/commit/44d725e9923549c1af8c57527fdb3372abe91aa0))

- Update external product types reference ([#1019](https://github.com/CS-SI/eodag/pull/1019),
  [`6a6344c`](https://github.com/CS-SI/eodag/commit/6a6344c5b8c49ad623a42a60eabea23e61efd898))

- Update external product types reference ([#1025](https://github.com/CS-SI/eodag/pull/1025),
  [`3323b91`](https://github.com/CS-SI/eodag/commit/3323b919ac264ea3c070bcb6ff9ceab719560ed2))

- Update NOTICE files ([#1016](https://github.com/CS-SI/eodag/pull/1016),
  [`622012a`](https://github.com/CS-SI/eodag/commit/622012a17ceba532d6205f1056e97e5037beda09))

- Use earth search v1 endpoint ([#754](https://github.com/CS-SI/eodag/pull/754),
  [`acf207e`](https://github.com/CS-SI/eodag/commit/acf207e2af4706e7c4f6e2e7dc5eac40b8c4a796))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Wekeo2 wekeo-broker api ([#1010](https://github.com/CS-SI/eodag/pull/1010),
  [`7bcdbc5`](https://github.com/CS-SI/eodag/commit/7bcdbc50cadba60507a6fbe805d8d6843e50075a))

- **server**: Cdsapi download using _dc_qs parameter
  ([#958](https://github.com/CS-SI/eodag/pull/958),
  [`1af3d19`](https://github.com/CS-SI/eodag/commit/1af3d19486b88be5758ffc7277ccf4237fc1acae))

- **server**: Common queryables for given provider ([#978](https://github.com/CS-SI/eodag/pull/978),
  [`149b4e5`](https://github.com/CS-SI/eodag/commit/149b4e5b1ec8a70b54d07c4edef1d8e151d24508))

- **server**: Delete file after download without streaming
  ([#992](https://github.com/CS-SI/eodag/pull/992),
  [`819247c`](https://github.com/CS-SI/eodag/commit/819247c9c57389db3b51d3d402b09edc5938ad53))

- **server**: Properly display next page object ([#895](https://github.com/CS-SI/eodag/pull/895),
  [`17244d7`](https://github.com/CS-SI/eodag/commit/17244d76f607dd2cf6ba2079e37241dbfeb819c4))

Co-authored-by: Aubin Lambaré <aubin.lambare@csgroup.eu>

- **server**: Raise error if search fallback fails
  ([#1001](https://github.com/CS-SI/eodag/pull/1001),
  [`db70682`](https://github.com/CS-SI/eodag/commit/db706825954deecc7f9936946bbcdccfc27159c4))

### Build System

- Add missing requirements ([#1020](https://github.com/CS-SI/eodag/pull/1020),
  [`29b824e`](https://github.com/CS-SI/eodag/commit/29b824ea55145a2974747525156b26aa7e47fa0a))

- Bump version ([#1026](https://github.com/CS-SI/eodag/pull/1026),
  [`bf7607a`](https://github.com/CS-SI/eodag/commit/bf7607ab6249d4c74376c75a5386cf31b9356ac4))

- Correct PYTHONPATH ([#976](https://github.com/CS-SI/eodag/pull/976),
  [`3a90ea3`](https://github.com/CS-SI/eodag/commit/3a90ea384a07297d4889ccbf6187a15ba88e19d4))

Co-authored-by: Aubin Lambaré <aubin.lambare@csgroup.eu>

- Remove owslib version upper limit ([#1021](https://github.com/CS-SI/eodag/pull/1021),
  [`ebfd3ec`](https://github.com/CS-SI/eodag/commit/ebfd3ec21d0b1737b3537c3a3a0a67d627149256))

- **docs**: Pin sphinxcontrib dependencies ([#988](https://github.com/CS-SI/eodag/pull/988),
  [`fe2a514`](https://github.com/CS-SI/eodag/commit/fe2a51497fa806f856e9bbb4e3911e7c78dad17e))

### Continuous Integration

- Github actions coverage report update ([#1024](https://github.com/CS-SI/eodag/pull/1024),
  [`3f08774`](https://github.com/CS-SI/eodag/commit/3f08774f80bc49f3dc50457a3ba0ffeb90c3be75))

### Documentation

- Yaml settings quoting ([#1022](https://github.com/CS-SI/eodag/pull/1022),
  [`49209ff`](https://github.com/CS-SI/eodag/commit/49209ff081784ca7d31121899ce1eb8eda7d294c))

### Features

- Add cop(ads, cds) product types ([#898](https://github.com/CS-SI/eodag/pull/898),
  [`0dcc36d`](https://github.com/CS-SI/eodag/commit/0dcc36d255600669d69fd757f7af6d20e5a4faf1))

Co-authored-by: alambare-csgroup <aubin.lambare@csgroup.eu>

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Add COP_DEM product types in creodias_s3 ([#1002](https://github.com/CS-SI/eodag/pull/1002),
  [`9138237`](https://github.com/CS-SI/eodag/commit/9138237cbe1d01fb50d1ffc46741c21391851060))

- Add timeout error ([#982](https://github.com/CS-SI/eodag/pull/982),
  [`1a0e007`](https://github.com/CS-SI/eodag/commit/1a0e007d5364fd65c246e95ab7d9d591d69bde3e))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Awsdownload streaming ([#997](https://github.com/CS-SI/eodag/pull/997),
  [`72e7a48`](https://github.com/CS-SI/eodag/commit/72e7a48eba23f7debb89903f31d67555b53fcbce))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Download assets subset ([#932](https://github.com/CS-SI/eodag/pull/932),
  [`4f74c83`](https://github.com/CS-SI/eodag/commit/4f74c83f7d7c7a50a84f31dd51c015725331c018))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Http download through cdsapi ([#946](https://github.com/CS-SI/eodag/pull/946),
  [`4fa1b42`](https://github.com/CS-SI/eodag/commit/4fa1b4237c6d540444135c94ae17af776a64ce47))

* feat: http download through cdsapi * fix: product location update after http download assets

- Implement new core method get_queryables ([#917](https://github.com/CS-SI/eodag/pull/917),
  [`aa09d73`](https://github.com/CS-SI/eodag/commit/aa09d7315921b1ad74353f7d444f4c8d535c9d6d))

Co-authored-by: LAMBARE Aubin <aubin.lambare@csgroup.eu>

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- List provider-specific queryables ([#911](https://github.com/CS-SI/eodag/pull/911),
  [`40fe987`](https://github.com/CS-SI/eodag/commit/40fe987ec3a0644e660653a7a330dbaefca9d610))

- New provider for creodias s3 ([#986](https://github.com/CS-SI/eodag/pull/986),
  [`dda681a`](https://github.com/CS-SI/eodag/commit/dda681ae148c4fb555ab80d7ec2689dbbc8c2937))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Product type alias ([#905](https://github.com/CS-SI/eodag/pull/905),
  [`b61e2a0`](https://github.com/CS-SI/eodag/commit/b61e2a032fd9a66cced767223761dd0f432f9bd5))

Co-authored-by: leso-kn <info@lesosoftware.com>

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Setting conf_dir with an environment variable and fallback directory
  ([#927](https://github.com/CS-SI/eodag/pull/927),
  [`a2466ae`](https://github.com/CS-SI/eodag/commit/a2466ae68ecd0d5772e4f4ae9a60c5ee944c1971))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Use constraints for queryables ([#981](https://github.com/CS-SI/eodag/pull/981),
  [`fbfc7d0`](https://github.com/CS-SI/eodag/commit/fbfc7d09b96fcd1137525225b788a6903ee2d1eb))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- **server**: Stac alternate assets ([#961](https://github.com/CS-SI/eodag/pull/961),
  [`dd8d653`](https://github.com/CS-SI/eodag/commit/dd8d6530485fbeebe49dc0644de79ab36c475a1f))

### Refactoring

- Add some type hint ([#880](https://github.com/CS-SI/eodag/pull/880),
  [`a6be03b`](https://github.com/CS-SI/eodag/commit/a6be03b6f51ce35987b926bf4f721e68a1e27538))

- Queryables type to Annotated ([#1005](https://github.com/CS-SI/eodag/pull/1005),
  [`748e34e`](https://github.com/CS-SI/eodag/commit/748e34e7b6fbce812d50a581aaad24a96c70bb65))

- Type hints fixes ([#983](https://github.com/CS-SI/eodag/pull/983),
  [`0f094d5`](https://github.com/CS-SI/eodag/commit/0f094d51424e293557348c3740db8da6f3ab54d4))

- **config/productTypes**: Ignore unindexed fields ([#996](https://github.com/CS-SI/eodag/pull/996),
  [`8bffd13`](https://github.com/CS-SI/eodag/commit/8bffd130baaeadb0dc87704c9a8e97806306affd))

### Testing

- All product_types list instead of random ([#1003](https://github.com/CS-SI/eodag/pull/1003),
  [`c159fd0`](https://github.com/CS-SI/eodag/commit/c159fd00c246f021e28d5f9d9f0230ea6a55e7af))

- Fix env var loading in test_http_server ([#962](https://github.com/CS-SI/eodag/pull/962),
  [`5ebb90b`](https://github.com/CS-SI/eodag/commit/5ebb90b62ce36838b7fb5a0bcd02abdba14e80d8))

- Reset logger after tests ([#936](https://github.com/CS-SI/eodag/pull/936),
  [`c7d09b5`](https://github.com/CS-SI/eodag/commit/c7d09b5943b8919db7f268623cf73ef23e35e4e7))

Co-authored-by: alambare-csgroup <aubin.lambare@csgroup.eu>

- System agnostic fixes ([#934](https://github.com/CS-SI/eodag/pull/934),
  [`1631c88`](https://github.com/CS-SI/eodag/commit/1631c888351605a5fbbc4a60334aada0b8462b6c))


## v2.11.0 (2023-11-20)

### Bug Fixes

- 500 http error for server internal auth errors ([#794](https://github.com/CS-SI/eodag/pull/794),
  [`62977ba`](https://github.com/CS-SI/eodag/commit/62977ba5d86c30d9ced37adf2b3205da26e29614))

- Authenticate only when performing search ([#802](https://github.com/CS-SI/eodag/pull/802),
  [`dea2243`](https://github.com/CS-SI/eodag/commit/dea22430d8a055dd40484318e1c2743c1cdfffd0))

- Bad providers handling when searching by id ([#805](https://github.com/CS-SI/eodag/pull/805),
  [`2af2d90`](https://github.com/CS-SI/eodag/commit/2af2d90a17d990a6fb3dbd79d679720df7742c56))

- Creodias & cop_dataspace search result count ([#929](https://github.com/CS-SI/eodag/pull/929),
  [`c89cf52`](https://github.com/CS-SI/eodag/commit/c89cf52893de68b3fd7912858dd02a76fe6a0ea3))

- Creodias and cop_dataspace metadata_mapping ([#915](https://github.com/CS-SI/eodag/pull/915),
  [`f0257df`](https://github.com/CS-SI/eodag/commit/f0257dff077709f00696fef4d90ae91585a11787))

- Default dates on wekeo ([#840](https://github.com/CS-SI/eodag/pull/840),
  [`6a93f02`](https://github.com/CS-SI/eodag/commit/6a93f02d44346c89e047e9b399904139922b879f))

- Docker user home dir ([#764](https://github.com/CS-SI/eodag/pull/764),
  [`d24850a`](https://github.com/CS-SI/eodag/commit/d24850aee464afd938875be5d316955035ddb8e1))

- Ewkt extraction for creodias and cop_dataspace ([#868](https://github.com/CS-SI/eodag/pull/868),
  [`7e199dc`](https://github.com/CS-SI/eodag/commit/7e199dc56bbe18440fd16f3e9ff8428650572540))

- Exceptions handling update ([#829](https://github.com/CS-SI/eodag/pull/829),
  [`a721a4e`](https://github.com/CS-SI/eodag/commit/a721a4e9d3461ef431805489394c0ebf164ab6f8))

- Extract USGS tarfiles ([#759](https://github.com/CS-SI/eodag/pull/759),
  [`9062756`](https://github.com/CS-SI/eodag/commit/90627560ce0c66f7ad5d38fc4c3960c76e1f8932))

- Flask 2.2.x as max version ([#722](https://github.com/CS-SI/eodag/pull/722),
  [`c7b8e24`](https://github.com/CS-SI/eodag/commit/c7b8e24d8970ac2889732304968df9e1e214f69b))

- Forbidden and unauthorized errors in token auth ([#791](https://github.com/CS-SI/eodag/pull/791),
  [`caff0bc`](https://github.com/CS-SI/eodag/commit/caff0bc12f7fa4af8238030af43700b5bd6d8c0e))

- Handle mundi missing storageStatus ([#743](https://github.com/CS-SI/eodag/pull/743),
  [`9d5caba`](https://github.com/CS-SI/eodag/commit/9d5caba74657b84a471b7e0392617c370c5f0ed1))

- Limit jsonpath-ng version ([#825](https://github.com/CS-SI/eodag/pull/825),
  [`18b22d5`](https://github.com/CS-SI/eodag/commit/18b22d5677bd39c14ed22369d4956df69b5281dc))

- Missing auth in search results ([#793](https://github.com/CS-SI/eodag/pull/793),
  [`3c7b74b`](https://github.com/CS-SI/eodag/commit/3c7b74bbc2efc05d7cb77e37df64cd0c8e1f3d44))

- Missing provider in stac downloadLink ([#774](https://github.com/CS-SI/eodag/pull/774),
  [`8561219`](https://github.com/CS-SI/eodag/commit/856121900f6d973eca9d2ad3c0de61bbd706ae2c))

- More verbose keycloak auth plugin errors ([#771](https://github.com/CS-SI/eodag/pull/771),
  [`ff32294`](https://github.com/CS-SI/eodag/commit/ff32294cd9cb36985a461dccd8484a585a784788))

- Plugin manager rebuild ([#919](https://github.com/CS-SI/eodag/pull/919),
  [`1d9f92c`](https://github.com/CS-SI/eodag/commit/1d9f92c563508322dd3b943845f8530087753cfa))

- Product-type specific metadata-mapping ([#830](https://github.com/CS-SI/eodag/pull/830),
  [`4650184`](https://github.com/CS-SI/eodag/commit/4650184637feaaee7e39f8d84da954789b26f7c3))

- Readthedocs git fetch unshallow ([#777](https://github.com/CS-SI/eodag/pull/777),
  [`ce9b54a`](https://github.com/CS-SI/eodag/commit/ce9b54a672a7055432b2c2905da86e1f49647c35))

- Remove module from logging and shorten loggers names
  ([#885](https://github.com/CS-SI/eodag/pull/885),
  [`93e61ca`](https://github.com/CS-SI/eodag/commit/93e61ca2f4d53f7da9d26cab44e9710092bf1dea))

- Remove mundi provider ([#890](https://github.com/CS-SI/eodag/pull/890),
  [`c580617`](https://github.com/CS-SI/eodag/commit/c5806179578bf4887ace271b5b284788e364b917))

- Remove step parameter in CAMS_EAC4 configuration ([#749](https://github.com/CS-SI/eodag/pull/749),
  [`c38d36e`](https://github.com/CS-SI/eodag/commit/c38d36ec0be2c490d04060030c10726ecf327972))

- Renamed shapely exceptions ([#824](https://github.com/CS-SI/eodag/pull/824),
  [`886e046`](https://github.com/CS-SI/eodag/commit/886e04651619965b9869e56cc90d2acc9b5ba389))

- Request-ftp requirement ([#781](https://github.com/CS-SI/eodag/pull/781),
  [`fa617ce`](https://github.com/CS-SI/eodag/commit/fa617ce0d31fed9941fb178cfeb1e30ed2a16cd8))

- Return only user requested item if id is present ([#856](https://github.com/CS-SI/eodag/pull/856),
  [`5165658`](https://github.com/CS-SI/eodag/commit/5165658467e52e2c1d7f5573ef3b1db466a2591b))

- Sanitize downloaded assets paths ([#745](https://github.com/CS-SI/eodag/pull/745),
  [`50d6e60`](https://github.com/CS-SI/eodag/commit/50d6e60396cff60f6373ab64af5a0229a77e6906))

- Sara provider conf ([#828](https://github.com/CS-SI/eodag/pull/828),
  [`c8ef1b9`](https://github.com/CS-SI/eodag/commit/c8ef1b9536a4ac91479dc0d9e6cdf04da6f533f0))

- Search fallback with raise_errors and empty results
  ([#807](https://github.com/CS-SI/eodag/pull/807),
  [`78179d5`](https://github.com/CS-SI/eodag/commit/78179d54d5f53e99d49cade6738b7a4b7568e09d))

- Search preferred provider and wekeo job error handling
  ([#790](https://github.com/CS-SI/eodag/pull/790),
  [`2eb52b8`](https://github.com/CS-SI/eodag/commit/2eb52b8300e3859712c74412a97d15181865ce97))

- Server-mode download for ext api providers ([#751](https://github.com/CS-SI/eodag/pull/751),
  [`3e1ccd4`](https://github.com/CS-SI/eodag/commit/3e1ccd42570453d1e8bea9c26c74ee767ded3d57))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Set creodias search timeout to 20s ([#894](https://github.com/CS-SI/eodag/pull/894),
  [`19d7d6b`](https://github.com/CS-SI/eodag/commit/19d7d6b21f378d8eb4566e4887bbf21b6fca0538))

- Set responses max version lt 0.24.0 ([#913](https://github.com/CS-SI/eodag/pull/913),
  [`430592a`](https://github.com/CS-SI/eodag/commit/430592a941773e6886a72d9bfcd7d7e2d72be8b9))

- Simplified mundi auth using HTTPHeaderAuth ([#804](https://github.com/CS-SI/eodag/pull/804),
  [`ee112d3`](https://github.com/CS-SI/eodag/commit/ee112d3035bcc70855a6efa115dac8cb1763e538))

- Update creodias auth to Creodias-new ([#763](https://github.com/CS-SI/eodag/pull/763),
  [`bd59008`](https://github.com/CS-SI/eodag/commit/bd59008d0bf2ec8ffe9c8daf3b882587c8775ba3))

- Update external product types reference ([#720](https://github.com/CS-SI/eodag/pull/720),
  [`072a0f2`](https://github.com/CS-SI/eodag/commit/072a0f210413b0a4b3c5689762fee498afedab86))

- Update external product types reference ([#729](https://github.com/CS-SI/eodag/pull/729),
  [`9d0e561`](https://github.com/CS-SI/eodag/commit/9d0e5617200c2035563c25a793caa8355b89e4ba))

- Update external product types reference ([#731](https://github.com/CS-SI/eodag/pull/731),
  [`2ff150a`](https://github.com/CS-SI/eodag/commit/2ff150a4e8274569d0baa0780ed6a6a750e64e35))

- Update external product types reference ([#737](https://github.com/CS-SI/eodag/pull/737),
  [`fdde58e`](https://github.com/CS-SI/eodag/commit/fdde58ebfc91c1c09d68ff51bbc09b8fb78649b2))

- Update external product types reference ([#738](https://github.com/CS-SI/eodag/pull/738),
  [`d9708f9`](https://github.com/CS-SI/eodag/commit/d9708f98c5a99e3ece37b24b556b0848463d2fe8))

- Update external product types reference ([#762](https://github.com/CS-SI/eodag/pull/762),
  [`6034cd1`](https://github.com/CS-SI/eodag/commit/6034cd1a2a595d294474c97301bd0dd598da79be))

- Update external product types reference ([#775](https://github.com/CS-SI/eodag/pull/775),
  [`e40b40d`](https://github.com/CS-SI/eodag/commit/e40b40d910c60e7445fc2e043f21abaa12b45bca))

- Update external product types reference ([#788](https://github.com/CS-SI/eodag/pull/788),
  [`9acf017`](https://github.com/CS-SI/eodag/commit/9acf017451f71c5488011f3add086a9936cfffc8))

- Update external product types reference ([#818](https://github.com/CS-SI/eodag/pull/818),
  [`e100b96`](https://github.com/CS-SI/eodag/commit/e100b96b75ee661ba6fce0555ee052b455b28705))

- Update external product types reference ([#838](https://github.com/CS-SI/eodag/pull/838),
  [`cb0217b`](https://github.com/CS-SI/eodag/commit/cb0217b5772a44fd7ffb384f0eda96fbd48e9bea))

- Update external product types reference ([#877](https://github.com/CS-SI/eodag/pull/877),
  [`3cb6ca9`](https://github.com/CS-SI/eodag/commit/3cb6ca9f12bae3cbf2013dc2f1cb60399ada0eb9))

- Update server body model to search by ids ([#822](https://github.com/CS-SI/eodag/pull/822),
  [`d0869f9`](https://github.com/CS-SI/eodag/commit/d0869f9105cb2051a8976245f1896f4b919c40b0))

- Use refresh token to get access token in keycloak auth
  ([#921](https://github.com/CS-SI/eodag/pull/921),
  [`67e0943`](https://github.com/CS-SI/eodag/commit/67e0943793dd20c2c6c6271b9e1d8168fdc42ed3))

- **server**: Correct links in stac model ([#813](https://github.com/CS-SI/eodag/pull/813),
  [`3371426`](https://github.com/CS-SI/eodag/commit/3371426f4f814d78817771feea718c91c09764a5))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- **server**: Handle DownloadError and RequestError in server mode
  ([#806](https://github.com/CS-SI/eodag/pull/806),
  [`3e9ec56`](https://github.com/CS-SI/eodag/commit/3e9ec56d1e0e83bc1bd00244f1ad9af7be3c44af))

- **server**: List providers in stac calalogs ([#884](https://github.com/CS-SI/eodag/pull/884),
  [`e98e0a9`](https://github.com/CS-SI/eodag/commit/e98e0a9028f5edb3b771c000e70e346f17a9208c))

- **server**: Load json string intersects param as dict
  ([#821](https://github.com/CS-SI/eodag/pull/821),
  [`5b98144`](https://github.com/CS-SI/eodag/commit/5b981447e127f35b3014aad073e9126b15c39ed0))

- **server**: Missing intersects parameter in request body model
  ([#797](https://github.com/CS-SI/eodag/pull/797),
  [`1a627c7`](https://github.com/CS-SI/eodag/commit/1a627c704f3e984d1a3f94b78cbccab91b83cd85))

- **server**: Multithreaded requests ([#843](https://github.com/CS-SI/eodag/pull/843),
  [`5e389e4`](https://github.com/CS-SI/eodag/commit/5e389e4e26d9e8058fd3919170908514233db7fd))

- **server**: Opened time intervals ([#837](https://github.com/CS-SI/eodag/pull/837),
  [`fefce06`](https://github.com/CS-SI/eodag/commit/fefce060c85b3831232e3111b6a16f34ac474b36))

- **server**: Provider setting in server mode ([#808](https://github.com/CS-SI/eodag/pull/808),
  [`9bebfed`](https://github.com/CS-SI/eodag/commit/9bebfedfa9a98e72efabfe420b7035e90e7fd640))

- **server**: Raise_errors disabled for server search fallback
  ([#812](https://github.com/CS-SI/eodag/pull/812),
  [`0b62dab`](https://github.com/CS-SI/eodag/commit/0b62dab313803c1655bae1d7afbb5dd5672c240c))

- **server**: Use only one of bbox and intersects on search
  ([#796](https://github.com/CS-SI/eodag/pull/796),
  [`4b1397b`](https://github.com/CS-SI/eodag/commit/4b1397bfdc79b0b9be0be3fc825df40949f4acae))

### Build System

- Bump version ([#780](https://github.com/CS-SI/eodag/pull/780),
  [`829f8a3`](https://github.com/CS-SI/eodag/commit/829f8a31a1cf67d046763a2fae1e2cd62e8f1c45))

- Bump version ([#931](https://github.com/CS-SI/eodag/pull/931),
  [`0abdf29`](https://github.com/CS-SI/eodag/commit/0abdf29a82f312960c0a1efc65d19b1f34e9331f))

### Continuous Integration

- Coverage to distinct pr comments ([#723](https://github.com/CS-SI/eodag/pull/723),
  [`f66ed1e`](https://github.com/CS-SI/eodag/commit/f66ed1ea46ae46391447f08c341a89adbd11517f))

- Latest pandoc version in gh actions ([#744](https://github.com/CS-SI/eodag/pull/744),
  [`274b6b9`](https://github.com/CS-SI/eodag/commit/274b6b9083d946bd98709ec44aa3409078bfe284))

- Limit fetch product types action PR body length ([#727](https://github.com/CS-SI/eodag/pull/727),
  [`bbd367a`](https://github.com/CS-SI/eodag/commit/bbd367a473c015928db5344b1df70ae1cbb56863))

- Remove tests from coverage ([#717](https://github.com/CS-SI/eodag/pull/717),
  [`e0108b2`](https://github.com/CS-SI/eodag/commit/e0108b26f7ab8b2b5ddf810ed47838ea6d14c1b8))

- Use flake8-eradicate and remove commented out code
  ([#832](https://github.com/CS-SI/eodag/pull/832),
  [`d824947`](https://github.com/CS-SI/eodag/commit/d824947150f3920f4ac88b10edd179990cb5f9fa))

### Documentation

- Corrected typo in the "Serialize/Deserialize" page of the documentation
  ([#920](https://github.com/CS-SI/eodag/pull/920),
  [`9a16a50`](https://github.com/CS-SI/eodag/commit/9a16a500177d10d53ab60d7a3affda860ce3e2a8))

- Extend documentation for guess_product_type and other minor updates
  ([#756](https://github.com/CS-SI/eodag/pull/756),
  [`9826723`](https://github.com/CS-SI/eodag/commit/982672369be388eea21234a593b99983ff6a3b75))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Update notice ([#724](https://github.com/CS-SI/eodag/pull/724),
  [`c328060`](https://github.com/CS-SI/eodag/commit/c328060affc212afe4a9e66f80f04854d4ec774d))

- Update openapi static spec ([#846](https://github.com/CS-SI/eodag/pull/846),
  [`ec1d847`](https://github.com/CS-SI/eodag/commit/ec1d847a11367a16d87d240e0e6fdeb65b1c6a74))

- Update overview graph ([#893](https://github.com/CS-SI/eodag/pull/893),
  [`b2e448f`](https://github.com/CS-SI/eodag/commit/b2e448f617651aff2014db0cf37385414e91d55a))

### Features

- Add providers metadata to items endpoint ([#879](https://github.com/CS-SI/eodag/pull/879),
  [`7f520bc`](https://github.com/CS-SI/eodag/commit/7f520bcc8d8005184e5f785a714ac4dee7388ea2))

- Add static type information ([#863](https://github.com/CS-SI/eodag/pull/863),
  [`094cdb9`](https://github.com/CS-SI/eodag/commit/094cdb97592302305b00be370b6db88b3c9d9e5e))

- Cop-dem through creodias ([#882](https://github.com/CS-SI/eodag/pull/882),
  [`176ac95`](https://github.com/CS-SI/eodag/commit/176ac95fce669078c0ba5e6b1035fec619280598))

- Eodag_providers_cfg_file env var ([#836](https://github.com/CS-SI/eodag/pull/836),
  [`ec4c868`](https://github.com/CS-SI/eodag/commit/ec4c868fc2bc885301dbd94a62805119f3cca9f3))

- Fallback mechanism for search
  ([`df440aa`](https://github.com/CS-SI/eodag/commit/df440aa6b35236a357ab0bbfd5d93fa94cefd3a8))

- Flask to FastAPI ([#701](https://github.com/CS-SI/eodag/pull/701),
  [`4c373fd`](https://github.com/CS-SI/eodag/commit/4c373fd081a54f93b1bcda3d669f19aaf1a05c7d))

- Helm chart ([#739](https://github.com/CS-SI/eodag/pull/739),
  [`92a537f`](https://github.com/CS-SI/eodag/commit/92a537f7811a06f336712de6b8c07a9b80cf6de6))

Co-authored-by: Julia Lahovnik <julia.lahovnik@csgroup.eu>

- Keep origin assets in the stac server response ([#681](https://github.com/CS-SI/eodag/pull/681),
  [`2441b63`](https://github.com/CS-SI/eodag/commit/2441b6392135501c0f215d031b94c5537b5d4e05))

- Per provider search timetout ([#841](https://github.com/CS-SI/eodag/pull/841),
  [`c63e4c7`](https://github.com/CS-SI/eodag/commit/c63e4c70e854dfcca8eef3ebc4b7a924ec73eeeb))

- Python 3.12 update ([#892](https://github.com/CS-SI/eodag/pull/892),
  [`4c340b0`](https://github.com/CS-SI/eodag/commit/4c340b09b0702ad90bb9110fc4cdf74c58a01f9c))

- Removed Python 3.7 support ([#903](https://github.com/CS-SI/eodag/pull/903),
  [`790df60`](https://github.com/CS-SI/eodag/commit/790df608a1a1aa1dbe87198d883602ecf82176e0))

- Restore pruned providers when configuration is updated
  ([#844](https://github.com/CS-SI/eodag/pull/844),
  [`cd527f1`](https://github.com/CS-SI/eodag/commit/cd527f1cad5855fa3f44ac1ebe8a2b909b40dfc2))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Return all available providers for collection ([#835](https://github.com/CS-SI/eodag/pull/835),
  [`a2506e6`](https://github.com/CS-SI/eodag/commit/a2506e6f92bccd0a6730480ebac98ca9257a5322))

- Roll back creodias to opensearch plugin ([#866](https://github.com/CS-SI/eodag/pull/866),
  [`6bdb107`](https://github.com/CS-SI/eodag/commit/6bdb107f5704df1fd868038d58617c8ac1d10779))

- Server search by ids ([#776](https://github.com/CS-SI/eodag/pull/776),
  [`fdd86a0`](https://github.com/CS-SI/eodag/commit/fdd86a08c40704a96ef8bbfc973078135af61db5))

- Server-mode parallel requests ([#741](https://github.com/CS-SI/eodag/pull/741),
  [`791fb4d`](https://github.com/CS-SI/eodag/commit/791fb4d6a95cc2145d56ceac7c59ecaec08c3fec))

- Server-mode streamed downloads ([#742](https://github.com/CS-SI/eodag/pull/742),
  [`6cc222a`](https://github.com/CS-SI/eodag/commit/6cc222a7e8e3bdba17c928380c99de1da795660b))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Thread id and server requests in debug logs ([#842](https://github.com/CS-SI/eodag/pull/842),
  [`2ff5763`](https://github.com/CS-SI/eodag/commit/2ff576397ad2ca5d8a839e6a0d478689ecea6b72))

- Update wekeo sentinel product types ([#902](https://github.com/CS-SI/eodag/pull/902),
  [`9e881ac`](https://github.com/CS-SI/eodag/commit/9e881acd332eeb36257ae1746bb0d925517c7d3a))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Use `downloadLink` if exists for STAC providers ([#757](https://github.com/CS-SI/eodag/pull/757),
  [`73b17aa`](https://github.com/CS-SI/eodag/commit/73b17aadf7eb92a2b156216aa6f84b9e4d186c31))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Wekeo driver update and new product types ([#798](https://github.com/CS-SI/eodag/pull/798),
  [`db336eb`](https://github.com/CS-SI/eodag/commit/db336ebe9e3359bc3549e546948ef59c54b632ae))

Co-authored-by: Julia Lahovnik <julia.lahovnik@csgroup.eu>

Co-authored-by: Aubin Lambaré <aubin.lambare@csgroup.eu>

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Wekeo provider ([#772](https://github.com/CS-SI/eodag/pull/772),
  [`cd7ad76`](https://github.com/CS-SI/eodag/commit/cd7ad766bf286e64dac10b3ac154f4a583961f01))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

Co-authored-by: Sylvain Brunato <61419125+sbrunato@users.noreply.github.com>

- **cop_ds**: Swap search plugin to opensearch ([#883](https://github.com/CS-SI/eodag/pull/883),
  [`42de3d8`](https://github.com/CS-SI/eodag/commit/42de3d8038269acbe282a2d9b2c93cd7e5ae316a))

- **server**: Add queryables endpoints ([#795](https://github.com/CS-SI/eodag/pull/795),
  [`03c72bc`](https://github.com/CS-SI/eodag/commit/03c72bcf1612639f8383dee32f3405d2042fd4af))

### Performance Improvements

- **creodias**: Use zipper URL to avoid unecessary redirect
  ([#819](https://github.com/CS-SI/eodag/pull/819),
  [`812bc56`](https://github.com/CS-SI/eodag/commit/812bc56b1cc74b3f2edf13efd665a5582d8a7f0c))

### Refactoring

- Remove object inheritance ([#881](https://github.com/CS-SI/eodag/pull/881),
  [`6e3277a`](https://github.com/CS-SI/eodag/commit/6e3277a4c53a8bdd53c4e5f4ede4e4ee48ee0e8c))

- Some search methods moved to base plugin ([#878](https://github.com/CS-SI/eodag/pull/878),
  [`177d771`](https://github.com/CS-SI/eodag/commit/177d77120e1c5bda5c84af638bdaa49a07edf5f4))

- Use wkt format for geometry in providers config ([#899](https://github.com/CS-SI/eodag/pull/899),
  [`f323366`](https://github.com/CS-SI/eodag/commit/f323366a3594cfbe97a671ec17535d6dff1b1cea))

- **server**: Get STAC collection by id ([#867](https://github.com/CS-SI/eodag/pull/867),
  [`f4eec1f`](https://github.com/CS-SI/eodag/commit/f4eec1fd64dbdb6de55462439f924a60d1623a4f))

### Testing

- Hydroweb_next public product-type usage ([#926](https://github.com/CS-SI/eodag/pull/926),
  [`09a9b79`](https://github.com/CS-SI/eodag/commit/09a9b79e8b9c9ccb412cb75e6d66de2e39892a05))

- Update test_end_to_end_complete_peps ([#872](https://github.com/CS-SI/eodag/pull/872),
  [`32c2654`](https://github.com/CS-SI/eodag/commit/32c2654aab6a70776703437eb8e8729d78fc18d7))

- Update test_search_by_tile ([#925](https://github.com/CS-SI/eodag/pull/925),
  [`4d2b7e3`](https://github.com/CS-SI/eodag/commit/4d2b7e3a63b49603d8cc1d0dda4d9be012d5d2e8))


## v2.10.0 (2023-04-18)

### Bug Fixes

- Clear plugin context before performing search by id
  ([#693](https://github.com/CS-SI/eodag/pull/693),
  [`324bc80`](https://github.com/CS-SI/eodag/commit/324bc80ddcbd1e4450f49dc93585deec41aac702))

- Enable default search geometry usage in FilterLatestIntersect crunch
  ([#707](https://github.com/CS-SI/eodag/pull/707),
  [`47452e5`](https://github.com/CS-SI/eodag/commit/47452e54c00659a4992df9bd1368cfbd21e1ccaf))

- Eodag-server docker sigterm ([#702](https://github.com/CS-SI/eodag/pull/702),
  [`08a4fbc`](https://github.com/CS-SI/eodag/commit/08a4fbc858a4deaa69431e923ab7b7355153e582))

- Guess_product_type should return given productType if specified
  ([#694](https://github.com/CS-SI/eodag/pull/694),
  [`913b5d8`](https://github.com/CS-SI/eodag/commit/913b5d8caa24d1dcd76616cedcfd8cb867b549cc))

- Items url through STAC search endpoint ([#698](https://github.com/CS-SI/eodag/pull/698),
  [`5ef8dac`](https://github.com/CS-SI/eodag/commit/5ef8dac76e5187e80747c778b919eb8280a369e0))

- Minimal pagination when searching by id ([#696](https://github.com/CS-SI/eodag/pull/696),
  [`d128d9c`](https://github.com/CS-SI/eodag/commit/d128d9c1ee839d08fcdd12e0e3685b3bb6aa462e))

- Sensortype missing when serving STAC items for discovered product types
  ([#699](https://github.com/CS-SI/eodag/pull/699),
  [`e564348`](https://github.com/CS-SI/eodag/commit/e5643482cce0f5e4f71685e9bf15b07827c1cfd4))

- Stac server catalogs cloud-cover filtering ([#705](https://github.com/CS-SI/eodag/pull/705),
  [`257eda4`](https://github.com/CS-SI/eodag/commit/257eda49272de8919f938083a81add9a34ef15c6))

- Stac server catalogs dates filtering ([#706](https://github.com/CS-SI/eodag/pull/706),
  [`6ff2907`](https://github.com/CS-SI/eodag/commit/6ff2907f7f0774237e550f587ad2b430389e69d3))

- Update external product types reference ([#703](https://github.com/CS-SI/eodag/pull/703),
  [`cbce353`](https://github.com/CS-SI/eodag/commit/cbce3538e142a6d6526478befd9700a2016351b9))

- Update external product types reference ([#712](https://github.com/CS-SI/eodag/pull/712),
  [`36fd6ae`](https://github.com/CS-SI/eodag/commit/36fd6aed8eda0964ccc6dc48d560d5f686d5bd5f))

- Update STAC browser catalogUrl param name ([#704](https://github.com/CS-SI/eodag/pull/704),
  [`c9bba53`](https://github.com/CS-SI/eodag/commit/c9bba53129226aef77466f1e34457eb4cd1046cc))

### Build System

- Bump version ([#716](https://github.com/CS-SI/eodag/pull/716),
  [`937c415`](https://github.com/CS-SI/eodag/commit/937c415548ac05446d485c1377b8fe438346e395))

### Documentation

- Contact email update ([#695](https://github.com/CS-SI/eodag/pull/695),
  [`e7873c0`](https://github.com/CS-SI/eodag/commit/e7873c05a43589f7c65a5fff115a1b74b1a8ee75))

- Providers description update ([#714](https://github.com/CS-SI/eodag/pull/714),
  [`035f5a7`](https://github.com/CS-SI/eodag/commit/035f5a74fb3c2a21f0f5372209162936a13a5c24))

- Ref to dockerhub eodag-server ([#715](https://github.com/CS-SI/eodag/pull/715),
  [`1596872`](https://github.com/CS-SI/eodag/commit/1596872284f30017553110d9fd43de9995ae2760))

### Features

- Better generated stac catalogs title & desc ([#710](https://github.com/CS-SI/eodag/pull/710),
  [`3018325`](https://github.com/CS-SI/eodag/commit/3018325990359f1f8092f434d36d138eb3f787da))

* feat: better generated stac catalogs title & desc

* docs: update stac browser screenshot

- Hydroweb_next as new provider ([#711](https://github.com/CS-SI/eodag/pull/711),
  [`ba515f3`](https://github.com/CS-SI/eodag/commit/ba515f30b6ee97ad8471b1edf2f5af5b70fe1c39))

- Search by tile using tileIdentifier ([#713](https://github.com/CS-SI/eodag/pull/713),
  [`98eae2e`](https://github.com/CS-SI/eodag/commit/98eae2ee770a1356ff7da39a3012aa7d2599f119))

### Refactoring

- Stac API 1.0.0-beta.3 to 1.0.0-rc.3 ([#697](https://github.com/CS-SI/eodag/pull/697),
  [`9bbad5b`](https://github.com/CS-SI/eodag/commit/9bbad5b0702da67fbad0c58d7153e7720a849d11))

- Stac server install in dockerfile ([#700](https://github.com/CS-SI/eodag/pull/700),
  [`1fb0807`](https://github.com/CS-SI/eodag/commit/1fb08074c6fc68a389142655065b5a9850b67cf1))

### Testing

- Advanced stac server tests ([#708](https://github.com/CS-SI/eodag/pull/708),
  [`919dd3c`](https://github.com/CS-SI/eodag/commit/919dd3c0755460597ab51a5af89715376d246917))


## v2.9.2 (2023-03-31)

### Bug Fixes

- Cdsapi default dates and refactor ([#672](https://github.com/CS-SI/eodag/pull/672),
  [`52cacf3`](https://github.com/CS-SI/eodag/commit/52cacf3b91425510b02ccdd661e480a378d3fa18))

- Ecmwfapi default dates and refactor ([#678](https://github.com/CS-SI/eodag/pull/678),
  [`873e45d`](https://github.com/CS-SI/eodag/commit/873e45dd75eb3b229ab51b2b3c80ffe6e8c10fd9))

- Peps storageStatus update ([#677](https://github.com/CS-SI/eodag/pull/677),
  [`16cdf28`](https://github.com/CS-SI/eodag/commit/16cdf28dd29f038e15fc97e91b1ccde0fe5f1354))

- Shapely transform inverted xy and warning ([#667](https://github.com/CS-SI/eodag/pull/667),
  [`e8c5a47`](https://github.com/CS-SI/eodag/commit/e8c5a47408a256139b6e864a2779a8b10947fa17))

- Update external product types for unknown provider
  ([#682](https://github.com/CS-SI/eodag/pull/682),
  [`3769147`](https://github.com/CS-SI/eodag/commit/37691478ab3e818695f84fb484d91ee85a77fa8f))

- Update external product types reference ([#691](https://github.com/CS-SI/eodag/pull/691),
  [`f271cb3`](https://github.com/CS-SI/eodag/commit/f271cb39985f26f74f6e54cb63176e943edb2bf0))

Co-authored-by: github-actions[bot] <github-actions[bot]@users.noreply.github.com>

- Update tests, code, ci to remove warnings ([#668](https://github.com/CS-SI/eodag/pull/668),
  [`93e33ee`](https://github.com/CS-SI/eodag/commit/93e33eeeaac63f40b3aa8255f54b483c2fcc9264))

- Urllib errors catch during search/discover ([#688](https://github.com/CS-SI/eodag/pull/688),
  [`07a2b79`](https://github.com/CS-SI/eodag/commit/07a2b79c88fad604d464db9d989abef248484f5a))

### Build System

- Bump version ([#689](https://github.com/CS-SI/eodag/pull/689),
  [`6584ef2`](https://github.com/CS-SI/eodag/commit/6584ef2f8a3c760266069defc9511337dd832ec8))

### Continuous Integration

- Upgrade gh-actions ([#670](https://github.com/CS-SI/eodag/pull/670),
  [`14ece44`](https://github.com/CS-SI/eodag/commit/14ece4499ce50e2edd366de18d9b49a1e23f7486))

### Documentation

- Pin sphinx-book-theme version ([#665](https://github.com/CS-SI/eodag/pull/665),
  [`1bbfaab`](https://github.com/CS-SI/eodag/commit/1bbfaab095a0e0bf4b5b68f9130fa57d37614f0f))

- Update readthedocs img ([#675](https://github.com/CS-SI/eodag/pull/675),
  [`14c9504`](https://github.com/CS-SI/eodag/commit/14c9504aaae0a64444e084c82e9640dad6ca4709))

### Features

- Add Planetary Computer as a new provider ([#659](https://github.com/CS-SI/eodag/pull/659),
  [`372afbe`](https://github.com/CS-SI/eodag/commit/372afbec3333e5538d9ac91cba2491d087b69a64))

Co-authored-by: Sylvain Brunato <61419125+sbrunato@users.noreply.github.com>

- Customized and faster deepcopy ([#664](https://github.com/CS-SI/eodag/pull/664),
  [`d071212`](https://github.com/CS-SI/eodag/commit/d0712120014ee1a20eed0f0b4d772ac344f2e308))

- Fetch product types optimization ([#683](https://github.com/CS-SI/eodag/pull/683),
  [`e6c220c`](https://github.com/CS-SI/eodag/commit/e6c220cbafe1b7bd46453bfb6f485e6946d38dae))

### Refactoring

- Metadata parsing ([#669](https://github.com/CS-SI/eodag/pull/669),
  [`bf33e4c`](https://github.com/CS-SI/eodag/commit/bf33e4c5105bbd28c7221094ea9c039820ab3afe))

- Update ext product types list ([#690](https://github.com/CS-SI/eodag/pull/690),
  [`36870f9`](https://github.com/CS-SI/eodag/commit/36870f9f3b613bf35ef5ce9c12350a0820a68433))

### Testing

- Fix CdsApi test following provider api update ([#679](https://github.com/CS-SI/eodag/pull/679),
  [`34c41ac`](https://github.com/CS-SI/eodag/commit/34c41ac9396dab0bce9b76f1f9244ed67d726701))

- Rewritten test_eoproduct_register_downloader_resolve_ignored
  ([#666](https://github.com/CS-SI/eodag/pull/666),
  [`c6c9d06`](https://github.com/CS-SI/eodag/commit/c6c9d06772e6ade9c8acf049b09945a37737dc39))


## v2.9.1 (2023-02-27)

### Bug Fixes

- Creodias max_items_per_page ([#649](https://github.com/CS-SI/eodag/pull/649),
  [`6a62711`](https://github.com/CS-SI/eodag/commit/6a62711aece1672564b9357cc74734b793944e4e))

- Prevent duplicated ODataV4Search custom args ([#652](https://github.com/CS-SI/eodag/pull/652),
  [`7a372eb`](https://github.com/CS-SI/eodag/commit/7a372ebeb4e378a171ffbb12d6748604cbff3ebe))

- Search errors handling ([#660](https://github.com/CS-SI/eodag/pull/660),
  [`d378061`](https://github.com/CS-SI/eodag/commit/d3780617dcd1fbcb80d0c3e32b537f893a98ac48))

### Build System

- Bump version ([#661](https://github.com/CS-SI/eodag/pull/661),
  [`1be8da1`](https://github.com/CS-SI/eodag/commit/1be8da11bb2dc6bf5a4defb80c38c1314fb8a50f))

### Features

- Customize requests headers with EODAG version as user agent
  ([#656](https://github.com/CS-SI/eodag/pull/656),
  [`0a3d308`](https://github.com/CS-SI/eodag/commit/0a3d308f6204f87413d34838ac73dd2dab07ef02))

- Eoproduct defaultGeometry property ([#653](https://github.com/CS-SI/eodag/pull/653),
  [`a10c807`](https://github.com/CS-SI/eodag/commit/a10c807e255da89c0138368a2d1592d204f9a7f4))

- Mundi georss geometries handling ([#654](https://github.com/CS-SI/eodag/pull/654),
  [`0194b16`](https://github.com/CS-SI/eodag/commit/0194b162c83a93a6c214c29186f478e0eaaa8104))

- New provider cop_dataspace ([#658](https://github.com/CS-SI/eodag/pull/658),
  [`e925418`](https://github.com/CS-SI/eodag/commit/e925418af0787c29957a92aaaf4eabdd511545a6))

- Sentinel5p and other product types updates for creodias mundi and onda
  ([#657](https://github.com/CS-SI/eodag/pull/657),
  [`e54ba86`](https://github.com/CS-SI/eodag/commit/e54ba8620457d4995589c4b4995b08d0cbfaaff3))


## v2.9.0 (2023-02-16)

### Bug Fixes

- Better download wait time precision ([#621](https://github.com/CS-SI/eodag/pull/621),
  [`8558510`](https://github.com/CS-SI/eodag/commit/855851045a7280efb55d411d478b382ca774d1e6))

- Check usgs available downloadSystem in download_options
  ([#612](https://github.com/CS-SI/eodag/pull/612),
  [`4a0d689`](https://github.com/CS-SI/eodag/commit/4a0d68987de913040e0ba16f9fe1d00cd10fe6e5))

- Cloud cover disabled for radar product types and onda queryable params
  ([#636](https://github.com/CS-SI/eodag/pull/636),
  [`9ea3f35`](https://github.com/CS-SI/eodag/commit/9ea3f35a9a1a2bd1e3de38585c01bfa727065dc4))

- Creodias API update ([#623](https://github.com/CS-SI/eodag/pull/623),
  [`86a0cf1`](https://github.com/CS-SI/eodag/commit/86a0cf1dedc84147ee772169af92993c8e4f9fe3))

Co-authored-by: Sylvain Brunato <sylvain.brunato@c-s.fr>

- Discovery_config in metadata_mapping ([#625](https://github.com/CS-SI/eodag/pull/625),
  [`139d22a`](https://github.com/CS-SI/eodag/commit/139d22a7b141131418504ea91d50c308498a8f5c))

- Flatten_top_directories on single file ([#634](https://github.com/CS-SI/eodag/pull/634),
  [`8bffc9c`](https://github.com/CS-SI/eodag/commit/8bffc9caffbc900116956cbd4dc484ab691efab2))

- Jsondecodeerror during order process ([#620](https://github.com/CS-SI/eodag/pull/620),
  [`37eb4e5`](https://github.com/CS-SI/eodag/commit/37eb4e53a97ceecb5189d87f14556c1bac4b2aab))

- Make map_product_type accept kwargs ([#629](https://github.com/CS-SI/eodag/pull/629),
  [`7960f93`](https://github.com/CS-SI/eodag/commit/7960f93232a5917b2a097b492fe9937f80f81fe2))

- Meteoblue download format ([#647](https://github.com/CS-SI/eodag/pull/647),
  [`216edc2`](https://github.com/CS-SI/eodag/commit/216edc2a7e22676ecfcbc77b71795fc319cb3dc4))

- Not-donwloaded products warning ([#635](https://github.com/CS-SI/eodag/pull/635),
  [`9aaf0cd`](https://github.com/CS-SI/eodag/commit/9aaf0cde61eba89c60209b7f29765f75bf72b9b9))

- Odata free text search operands filter ([#624](https://github.com/CS-SI/eodag/pull/624),
  [`ae475d6`](https://github.com/CS-SI/eodag/commit/ae475d6b12305d81a6dda8cdb1031be5c1c4bd21))

- Optimized jsonpath.parse using common_metadata_mapping_path
  ([#626](https://github.com/CS-SI/eodag/pull/626),
  [`dba5c61`](https://github.com/CS-SI/eodag/commit/dba5c617ada35a3f9b7fa6ecf08bc2dc4547884c))

- Progress bar adjustable refresh ([#643](https://github.com/CS-SI/eodag/pull/643),
  [`3099b2a`](https://github.com/CS-SI/eodag/commit/3099b2a897480236598cf6fc36b4c1518fc04160))

- Restore creodias product types discovery ([#639](https://github.com/CS-SI/eodag/pull/639),
  [`5de90ce`](https://github.com/CS-SI/eodag/commit/5de90ce432c272f2b9dbe358a0e187c5b9fe0bad))

- Simplify S2_MSI_L1C internal usage with peps ([#630](https://github.com/CS-SI/eodag/pull/630),
  [`05e94a5`](https://github.com/CS-SI/eodag/commit/05e94a5c534fb4195021f27ad0842046a64d3a33))

- Update external product types reference ([#638](https://github.com/CS-SI/eodag/pull/638),
  [`bc21b08`](https://github.com/CS-SI/eodag/commit/bc21b08fc27d34935134b66e6d056dfe2d6de00a))

- Update external product types reference ([#640](https://github.com/CS-SI/eodag/pull/640),
  [`6176b8e`](https://github.com/CS-SI/eodag/commit/6176b8e7e6cd67680d03d99b3483de9f66c34dbd))

- Update external product types reference ([#644](https://github.com/CS-SI/eodag/pull/644),
  [`cdaac24`](https://github.com/CS-SI/eodag/commit/cdaac241ecb7a08c46cda6f6c8eba845e5842064))

### Build System

- Bump version ([#648](https://github.com/CS-SI/eodag/pull/648),
  [`9aa7808`](https://github.com/CS-SI/eodag/commit/9aa780831322841315c132ca4aa8be833199a324))

### Documentation

- Credentials setting using environment variables better doc
  ([#641](https://github.com/CS-SI/eodag/pull/641),
  [`92392d0`](https://github.com/CS-SI/eodag/commit/92392d0f68278088a396341faf15224a5865987a))

- Make meteoblue product types visible ([#642](https://github.com/CS-SI/eodag/pull/642),
  [`6f52040`](https://github.com/CS-SI/eodag/commit/6f52040628c8627d2c1e1dc62080a2ac474884cd))

### Features

- Handle EWKT geometry format ([#619](https://github.com/CS-SI/eodag/pull/619),
  [`2c26978`](https://github.com/CS-SI/eodag/commit/2c269784bc329e88dc4e3477b12fc4eadc475831))

- Mix count and search requests when possible ([#632](https://github.com/CS-SI/eodag/pull/632),
  [`69d24e8`](https://github.com/CS-SI/eodag/commit/69d24e856d04abbf44a81786b67cc26e98d43ee5))

- Mundi OFFLINE products order mechanism ([#645](https://github.com/CS-SI/eodag/pull/645),
  [`cc33191`](https://github.com/CS-SI/eodag/commit/cc331917e9b54bfebbc6918e4e4a2d9458200d66))

- Optimize onda search and update discover_metadata mechanism
  ([#616](https://github.com/CS-SI/eodag/pull/616),
  [`70586e9`](https://github.com/CS-SI/eodag/commit/70586e9482a65e6469c993e5bd1cc70f78f8f022))

- Simplify odata metadata mapping using pre-mapping
  ([#622](https://github.com/CS-SI/eodag/pull/622),
  [`0cacf05`](https://github.com/CS-SI/eodag/commit/0cacf05d65f2afb1663cf0919aa2384ef5a5399e))

### Testing

- End-to-end and core tests updates ([#646](https://github.com/CS-SI/eodag/pull/646),
  [`7f1f490`](https://github.com/CS-SI/eodag/commit/7f1f49051e247a0f3e2d2c05ee6040b489aec363))

- Optimizes and fixes tests ([#631](https://github.com/CS-SI/eodag/pull/631),
  [`6b7ca26`](https://github.com/CS-SI/eodag/commit/6b7ca26d5291602ce5b92beb148b359d6a1f5d05))


## v2.8.0 (2023-01-17)

### Bug Fixes

- Adapt to shapely v2.0 ([#580](https://github.com/CS-SI/eodag/pull/580),
  [`b8db03b`](https://github.com/CS-SI/eodag/commit/b8db03b263c8523bb9d100c95d924202851794a4))

- Awsdownload SAFE build fix and more tests ([#609](https://github.com/CS-SI/eodag/pull/609),
  [`eec4adf`](https://github.com/CS-SI/eodag/commit/eec4adfd9d49038c15e3e9dbbad56b49b6167b24))

* fix: out of safe format assets

* fix: renamed AwsDownload.get_bucket_name_and_prefix to get_product_bucket_name_and_prefix

* fix: asset out of SAFE pattern wont break AwsDownload

* test: more AwsDownload tests

- Disable discover_product_types for StaticStacSearch
  ([#590](https://github.com/CS-SI/eodag/pull/590),
  [`870580e`](https://github.com/CS-SI/eodag/commit/870580e4565e533838a1b3c1b2acd2edd335de11))

- Fixed flatten top dirs mechanism ([#576](https://github.com/CS-SI/eodag/pull/576),
  [`dd6069c`](https://github.com/CS-SI/eodag/commit/dd6069c4789bcd14b8cbabee043a986f08ac2363))

- Ignore percent vars resolve errors in register_downloader
  ([#586](https://github.com/CS-SI/eodag/pull/586),
  [`c91cba7`](https://github.com/CS-SI/eodag/commit/c91cba779c1913985640b99e2c019c9c000bb4a0))

- Landsat c1 no more available on usgs ([#601](https://github.com/CS-SI/eodag/pull/601),
  [`df7af23`](https://github.com/CS-SI/eodag/commit/df7af23aaa92449bc6319bf66d0c24884dd0e1e7))

- Missing space needed in pytest cli call ([#598](https://github.com/CS-SI/eodag/pull/598),
  [`7d105d1`](https://github.com/CS-SI/eodag/commit/7d105d12a32d659557c20d763e6ba189c66ab1f8))

- Ordered keywords in discovered product types ([#597](https://github.com/CS-SI/eodag/pull/597),
  [`641ccfd`](https://github.com/CS-SI/eodag/commit/641ccfdec5141c4cf4379476bb9c6061ed9a6d06))

- Pin ipython version in docs for nbsphinx ([#582](https://github.com/CS-SI/eodag/pull/582),
  [`90eaaff`](https://github.com/CS-SI/eodag/commit/90eaaff6516332521e96aaf5cb55a22f792d6385))

- Postjsonsearch request error and tests ([#610](https://github.com/CS-SI/eodag/pull/610),
  [`58b6093`](https://github.com/CS-SI/eodag/commit/58b6093b2522e036f5c617bd3cbd29fd4e4c6b7c))

- Remove product_type custom arg from QueryStringSearch.query
  ([#589](https://github.com/CS-SI/eodag/pull/589),
  [`acfbc8e`](https://github.com/CS-SI/eodag/commit/acfbc8e39a2a13a1f632c9e0c9e0b874d781f6af))

- Remove unavailable sobloo provider ([#607](https://github.com/CS-SI/eodag/pull/607),
  [`b5486f7`](https://github.com/CS-SI/eodag/commit/b5486f719e4169bca5ce7701ed9b22c9dd0b44d9))

- Update auth plugins docs and error handling ([#588](https://github.com/CS-SI/eodag/pull/588),
  [`106a9e0`](https://github.com/CS-SI/eodag/commit/106a9e0940f4c19133db6293d7a74d2360f5d7f9))

- Update external product types reference ([#593](https://github.com/CS-SI/eodag/pull/593),
  [`77cf3d7`](https://github.com/CS-SI/eodag/commit/77cf3d7338d90a4034a769766ce1cc85045264be))

- Update external product types reference ([#595](https://github.com/CS-SI/eodag/pull/595),
  [`ca5c824`](https://github.com/CS-SI/eodag/commit/ca5c82413691626093080f0cb47d9c19172b7b93))

- Update external product types reference ([#599](https://github.com/CS-SI/eodag/pull/599),
  [`0e11b56`](https://github.com/CS-SI/eodag/commit/0e11b5665e2a8f9a2d06c66e8e791d04b6134331))

- Update read_local_json to catch OSErrors ([#572](https://github.com/CS-SI/eodag/pull/572),
  [`dacb233`](https://github.com/CS-SI/eodag/commit/dacb2333dbfbaa5bd582674e829171847963b09e))

### Build System

- Bump version ([#611](https://github.com/CS-SI/eodag/pull/611),
  [`e1ca0e0`](https://github.com/CS-SI/eodag/commit/e1ca0e037bbe14b97a38b61c1d38058955d8de62))

### Continuous Integration

- Pre-commit update ([#579](https://github.com/CS-SI/eodag/pull/579),
  [`dc9f2c9`](https://github.com/CS-SI/eodag/commit/dc9f2c95cf67b368bff8e5a977620e96010e2f26))

### Documentation

- Make product types catalog more visible ([#603](https://github.com/CS-SI/eodag/pull/603),
  [`c2531ce`](https://github.com/CS-SI/eodag/commit/c2531ce9744824324d6d03fa7e8ea9ea9ee00e58))

- Sara provider documentation ([#602](https://github.com/CS-SI/eodag/pull/602),
  [`d238c08`](https://github.com/CS-SI/eodag/commit/d238c0853d29b5c2cc3a594f60a6e6e6ce6ad3ea))

* docs: sara provider documentation

* test: sara provider end-to-end test

### Features

- Add support for py311 ([#552](https://github.com/CS-SI/eodag/pull/552),
  [`3465afe`](https://github.com/CS-SI/eodag/commit/3465afe00a492e73bfd517f19c409ba21196f85f))

- Added SARA as a provider and respective S3 product definitions.
  ([#578](https://github.com/CS-SI/eodag/pull/578),
  [`4cd2070`](https://github.com/CS-SI/eodag/commit/4cd207078be7f97b1377677d242f9ff8a83164fc))

- Discovered product types keywords ([#592](https://github.com/CS-SI/eodag/pull/592),
  [`92565f6`](https://github.com/CS-SI/eodag/commit/92565f6327a5c696d73f9713ce609082e3ef3c1b))

- Http asset size from get method ([#566](https://github.com/CS-SI/eodag/pull/566),
  [`ce6d103`](https://github.com/CS-SI/eodag/commit/ce6d103450676c5d1a736500cdb803e1aa5c47f5))

- New meteoblue provider ([#604](https://github.com/CS-SI/eodag/pull/604),
  [`6fee322`](https://github.com/CS-SI/eodag/commit/6fee322d19ecc2805f7ab44139b3c555b8cad40f))

* feat: new HttpQueryStringAuth plugin

* test: HttpQueryStringAuth

* feat: new BuildPostSearchResult plugin

* fix: read outputs_extension from download plugin conf

* feat: HTTPDownload.orderDownload and HTTPDownload.orderDownloadStatus methods

* fix: metadata_mapping to_geo_interface changed to to_geojson

* feat: new meteoblue provider

* fix: sort query dict items in BuildPostSearchResult

* test: BuildPostSearchResult

* test: orderDownload and orderDownloadStatus

* docs: meteoblue provider

* test: meteoblue end-to-end test

### Testing

- Read_local_json raises STACOpenerError ([#574](https://github.com/CS-SI/eodag/pull/574),
  [`73e95cb`](https://github.com/CS-SI/eodag/commit/73e95cb6407329faf860cb775e1dd61838e6a2c4))


## v2.7.0 (2022-11-29)

### Bug Fixes

- Continue if error on gh actions tests publish ([#558](https://github.com/CS-SI/eodag/pull/558),
  [`643bcd9`](https://github.com/CS-SI/eodag/commit/643bcd9812ce99171aaa895a2e29af68bc0c164f))

- Fetch only given provider if specified ([#557](https://github.com/CS-SI/eodag/pull/557),
  [`df9f01d`](https://github.com/CS-SI/eodag/commit/df9f01d871bb398367a103021f82c587e95ad219))

- Handle local assets in HTTPDownload ([#561](https://github.com/CS-SI/eodag/pull/561),
  [`29c1474`](https://github.com/CS-SI/eodag/commit/29c1474e5016cd8158c890ec5210af2062c73a49))

- Request error handling during search_all ([#554](https://github.com/CS-SI/eodag/pull/554),
  [`2ddca49`](https://github.com/CS-SI/eodag/commit/2ddca49329c26796957ec7a957e1fde15ab6e174))

- Warning if keycloak auth error while discovering product types
  ([#555](https://github.com/CS-SI/eodag/pull/555),
  [`b4c8b9f`](https://github.com/CS-SI/eodag/commit/b4c8b9f7d1082bbd30e7870ef0a5288a135d8e38))

### Build System

- Bump version ([#563](https://github.com/CS-SI/eodag/pull/563),
  [`56daab8`](https://github.com/CS-SI/eodag/commit/56daab80dc685f4b7ba3a6afd9c115597fc5297b))

### Documentation

- Changelog typo ([#553](https://github.com/CS-SI/eodag/pull/553),
  [`bb6dca4`](https://github.com/CS-SI/eodag/commit/bb6dca41fd5f6d20afbfba67c0a0aa2187ce37af))

- Fix cli examples and typos in contribute page ([#562](https://github.com/CS-SI/eodag/pull/562),
  [`3c4ca8a`](https://github.com/CS-SI/eodag/commit/3c4ca8af92d257921500fb5e920a53aae947b398))

### Features

- Fetch ext product types before searching unkown product type
  ([#559](https://github.com/CS-SI/eodag/pull/559),
  [`68f98df`](https://github.com/CS-SI/eodag/commit/68f98df4f1adcf2a4c28ff8ccfd8a9da5e419fd5))


## v2.6.2 (2022-11-15)

### Bug Fixes

- Accept all local files uri formats ([#545](https://github.com/CS-SI/eodag/pull/545),
  [`7254be5`](https://github.com/CS-SI/eodag/commit/7254be5e09df6acb74be637236087f4bbf72b8de))

- New methods to get assets filename from header ([#542](https://github.com/CS-SI/eodag/pull/542),
  [`f73ba14`](https://github.com/CS-SI/eodag/commit/f73ba149625ed274fcb55ad5ab05b1f6ac4601e7))

- Temporarily add py dep for pytest-html ([#541](https://github.com/CS-SI/eodag/pull/541),
  [`3cdbd4c`](https://github.com/CS-SI/eodag/commit/3cdbd4c6ea77a25f85c6fac3314a22bf1c5a2cd1))

- Temporarily set pytest-html max version ([#540](https://github.com/CS-SI/eodag/pull/540),
  [`79f40a3`](https://github.com/CS-SI/eodag/commit/79f40a3daa8d0ad860101e068fa201851db4dbad))

### Build System

- Bump version ([#551](https://github.com/CS-SI/eodag/pull/551),
  [`2b38541`](https://github.com/CS-SI/eodag/commit/2b3854153b0f8246f73dc419df2dc438f8708816))

### Continuous Integration

- Pre-commit repos update ([#535](https://github.com/CS-SI/eodag/pull/535),
  [`380ce3f`](https://github.com/CS-SI/eodag/commit/380ce3fc5fc744c250952e81ccc58688faaffd15))

### Documentation

- Fixed rtype for guess_product_type ([#543](https://github.com/CS-SI/eodag/pull/543),
  [`837c127`](https://github.com/CS-SI/eodag/commit/837c127b5068fd87a99b875206b95d44e48fdb50))

### Refactoring

- Remove unused code, templates and description.md ([#544](https://github.com/CS-SI/eodag/pull/544),
  [`cd3b08a`](https://github.com/CS-SI/eodag/commit/cd3b08af8d67795eb582c0076ba169f163925c35))

### Testing

- Improve cli test coverage ([#539](https://github.com/CS-SI/eodag/pull/539),
  [`d2f4b61`](https://github.com/CS-SI/eodag/commit/d2f4b61ed8b7e76455f68b54e93a38fb9220356f))

- Improve core test coverage ([#549](https://github.com/CS-SI/eodag/pull/549),
  [`fc15d0f`](https://github.com/CS-SI/eodag/commit/fc15d0fb47eec7b17d6ac0b33713b28f3e261f80))


## v2.6.1 (2022-10-19)

### Bug Fixes

- Align sensorType to opensearch-eo ([#528](https://github.com/CS-SI/eodag/pull/528),
  [`b66ad3b`](https://github.com/CS-SI/eodag/commit/b66ad3bfbfca5c51cf3462f6ca2250c10be7dafe))

- Aws bucket extraction ([#524](https://github.com/CS-SI/eodag/pull/524),
  [`418da7c`](https://github.com/CS-SI/eodag/commit/418da7cc9fa0d19aaaf4b9a3b3a56db404e61bf7))

- Cdsapi logging handler ([#522](https://github.com/CS-SI/eodag/pull/522),
  [`0244dae`](https://github.com/CS-SI/eodag/commit/0244dae9d572a63c5fca50e91b24d2a975c63819))

- Rest search without stac formatting ([#526](https://github.com/CS-SI/eodag/pull/526),
  [`59ac844`](https://github.com/CS-SI/eodag/commit/59ac8445bcfbbe54b83ca3c7fabaa6169db0998d))

### Build System

- Bump version ([#531](https://github.com/CS-SI/eodag/pull/531),
  [`94eb350`](https://github.com/CS-SI/eodag/commit/94eb3500e8cbc2220830bf3829bfc3639a94b15f))

### Documentation

- Fixes params tables glitch ([#527](https://github.com/CS-SI/eodag/pull/527),
  [`81a4337`](https://github.com/CS-SI/eodag/commit/81a4337b77d1bcc2fdbcbf7002e224bdcc9ae761))

### Features

- Do not run flasgger automatically ([#529](https://github.com/CS-SI/eodag/pull/529),
  [`2086412`](https://github.com/CS-SI/eodag/commit/2086412c7056207c6f082431883f4227a749aa67))

- Remove cloudcover restriction in product types discovery
  ([#530](https://github.com/CS-SI/eodag/pull/530),
  [`b94e3e1`](https://github.com/CS-SI/eodag/commit/b94e3e18768d308acb6c229c27f6a9c7a3fab268))

### Testing

- Cli version ([#525](https://github.com/CS-SI/eodag/pull/525),
  [`df0c9b5`](https://github.com/CS-SI/eodag/commit/df0c9b5a3dd65b9cc2c56b88071d6b13b07fe606))

- End-to-end tests update ([#523](https://github.com/CS-SI/eodag/pull/523),
  [`58335e7`](https://github.com/CS-SI/eodag/commit/58335e728fff5b98bd85b96fead271429773a593))


## v2.6.0 (2022-10-07)

### Bug Fixes

- Cdsapi logging ([#513](https://github.com/CS-SI/eodag/pull/513),
  [`158fac8`](https://github.com/CS-SI/eodag/commit/158fac82232af978700e8f829bd5b7e227774a4c))

- Discover product types for new default providers ([#493](https://github.com/CS-SI/eodag/pull/493),
  [`6ff8e5f`](https://github.com/CS-SI/eodag/commit/6ff8e5f2d5828076f186d61b77ee393c70f9ee21))

- Discover_product_types auth ([#486](https://github.com/CS-SI/eodag/pull/486),
  [`f4b5f52`](https://github.com/CS-SI/eodag/commit/f4b5f523553f67b1c2aeec03017fd462693164f9))

- Do not build search plugins when updating product types list
  ([#500](https://github.com/CS-SI/eodag/pull/500),
  [`b8128f1`](https://github.com/CS-SI/eodag/commit/b8128f1348eaea9a48bf8c99ad18b8dd5a5c2a6a))

- Drop support for python3.6 ([#505](https://github.com/CS-SI/eodag/pull/505),
  [`e68536c`](https://github.com/CS-SI/eodag/commit/e68536c3469ab6181e96e3e8c095b1bf75b1deca))

- Id cast to str in progress_callback ([#490](https://github.com/CS-SI/eodag/pull/490),
  [`ff88331`](https://github.com/CS-SI/eodag/commit/ff88331f734ec6b3a28ebe7c5a8eacda61187f2a))

- Logout and in if usgs apikey expires ([#489](https://github.com/CS-SI/eodag/pull/489),
  [`0a782d7`](https://github.com/CS-SI/eodag/commit/0a782d7f476a993170f7d60c006be09b4cfa2b47))

- Metadata-mapping with providers update ([#483](https://github.com/CS-SI/eodag/pull/483),
  [`9639b37`](https://github.com/CS-SI/eodag/commit/9639b374e85513056237adaa925f104f38677820))

- Pin flask version to prevent doctest error ([#492](https://github.com/CS-SI/eodag/pull/492),
  [`3b9eb8c`](https://github.com/CS-SI/eodag/commit/3b9eb8cfec74a0ca054480c806263c2e3e9433ca))

- Timeout set for all requests methods ([#495](https://github.com/CS-SI/eodag/pull/495),
  [`f0d13e7`](https://github.com/CS-SI/eodag/commit/f0d13e76f1c335433b98731409fbe42c8252df4e))

- Update external product types reference ([#481](https://github.com/CS-SI/eodag/pull/481),
  [`918f2d1`](https://github.com/CS-SI/eodag/commit/918f2d1602cf5e0e351d155997ff24f7a3cd243e))

Co-authored-by: github-actions[bot] <github-actions[bot]@users.noreply.github.com>

- Update flask version limit ([#496](https://github.com/CS-SI/eodag/pull/496),
  [`f52c964`](https://github.com/CS-SI/eodag/commit/f52c964ce52a5655f08616011d509b78d2b7c79c))

- Update nbconvert ([#497](https://github.com/CS-SI/eodag/pull/497),
  [`04b9584`](https://github.com/CS-SI/eodag/commit/04b9584dfeb820d87f5fef1215a02c5f24446f65))

- Update provider with new plugin entry ([#484](https://github.com/CS-SI/eodag/pull/484),
  [`f6f97fe`](https://github.com/CS-SI/eodag/commit/f6f97fe82cb3d9c7fbf24396be22596ae87267d0))

- Update UsgsApi plugin ([#508](https://github.com/CS-SI/eodag/pull/508),
  [`1339844`](https://github.com/CS-SI/eodag/commit/1339844dd6fe8f882dcb90242b9736094e3830fc))

- Updated creodias auth settings ([#514](https://github.com/CS-SI/eodag/pull/514),
  [`eb054a4`](https://github.com/CS-SI/eodag/commit/eb054a46f117e0971f772337bd70e5b5823a53d2))

### Build System

- Bump version ([#516](https://github.com/CS-SI/eodag/pull/516),
  [`771e12c`](https://github.com/CS-SI/eodag/commit/771e12c40778392a28c3673d8eaffa682b2ce2b4))

### Documentation

- Reorder sections in ecmwf tuto ([#511](https://github.com/CS-SI/eodag/pull/511),
  [`2cba529`](https://github.com/CS-SI/eodag/commit/2cba529db09de3aa96db757e1afddd1a1c483ebb))

- Typos ([#510](https://github.com/CS-SI/eodag/pull/510),
  [`482eae3`](https://github.com/CS-SI/eodag/commit/482eae366a3992845b97939a3d2e0d828a1f3392))

### Features

- Add cop_ads and cop_cds providers with CdsApi plugin
  ([`95f6c32`](https://github.com/CS-SI/eodag/commit/95f6c321aceea84292827bafc5b3f865bd818573))

- Allow empty geometry for stac providers ([#485](https://github.com/CS-SI/eodag/pull/485),
  [`fc01129`](https://github.com/CS-SI/eodag/commit/fc01129a1a1ddcdbd9640d411d68f810419fc030))

- Cached jsonpath.parse ([#502](https://github.com/CS-SI/eodag/pull/502),
  [`ac4edeb`](https://github.com/CS-SI/eodag/commit/ac4edebf1b9c3bc699522bd890870557938a7a1b))

- External product types conf on gh pages ([#491](https://github.com/CS-SI/eodag/pull/491),
  [`a65a6bc`](https://github.com/CS-SI/eodag/commit/a65a6bcafd45896a278ddbb48c766dbc73f77eb8))

### Refactoring

- Download retry decorator and tests ([#506](https://github.com/CS-SI/eodag/pull/506),
  [`b57fc76`](https://github.com/CS-SI/eodag/commit/b57fc768c1a08e1e255b8fa44b3785255bc8ca23))

### Testing

- Download plugins ([#494](https://github.com/CS-SI/eodag/pull/494),
  [`07abe78`](https://github.com/CS-SI/eodag/commit/07abe78d376a55fa3365b4ed46c7da89448a38ca))

- Less restrictive comparison in download retry tests
  ([#517](https://github.com/CS-SI/eodag/pull/517),
  [`e4d8775`](https://github.com/CS-SI/eodag/commit/e4d87758af5d0e850f33a76b424f6dc507783097))


## v2.5.2 (2022-07-05)

### Bug Fixes

- Jsonpath issue causing missing productPath property
  ([#480](https://github.com/CS-SI/eodag/pull/480),
  [`3f39f6c`](https://github.com/CS-SI/eodag/commit/3f39f6cf0565cf11b13d0fa293e0a10d7d9ef8f9))

* fix: jsonpath issue causing missing productPath property

* build: bump version


## v2.5.1 (2022-06-27)

### Bug Fixes

- Broken stac aws download conf ([#475](https://github.com/CS-SI/eodag/pull/475),
  [`54a5182`](https://github.com/CS-SI/eodag/commit/54a51822ae350e54d2b7d353db377b6ff2886518))

* fix: broken stac aws download conf

* build: bump version

- Fetch product types gh action failures ([#472](https://github.com/CS-SI/eodag/pull/472),
  [`66a9d2f`](https://github.com/CS-SI/eodag/commit/66a9d2fc0ae0c94e498a8d9f14a7a54268c1c3d2))

* fix: fetch product types gh action when nothing to commit

* fix: new line at end of ext_product_types.json

- Skip commit summary when not needed in fetch product types ci
  ([#473](https://github.com/CS-SI/eodag/pull/473),
  [`fa1e8c0`](https://github.com/CS-SI/eodag/commit/fa1e8c001a23dd4a42005c87e31f75da5d886d74))

- Update external product types reference ([#471](https://github.com/CS-SI/eodag/pull/471),
  [`a003087`](https://github.com/CS-SI/eodag/commit/a00308772c359998bff5fa04549a4f14bdd0026e))

Co-authored-by: github-actions[bot] <github-actions[bot]@users.noreply.github.com>

- Use PR in github action to update external product types reference
  ([#470](https://github.com/CS-SI/eodag/pull/470),
  [`f2c495d`](https://github.com/CS-SI/eodag/commit/f2c495d1ce6346d2d4a31e40203a5c6e57b96344))

### Build System

- Downgrade owslib with py310 ([#469](https://github.com/CS-SI/eodag/pull/469),
  [`1c7edf6`](https://github.com/CS-SI/eodag/commit/1c7edf6d8ab8506d2ad186ac51e3bce62515aa74))

- Downgrade owslib with py310 ([#469](https://github.com/CS-SI/eodag/pull/469),
  [`e161f5d`](https://github.com/CS-SI/eodag/commit/e161f5dd5dab137f26c38baf6838c5657837ab53))

- Setuptools_scm max version for py36 ([#477](https://github.com/CS-SI/eodag/pull/477),
  [`f2d9979`](https://github.com/CS-SI/eodag/commit/f2d9979b5391b95322622f5fe28de2f963a8200b))

### Features

- Product types discovery ([#467](https://github.com/CS-SI/eodag/pull/467),
  [`e12c166`](https://github.com/CS-SI/eodag/commit/e12c166ecde9346dac9677ad6799c85b013c3586))


## v2.5.0 (2022-06-07)

### Bug Fixes

- Clear search context after each search() call ([#433](https://github.com/CS-SI/eodag/pull/433),
  [`3c7424c`](https://github.com/CS-SI/eodag/commit/3c7424c81cf70e4f430305a63cb0e22096c7b9cd))

- Get all available metadata for onda products ([#440](https://github.com/CS-SI/eodag/pull/440),
  [`877366d`](https://github.com/CS-SI/eodag/commit/877366d620216caa2557de6a217f4c606277b5e4))

- Need_auth and api plugin search ([#448](https://github.com/CS-SI/eodag/pull/448),
  [`cc1f51b`](https://github.com/CS-SI/eodag/commit/cc1f51b2da7eafd3fa077fc21914081bcd227b4a))

- Rename GRANULE first folder during SAFE build ([#434](https://github.com/CS-SI/eodag/pull/434),
  [`c28ab8f`](https://github.com/CS-SI/eodag/commit/c28ab8fc4b997873fbbd3095a33d9fe7f5427b84))

- Requests intersphinx url ([#460](https://github.com/CS-SI/eodag/pull/460),
  [`909354f`](https://github.com/CS-SI/eodag/commit/909354f089a3e08e810a194a10ce54858b26e6f6))

- Unwanted string in logging time ([#444](https://github.com/CS-SI/eodag/pull/444),
  [`06dd23d`](https://github.com/CS-SI/eodag/commit/06dd23d5d2ebb020032972ed77617403de75e31b))

- Update black and adapts json data handling to flask 2.1.0
  ([#430](https://github.com/CS-SI/eodag/pull/430),
  [`9b4fd08`](https://github.com/CS-SI/eodag/commit/9b4fd08d2cd7f8431e2e67d9f514b67e86450817))

* fix: pinned black version in pre-commit update

* refactor: black formatting

* fix: adapts json data handling to flask 2.1.0 update

- Use mock in stac server search tests ([#464](https://github.com/CS-SI/eodag/pull/464),
  [`7209dda`](https://github.com/CS-SI/eodag/commit/7209dda749c97fca63a9f97743edeeca45f1b885))

### Build System

- Bump version ([#465](https://github.com/CS-SI/eodag/pull/465),
  [`8ba0f7f`](https://github.com/CS-SI/eodag/commit/8ba0f7fc51b85495aced56a810e21f9945dab42e))

- Packaging update following PEP517 ([#435](https://github.com/CS-SI/eodag/pull/435),
  [`e470a6e`](https://github.com/CS-SI/eodag/commit/e470a6ecbf0876d6fd2089724ccd096b579e1cef))

### Documentation

- Copyright date fix ([#436](https://github.com/CS-SI/eodag/pull/436),
  [`f6d0ded`](https://github.com/CS-SI/eodag/commit/f6d0deded4e490655dc612e30f80a2cd84f6f1f5))

- Fix shapefiles deadlink in sentinel-1 ship detection tutorial
  ([#451](https://github.com/CS-SI/eodag/pull/451),
  [`ff9fcee`](https://github.com/CS-SI/eodag/commit/ff9fceef56fe7e840b257c257b58707ed441429b))

- Fix typehint of kwargs according to PEP484 ([#438](https://github.com/CS-SI/eodag/pull/438),
  [`95c7e31`](https://github.com/CS-SI/eodag/commit/95c7e31da01dc695c7abd014c135359653f684c2))

### Features

- Add filter_online to SearchResult ([#458](https://github.com/CS-SI/eodag/pull/458),
  [`835eab7`](https://github.com/CS-SI/eodag/commit/835eab785d40ee21fdfa8af383d3c788aaa7dee9))

- Add more convert methods to SearchResult ([#450](https://github.com/CS-SI/eodag/pull/450),
  [`be026c2`](https://github.com/CS-SI/eodag/commit/be026c211b2ef28ceb8b13437a8eceaf4245689b))

- Allow headers and url formatting in TokenAuth ([#447](https://github.com/CS-SI/eodag/pull/447),
  [`99db80a`](https://github.com/CS-SI/eodag/commit/99db80a896fa443dcff89602ff84d2b5c78507ad))

- Auth on private stac search ([#443](https://github.com/CS-SI/eodag/pull/443),
  [`69baba5`](https://github.com/CS-SI/eodag/commit/69baba503b6ab715e3967beb1f068a17756c74b3))

- Better logs when a product is ordered ([#449](https://github.com/CS-SI/eodag/pull/449),
  [`2a18716`](https://github.com/CS-SI/eodag/commit/2a18716339ef7ec5f8b3f3fe001e13aac1d35394))

- New ecmwf provider and api plugin ([#452](https://github.com/CS-SI/eodag/pull/452),
  [`862ad15`](https://github.com/CS-SI/eodag/commit/862ad152b83c9989b34f1381c76a450b110eed3a))

- New provider earth_search_gcs ([#462](https://github.com/CS-SI/eodag/pull/462),
  [`9e6e51d`](https://github.com/CS-SI/eodag/commit/9e6e51dd3a6cacf02ac232860cb40a8059ab39c4))

- Prune providers without credentials needing auth for search
  ([#442](https://github.com/CS-SI/eodag/pull/442),
  [`92a1fe2`](https://github.com/CS-SI/eodag/commit/92a1fe2131597b3b5c2d35d39272ec25baab8783))

- Requester_pays, base_uri, and and ignore_assets AwsDownload options
  ([#456](https://github.com/CS-SI/eodag/pull/456),
  [`414f84e`](https://github.com/CS-SI/eodag/commit/414f84eb1308688503053f47dde9c64f55d7c16f))

- Setuptools_scm usage ([#431](https://github.com/CS-SI/eodag/pull/431),
  [`4ca485c`](https://github.com/CS-SI/eodag/commit/4ca485c12f465348c4a08c082de86b162ee23144))

* feat: setuptools_scm usage

* fix: update package build & check

* fix: version guess from gh actions


## v2.4.0 (2022-03-09)

### Bug Fixes

- Add timeout for download stream requests ([#394](https://github.com/CS-SI/eodag/pull/394),
  [`589ca10`](https://github.com/CS-SI/eodag/commit/589ca1062877b48239c2df93844e497b25119fe1))

- Alternative http assets infos fetch ([#373](https://github.com/CS-SI/eodag/pull/373),
  [`c6fc141`](https://github.com/CS-SI/eodag/commit/c6fc141ff43b2183690d433e8dff89d27c65ad80))

- Creodias archive_depth and e2e complete test ([#410](https://github.com/CS-SI/eodag/pull/410),
  [`47c0e33`](https://github.com/CS-SI/eodag/commit/47c0e33bd503c04b0bbf9e2a8e54b8337248e04a))

- Disable cloudCover for RADAR product types ([#389](https://github.com/CS-SI/eodag/pull/389),
  [`a3dc5d5`](https://github.com/CS-SI/eodag/commit/a3dc5d53178cc613295b34bfb6e2ce98a6c9fed2))

- More explicit end-to-end tests error messages ([#398](https://github.com/CS-SI/eodag/pull/398),
  [`470aa49`](https://github.com/CS-SI/eodag/commit/470aa492fa79d8d89f84a1277d783c38dd5d04aa))

- Notavailableerror using usgs api ([#393](https://github.com/CS-SI/eodag/pull/393),
  [`fc86004`](https://github.com/CS-SI/eodag/commit/fc86004695bdfe03d6add6b5ff1b66d390b2a084))

- Pin markupsafe for doc build ([#399](https://github.com/CS-SI/eodag/pull/399),
  [`45a1f08`](https://github.com/CS-SI/eodag/commit/45a1f086e8ca083a378c951ecaf5513072891565))

- Productpath regex for earth_search ([#405](https://github.com/CS-SI/eodag/pull/405),
  [`8c3c1c1`](https://github.com/CS-SI/eodag/commit/8c3c1c1e526f81f71a3ee01b10a9eb7f81ea3647))

- Temporally remove callback to download methods ([#371](https://github.com/CS-SI/eodag/pull/371),
  [`1891f4b`](https://github.com/CS-SI/eodag/commit/1891f4b3ff7554ebe04c7ee9fa2a5af5de407753))

This reverts commit 6ca2b90f1997aa10e66ddee2b1e33a385014bf7f.

- Usgsapi inheritance for download_all ([#379](https://github.com/CS-SI/eodag/pull/379),
  [`6e6e689`](https://github.com/CS-SI/eodag/commit/6e6e6890a52ac8ad4d0f989f41a726b35d9cf5d8))

### Build System

- Bump version ([#421](https://github.com/CS-SI/eodag/pull/421),
  [`c6dfc7e`](https://github.com/CS-SI/eodag/commit/c6dfc7ebaaea5a0ad9dd3095ab9fa537d6d10a2d))

### Continuous Integration

- Cov reports only for PR ([#416](https://github.com/CS-SI/eodag/pull/416),
  [`059bc07`](https://github.com/CS-SI/eodag/commit/059bc078285edd7a8d41bc7e37212a8b18ef4186))

- Coverage reports in gh actions ([#411](https://github.com/CS-SI/eodag/pull/411),
  [`4e739f8`](https://github.com/CS-SI/eodag/commit/4e739f869a8d73c2e0ae5898ebc2ac27e66edfcc))

- Nose replaced with pytest and published test reports
  ([#406](https://github.com/CS-SI/eodag/pull/406),
  [`6ca3d50`](https://github.com/CS-SI/eodag/commit/6ca3d507cb64e3456f21a77981a0eebc62342f92))

### Documentation

- Cleanup and update of docstrings ([#355](https://github.com/CS-SI/eodag/pull/355),
  [`70aa455`](https://github.com/CS-SI/eodag/commit/70aa45515b7b7c11326419abcf616979e7b6e024))

- Csgroup logos updated ([#374](https://github.com/CS-SI/eodag/pull/374),
  [`da6df3f`](https://github.com/CS-SI/eodag/commit/da6df3fbc13912fb44e6cff3a3d1a74ac794bbec))

- Fix broken link in documentation ([#388](https://github.com/CS-SI/eodag/pull/388),
  [`74aaad6`](https://github.com/CS-SI/eodag/commit/74aaad6bca89d8d1e60c109886b9c151e8b739ab))

- Metadata mapping documentation ([#419](https://github.com/CS-SI/eodag/pull/419),
  [`2b11eee`](https://github.com/CS-SI/eodag/commit/2b11eee3de71cae9f49e910f8b3a3c1d43ffaf08))

- Update doc and tutos following API simplifications
  ([#420](https://github.com/CS-SI/eodag/pull/420),
  [`ace638f`](https://github.com/CS-SI/eodag/commit/ace638ff0a6ae55aa77788a62c0b95b777e124ea))

### Features

- Add callback to download methods (#121)(#357)
  ([`6ca2b90`](https://github.com/CS-SI/eodag/commit/6ca2b90f1997aa10e66ddee2b1e33a385014bf7f))

* feat: add callback to download_all method (#121)

* feat: add callback to download method (#121)

* test: add utilities to EODagTestCase and refactor TestEOProduct

* test: add tests for the callbacks of the methods download and download_all (#121)

- Add callback to download_all method (#121)(#381)
  ([`5400db4`](https://github.com/CS-SI/eodag/commit/5400db484dc95b5e42e96ee05578a8fa261e86d0))

* test: add utilities to EODagTestCase and refactor TestEOProduct

* feat: add callback to download_all method (#121)

* test: add tests for download_all callback (#121)

* docs: add eodag.utils.DownloadedCallback to api reference (#121)

- Add support for py310 ([#407](https://github.com/CS-SI/eodag/pull/407),
  [`2d8cec2`](https://github.com/CS-SI/eodag/commit/2d8cec2f6c3a1d7d23c6df6709cb0e3f18780548))

- Added awsProductId property for usgs_satapi_aws ([#377](https://github.com/CS-SI/eodag/pull/377),
  [`ba7f655`](https://github.com/CS-SI/eodag/commit/ba7f6555ce49c2cef428ec24c959da71e8e6e603))

- Attach the crunchers directly to SearchResult (#206)
  ([#359](https://github.com/CS-SI/eodag/pull/359),
  [`91e1a90`](https://github.com/CS-SI/eodag/commit/91e1a90b827defeee2fc20b9da4a8e1890ba013e))

- Automatic deletion of downloaded product zip after extraction (#144)
  ([#358](https://github.com/CS-SI/eodag/pull/358),
  [`3963758`](https://github.com/CS-SI/eodag/commit/3963758fc5fda86da4799a26eb64fbc610c444da))

* feat: automatic deletion of downloaded product zip after extraction (#144)

* feat: extract archives to temporary directory (#144)

* test: fix after automatic deletion of the archives was added (#144)

* test: add test for automatic deletion of downloaded product zip after extraction (#144)

* docs: document delete_archive configuration (#144)

- Guess eoproduct.product_type from properties ([#380](https://github.com/CS-SI/eodag/pull/380),
  [`df05c35`](https://github.com/CS-SI/eodag/commit/df05c353836883546e47db4057123ac501e003c6))

- Keywords usage in product_types configuration ([#372](https://github.com/CS-SI/eodag/pull/372),
  [`2841f58`](https://github.com/CS-SI/eodag/commit/2841f58862cca114d497ef8fa64a3c6b23ed5c84))

- Post reqs in StacSearch ([#363](https://github.com/CS-SI/eodag/pull/363),
  [`97f2357`](https://github.com/CS-SI/eodag/commit/97f23579c8d6f63ec209f5a1660f1133d483d2fb))

- Stac api query fragment usage ([#367](https://github.com/CS-SI/eodag/pull/367),
  [`18d93f6`](https://github.com/CS-SI/eodag/commit/18d93f6fffef5f84d5fdec8d4342d6f98c8290fe))

* feat: stac api query fragment usage

* test: metadata mapping conversions

* docs: metadata mapping update

- Stac server handling STAC Query fragment requests using client mapping criterias
  ([#417](https://github.com/CS-SI/eodag/pull/417),
  [`51a489a`](https://github.com/CS-SI/eodag/commit/51a489a728b581fbee5e1f26173cf813285c2460))

* feat: stac server criteria mapping from 'stac_provider.yml' (#395)

* test: add test_stac_utils, improve coverage of eodag.rest.utils

### Refactoring

- Eoproduct, SearchResult, and crunches easier to import
  ([#356](https://github.com/CS-SI/eodag/pull/356),
  [`16a7f51`](https://github.com/CS-SI/eodag/commit/16a7f51110a7bf82f6986008634125e6ea9dd1a5))

* refactor: add EOProduct and SearchResult to main namespace (#170)

* refactor: add eodag.crunch to import filters in eodag.plugins.crunch.filter_xxx (#170)

### Testing

- Cli verbose level fix in tests ([#401](https://github.com/CS-SI/eodag/pull/401),
  [`d9f16f4`](https://github.com/CS-SI/eodag/commit/d9f16f411fdf5eb6ad752f984782dd06ed882dc8))

- Prevent failing actions for windows py3.9.8 ([#361](https://github.com/CS-SI/eodag/pull/361),
  [`2b33dfc`](https://github.com/CS-SI/eodag/commit/2b33dfc605c411169002ab3c5d637c3b5b247c07))

- Update dates for sobloo end-to-end test ([#366](https://github.com/CS-SI/eodag/pull/366),
  [`2838ac4`](https://github.com/CS-SI/eodag/commit/2838ac480451cc2210ba91312b9b7351ee2fbb7c))

- Use tmp eodag conf dir ([#415](https://github.com/CS-SI/eodag/pull/415),
  [`db5bd23`](https://github.com/CS-SI/eodag/commit/db5bd23326ff640b5305c591a9ccbd1e77e21a54))


## v2.3.4 (2021-10-08)

### Bug Fixes

- Get_quicklook method for onda provider ([#344](https://github.com/CS-SI/eodag/pull/344),
  [`b0253f3`](https://github.com/CS-SI/eodag/commit/b0253f32b4def3f53421936de9b1bd0abe800489))

- Progresscallback smooth display and renamed input parameter
  ([#345](https://github.com/CS-SI/eodag/pull/345),
  [`e6b8a96`](https://github.com/CS-SI/eodag/commit/e6b8a963b764895045e9832751036ce08af0cc86))

- Removed stac eo:bands for zipped products ([#341](https://github.com/CS-SI/eodag/pull/341),
  [`ee9af26`](https://github.com/CS-SI/eodag/commit/ee9af265d6a5799ed0da917dc312316d46df8ff1))

- Stac 1.0.0 update ([#347](https://github.com/CS-SI/eodag/pull/347),
  [`1cd1b46`](https://github.com/CS-SI/eodag/commit/1cd1b4671c4691e6d4e783933d377aca29fe3f2c))

- Unwanted percent-encoded keys with mundi S2_MSI_L2A
  ([#350](https://github.com/CS-SI/eodag/pull/350),
  [`d4bd54e`](https://github.com/CS-SI/eodag/commit/d4bd54e656d6f356961230f9b383e5c85bf92b80))

- Update usgs to enable search_all ([#340](https://github.com/CS-SI/eodag/pull/340),
  [`bbf8587`](https://github.com/CS-SI/eodag/commit/bbf8587043eb0a419242234dfd15486e435a510e))

### Build System

- Bump version ([#353](https://github.com/CS-SI/eodag/pull/353),
  [`3a4b586`](https://github.com/CS-SI/eodag/commit/3a4b586d6e99460eeffdc6ff9321d0f0e0efcec0))

### Documentation

- Link to labextension in readme and side-projects ([#352](https://github.com/CS-SI/eodag/pull/352),
  [`6d44c2a`](https://github.com/CS-SI/eodag/commit/6d44c2ae897d94d92b7d8e6d8ac425910cf0af7e))


## v2.3.3 (2021-08-11)

### Bug Fixes

- Eodag-cube 0.2.0 required ([#338](https://github.com/CS-SI/eodag/pull/338),
  [`d3ada37`](https://github.com/CS-SI/eodag/commit/d3ada3735d2afd76ec44d4dd70cf93db59b6ed0f))

- Missing search_plugin when searching by id ([#335](https://github.com/CS-SI/eodag/pull/335),
  [`304446b`](https://github.com/CS-SI/eodag/commit/304446bccecc4c41f07e0f329df699dbbd8ee49a))

- Remove StopIteration usage following PEP-479 ([#337](https://github.com/CS-SI/eodag/pull/337),
  [`00bf073`](https://github.com/CS-SI/eodag/commit/00bf073000fbc7bcc1d349ad8217e9ea3bac2eab))

### Chores

- Bump version ([#339](https://github.com/CS-SI/eodag/pull/339),
  [`1e049ee`](https://github.com/CS-SI/eodag/commit/1e049ee4c4a23e656de8794b46ff11f58a36242a))

### Documentation

- More logging when searching by id ([#336](https://github.com/CS-SI/eodag/pull/336),
  [`d2b436a`](https://github.com/CS-SI/eodag/commit/d2b436a45aff991233f68e60dc1f02d6286f0cc3))


## v2.3.2 (2021-07-29)

### Bug Fixes

- Do not prepare search_all twice ([#330](https://github.com/CS-SI/eodag/pull/330),
  [`2f6ebe8`](https://github.com/CS-SI/eodag/commit/2f6ebe8be618de9538288f2ce17fe6c7f85c0c8b))

- Guess and set product_type when searching by id ([#320](https://github.com/CS-SI/eodag/pull/320),
  [`21b6708`](https://github.com/CS-SI/eodag/commit/21b67083ba26357877083d4d1dd330c33c42697b))

- Prevent eol auto changes on windows causing docker crashes
  ([#324](https://github.com/CS-SI/eodag/pull/324),
  [`db3c4ec`](https://github.com/CS-SI/eodag/commit/db3c4ec1720875f3396c4a847aad3afdd3369ec0))

- Pystac v1.0 update ([#321](https://github.com/CS-SI/eodag/pull/321),
  [`37af691`](https://github.com/CS-SI/eodag/commit/37af69194d80522884cb5108ca85487b40255b03))

### Chores

- Bump version ([#331](https://github.com/CS-SI/eodag/pull/331),
  [`067928e`](https://github.com/CS-SI/eodag/commit/067928e97f70af2523bcd35df829eaf3465d5043))

### Features

- Configurable eodag logging in docker stac-server ([#323](https://github.com/CS-SI/eodag/pull/323),
  [`4a3e67a`](https://github.com/CS-SI/eodag/commit/4a3e67acdf85f12d65ca0ba3d1f083d3888a2053))

- Enable kwargs when searching by id ([#329](https://github.com/CS-SI/eodag/pull/329),
  [`53c1c5e`](https://github.com/CS-SI/eodag/commit/53c1c5e4e42c309e5f6da92d39107ebf8784e5d3))

- Expose aws env settings in AwsDownload ([#319](https://github.com/CS-SI/eodag/pull/319),
  [`389bae3`](https://github.com/CS-SI/eodag/commit/389bae3a525001d7817471b686f0b49a1ef8bafc))


## v2.3.1 (2021-07-09)

### Bug Fixes

- Dockerfile update for stac-browser v2.0 ([#314](https://github.com/CS-SI/eodag/pull/314),
  [`30306e5`](https://github.com/CS-SI/eodag/commit/30306e52f403e7471b37ed22e9c606c718f40f5f))

Co-authored-by: Sylvain Brunato <sylvain.brunato@irap.omp.eu>

### Chores

- Bump version ([#318](https://github.com/CS-SI/eodag/pull/318),
  [`8c5a658`](https://github.com/CS-SI/eodag/commit/8c5a6589657dbf86d1c61631bb9e3dd7eff9c995))

### Features

- Eoproduct drivers definition update ([#316](https://github.com/CS-SI/eodag/pull/316),
  [`7f7a236`](https://github.com/CS-SI/eodag/commit/7f7a2368b38f4b13d3d81a44e088a5cd82b54435))

- New notebook extra dependency ([#317](https://github.com/CS-SI/eodag/pull/317),
  [`6e82bad`](https://github.com/CS-SI/eodag/commit/6e82bad4a484d4c4bbbbb4f98faad64a06b24518))


## v2.3.0 (2021-06-24)

### Bug Fixes

- _deprecated wasn't resetting the warning filters correctly
  ([#247](https://github.com/CS-SI/eodag/pull/247),
  [`d92440f`](https://github.com/CS-SI/eodag/commit/d92440f97e458e7d75b673b5495ff88ff5072f57))

- Add warning when searching with non preferred provider
  ([#260](https://github.com/CS-SI/eodag/pull/260),
  [`84aac94`](https://github.com/CS-SI/eodag/commit/84aac9405cd346a366e7499d043e1e6959a66f30))

- Auto extract if extract is not set ([#249](https://github.com/CS-SI/eodag/pull/249),
  [`6ede794`](https://github.com/CS-SI/eodag/commit/6ede794e68cb3ae069ef90ea42192e9957dcce2f))

* fix: auto extract if extract is not set

* fix: more info in the config template

* fix: a broken test and make others more robust

- Ci failure following deps upgrade ([#280](https://github.com/CS-SI/eodag/pull/280),
  [`88c016d`](https://github.com/CS-SI/eodag/commit/88c016d24a702581af416fc23a995c10a65174d2))

* tests: click v8 option error message reformatted

* tests: cli cruncher args type fix

* fix: nbsphinx broken with Jinja2 update

- Conf updatable from non-queryable params to queryable
  ([#288](https://github.com/CS-SI/eodag/pull/288),
  [`4aa610a`](https://github.com/CS-SI/eodag/commit/4aa610a0d84fe3fb2dcd8691e5b8cead9de65d54))

- Do not use ipywidgets for the Notebookwidgets representation
  ([#223](https://github.com/CS-SI/eodag/pull/223),
  [`7054aa3`](https://github.com/CS-SI/eodag/commit/7054aa316e91b5841902e8afd67e28209a85b716))

- Don't propagate kwargs used for guessing a product type
  ([#248](https://github.com/CS-SI/eodag/pull/248),
  [`f344ddd`](https://github.com/CS-SI/eodag/commit/f344dddf8cb9f0d512dd13984ebcaf16178485fe))

* fix: don't propagate kwargs used for guessing a product type

* fix: replace deprecated unittest assertEquals and assertDictContainsSubset

- Download_all doesn't empty the passed list of products
  ([#253](https://github.com/CS-SI/eodag/pull/253),
  [`dad8bb0`](https://github.com/CS-SI/eodag/commit/dad8bb09fa9fdeafce7d4a103d284dfc6dd1bbf9))

- Earth Search uses next_page_url_tpl to get the next page in search_iter_page
  ([#274](https://github.com/CS-SI/eodag/pull/274),
  [`9096a12`](https://github.com/CS-SI/eodag/commit/9096a12402068ac711b825956166a3de1051823f))

- Homogenize inconsistent paths returned by download methods
  ([#244](https://github.com/CS-SI/eodag/pull/244),
  [`6ab4262`](https://github.com/CS-SI/eodag/commit/6ab4262a133f051f6699881fb9352237e16cbcc8))

* feat: add two utilities to convert paths to uri

* fix: plugin.download returns a filesystem path, not a file URI

* tests: add complete PEPS download end-to-end test

* fix: wrong location set in the http plugin

- Ignore and log misconfigured provider from user conf
  ([#296](https://github.com/CS-SI/eodag/pull/296),
  [`facf8bf`](https://github.com/CS-SI/eodag/commit/facf8bf029fb74a84236b40b86c33a1265f35621))

- Iso 8601 formatted datetimes accepted everywhere ([#257](https://github.com/CS-SI/eodag/pull/257),
  [`c564fdd`](https://github.com/CS-SI/eodag/commit/c564fdd2b5a4f968bf2f58c916cf094bcf378008))

* fix: ISO8601 format accepted everywhere

* fix: support non UTC datetime

- Keyerror on search by id ([#290](https://github.com/CS-SI/eodag/pull/290),
  [`f488962`](https://github.com/CS-SI/eodag/commit/f48896229a00acaca2738ad175aac14dce60e42e))

- List_product_types must not return GENERIC_PRODUCT_TYPE
  ([#261](https://github.com/CS-SI/eodag/pull/261),
  [`d18287d`](https://github.com/CS-SI/eodag/commit/d18287d37a7deb98457d7068402218983150c7f8))

- Load user config file with settings of providers from ext plugin, fixes GH-234
  ([#235](https://github.com/CS-SI/eodag/pull/235),
  [`96d85ab`](https://github.com/CS-SI/eodag/commit/96d85ab3eb0b76bde134db6563a0505de6bbc467))

- Log warning when items_per_page > max_items_per_page
  ([#273](https://github.com/CS-SI/eodag/pull/273),
  [`a769ab6`](https://github.com/CS-SI/eodag/commit/a769ab66c8890633645e702dcdce4491c92a6cc6))

* fix: log warning when items_per_page > max_items_per_page

* fix: increase log level for search_all at each iteration

* fix: add max_items_per_page for some providers

* fix: existing tests

* tests: add a test

- Make setup_logging easier to import ([#221](https://github.com/CS-SI/eodag/pull/221),
  [`47dc78c`](https://github.com/CS-SI/eodag/commit/47dc78cc31f2a462199f32112a2dfb7ef3e6f13a))

- More explicit message on misconfigured auth ([#293](https://github.com/CS-SI/eodag/pull/293),
  [`ed3026d`](https://github.com/CS-SI/eodag/commit/ed3026d5ab322d0097a77598e0ae2fb455030488))

- Paths when downloading and extracting again with archive depth
  ([#292](https://github.com/CS-SI/eodag/pull/292),
  [`df15f00`](https://github.com/CS-SI/eodag/commit/df15f005a1767d69701c2f655e57c82bcd2ceed3))

- Prevent NotebookWidgets.display_html in ipython shell
  ([#307](https://github.com/CS-SI/eodag/pull/307),
  [`e44c9e4`](https://github.com/CS-SI/eodag/commit/e44c9e4a29fd837fa80e4f680c83eb26ae77d7ba))

- Recreate whoosh index when unsupported pickle protocol
  ([#258](https://github.com/CS-SI/eodag/pull/258),
  [`5eb6bb0`](https://github.com/CS-SI/eodag/commit/5eb6bb0a257b5d5ac4bd6623d873d62d0c4b09e7))

- Reload plugins after providers settings update from user conf
  ([#306](https://github.com/CS-SI/eodag/pull/306),
  [`139f5c6`](https://github.com/CS-SI/eodag/commit/139f5c620c09c309e5e260f635b76ae2f3ff7873))

- Remove out-of-date wekeo driver ([#295](https://github.com/CS-SI/eodag/pull/295),
  [`45b4ca5`](https://github.com/CS-SI/eodag/commit/45b4ca50c6cf866286530ccd712634d4a166ddee))

- Return as many products as found by whoosh ([#246](https://github.com/CS-SI/eodag/pull/246),
  [`4f7edc8`](https://github.com/CS-SI/eodag/commit/4f7edc812255f2698d5fe03cd6514d74fdc16f82))

- Sentinel-3 products not available on peps any more
  ([#304](https://github.com/CS-SI/eodag/pull/304),
  [`e1c6173`](https://github.com/CS-SI/eodag/commit/e1c6173efc70ef9fa404eb5ab12dc644d2140410))

### Chores

- Bump version ([#302](https://github.com/CS-SI/eodag/pull/302),
  [`f32b807`](https://github.com/CS-SI/eodag/commit/f32b8071ac367db96ff8f9f8709f0771f9d898f2))

- Bump version ([#308](https://github.com/CS-SI/eodag/pull/308),
  [`362055e`](https://github.com/CS-SI/eodag/commit/362055e3ec7e651eaa2358dbac083a476ede7a43))

### Documentation

- Clearer info about default filename and output folder
  ([#254](https://github.com/CS-SI/eodag/pull/254),
  [`3c7598b`](https://github.com/CS-SI/eodag/commit/3c7598b22ba9e3de1c6ed901455b42b65179e5d9))

- Default links to readthedocs latest version ([#287](https://github.com/CS-SI/eodag/pull/287),
  [`f96a93c`](https://github.com/CS-SI/eodag/commit/f96a93c1ec617b044ff3887ec50cae344e5aeab1))

- Documentation overhaul ([#233](https://github.com/CS-SI/eodag/pull/233),
  [`bab1b7e`](https://github.com/CS-SI/eodag/commit/bab1b7e9c81e096d62ef6b5a2a736445c3b546d7))

- Documentation update before v2.3.0b1 release ([#301](https://github.com/CS-SI/eodag/pull/301),
  [`62c75fe`](https://github.com/CS-SI/eodag/commit/62c75feb7f2ae44e50eaecaa6b4e04936a4451fa))

- Fix intersphinx_mapping links ([#282](https://github.com/CS-SI/eodag/pull/282),
  [`a9c30da`](https://github.com/CS-SI/eodag/commit/a9c30da9978d69ef55b384c7b401195df0cf5afd))

- Fix list_product_types output ([#284](https://github.com/CS-SI/eodag/pull/284),
  [`6d29809`](https://github.com/CS-SI/eodag/commit/6d29809a0dcec97df12ef8644646a3364a9c0a99))

- Readme, badges and classifiers update ([#224](https://github.com/CS-SI/eodag/pull/224),
  [`8c318a5`](https://github.com/CS-SI/eodag/commit/8c318a5c52bac8471362ff04b6c10f6de5e6a7b4))

- Request an access to M2M API for usgs ([#269](https://github.com/CS-SI/eodag/pull/269),
  [`7da1505`](https://github.com/CS-SI/eodag/commit/7da1505fa2936c10deee4350019633959a96d8a5))

- User friendly parameters mapping documentation ([#299](https://github.com/CS-SI/eodag/pull/299),
  [`fdc853e`](https://github.com/CS-SI/eodag/commit/fdc853ee28ea3b9eba27e290ebf9fabde210c715))

* docs: user friendly parameters mapping documentation

* ci: params_mapping_to_csv in docs test env

### Features

- Creodias metadata mapping update ([#294](https://github.com/CS-SI/eodag/pull/294),
  [`1275815`](https://github.com/CS-SI/eodag/commit/1275815cb54449ff7f6cf671199ace2820c174e6))

- Get_logging_verbose function added ([#283](https://github.com/CS-SI/eodag/pull/283),
  [`d175b32`](https://github.com/CS-SI/eodag/commit/d175b32dc96732d754bcb09f3f2f2a78011f1af3))

- Rewrote progress callback mechanism ([#276](https://github.com/CS-SI/eodag/pull/276),
  [`3ce721d`](https://github.com/CS-SI/eodag/commit/3ce721d84aae3c0d090173669419c5c6448dca4c))

* feat: tqdm.auto usage

* feat: mutable progress bar

* fix: unified ProgressCallback usage

* feat: rewrote ProgressCallback interfaces and mechanism

* docs: update ProgressCallback documentation

* docs: update setup_logging in tutorials

- Safe build for STAC AWS providers ([#218](https://github.com/CS-SI/eodag/pull/218),
  [`fec965f`](https://github.com/CS-SI/eodag/commit/fec965f791a74dbf658e0833e1507b7ac950d09d))

* feat: S1_SAR_GRD SAFE build for astraea_eod

* feat: S2_MSI_L1C S2_MSI_L2A SAFE build for earth_sarch

* feat: S2_MSI_L1C S2_MSI_L2A SAFE build for astraea_eod

* feat: check manisfest.safe for SAFE build

* test: safe build tests

- Sentinel non-safe product types ([#228](https://github.com/CS-SI/eodag/pull/228),
  [`dac0046`](https://github.com/CS-SI/eodag/commit/dac0046937df69c25978146637baf7d230519778))

* feat: distinct sentinel non-safe product types

* feat: new provider earth_search_cog for S2_MSI_L2A_COG

* fix: aws safe product destination path

### Testing

- Fixes root link in stac static resources ([#219](https://github.com/CS-SI/eodag/pull/219),
  [`c83d889`](https://github.com/CS-SI/eodag/commit/c83d889286c67678bc556043e11e19f34da10b99))

- Progress_callback unit tests ([#285](https://github.com/CS-SI/eodag/pull/285),
  [`3945ddd`](https://github.com/CS-SI/eodag/commit/3945ddd15a94266dfe79a0c89ed16d09fec179b7))


## v2.2.0 (2021-03-26)

### Bug Fixes

- Conf update with external plugin, fixes GH-184 ([#189](https://github.com/CS-SI/eodag/pull/189),
  [`fc2bd76`](https://github.com/CS-SI/eodag/commit/fc2bd76ae3cc775ed9068461c4cbc1892ce3fe28))

- Cors issue with docker-compose ([#188](https://github.com/CS-SI/eodag/pull/188),
  [`11a6c14`](https://github.com/CS-SI/eodag/commit/11a6c14378b0f02b8708b38ce7bc68a984beb4ce))

- Locations should not be part of the kwargs passed to query
  ([#186](https://github.com/CS-SI/eodag/pull/186),
  [`17a6cbb`](https://github.com/CS-SI/eodag/commit/17a6cbbaa0bff042eace060a4e6d269a2a9b1efd))

- More explicit signature for setup_logging ([#200](https://github.com/CS-SI/eodag/pull/200),
  [`720588a`](https://github.com/CS-SI/eodag/commit/720588ae14b19f555c80b89019722a45770aff1d))

- Usgs plugin uses m2m api ([#209](https://github.com/CS-SI/eodag/pull/209),
  [`cfc291f`](https://github.com/CS-SI/eodag/commit/cfc291ff30ab84fcf4f11798dc012437b6154d1c))

* fix: usgs plugin using m2m api

* fix: misconfigured provider skip

- Whoosh search returns all the matching elements ([#201](https://github.com/CS-SI/eodag/pull/201),
  [`0c16038`](https://github.com/CS-SI/eodag/commit/0c1603874f11495dfa9a2340e699059a4f24212a))

### Chores

- Tox fix for pypi ([#181](https://github.com/CS-SI/eodag/pull/181),
  [`c043500`](https://github.com/CS-SI/eodag/commit/c043500cd6aa80303c2d961e08f3e6769d8eba3b))

### Documentation

- Documentation update for 2.2.0 ([#211](https://github.com/CS-SI/eodag/pull/211),
  [`88fd434`](https://github.com/CS-SI/eodag/commit/88fd434ec96bf56620bf133915c3d2e5dcafb23d))

- Fixed and scrollable sidebar ([#196](https://github.com/CS-SI/eodag/pull/196),
  [`0adf3de`](https://github.com/CS-SI/eodag/commit/0adf3de6d3792755c2498f51b3b9ce29a3f6038f))

- Update documentation and community templates ([#198](https://github.com/CS-SI/eodag/pull/198),
  [`2140d9d`](https://github.com/CS-SI/eodag/commit/2140d9dce4808d6d5f1ecc70439c0cd11fcd1a60))

### Features

- Add --all option to the search command to search for all the products
  ([#204](https://github.com/CS-SI/eodag/pull/204),
  [`49b15cc`](https://github.com/CS-SI/eodag/commit/49b15ccd7aa5b83f19fb98b8b4a0dae279c2c18c))

- Add docker-compose for STAC server and browser ([#183](https://github.com/CS-SI/eodag/pull/183),
  [`7f1f3e1`](https://github.com/CS-SI/eodag/commit/7f1f3e10deb70213006f83fb0508fce6d72b5fc0))

Co-authored-by: apparell <pasquale.papparella@pm.me>

- Add two new methods to search for products, search_iter_page and search_all
  ([#190](https://github.com/CS-SI/eodag/pull/190),
  [`ab1c105`](https://github.com/CS-SI/eodag/commit/ab1c1054e802d7a25980c331eb19a1c48f1ffc53))

* refactor: TestCore

* tests: move guess_product_type tests from doctests to unit tests

* tests: add a single end-to-end test for _search_by_product with sobloo

* refactor: add _prepare_search method that is used by search internally

* feat: add a warning when box or bbox are used instead of geom in a search

* tests: add tests for _prepare_search and guess_product_type

* feat: add count to _do_search and _do_search tests

* feat: expose raise_errors in _do_search and docstring

* feat: add search_iter_page to iterate over the pages of a product search

* feat: add search_all to EODataAccessGateway

* fix: stop iteration if the next page returns the same first product

* fix: improve an error message in set_preferred_provider and black

* fix: failing test due to the removal of locations from kwargs in _prepare_search

* fix: wrong pagination entry in stac_provider.yml

* tests: fix execute_search to trigger a count request by default

* feat: add a mechanism to get the next page in a search

* tests: add a couple of end-to-end tests for search_all

* fix: add a next_page_url to QueryStringSearch, used in search_iter_page if available

* fix: do not _search_by_id if id is None, as expected by the CLI

- New pagination key next_page_url_key_path ([#199](https://github.com/CS-SI/eodag/pull/199),
  [`4f1604e`](https://github.com/CS-SI/eodag/commit/4f1604ee1167fdef1ee7395af6781e2f1df14577))

### Testing

- Add windows support ([#192](https://github.com/CS-SI/eodag/pull/192),
  [`af9afc8`](https://github.com/CS-SI/eodag/commit/af9afc8f4e21f6af129c10a1763fb560ac0dfbe2))

* fix: usage of NamedTemporaryFile on Windows

* fix: correctly replace the default location file path

* fix: not just expect a unix tmp directory

* CI: run the unit/integration tests on windows

* CI: attempt to find where nose fails on windows

* CI: add --traverse-namespace to fix nose on Windows from PY38


## v2.1.1 (2021-03-18)

### Bug Fixes

- Wrong mutually exclusive option in the search command
  ([#173](https://github.com/CS-SI/eodag/pull/173),
  [`7e879d2`](https://github.com/CS-SI/eodag/commit/7e879d265c568c7642b0bc5cfe162885bd8aa3ed))

### Chores

- Bump version
  ([`277b1e1`](https://github.com/CS-SI/eodag/commit/277b1e1d4aefdcf06652e592ff7d82992b9647c8))

- Ci with GitHub actions ([#159](https://github.com/CS-SI/eodag/pull/159),
  [`541794b`](https://github.com/CS-SI/eodag/commit/541794bb1ca3d4f31b7df75d9c6ee62b0535dbb5))

- Tox fix for pypi (#181) ([#182](https://github.com/CS-SI/eodag/pull/182),
  [`044fd8b`](https://github.com/CS-SI/eodag/commit/044fd8b904f84c579e1ac84fe8c5aac6a9b9591e))

- Update tox ([#160](https://github.com/CS-SI/eodag/pull/160),
  [`857eeb7`](https://github.com/CS-SI/eodag/commit/857eeb73333698ec4f2e1f71fbbb7f4b59fa7b7a))

* chor: tox pypi - skip package and dev deps install * chor: add linters to tox envlist

### Documentation

- Display star number instead of watch number ([#175](https://github.com/CS-SI/eodag/pull/175),
  [`d278e12`](https://github.com/CS-SI/eodag/commit/d278e12087d8e7aae17e9ba46c798e1bd8f5b4cd))

- Menu items sort
  ([`16619f2`](https://github.com/CS-SI/eodag/commit/16619f23e16bcc72fad0ba5cbd7d0999c90ceb3b))

- References to eodag-sentinelsat
  ([`1a38d08`](https://github.com/CS-SI/eodag/commit/1a38d085d1839a4c46b6a66bde32ced31d7ce60f))

### Features

- Auto load ext plugins providers config, fixes GH-172
  ([#176](https://github.com/CS-SI/eodag/pull/176),
  [`21a2dae`](https://github.com/CS-SI/eodag/commit/21a2dae43674fa1d751e21d20068bd6973684fa9))


## v2.1.0 (2021-03-09)

### Bug Fixes

- Add count bool parameter to query methods
  ([`057c1e6`](https://github.com/CS-SI/eodag/commit/057c1e69872214c5150d64055180c6e691acdf1f))

- Aws auth and download
  ([`2df5db5`](https://github.com/CS-SI/eodag/commit/2df5db5e33ec42dd09c66a5a50ef1692866a7532))

- Dates considered as utc to create a timestamp for sobloo
  ([`5b06ca3`](https://github.com/CS-SI/eodag/commit/5b06ca3e23d741a446a798958fff3d8a2d36347b))

- Download progress_callback, fixes GH-157
  ([`ce84b33`](https://github.com/CS-SI/eodag/commit/ce84b330b88552a36c351928d053c4aa6ed6824e))

- Eodag-cube does not yet allow to download a product subset, fixes GH-153
  ([`27b2db2`](https://github.com/CS-SI/eodag/commit/27b2db249b9e66ce41e86f8e03ebb9e8ff27630d))

- Expose a timeout parameter in load_stac_items
  ([`85be8a7`](https://github.com/CS-SI/eodag/commit/85be8a721aa2479811a5dc0bc62cf42b5e836bbe))

- Metadata mapping update and uniformization, fixes GH-154
  ([`a958dae`](https://github.com/CS-SI/eodag/commit/a958dae2af30d999ea225d1232e386806657ab27))

- Remove dependency to unidecode, fixes GH-158
  ([`99cb67b`](https://github.com/CS-SI/eodag/commit/99cb67b58c62e60c67dd557afb17a7d71f1e38a1))

- Remove python3.5 support
  ([`f67c365`](https://github.com/CS-SI/eodag/commit/f67c365a4534b51ddbf9290767112bcd09bff89e))

- Return empty list when no results entry in a JSON response, fixes GH-155
  ([`7c7f00c`](https://github.com/CS-SI/eodag/commit/7c7f00c30d4a0afd377e52666b7e454d357c0d21))

- Skip pagination starts from 1 for mundi, not 0
  ([`a043e2a`](https://github.com/CS-SI/eodag/commit/a043e2acbfc2872ef8381adadc498ba3bee320fc))

- Two error messages
  ([`ff65795`](https://github.com/CS-SI/eodag/commit/ff657954650d274b920283980c0dd8bd656cdd2a))

- Updatable metadata-mapping for stac providers
  ([`b826f21`](https://github.com/CS-SI/eodag/commit/b826f21453e086ab90dbcbb1e06dcbaa5cf9d6cc))

- Use pystac to open STAC static catalogs
  ([`431c47c`](https://github.com/CS-SI/eodag/commit/431c47c78e631508409120e8b13484721641c30f))

### Chores

- Bump version
  ([`0852432`](https://github.com/CS-SI/eodag/commit/08524322b0e2b9feef3ea6a252b29dfb31073766))

### Documentation

- Copernicus dem tutorial
  ([`07aa48a`](https://github.com/CS-SI/eodag/commit/07aa48a4eb4b9025df8b47136a6210e49aaa913a))

- Readme update
  ([`ee240fa`](https://github.com/CS-SI/eodag/commit/ee240fa3f09a90461fa445167b75c82cc456b9bb))

- Readme update
  ([`ab57fc9`](https://github.com/CS-SI/eodag/commit/ab57fc9c5c14b57d513271ad89955afe0235083d))

### Features

- Add a locations dict parameter to search
  ([`616d1a9`](https://github.com/CS-SI/eodag/commit/616d1a960324313c18309d905c4465ece3f9b90b))

- Add quicklook & thumbnail to stac properties
  ([`0f3b23e`](https://github.com/CS-SI/eodag/commit/0f3b23e30e2160f1a551ba8ef8c1d7f353b577b3))

- Assets support for HTTPDownload
  ([`02f9d9f`](https://github.com/CS-SI/eodag/commit/02f9d9f25c23d4ba55b0ac03a5e4380a6f5b5ffe))

- Earth_search as new provider
  ([`4f64016`](https://github.com/CS-SI/eodag/commit/4f6401661a6724c9c95a3538f7043a90a1e586be))

- Intersects option for filteroverlap
  ([`7166a42`](https://github.com/CS-SI/eodag/commit/7166a42da9c5e337cc73d6b195d50f3220b0e607))

- List providers supporting a given product_type
  ([`31ca3eb`](https://github.com/CS-SI/eodag/commit/31ca3eb878b7585310898d409f7293391b8196dc))

- New AwsAuth plugin enables no-sign-request and profiles
  ([`b665dd4`](https://github.com/CS-SI/eodag/commit/b665dd4c448d773b243c2ded09efdd5d0bda1248))

- New provider usgs_satapi_aws
  ([`c9fd10d`](https://github.com/CS-SI/eodag/commit/c9fd10d0fc241193ae65f2f608b31bd581922876))

- New StaticStacSearch plugin
  ([`d1b8f36`](https://github.com/CS-SI/eodag/commit/d1b8f36f9b357308373095d8848f3a68fe090c65))


## v2.0.1 (2021-02-05)

### Bug Fixes

- Add warning for the total number of results returned by theia
  ([`f2b3d07`](https://github.com/CS-SI/eodag/commit/f2b3d076b022d8dc7b9f7a21498297c665f5a05f))

- Aws_eos geom search
  ([`aac44a6`](https://github.com/CS-SI/eodag/commit/aac44a61ad42133c1e32224e0699dc6eb32e5ff3))

- Aws_eos metadata re-mapping
  ([`790e9f5`](https://github.com/CS-SI/eodag/commit/790e9f56e2aeb9b2805f522057cb4da4d84aa8e4))

- Better wrong or missing credentials handling
  ([`23af1f0`](https://github.com/CS-SI/eodag/commit/23af1f0e8f4247e5ad3a1b88f0440685180f40fe))

- Broken pip search
  ([`bfe347d`](https://github.com/CS-SI/eodag/commit/bfe347db7216ece9df232d70e11babc17b2c1a04))

- Changed country key in locations conf template
  ([`6576287`](https://github.com/CS-SI/eodag/commit/657628718e509b88d39e0222869de23cacc8f9ab))

- Cli list product_types
  ([`d2a7386`](https://github.com/CS-SI/eodag/commit/d2a738611ea795d0a3f3a38f825bfed1252a9ded))

- Cli serve-rest settings import
  ([`25d029a`](https://github.com/CS-SI/eodag/commit/25d029aad616213e10feec63e25dfdc2dc564275))

- Cli update for geom search, fixes eodag/eodag#17
  ([`7708015`](https://github.com/CS-SI/eodag/commit/77080155d2e0089816e89e9b777dc38fd7d3d61d))

- Do not try to import rasterio, fixes GH-150
  ([`6db9e71`](https://github.com/CS-SI/eodag/commit/6db9e711581ffd06bb69592e65d6b4f8d19f8bb5))

- Dynamic recent dates for onda end to end test
  ([`ec4f4b1`](https://github.com/CS-SI/eodag/commit/ec4f4b1b883d0f65b27ecc1f1e723f6774da330c))

- E2e test mundi extent
  ([`614075f`](https://github.com/CS-SI/eodag/commit/614075f279cebe61c79aca7355f2653efeafda94))

- Expose __version__ in main __init__.py
  ([`98dcc6b`](https://github.com/CS-SI/eodag/commit/98dcc6b651d0a7f3d1b465480e461ec7b2d9a460))

- Gitlab-ci docker img update
  ([`425e44c`](https://github.com/CS-SI/eodag/commit/425e44c08aca1ebca8d5e4d342c40e90c3f6f7b2))

- Gitlab-ci pypi publish
  ([`8a891ef`](https://github.com/CS-SI/eodag/commit/8a891ef2ec144e9ced5f28134320b1e9affde560))

- Index rebuild on nfs, fixes GH-151
  ([`d893dec`](https://github.com/CS-SI/eodag/commit/d893dec5e2e76a3d4b502680e48ff2386edf5474))

- Labextension legacy rest compatibility
  ([`49366bd`](https://github.com/CS-SI/eodag/commit/49366bd6b7509466114cfec804003f6fe726bb85))

- More verbose build_index error
  ([`9405571`](https://github.com/CS-SI/eodag/commit/9405571bdc8b43bb9a98de86478270c5f5ee93f4))

- Multipolygons geom search and stac-serve
  ([`6881134`](https://github.com/CS-SI/eodag/commit/6881134cfe797e191ad1c67f56653c547756a965))

- Precommit fails with py36
  ([`c14d345`](https://github.com/CS-SI/eodag/commit/c14d345e320f5f6cfa19c62583461fc2e971a1a2))

- Remove location param from query after usage
  ([`8e6a79a`](https://github.com/CS-SI/eodag/commit/8e6a79afacb39230738d23ff1143e951fe3029ed))

- Rename sort_by_extent to group_by_extent
  ([`b7fe6b1`](https://github.com/CS-SI/eodag/commit/b7fe6b152341fdecbbf3b4c3d4c21b09393822a8))

- Return extracted path after download
  ([`7714bea`](https://github.com/CS-SI/eodag/commit/7714bea1c1bf4a80f9607256881cbccf9a997c16))

- Same name locations geom union instead of intersect
  ([`fdf2b08`](https://github.com/CS-SI/eodag/commit/fdf2b08fc4d2cde352c1a1fa701c62fff82dc4d7))

- Search using product_type_def_params and product_type
  ([`4bcbe55`](https://github.com/CS-SI/eodag/commit/4bcbe5592f8426e3936fefec7d81c4db4ebcd0b7))

- Stac api 1.0.0-beta.1 update
  ([`82f2753`](https://github.com/CS-SI/eodag/commit/82f27537b0e87d7c6fae7df8f77736706c581ea1))

- Stac items links
  ([`64557a9`](https://github.com/CS-SI/eodag/commit/64557a95b8ded531f5d151dd4ea57b9647b74c3f))

- Stac provider dates format
  ([`cebac98`](https://github.com/CS-SI/eodag/commit/cebac98290221b1edca0b314b70f587e1b6aa55d))

- Tests can run in parallel mode with tox, fixes GH-103
  ([`b487473`](https://github.com/CS-SI/eodag/commit/b4874734c0ac5a8ff2d643d7bee680d2addfa6c3))

- Typeerror on unexpected geometry type
  ([`e356ed0`](https://github.com/CS-SI/eodag/commit/e356ed05eba7a616f69cc71d469dad67fc5d9304))

- Update_providers_config with existing provider
  ([`8f74bea`](https://github.com/CS-SI/eodag/commit/8f74bea8a26d0d16b302fca50ee912801caaeadd))

- Use jsonpath-ng instead of jsonpath-rw and pyjq
  ([`1d00fe3`](https://github.com/CS-SI/eodag/commit/1d00fe3cca8f8c0d908739c3f5b1e543d1785d7d))

- Various issues with the crunchers
  ([`7bc6947`](https://github.com/CS-SI/eodag/commit/7bc694749053bae7a060f7ff04832702aea84199))

- Whoosh fields update
  ([`4a15d7f`](https://github.com/CS-SI/eodag/commit/4a15d7f894a379d48639876796ee159cac4c3986))

### Chores

- Bump version
  ([`bd351ec`](https://github.com/CS-SI/eodag/commit/bd351ec791b91862944e1eeff9f89483cb85ce86))

- Bump version
  ([`c667e72`](https://github.com/CS-SI/eodag/commit/c667e72bcff1fd6357894ae6f27dbb4c5e1c3d2b))

- Gitlab ci configuration, fixes eodag/eodag#22
  ([`8c8bf95`](https://github.com/CS-SI/eodag/commit/8c8bf95a220736f7b795284f4be246615851c131))

- Nbsphinx version
  ([`d2817ce`](https://github.com/CS-SI/eodag/commit/d2817ce1603a1b17855d0a284d8a29f0adb79e5b))

- Python versions update
  ([`741a340`](https://github.com/CS-SI/eodag/commit/741a34068d0a91f4bbac46d863623c91d65ff5b9))

- Removed fixed dependencies, fixes GH-82
  ([`ded0bfe`](https://github.com/CS-SI/eodag/commit/ded0bfe5da11e7ff4c2288abf7a9d93cc34f28c9))

- Tooling update
  ([`fc07f66`](https://github.com/CS-SI/eodag/commit/fc07f66ed0a968382f3b110d620e262551d97c5b))

### Code Style

- Lighter crunchers logging
  ([`3696fc8`](https://github.com/CS-SI/eodag/commit/3696fc842f925303dc6947c61aafea15dda1460e))

### Documentation

- Readme update
  ([`f3d5535`](https://github.com/CS-SI/eodag/commit/f3d5535a06fefdde2f79da3ecaaf59323d076a20))

- Stac client tuto
  ([`5e6764e`](https://github.com/CS-SI/eodag/commit/5e6764ed1250c943e4b8d3aa0215c70b33b9effd))

- Swagger stac api doc
  ([`e095901`](https://github.com/CS-SI/eodag/commit/e095901e956f1d9be431b198fd327674255741d2))

- V2.0 documentation update
  ([`3a645b6`](https://github.com/CS-SI/eodag/commit/3a645b694364307a92745193109a6ab76cde2744))

### Features

- Add new provider dynamically
  ([`b912305`](https://github.com/CS-SI/eodag/commit/b912305ee2bd1995c8cad9c79a2846344f1d5a25))

- Allow to dynamically set download options, fixes GH-145 GH-112
  ([`1ad5afe`](https://github.com/CS-SI/eodag/commit/1ad5afead302158d87a243396ff7bd96451eb995))

- Astraea_eod as new STAC provider
  ([`1a0ff44`](https://github.com/CS-SI/eodag/commit/1a0ff440607dc92e519e6ba43d9c868679c720b3))

- Generic_product_type usage for unknown product types fixes
  ([`73a0364`](https://github.com/CS-SI/eodag/commit/73a03646ea3ad2019cb180ff1da6368e649388d7))

- Get_data, drivers and rpc server moved to eodag-cube
  ([`de3f873`](https://github.com/CS-SI/eodag/commit/de3f873581b2b570b5d7b7a162b5c1491ad1db9d))

- Load static features as SearchResult, fixes eodag/eodag#3
  ([`21ca0e5`](https://github.com/CS-SI/eodag/commit/21ca0e5281f01a6330d72c50356fe099fe2facb7))

- Load static stac catalogs, fixes eodag/eodag#24
  ([`747b966`](https://github.com/CS-SI/eodag/commit/747b966b60d3382fcd3aaf39481ebaa5983c4cf3))

- New crunches FilterDate, FilterDate and updated FilterOverlap, fixes GH-137
  ([`e63d06d`](https://github.com/CS-SI/eodag/commit/e63d06d69e66ecdb6a0d15ec90de84ed4cb65469))

- New method deserialize_and_register, fixes eodag/eodag#23 GH-140
  ([`a66523f`](https://github.com/CS-SI/eodag/commit/a66523fc019f861927667702ee2142e088ffdb4f))

- No fixed provider for stac server
  ([`05b24fc`](https://github.com/CS-SI/eodag/commit/05b24fc692cc5b55400ed8339b638b1eafe4d0e9))

- Product types update
  ([`6bdc5bb`](https://github.com/CS-SI/eodag/commit/6bdc5bb25635739c60b747ff42dc993d596778b0))

- Search by geometry instead of bbox, fixes #49
  ([`8f2750e`](https://github.com/CS-SI/eodag/commit/8f2750e07681f6522b9b5c5f6e5e272dde79683e))

- Stac collections filterables
  ([`97b9b6a`](https://github.com/CS-SI/eodag/commit/97b9b6a7f4df6a7db419a3e3c8a39c165f1bfc6d))

- Stac compliant rest api
  ([`29e4d99`](https://github.com/CS-SI/eodag/commit/29e4d992b7b838033651297dc0e483df221da5f9))

- Stac custom search
  ([`eb73623`](https://github.com/CS-SI/eodag/commit/eb73623a3713432f93dd17daee90a4aa58df1ce6))

- Support regex query from locations file
  ([`351e378`](https://github.com/CS-SI/eodag/commit/351e37851a4891942305ca32210f8c41c043bc41))

- Use locations conf template by default, fixes eodag/eodag#6
  ([`115e53c`](https://github.com/CS-SI/eodag/commit/115e53c387d4514004a18f92552d94e640cfb3eb))

### Refactoring

- Black reformat and copyright date update
  ([`91f2d1f`](https://github.com/CS-SI/eodag/commit/91f2d1f684e068bd264d3e677b3c45ecb4898750))

- Py35 compatibility, docstrings
  ([`953acd7`](https://github.com/CS-SI/eodag/commit/953acd7a49cd181bad9fcfffafd70bb1ed0e9c55))

- Removed py27 compatibility code
  ([`a3c8e2b`](https://github.com/CS-SI/eodag/commit/a3c8e2b0c35491c3e399656391ea05deaa9fee52))

- Replace fiona by pyshp
  ([`1a9d488`](https://github.com/CS-SI/eodag/commit/1a9d4887a081cf43d2c0e309ffdc6ef843f2c64d))

- Utils methods
  ([`c38ef08`](https://github.com/CS-SI/eodag/commit/c38ef0817f259a80417cc3d22c19621db11e2344))

### Testing

- Click 7.0 vs 7.1 compatibility
  ([`14500e9`](https://github.com/CS-SI/eodag/commit/14500e9e5f8844fcf2efbc4ce2fbfc5ef338f5d8))

- More stac features
  ([`dacce19`](https://github.com/CS-SI/eodag/commit/dacce191cd15c0a188339d875e7aff2e5ef7e2b9))

- Product_type fixes
  ([`e6e6931`](https://github.com/CS-SI/eodag/commit/e6e6931f4cbd85f86fdc1f57fdfb8caa4241d952))

- Search by geometry
  ([`b69375c`](https://github.com/CS-SI/eodag/commit/b69375cd03463e28087303230fdc3e9857d5e0e1))

- Stac features
  ([`a47806e`](https://github.com/CS-SI/eodag/commit/a47806ed24bb4bee18d53559e6582d2bd89a8a28))

- Stac static catalog
  ([`c925f7a`](https://github.com/CS-SI/eodag/commit/c925f7aac756a06bd9ead5892e2bf2d0cd8b632d))

- Tests added to common methods
  ([`86c7977`](https://github.com/CS-SI/eodag/commit/86c797763aa180f422da55c3f7bf508759043db9))


## v1.6.0 (2020-08-24)

### Bug Fixes

- Aws_s3_sentinel2_l1c replaced with aws_eos
  ([`cea9a93`](https://github.com/CS-SI/eodag/commit/cea9a937476321d9dd944e8ea08495fa8e616854))

- Download error after zip delete, fixes #142
  ([`39308ae`](https://github.com/CS-SI/eodag/commit/39308ae78fae7bf96c30552cf12543bd9f0b6009))

- Empty paths returned by HTTPDownload.download_all()
  ([`6399631`](https://github.com/CS-SI/eodag/commit/63996319f57d9eb6d73e01908f29b3e6a1740724))

- Format warning by flake8 latest version
  ([`7448cf8`](https://github.com/CS-SI/eodag/commit/7448cf8e41a83e56197ca1fef913d3dd2defb90d))

- Lansat-8 search for onda
  ([`c068ff8`](https://github.com/CS-SI/eodag/commit/c068ff83569388eda41d1d22cf79daa1fdaf4192))

- Negative coords in returned bbox geometry, fixes #143
  ([`208c114`](https://github.com/CS-SI/eodag/commit/208c114843d9c1422eb26acc0abf27d99ff945e7))

- Progress_bar max_size preset
  ([`2a5d405`](https://github.com/CS-SI/eodag/commit/2a5d4052c360be9b7109ca570209c46f533b58c5))

- Python-dateutil version for moto update, fixes #141
  ([`4b0b67d`](https://github.com/CS-SI/eodag/commit/4b0b67d79c0e5f48f4a8419ef24176b1d126891b))

- Rest server import error, fixes #132
  ([`b80ea0f`](https://github.com/CS-SI/eodag/commit/b80ea0f05cb45afc45b71a62b0f39e7a585e86c6))

- Shapely parseException warning, fixes #123
  ([`623b32a`](https://github.com/CS-SI/eodag/commit/623b32a3e769bf5db4a89657d85a05b50a7f18de))

- Store & check product types index version
  ([`69779cb`](https://github.com/CS-SI/eodag/commit/69779cb8ae70c4acf46493cd031565f55a31b1e6))

- Unparsed base_uri in properties, fixes #122
  ([`1e0d894`](https://github.com/CS-SI/eodag/commit/1e0d894920e8bb553d6370c64c6fa180cf94fc27))

- Usgs product summary pattern update
  ([`5cf3cc6`](https://github.com/CS-SI/eodag/commit/5cf3cc6c42de4f08c14c2f66e31781250e129813))

### Chores

- Removed xarray pkg version upper bound
  ([`52e8363`](https://github.com/CS-SI/eodag/commit/52e8363b9474081310f65b51aa94366bc0ace6f8))

### Features

- Added support for py38
  ([`fe0d8da`](https://github.com/CS-SI/eodag/commit/fe0d8da7e266338d140d18f9032c61efef033a66))

- Advanced tuto notebook, fixes #130
  ([`22f02d8`](https://github.com/CS-SI/eodag/commit/22f02d89ed490ed91add246755a5548faf41bc57))

- Cbers-4 for aws_eos
  ([`baa5f84`](https://github.com/CS-SI/eodag/commit/baa5f84dece41575d9f94a112f34ad354a290a55))

- Default user_conf usage in cli mode
  ([`2ec4edb`](https://github.com/CS-SI/eodag/commit/2ec4edb0bf37f2030b349e7fe82fe51e8faa0a53))

/bin/bash: :wq: command not found

- Lansat-8, MODIS, NAIP for aws_eos
  ([`154fe2e`](https://github.com/CS-SI/eodag/commit/154fe2e0825a8cb2889717662d007ffc6490a084))

- Log Retry-After info returned by provider, fixes #37
  ([`10c7b12`](https://github.com/CS-SI/eodag/commit/10c7b129002d5e7a8a5d8ff3df4cd6886c8fde9b))

- Metadata auto discovery, replaces custom param
  ([`9445964`](https://github.com/CS-SI/eodag/commit/9445964a8680c19237729b709b2a53d8602d2b74))

- New PostJsonSearch plugin, aws_eos provider + S2_MSI_L1C to SAFE
  ([`539c605`](https://github.com/CS-SI/eodag/commit/539c605e683b35b7e4e7142487162b33a05b22c1))

- New theia product types for S2, SPOT, VENUS, OSO
  ([`bb9ee42`](https://github.com/CS-SI/eodag/commit/bb9ee4253dfa9d735c38e102b091aa83cf903b90))

- Peps queryable params update
  ([`fd00cae`](https://github.com/CS-SI/eodag/commit/fd00cae7f0e7bf3013a8d7cf2c7fa725d9bb7363))

- S1_sar_grd and S2_MSI_L2A for aws_eos to SAFE format
  ([`a0ba8d4`](https://github.com/CS-SI/eodag/commit/a0ba8d4255d7a0c872b8f2cff832ebcc59c5acf0))

- S2_msi_l2a for aws_eos search by id (specific_qssearch feature)
  ([`662eaf1`](https://github.com/CS-SI/eodag/commit/662eaf1fcf007ecc1136ac122b4457af90c57f3d))

- Use product_type_config as default product properties
  ([`5a175cb`](https://github.com/CS-SI/eodag/commit/5a175cb4a82207b90e6194cc4e9fda6056d8cbdf))

### Refactoring

- Download prepare & finalize to base plugin
  ([`ada6797`](https://github.com/CS-SI/eodag/commit/ada67975003874095543df3da570984d26ba1b7b))

- Jsonpath obj creation factorized
  ([`49e924d`](https://github.com/CS-SI/eodag/commit/49e924d5831f6d4a42df754a9ed0326da72076a6))

### Testing

- E2e tests for offline peps & aws_eos
  ([`4e1923b`](https://github.com/CS-SI/eodag/commit/4e1923be4e03a14d7acbd1b3baec21a85ece9969))

- End-to-end dates update
  ([`2ceef7c`](https://github.com/CS-SI/eodag/commit/2ceef7c14d699c4f9d919147410324ad0d2a4e10))

- End-to-end dates update
  ([`5ac08ec`](https://github.com/CS-SI/eodag/commit/5ac08ec040fe64d716cf12f8093f717e9161e08a))

- Use tempdir for serialization, fixes #100
  ([`d6f3f48`](https://github.com/CS-SI/eodag/commit/d6f3f48707f630f098f566801e8b941065a5dc25))


## v1.5.2 (2020-05-07)

### Bug Fixes

- Cli download_all register plugin, fixes #134
  ([`6e6aed8`](https://github.com/CS-SI/eodag/commit/6e6aed84ac3ea8cd5c2f5860db5b851f4b8b79d2))


## v1.5.1 (2020-04-08)

### Bug Fixes

- Productionstatus renamed to storageStatus
  ([`d11af66`](https://github.com/CS-SI/eodag/commit/d11af6601cf25f195c247eb28162c7904fde8656))


## v1.5.0 (2020-04-08)

### Bug Fixes

- Auth errors messages more explicit
  ([`378694c`](https://github.com/CS-SI/eodag/commit/378694cd2c084cb748ddb99d8b36c48add119232))

- New search endoint aws_s3_sentinel2_l1c and RequestPayer option usage, fixes #131
  ([`c8f75c5`](https://github.com/CS-SI/eodag/commit/c8f75c530602e6a4bf4a7872e22bbb6ea3b6e8fa))

### Build System

- Freeze click version to prevent test fail
  ([`4776cf9`](https://github.com/CS-SI/eodag/commit/4776cf9bec1e7550a0cae4a2e0606135f6851115))

### Chores

- Bump version
  ([`9680cf3`](https://github.com/CS-SI/eodag/commit/9680cf3ab6e856f9ec01f78eb3bf8b2b7ce61086))

### Features

- Not-available products download management, fixes #125
  ([`05e2202`](https://github.com/CS-SI/eodag/commit/05e2202b6c3d9426d2d19a2e002460de83f38ae9))

- Productionstatus standardization over providers
  ([`63eea5a`](https://github.com/CS-SI/eodag/commit/63eea5a4a885f9f7449dbba8e5114ac5b640b2ec))

### Testing

- E2e test minor changes
  ([`766faaa`](https://github.com/CS-SI/eodag/commit/766faaadc60499dc0e8de89bb0b1316e0d3d235b))

- Update SUPPORTED_PRODUCT_TYPES
  ([`0f70077`](https://github.com/CS-SI/eodag/commit/0f700776ba303783ecf9eb3df24f73777698615a))


## v1.4.2 (2020-03-04)

### Bug Fixes

- Skip badly configured providers in user conf, see #129
  ([`aa88fa6`](https://github.com/CS-SI/eodag/commit/aa88fa6a5062bd2851fcf9829911a549e217bd0b))


## v1.4.1 (2020-02-25)

### Bug Fixes

- Warning message if an unknow provider is found in user conf, fixes #129
  ([`df6b4fe`](https://github.com/CS-SI/eodag/commit/df6b4fee645c2d44507246f564cf980c63fef045))


## v1.4.0 (2020-02-24)

### Bug Fixes

- Deprecation warnings in tests and py27 compatibility
  ([`034819a`](https://github.com/CS-SI/eodag/commit/034819a4a0cf43ac641854d14287ffc954f30622))

- Onda query quoting
  ([`28073e8`](https://github.com/CS-SI/eodag/commit/28073e8808184f9a9241a032d73607fb79977201))

- Sobloo and creodias quicklook
  ([`53cb3bb`](https://github.com/CS-SI/eodag/commit/53cb3bbc7818812e49ea7f010ea1c749aaac0d99))

- Theia-landsat provider moved to theia, fixes #95
  ([`22e74b8`](https://github.com/CS-SI/eodag/commit/22e74b88142eb7fc85ae0b9e40e10eef2171d649))

- Urllib HTTP errors handle
  ([`e22bc33`](https://github.com/CS-SI/eodag/commit/e22bc33f3364bb6c4f9bfd1bb392557259063cfd))

### Features

- Add to query the parameters set in the provider product type definition
  ([`ed3daa0`](https://github.com/CS-SI/eodag/commit/ed3daa03579f1aa53c983e6810389fea0f233d44))

- New S3RestDownload plugin for mundi, fixes #127
  ([`863b372`](https://github.com/CS-SI/eodag/commit/863b3725fa3021b3ab2bc66644a2994639692de4))

- S2_msi_l2a support for peps, fixes #124
  ([`18ab40f`](https://github.com/CS-SI/eodag/commit/18ab40f929d71709733bbaf603b7665352c88952))

- S3_olci_l2lfr support for mundi, see #124
  ([`a5c6389`](https://github.com/CS-SI/eodag/commit/a5c6389823101998a01071abe6c35f27dfc1cb3c))

### Testing

- Creodias and onda in end-to-end tests
  ([`0c8d6c8`](https://github.com/CS-SI/eodag/commit/0c8d6c8a1f4426d441d3ed7d33b61889219ce1ac))

- Mundi in end-to-end tests
  ([`1a8ac9c`](https://github.com/CS-SI/eodag/commit/1a8ac9cf8fd0c4528ed311924eea2e4fb39a0098))


## v1.3.6 (2020-01-24)

### Bug Fixes

- End-to-end tests, fixes #119, fixes #98
  ([`5beec33`](https://github.com/CS-SI/eodag/commit/5beec33b6475bc90770cb43ca7d754ccd9453da9))

- Missing auth and remote location parsing in download_all, fixes #118
  ([`283b759`](https://github.com/CS-SI/eodag/commit/283b75903ce67203fcf59fab36887d71fda4939d))

- Py27 encodeurl in querystring
  ([`dc08dbd`](https://github.com/CS-SI/eodag/commit/dc08dbda4dcb2af872095aecc0e9064d3a59a595))

- Usgs plugin, fixes #73
  ([`f02ecbd`](https://github.com/CS-SI/eodag/commit/f02ecbd4fa40d8bbbe2ca8c42511ec32d8cf4083))


## v1.3.5 (2020-01-07)

### Bug Fixes

- New test for readme/pypi syntax
  ([`d8bb323`](https://github.com/CS-SI/eodag/commit/d8bb323df1f543da09045780ab98d9231ed68246))

- Removed traceback from geom intersection warning, fixes #114
  ([`d669625`](https://github.com/CS-SI/eodag/commit/d669625d572f4759b23f1dcd88cf9cc0e07f5c74))

- Tqdm_notebook warning, fixes #117
  ([`8b118ee`](https://github.com/CS-SI/eodag/commit/8b118eea3dcfaf194d2e649730596e01e183c1eb))

- **doc**: Doc update for provider priorities and params_mapping
  ([`0bfa61d`](https://github.com/CS-SI/eodag/commit/0bfa61dbe39a0ad7717b820a4fa5a1f8efcf43f9))


## v1.3.4 (2019-12-13)

### Bug Fixes

- Readme syntax
  ([`8570750`](https://github.com/CS-SI/eodag/commit/857075060fe5137cbe8a90647cdd9e143307aac3))

- Set owslib version to 0.18.0 (py27 support dropped)
  ([`ee83a74`](https://github.com/CS-SI/eodag/commit/ee83a7458d275fa395dc3e59ee4f405899457d70))

- **doc**: New badges in readme and CS logo
  ([`7795cf1`](https://github.com/CS-SI/eodag/commit/7795cf1ddd8657ab61e33af849a25f71787bf0dc))

- **provider**: Use sobloo official api endpoint, fixes #115
  ([`782d34c`](https://github.com/CS-SI/eodag/commit/782d34c9511720b08662f6003a19e8d094d4e7bb))


## v1.3.3 (2019-10-11)


## v1.3.2 (2019-09-27)


## v1.3.1 (2019-09-27)


## v1.3.0 (2019-09-06)


## v1.2.3 (2019-08-26)


## v1.2.2 (2019-08-23)


## v1.2.1 (2019-08-23)


## v1.2.0 (2019-08-22)


## v1.1.3 (2019-08-05)


## v1.1.2 (2019-08-05)


## v1.1.1 (2019-07-26)


## v1.1.0 (2019-07-23)


## v1.0.1 (2019-04-30)


## v0.7.3 (2019-04-16)


## v0.7.2 (2019-03-26)


## v0.7.1 (2019-03-01)


## v0.7.0 (2018-12-04)


## v0.6.3 (2018-10-04)


## v0.6.2 (2018-09-24)


## v0.6.1 (2018-09-19)


## v0.6.0 (2018-08-09)


## v0.5.0 (2018-08-02)


## v0.4.0 (2018-07-26)


## v0.3.0 (2018-07-23)


## v0.2.0 (2018-07-17)


## v0.1.0 (2018-06-20)


## v0.0.1 (2018-06-21)
