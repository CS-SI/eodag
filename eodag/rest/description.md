# eodag-server

eodag-server is a REST API for EODAG search tool implementing OpenSearch Geo interface.


## Searching

The server provides a GET endpoint with a route defined by:

```
http://hostname/<product_type>/?param=value
```

See below to get the list of available product types.

Supported request parameter is

* box: the search bounding box defined by: min_lon,min_lat,max_lon,max_lat.
* dtstart: the start date
* dtend: the end date
* cloudCover: cloud cover

Example URL:

<{base_url}S2_MSI_L1C/?box=0,43,1,44>

## Filtering

The service provides ability to filter search results by implemented EODAG crunchers.
To activate a filter, add the 'filter' request parameter.

Available filters and their matching EODAG cruncher are:

* latestIntersect -> FilterLatestIntersect
* latestByName -> FilterLatestByName
* overlap -> FilterOverlap

Some filters may require additional configuration parameters
which can be set as request parameters.
For example, overlap filter requires adding a 'minimum_overlap' parameter to the request.

Example URL:

<{base_url}S2_MSI_L1C/?box=0,43,1,44&filter=overlap&minimum_overlap=0>

## Product types

Supported product types are:

{product_types}
