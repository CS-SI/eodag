.. _providers:

Featured providers
===================

`eodag` connects you to a variety of Earth Observation (EO) data providers.
This section introduces the **featured providers** that are already integrated, so you can
easily start searching, accessing, and downloading products.

Some providers are completely open, while others require an account to access their data.
If credentials are needed, check the :doc:`registration guide <register>` for details.

Description
^^^^^^^^^^^

Products from the following providers are made available through ``eodag``:

.. dropdown:: **Copernicus Services** (5 providers)
   :color: primary
   :icon: cloud

   European Union's comprehensive Earth observation program providing climate, atmosphere, and marine data.

   .. list-table::
      :widths: 30 70
      :header-rows: 1

      * - Provider
        - Description
      * - `cop_ads <https://ads.atmosphere.copernicus.eu>`_
        - Copernicus Atmosphere Data Store
      * - `cop_cds <https://cds.climate.copernicus.eu>`_
        - Copernicus Climate Data Store
      * - `cop_dataspace <https://dataspace.copernicus.eu/>`_
        - Copernicus Data Space Ecosystem
      * - `cop_ewds <https://ewds.climate.copernicus.eu>`_
        - CEMS Early Warning Data Store
      * - `cop_marine <https://marine.copernicus.eu>`_
        - Copernicus Marine Service

.. dropdown:: **Cloud Platforms** (5 providers)
   :color: secondary
   :icon: server

   Major cloud providers offering scalable access to Earth observation datasets.

   .. list-table::
      :widths: 30 70
      :header-rows: 1

      * - Provider
        - Description
      * - `aws_eos <https://eos.com/>`_
        - EOS Data Analytics search for Amazon public datasets
      * - `earth_search <https://www.element84.com/earth-search/>`_
        - Element84 Earth Search
      * - `earth_search_cog <https://www.element84.com/earth-search/>`_
        - Element84 Earth Search COG
      * - `earth_search_gcs <https://cloud.google.com/storage/docs/public-datasets>`_
        - Element84 Earth Search and Google Cloud Storage
      * - `planetary_computer <https://planetarycomputer.microsoft.com/>`_
        - Microsoft Planetary Computer

.. dropdown:: **European Agencies** (8 providers)
   :color: success
   :icon: organization

   National and regional European space agencies and research institutions.

   .. list-table::
      :widths: 30 70
      :header-rows: 1

      * - Provider
        - Description
      * - `creodias <https://creodias.eu/>`_
        - CloudFerro DIAS
      * - `creodias_s3 <https://creodias.eu/>`_
        - CloudFerro DIAS data through S3 protocol
      * - `dedl <https://hda.data.destination-earth.eu/ui>`_
        - Destination Earth Data Lake (DEDL)
      * - `dedt_lumi <https://polytope.lumi.apps.dte.destination-earth.eu/openapi>`_
        - DestinE Digital Twin output on Lumi
      * - `ecmwf <https://www.ecmwf.int/>`_
        - European Centre for Medium-Range Weather Forecasts
      * - `eumetsat_ds <https://data.eumetsat.int>`_
        - EUMETSAT Data Store
      * - `fedeo_ceda <https://climate.esa.int/en/>`_
        - FedEO CEDA through CEOS Federated EO missions
      * - `wekeo_main <https://www.wekeo.eu/>`_
        - WEkEO Copernicus Sentinel, DEM, and CLMS data

.. dropdown:: **French Providers** (4 providers)
   :color: info
   :icon: location

   French National Space Agency (CNES) and research institutions.

   .. list-table::
      :widths: 30 70
      :header-rows: 1

      * - Provider
        - Description
      * - `geodes <https://geodes.cnes.fr>`_
        - CNES Earth Observation portal
      * - `geodes_s3 <https://geodes.cnes.fr>`_
        - CNES Earth Observation portal with S3 Datalake
      * - `hydroweb_next <https://hydroweb.next.theia-land.fr>`_
        - Hydroweb.next thematic hub for hydrology
      * - `peps <https://peps.cnes.fr/rocket/#/home>`_
        - CNES catalog for Sentinel products

.. dropdown:: **U.S. Providers** (2 providers)
   :color: warning
   :icon: location

   United States geological and space agencies.

   .. list-table::
      :widths: 30 70
      :header-rows: 1

      * - Provider
        - Description
      * - `usgs <https://earthexplorer.usgs.gov/>`_
        - U.S geological survey catalog for Landsat products
      * - `usgs_satapi_aws <https://landsatlook.usgs.gov/sat-api/>`_
        - USGS Landsatlook SAT API

.. dropdown:: **Other Regional** (4 providers)
   :color: dark
   :icon: globe

   Regional and specialized data providers worldwide.

   .. list-table::
      :widths: 30 70
      :header-rows: 1

      * - Provider
        - Description
      * - `meteoblue <https://content.meteoblue.com/en/business-solutions/weather-apis/dataset-api>`_
        - Meteoblue forecast
      * - `sara <https://copernicus.nci.org.au>`_
        - Sentinel Australasia Regional Access
      * - `wekeo_cmems <https://www.wekeo.eu>`_
        - Copernicus Marine (CMEMS) data from WEkEO
      * - `wekeo_ecmwf <https://www.wekeo.eu/>`_
        - WEkEO ECMWF data
