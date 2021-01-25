# -*- coding: utf-8 -*-
# Copyright 2020, CS GROUP - France, http://www.c-s.fr
#
# This file is part of EODAG project
#     https://www.github.com/CS-SI/EODAG
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging
import re
from urllib.error import HTTPError as urllib_HTTPError
from urllib.request import urlopen

import jsonpath_ng as jsonpath
import requests
from lxml import etree

from eodag.api.product import EOProduct
from eodag.api.product.metadata_mapping import (
    NOT_MAPPED,
    format_metadata,
    get_metadata_path,
    get_metadata_path_value,
    get_search_param,
    properties_from_json,
    properties_from_xml,
)
from eodag.config import load_stac_provider_config
from eodag.plugins.search.base import Search
from eodag.utils import (
    GENERIC_PRODUCT_TYPE,
    dict_items_recursive_apply,
    format_dict_items,
    quote,
    update_nested_dict,
    urlencode,
)
from eodag.utils.exceptions import AuthenticationError, RequestError

logger = logging.getLogger("eodag.plugins.search.qssearch")


class QueryStringSearch(Search):
    """A plugin that helps implementing any kind of search protocol that relies on
    query strings (e.g: opensearch).

    The available configuration parameters for this kind of plugin are:

        - **result_type**: (optional) One of "json" or "xml", depending on the
          representation of the provider's search results. The default is "json"

        - **results_entry**: (mandatory) The name of the key in the provider search
          result that gives access to the result entries

        - **api_endpoint**: (mandatory) The endpoint of the provider's search interface

        - **literal_search_params**: (optional) A mapping of (search_param =>
          search_value) pairs giving search parameters to be passed as is in the search
          url query string. This is useful for example in situations where the user wants
          to pass-in a search query as it is done on the provider interface. In such a case,
          the user can put in his configuration file the query he needs to pass to the provider.

        - **pagination**: (mandatory) The configuration of how the pagination is done
          on the provider. It is a tree with the following nodes:

          - *next_page_url_tpl*: The template for pagination requests. This is a simple
            Python format string which will be resolved using the following keywords:
            ``url`` (the base url of the search endpoint), ``search`` (the query string
            corresponding to the search request), ``items_per_page`` (the number of
            items to return per page), ``skip`` (the number of items to skip) and
            ``page`` (which page to return).

          - *total_items_nb_key_path*: (optional) An XPath or JsonPath leading to the
            total number of results satisfying a request. This is used for providers
            which provides the total results metadata along with the result of the
            query and don't have an endpoint for querying the number of items
            satisfying a request, or for providers for which the count endpoint returns
            a json or xml document

          - *count_endpoint*: (optional) The endpoint for counting the number of items
            satisfying a request

        - **free_text_search_operations**: (optional) A tree structure of the form::

            <search-param>:     # e.g: $search
                union: # how to join the operations below (e.g: ' AND ' -->
                       # '(op1 AND op2) AND (op3 OR op4)')
                wrapper: # a pattern for how each operation will be wrapped
                         # (e.g: '({})' --> '(op1 AND op2)')
                operations:     # The operations to build
                  <opname>:     # e.g: AND
                    - <op1>    # e.g:
                               # 'sensingStartDate:[{startTimeFromAscendingNode}Z TO *]'
                    - <op2>    # e.g:
                        # 'sensingStopDate:[* TO {completionTimeFromAscendingNode}Z]'
                    ...
                  ...
            ...

          With the structure above, each operation will become a string of the form:
          '(<op1> <opname> <op2>)', then the operations will be joined together using
          the union string and finally if the number of operations is greater than 1,
          they will be wrapped as specified by the wrapper config key.

    The search plugins of this kind can detect when a metadata mapping is "query-able",
    and get the semantics of how to format the query string parameter that enables to
    make a query on the corresponding metadata. To make a metadata query-able, just
    configure it in the metadata mapping to be a list of 2 items, the first one being
    the specification of the query string search formatting. The later is a string
    following the specification of Python string formatting, with a special behaviour
    added to it. For example, an entry in the metadata mapping of this kind::

        completionTimeFromAscendingNode:
            - 'f=acquisition.endViewingDate:lte:{completionTimeFromAscendingNode#timestamp}'
            - '$.properties.acquisition.endViewingDate'

    means that the search url will have a query string parameter named *"f"* with a
    value of *"acquisition.endViewingDate:lte:1543922280.0"* if the search was done
    with the value of ``completionTimeFromAscendingNode`` being
    ``2018-12-04T12:18:00``. What happened is that
    ``{completionTimeFromAscendingNode#timestamp}`` was replaced with the timestamp
    of the value of ``completionTimeFromAscendingNode``. This example shows all there
    is to know about the semantics of the query string formatting introduced by this
    plugin: any eodag search parameter can be referenced in the query string
    with an additional optional conversion function that is separated from it by a
    ``#`` (see :func:`~eodag.utils.format_metadata` for further details on the
    available converters). Note that for the values in the
    ``free_text_search_operations`` configuration parameter follow the same rule.
    """

    COMPLEX_QS_REGEX = re.compile(r"^(.+=)?([^=]*)({.+})+([^=&]*)$")
    DEFAULT_ITEMS_PER_PAGE = 10
    extract_properties = {"xml": properties_from_xml, "json": properties_from_json}

    def __init__(self, provider, config):
        super(QueryStringSearch, self).__init__(provider, config)
        self.config.__dict__.setdefault("result_type", "json")
        self.config.__dict__.setdefault("results_entry", "features")
        self.config.__dict__.setdefault("pagination", {})
        self.config.__dict__.setdefault("free_text_search_operations", {})
        self.search_urls = []
        self.query_params = dict()
        self.query_string = ""

    def query(self, items_per_page=None, page=None, *args, **kwargs):
        """Perform a search on an OpenSearch-like interface"""
        product_type = kwargs.get("productType", None)
        if product_type == GENERIC_PRODUCT_TYPE:
            logger.warning(
                "GENERIC_PRODUCT_TYPE is not a real product_type and should only be used internally as a template"
            )
            return [], 0
        provider_product_type = self.map_product_type(product_type, *args, **kwargs)
        keywords = {k: v for k, v in kwargs.items() if k != "auth" and v is not None}
        keywords["productType"] = (
            provider_product_type
            if (provider_product_type and provider_product_type != GENERIC_PRODUCT_TYPE)
            else product_type
        )
        # Add to the query, the queryable parameters set in the provider product type definition
        self.product_type_def_params = self.get_product_type_def_params(
            product_type, *args, **kwargs
        )
        # if product_type_def_params is set, remove product_type as it may conflict with this conf
        if self.product_type_def_params:
            keywords.pop("productType", None)
        keywords.update(
            {
                k: v
                for k, v in self.product_type_def_params.items()
                if k not in keywords.keys()
                and k in self.config.metadata_mapping.keys()
                and isinstance(self.config.metadata_mapping[k], list)
            }
        )

        qp, qs = self.build_query_string(product_type, *args, **keywords)

        self.query_params = qp
        self.query_string = qs
        self.search_urls, total_items = self.collect_search_urls(
            page=page, items_per_page=items_per_page, *args, **kwargs
        )
        provider_results = self.do_search(
            items_per_page=items_per_page, *args, **kwargs
        )
        eo_products = self.normalize_results(
            provider_results, product_type, provider_product_type, *args, **kwargs
        )
        return eo_products, (total_items or len(eo_products))

    def build_query_string(self, *args, **kwargs):
        """Build The query string using the search parameters"""
        logger.debug("Building the query string that will be used for search")

        if "raise_errors" in kwargs.keys():
            del kwargs["raise_errors"]
        # . not allowed in eodag_search_key, replaced with %2E
        kwargs = {k.replace(".", "%2E"): v for k, v in kwargs.items()}

        queryables = self.get_queryables(kwargs)
        query_params = {}
        # Get all the search parameters that are recognised as queryables by the
        # provider (they appear in the queryables dictionary)

        for eodag_search_key, provider_search_key in queryables.items():
            user_input = kwargs[eodag_search_key]

            if self.COMPLEX_QS_REGEX.match(provider_search_key):
                parts = provider_search_key.split("=")
                if len(parts) == 1:
                    formatted_query_param = format_metadata(
                        provider_search_key, *args, **kwargs
                    )
                    if "{{" in provider_search_key:
                        # json query string (for POST request)
                        update_nested_dict(
                            query_params, json.loads(formatted_query_param)
                        )
                    else:
                        query_params[eodag_search_key] = formatted_query_param
                else:
                    provider_search_key, provider_value = parts
                    query_params.setdefault(provider_search_key, []).append(
                        format_metadata(provider_value, *args, **kwargs)
                    )
            else:
                query_params[provider_search_key] = user_input

        # Now get all the literal search params (i.e params to be passed "as is"
        # in the search request)
        # ignore additional_params if it isn't a dictionary
        literal_search_params = getattr(self.config, "literal_search_params", {})
        if not isinstance(literal_search_params, dict):
            literal_search_params = {}

        # Now add formatted free text search parameters (this is for cases where a
        # complex query through a free text search parameter is available for the
        # provider and needed for the consumer)
        literal_search_params.update(self.format_free_text_search(**kwargs))
        for provider_search_key, provider_value in literal_search_params.items():
            if isinstance(provider_value, list):
                query_params.setdefault(provider_search_key, []).extend(provider_value)
            else:
                query_params.setdefault(provider_search_key, []).append(provider_value)

        # Build the final query string, in one go without quoting it
        # (some providers do not operate well with urlencoded and quoted query strings)
        return (
            query_params,
            urlencode(
                query_params, doseq=True, quote_via=lambda x, *_args, **_kwargs: x
            ),
        )

    def format_free_text_search(self, **kwargs):
        """Build the free text search parameter using the search parameters"""
        query_params = {}
        for param, operations_config in self.config.free_text_search_operations.items():
            union = operations_config["union"]
            wrapper = operations_config.get("wrapper", "{}")
            formatted_query = []
            for operator, operands in operations_config["operations"].items():
                # The Operator string is the operator wrapped with spaces
                operator = " {} ".format(operator)
                # Build the operation string by joining the formatted operands together
                # using the operation string
                operation_string = operator.join(
                    format_metadata(operand, **kwargs)
                    for operand in operands
                    if any(
                        kw in operand and val is not None for kw, val in kwargs.items()
                    )
                )
                # Finally wrap the operation string as specified by the wrapper and add
                # it to the list of queries (only if the operation string is not empty)
                if operation_string:
                    query = wrapper.format(operation_string)
                    formatted_query.append(query)
            # Join the formatted query using the "union" config parameter, and then
            # wrap it with the Python format string specified in the "wrapper" config
            # parameter
            final_query = union.join(formatted_query)
            if len(operations_config["operations"]) > 1 and len(formatted_query) > 1:
                final_query = wrapper.format(query_params[param])
            if final_query:
                query_params[param] = final_query
        return query_params

    def get_queryables(self, search_params):
        """Retrieve the metadata mappings that are query-able"""
        logger.debug("Retrieving queryable metadata from metadata_mapping")
        queryables = {}
        for eodag_search_key, user_input in search_params.items():
            if user_input is not None:
                md_mapping = self.config.metadata_mapping.get(
                    eodag_search_key, (None, NOT_MAPPED)
                )
                _, md_value = md_mapping
                # query param from defined metadata_mapping
                if md_mapping is not None and isinstance(md_mapping, list):
                    search_param = get_search_param(md_mapping)
                    if search_param is not None:
                        queryables[eodag_search_key] = search_param
                # query param from metadata auto discovery
                elif md_value == NOT_MAPPED and getattr(
                    self.config, "discover_metadata", {}
                ).get("auto_discovery", False):
                    pattern = re.compile(
                        self.config.discover_metadata.get("metadata_pattern", "")
                    )
                    search_param_cfg = self.config.discover_metadata.get(
                        "search_param", ""
                    )
                    if pattern.match(eodag_search_key) and isinstance(
                        search_param_cfg, str
                    ):
                        search_param = search_param_cfg.format(
                            metadata=eodag_search_key
                        )
                        queryables[eodag_search_key] = search_param
                    elif pattern.match(eodag_search_key) and isinstance(
                        search_param_cfg, dict
                    ):
                        search_param_cfg_parsed = dict_items_recursive_apply(
                            search_param_cfg,
                            lambda k, v: v.format(metadata=eodag_search_key),
                        )
                        for k, v in search_param_cfg_parsed.items():
                            if getattr(self.config, k, None):
                                update_nested_dict(
                                    getattr(self.config, k), v, extend_list_values=True
                                )
                            else:
                                logger.warning(
                                    "Could not use discover_metadata[search_param]: no entry for %s in plugin config",
                                    k,
                                )
        return queryables

    def collect_search_urls(self, page=None, items_per_page=None, *args, **kwargs):
        """Build paginated urls"""
        urls = []
        total_results = 0
        for collection in self.get_collections(*args, **kwargs):
            # skip empty collection if one is required in api_endpoint
            if "{collection}" in self.config.api_endpoint and not collection:
                continue
            search_endpoint = self.config.api_endpoint.rstrip("/").format(
                collection=collection
            )
            if page is not None and items_per_page is not None:
                count_endpoint = self.config.pagination.get(
                    "count_endpoint", ""
                ).format(collection=collection)
                if count_endpoint:
                    count_url = "{}?{}".format(count_endpoint, self.query_string)
                    _total_results = self.count_hits(
                        count_url, result_type=self.config.result_type
                    )
                else:
                    # First do one request querying only one element (lightweight
                    # request to schedule the pagination)
                    next_url_tpl = self.config.pagination["next_page_url_tpl"]
                    count_url = next_url_tpl.format(
                        url=search_endpoint,
                        search=self.query_string,
                        items_per_page=1,
                        page=1,
                        skip=0,
                    )
                    _total_results = self.count_hits(
                        count_url, result_type=self.config.result_type
                    )
                total_results += _total_results or 0
                next_url = self.config.pagination["next_page_url_tpl"].format(
                    url=search_endpoint,
                    search=self.query_string,
                    items_per_page=items_per_page,
                    page=page,
                    skip=(page - 1) * items_per_page,
                )
            else:
                next_url = "{}?{}".format(search_endpoint, self.query_string)
            urls.append(next_url)
        return urls, total_results

    def do_search(self, items_per_page=None, *args, **kwargs):
        """Perform the actual search request.

        If there is a specified number of items per page, return the results as soon
        as this number is reached

        :param int items_per_page: (Optional) The number of items to return for one page
        """
        results = []
        for search_url in self.search_urls:
            try:
                response = self._request(
                    search_url,
                    info_message="Sending search request: {}".format(search_url),
                    exception_message="Skipping error while searching for {} {} "
                    "instance:".format(self.provider, self.__class__.__name__),
                )
            except RequestError:
                raise StopIteration
            else:
                if self.config.result_type == "xml":
                    root_node = etree.fromstring(response.content)
                    namespaces = {k or "ns": v for k, v in root_node.nsmap.items()}
                    result = [
                        etree.tostring(entry)
                        for entry in root_node.xpath(
                            self.config.results_entry, namespaces=namespaces
                        )
                    ]
                else:
                    result = response.json().get(
                        self.config.results_entry, [response.json()]
                    )
                if getattr(self.config, "merge_responses", False):
                    results = (
                        [dict(r, **result[i]) for i, r in enumerate(results)]
                        if results
                        else result
                    )
                else:
                    results.extend(result)
            if items_per_page is not None and len(results) == items_per_page:
                return results
        return results

    def normalize_results(self, results, *args, **kwargs):
        """Build EOProducts from provider results"""
        logger.debug("Adapting plugin results to eodag product representation")
        products = []
        for result in results:
            product = EOProduct(
                self.provider,
                QueryStringSearch.extract_properties[self.config.result_type](
                    result,
                    self.config.metadata_mapping,
                    discovery_pattern=getattr(self.config, "discover_metadata", {}).get(
                        "metadata_pattern", None
                    ),
                    discovery_path=getattr(self.config, "discover_metadata", {}).get(
                        "metadata_path", "null"
                    ),
                ),
                *args,
                **kwargs
            )
            # use product_type_config as default properties
            product.properties = dict(
                getattr(self.config, "product_type_config", {}), **product.properties
            )
            products.append(product)
        return products

    def count_hits(self, count_url, result_type="json"):
        """Count the number of results satisfying some criteria"""
        # Handle a very annoying special case :'(
        url = count_url.replace("$format=json&", "")
        response = self._request(
            url,
            info_message="Sending count request: {}".format(url),
            exception_message="Skipping error while counting results for {} {} "
            "instance:".format(self.provider, self.__class__.__name__),
        )
        if result_type == "xml":
            root_node = etree.fromstring(response.content)
            total_nb_results = root_node.xpath(
                self.config.pagination["total_items_nb_key_path"],
                namespaces={k or "ns": v for k, v in root_node.nsmap.items()},
            )[0]
            total_results = int(total_nb_results)
        else:
            count_results = response.json()
            if isinstance(count_results, dict):
                path_parsed = jsonpath.parse(
                    self.config.pagination["total_items_nb_key_path"]
                )
                total_results = path_parsed.find(count_results)[0].value
            else:  # interpret the result as a raw int
                total_results = int(count_results)
        return total_results

    def get_collections(self, *args, **kwargs):
        """Get the collection to which the product belongs"""
        # See https://earth.esa.int/web/sentinel/missions/sentinel-2/news/-
        # /asset_publisher/Ac0d/content/change-of
        # -format-for-new-sentinel-2-level-1c-products-starting-on-6-december
        product_type = kwargs.get("productType")
        if product_type is None and not self.product_type_def_params:
            collections = set()
            collection = getattr(self.config, "collection", None)
            if collection is None:
                try:
                    for product_type, product_config in self.config.products.items():
                        if product_type != GENERIC_PRODUCT_TYPE:
                            collections.add(product_config["collection"])
                        else:
                            collections.add(
                                format_dict_items(product_config, **kwargs).get(
                                    "collection", ""
                                )
                            )
                except KeyError:
                    collections.add("")
            else:
                collections.add(collection)
            return tuple(collections)
        if self.provider == "peps":
            if product_type == "S2_MSI_L1C":
                date = kwargs.get("startTimeFromAscendingNode")
                # If there is no criteria on date, we want to query all the collections
                # known for providing L1C products
                if date is None:
                    collections = ("S2", "S2ST")
                else:
                    match = re.match(
                        r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})", date
                    ).groupdict()
                    year, month, day = (
                        int(match["year"]),
                        int(match["month"]),
                        int(match["day"]),
                    )
                    if year > 2016 or (year == 2016 and month == 12 and day > 5):
                        collections = ("S2ST",)
                    else:
                        collections = ("S2", "S2ST")
            else:
                collections = (self.product_type_def_params.get("collection", ""),)
        else:
            collection = getattr(self.config, "collection", None)
            if collection is None:
                collection = (
                    self.product_type_def_params.get("collection", None) or product_type
                )
            collections = (
                (collection,) if not isinstance(collection, list) else tuple(collection)
            )
        return collections

    def map_product_type(self, product_type, *args, **kwargs):
        """Map the eodag product type to the provider product type"""
        if product_type is None:
            return
        logger.debug("Mapping eodag product type to provider product type")
        return self.config.products.get(product_type, {}).get(
            "product_type", GENERIC_PRODUCT_TYPE
        )

    def get_product_type_def_params(self, product_type, *args, **kwargs):
        """Get the provider product type definition parameters"""
        if product_type in self.config.products.keys():
            logger.debug(
                "Getting provider product type definition parameters for %s",
                product_type,
            )
            return self.config.products[product_type]
        elif GENERIC_PRODUCT_TYPE in self.config.products.keys():
            logger.debug(
                "Getting genric provider product type definition parameters for %s",
                product_type,
            )
            return {
                k: v
                for k, v in format_dict_items(
                    self.config.products[GENERIC_PRODUCT_TYPE], **kwargs
                ).items()
                if v
            }

        else:
            return {}

    def _request(self, url, info_message=None, exception_message=None):
        try:
            # requests auto quote url params, without any option to prevent it
            # use urllib instead of requests if req must be sent unquoted
            if hasattr(self.config, "dont_quote"):
                # keep unquoted desired params
                base_url, params = url.split("?")
                qry = quote(params)
                for keep_unquoted in self.config.dont_quote:
                    qry = qry.replace(quote(keep_unquoted), keep_unquoted)

                # prepare req for Response building
                req = requests.Request(method="GET", url=base_url)
                prep = req.prepare()
                prep.url = base_url + "?" + qry
                # send urllib req
                if info_message:
                    logger.info(info_message.replace(url, prep.url))
                urllib_response = urlopen(prep.url)
                # py2 compatibility : prevent AttributeError: addinfourl instance has no attribute 'reason'
                if not hasattr(urllib_response, "reason"):
                    urllib_response.reason = ""
                if not hasattr(urllib_response, "status") and hasattr(
                    urllib_response, "code"
                ):
                    urllib_response.status = urllib_response.code
                # build Response
                adapter = requests.adapters.HTTPAdapter()
                response = adapter.build_response(prep, urllib_response)
            else:
                if info_message:
                    logger.info(info_message)
                response = requests.get(url)
                response.raise_for_status()
        except (requests.HTTPError, urllib_HTTPError) as err:
            err_msg = err.readlines() if hasattr(err, "readlines") else ""
            if exception_message:
                logger.exception("%s %s" % (exception_message, err_msg))
            else:
                logger.exception(
                    "Skipping error while requesting: %s (provider:%s, plugin:%s): %s",
                    url,
                    self.provider,
                    self.__class__.__name__,
                    err_msg,
                )
            raise RequestError(str(err))
        return response


class AwsSearch(QueryStringSearch):
    """A specialisation of RestoSearch that modifies the way the EOProducts are built
    from the search results"""

    def normalize_results(self, results, *args, **kwargs):
        """Transform metadata from provider representation to eodag representation"""
        normalized = []
        logger.debug("Adapting plugin results to eodag product representation")
        for result in results:
            ref = result["properties"]["title"].split("_")[5]
            year = result["properties"]["completionDate"][0:4]
            month = str(int(result["properties"]["completionDate"][5:7]))
            day = str(int(result["properties"]["completionDate"][8:10]))

            properties = QueryStringSearch.extract_properties[self.config.result_type](
                result, self.config.metadata_mapping
            )

            properties["downloadLink"] = (
                "s3://tiles/{ref[1]}{ref[2]}/{ref[3]}/{ref[4]}{ref[5]}/{year}/"
                "{month}/{day}/0/"
            ).format(**locals())
            normalized.append(EOProduct(self.provider, properties, *args, **kwargs))
        return normalized


class ODataV4Search(QueryStringSearch):
    """A specialisation of a QueryStringSearch that does a two step search to retrieve
    all products metadata"""

    def do_search(self, *args, **kwargs):
        """Do a two step search, as the metadata are not given into the search result"""
        # TODO: This plugin is still very specific to the ONDA provider.
        #       Be careful to generalize it if needed when the chance to do so arrives
        final_result = []
        # Query the products entity set for basic metadata about the product
        for entity in super(ODataV4Search, self).do_search(*args, **kwargs):
            entity_metadata = {
                "quicklook": entity["quicklook"],
                "id": entity["id"],
                "footprint": entity["footprint"],
                "downloadable": entity["downloadable"],
                "offline": entity["offline"],
            }
            metadata_url = self.get_metadata_search_url(entity)
            try:
                response = requests.get(metadata_url)
                response.raise_for_status()
            except requests.HTTPError:
                logger.exception(
                    "Skipping error while searching for %s %s instance:",
                    self.provider,
                    self.__class__.__name__,
                )
            else:
                entity_metadata.update(
                    {item["id"]: item["value"] for item in response.json()["value"]}
                )
                final_result.append(entity_metadata)
        return final_result

    def get_metadata_search_url(self, entity):
        """Build the metadata link for the given entity"""
        return "{}({})/Metadata".format(
            self.config.api_endpoint.rstrip("/"), entity["id"]
        )


class PostJsonSearch(QueryStringSearch):
    """A specialisation of a QueryStringSearch that uses POST method"""

    def __init__(self, provider, config):
        super(PostJsonSearch, self).__init__(provider, config)
        self.config.results_entry = "results"

    def update_metadata_mapping(self, metadata_mapping):
        """Update plugin metadata_mapping with input metadata_mapping configuration
        """
        self.config.metadata_mapping.update(metadata_mapping)
        for metadata in metadata_mapping:
            path = get_metadata_path_value(self.config.metadata_mapping[metadata])
            # check if path has already been parsed
            if isinstance(path, str):
                conversion, path = get_metadata_path(
                    self.config.metadata_mapping[metadata]
                )
                try:
                    # If the metadata is queryable (i.e a list of 2 elements), replace the value of the last item
                    if len(self.config.metadata_mapping[metadata]) == 2:
                        self.config.metadata_mapping[metadata][1] = (
                            conversion,
                            jsonpath.parse(path),
                        )
                    else:
                        self.config.metadata_mapping[metadata] = (
                            conversion,
                            jsonpath.parse(path),
                        )
                except Exception:  # jsonpath_ng does not provide a proper exception
                    # Assume the mapping is to be passed as is.
                    # Ignore any transformation specified. If a value is to be passed as is, we don't want to transform
                    # it further
                    _, text = get_metadata_path(self.config.metadata_mapping[metadata])
                    if len(self.config.metadata_mapping[metadata]) == 2:
                        self.config.metadata_mapping[metadata][1] = (None, text)
                    else:
                        self.config.metadata_mapping[metadata] = (None, text)

    def query(self, items_per_page=None, page=None, *args, **kwargs):
        """Perform a search on an OpenSearch-like interface"""
        product_type = kwargs.get("productType", None)
        provider_product_type = self.map_product_type(product_type, *args, **kwargs)
        keywords = {k: v for k, v in kwargs.items() if k != "auth" and v is not None}
        keywords["productType"] = (
            provider_product_type
            if (provider_product_type and provider_product_type != GENERIC_PRODUCT_TYPE)
            else product_type
        )

        # provider product type specific conf
        self.product_type_def_params = self.get_product_type_def_params(
            product_type, *args, **kwargs
        )

        # update config using provider product type definition metadata_mapping
        # from another product
        other_product_for_mapping = self.product_type_def_params.get(
            "metadata_mapping_from_product", ""
        )
        if other_product_for_mapping:
            other_product_type_def_params = self.get_product_type_def_params(
                other_product_for_mapping, *args, **kwargs
            )
            self.update_metadata_mapping(
                other_product_type_def_params.get("metadata_mapping", {})
            )
        # from current product
        self.update_metadata_mapping(
            self.product_type_def_params.get("metadata_mapping", {})
        )

        # Add to the query, the queryable parameters set in the provider product type definition
        keywords.update(
            {
                k: v
                for k, v in self.product_type_def_params.items()
                if k not in keywords.keys()
                and k in self.config.metadata_mapping.keys()
                and isinstance(self.config.metadata_mapping[k], list)
            }
        )

        qp, _ = self.build_query_string(product_type, *args, **keywords)

        for query_param, query_value in qp.items():
            if (
                query_param
                in self.config.products[product_type].get(
                    "specific_qssearch", {"parameters": []}
                )["parameters"]
            ):
                self.config.api_endpoint = query_value
                self.config.metadata_mapping = self.config.products[product_type][
                    "specific_qssearch"
                ]["metadata_mapping"]
                self.config.results_entry = self.config.products[product_type][
                    "specific_qssearch"
                ]["results_entry"]
                self.config.collection = self.config.products[product_type][
                    "specific_qssearch"
                ].get("collection", None)
                self.config.merge_responses = self.config.products[product_type][
                    "specific_qssearch"
                ].get("merge_responses", None)
                super(PostJsonSearch, self).__init__(
                    provider=self.provider, config=self.config
                )
                self.count_hits = lambda *x, **y: 1
                self._request = super(PostJsonSearch, self)._request
                return super(PostJsonSearch, self).query(
                    items_per_page=items_per_page, page=page, *args, **kwargs
                )

        # If we were not able to build query params but have search criteria, this means
        # the provider does not support the search criteria given. If so, stop searching
        # right away
        if not qp and keywords:
            return [], 0
        self.query_params = qp
        self.search_urls, total_items = self.collect_search_urls(
            page=page, items_per_page=items_per_page, *args, **kwargs
        )
        provider_results = self.do_search(
            items_per_page=items_per_page, *args, **kwargs
        )
        eo_products = self.normalize_results(
            provider_results, product_type, *args, **kwargs
        )
        return eo_products, (total_items or len(eo_products))

    def collect_search_urls(self, page=None, items_per_page=None, *args, **kwargs):
        """Adds pagination to query parameters, and auth to url"""
        urls = []
        total_results = 0
        for collection in self.get_collections(*args, **kwargs):
            search_endpoint = self.config.api_endpoint.rstrip("/").format(
                **dict(collection=collection, **kwargs["auth"].config.credentials)
            )
            if page is not None and items_per_page is not None:
                count_endpoint = self.config.pagination.get(
                    "count_endpoint", ""
                ).format(
                    **dict(collection=collection, **kwargs["auth"].config.credentials)
                )
                if count_endpoint:
                    _total_results = self.count_hits(
                        count_endpoint, result_type=self.config.result_type
                    )
                else:
                    # First do one request querying only one element (lightweight
                    # request to schedule the pagination)

                    # update query params with pagination
                    unmapped_pagination_params = dict(items_per_page=1, page=1, skip=0)
                    pagination_params = {}
                    for (
                        eodag_pagination_key,
                        user_input,
                    ) in unmapped_pagination_params.items():
                        if user_input is not None:
                            pagination_mapping = self.config.pagination.get(
                                eodag_pagination_key, None
                            )
                            if pagination_mapping is not None and isinstance(
                                pagination_mapping, list
                            ):
                                pagination_key = pagination_mapping[0]
                                if pagination_key is not None:
                                    pagination_params[pagination_key] = user_input

                    self.query_params.update(pagination_params)
                    _total_results = self.count_hits(
                        search_endpoint, result_type=self.config.result_type
                    )
                if getattr(self.config, "merge_responses", False):
                    total_results = _total_results or 0
                else:
                    total_results += _total_results or 0
                next_page_query_obj = self.config.pagination[
                    "next_page_query_obj"
                ].format(
                    items_per_page=items_per_page,
                    page=page,
                    skip=(page - 1) * items_per_page,
                )
                update_nested_dict(self.query_params, json.loads(next_page_query_obj))

            urls.append(search_endpoint)
        return urls, total_results

    def _request(self, url, info_message=None, exception_message=None):
        try:
            if info_message:
                logger.info(info_message)
            response = requests.post(url, json=self.query_params)
            response.raise_for_status()
        except (requests.HTTPError, urllib_HTTPError) as err:
            # check if error is identified as auth_error in provider conf
            auth_errors = getattr(self.config, "auth_error_code", [None])
            if not isinstance(auth_errors, list):
                auth_errors = [auth_errors]
            if err.response.status_code in auth_errors:
                raise AuthenticationError(
                    "HTTP Error {} returned:\n{}\nPlease check your credentials for {}".format(
                        err.response.status_code,
                        err.response.text.strip(),
                        self.provider,
                    )
                )
            if exception_message:
                logger.exception(exception_message)
            else:
                logger.exception(
                    "Skipping error while requesting: %s (provider:%s, plugin:%s):",
                    url,
                    self.provider,
                    self.__class__.__name__,
                )
            raise RequestError(str(err))
        return response


class StacSearch(QueryStringSearch):
    """A specialisation of a QueryStringSearch that uses generic STAC configuration"""

    def __init__(self, provider, config):
        stac_provider_config = load_stac_provider_config()
        config.__dict__.setdefault(
            "pagination", stac_provider_config.get("search", {}).get("pagination", {})
        )
        config.__dict__.setdefault(
            "discover_metadata",
            stac_provider_config.get("search", {}).get("discover_metadata", {}),
        )
        config.__dict__.setdefault(
            "metadata_mapping",
            stac_provider_config.get("search", {}).get("metadata_mapping", {}),
        )

        super(QueryStringSearch, self).__init__(provider, config)
        self.config.__dict__.setdefault("result_type", "json")
        self.config.__dict__.setdefault("results_entry", "features")
        self.config.__dict__.setdefault("free_text_search_operations", {})
        self.search_urls = []
        self.query_params = dict()
        self.query_string = ""

        # TODO: fetch /collections to add dynamically product types
        # response = self._request(
        #     config.api_endpoint.replace("/search", "/collections"),
        # )
        # collections = [c["id"] for c in response.json().get("collections", {}) if "id" in c.keys()]
        # for c in collections:
        #     if c not in str(self.config.products):
        #         self.config.products[c] = {"product_type": c}

    def normalize_results(self, results, *args, **kwargs):
        """Build EOProducts from provider results"""

        products = super(StacSearch, self).normalize_results(results, *args, **kwargs)

        # move assets from properties to product's attr
        for product in products:
            product.assets = product.properties.pop("assets", [])

        return products
