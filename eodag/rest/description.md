# eodag-server

eodag-server is a REST API for EODAG search tool implementing OpenSearch Geo interface.


## Searching

### By product type

The server provides a GET endpoint with a route defined by:

```
http://hostname/<product_type>/?param=value
```

See below to get the list of available product types.

Supported request parameters are:

* `box`: the search bounding box defined by: min_lon,min_lat,max_lon,max_lat.
* `dtstart`: the start date
* `dtend`: the end date
* `cloudCover`: cloud cover

Example URL:

<{base_url}S2_MSI_L1C/?box=0,43,1,44>

It is also possible to paginate the result. Informations about pagination are returned in each response to a search
request. Pagination paramaters are:

* `page`: The page number (int, defaults to 1)
* `itemsPerPage`: The maximum number of items per page (int, defaults to {ipp})

### By UID

Since version 1.0 of eodag, it is now possible to search directly an EO product based on its
ID. The endpoint is the following:

```
http://hostname/<uid>/?provider=value
```

You can even specify on which provider to perform the request if you have this information.
This may speed up your search.

Example requests:

<{base_url}search/S2B_MSIL1C_20180824T105019_N0206_R051_T30TYN_20180824T151058/>

<{base_url}search/S2B_MSIL1C_20180824T105019_N0206_R051_T30TYN_20180824T151058/?provider=onda>

## Filtering

The service provides ability to filter search results by implemented EODAG crunchers.
To activate a filter, add the 'filter' request parameter.

Available filters and their matching EODAG cruncher are:

* `latestIntersect` -> FilterLatestIntersect
* `latestByName` -> FilterLatestByName
* `overlap` -> FilterOverlap

Some filters may require additional configuration parameters
which can be set as request parameters.
For example, overlap filter requires adding a 'minimum_overlap' parameter to the request.

Example URL:

<{base_url}S2_MSI_L1C/?box=0,43,1,44&filter=overlap&minimum_overlap=0>

## Quicklooks

Since version 1.0, an endpoint is available for retrieving EO products quicklooks based on
their UID:

```
http://hostname/quicklook/<uid>/?provider=value
```

The UID is mandatory, and the provider query parameter can be provided to speed up the
retrieval of the quicklook.

Example URL (with a request on a provider known to make available the quicklook without authentication):

<{base_url}quicklook/S2B_MSIL1C_20180824T105019_N0206_R051_T30TYN_20180824T151058/?provider=onda>

The request for a quicklook may fail due to authentication problems or provider's access problem, or inconsistency
between the URL given in the search result of the provider and the way to access this URL

## Product types

There is an endpoint for listing supported product types:

* <{base_url}product-types/> for all providers supported product types or
* <{base_url}product-types/$provider> for product types supported only by $provider.

The result is a json with product type ID and metadata.

The product types search can be filtered like this:

```
{base_url}product-types/?param1=value1&param2=value2
```

where parameters are:

* `instrument`: the name of the instrument producing this type of product (e.g.: OLCI, TIRS). As a general rule, it is
  the abbreviation of the commercial name of the instrument. Most of the time, this will be official
* `platform`: the platform producing this type of products (e.g.: SENTINEL2, LANDSAT8). As a general rule, it is
  constituted with the commercial name of the platform in capital letters, followed by a number - if any
* `platformSerialIdentifier`: an identifier of the platform (e.g.: S2A, L8). As a general rule, it is constituted with
  the first letter of the platform in capitals, followed by a number of the platform if any, and a letter from A to Z
  if there are many satellite for this platform. If the platform does not have a number, a trigram will be used as an
  identifier. Also, if there is a well-known international standard serial identifier for the platform, it will be used
* `processingLevel`: the processing level of the product type (e.g.: L1, L2, L0). In general, it is constituted by `L`
  and the a number from 0 onward indicating the level number
* `sensorType`: the type of censor (e.g.: OPTICAL, RADAR). This tries to follow as much as possible
  [This OGC standard](https://www.opengeospatial.org/standards/cat2eoext4ebrim)

Supported product types are:

{product_types}
