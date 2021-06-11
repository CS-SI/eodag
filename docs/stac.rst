.. _stac:

STAC Support
============


``eodag``'s interfaces are compliant with the `SpatioTemporal Asset Catalog <https://github.com/radiantearth/stac-spec>`_
(STAC) specification.

STAC client
-----------

STAC API providers can be configured to be used for `search` and `download` using EODAG.
Some providers (*astraea_eod*, *earth_search*, *usgs_satapi_aws*) are already implemented
and new providers can be dynamically added by the user. Static catalogs can also be
fetched by EODAG.

STAC server
-----------

EODAG can run as STAC API REST server and give access to configured
providers data through a STAC compliant search API.

.. toctree::
   :maxdepth: 2

   STAC client <notebooks/tutos/tuto_stac_client.ipynb>
   stac_rest
