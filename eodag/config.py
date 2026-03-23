# -*- coding: utf-8 -*-
# Copyright 2018, CS GROUP - France, https://www.csgroup.eu/
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
from __future__ import annotations

import logging
import os
import tempfile
from importlib.resources import files as res_files
from inspect import isclass
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Literal,
    Mapping,
    Optional,
    Union,
    get_type_hints,
)

import orjson
import requests
import yaml
import yaml.parser
from annotated_types import Gt
from jsonpath_ng import JSONPath
from typing_extensions import TypedDict

from eodag.utils import (
    AUTH_TOPIC_KEYS,
    HTTP_REQ_TIMEOUT,
    PLUGINS_TOPIC_KEYS,
    STAC_SEARCH_PLUGINS,
    USER_AGENT,
    CredsStoreType,
    cached_yaml_load,
    cached_yaml_load_all,
    cast_scalar_value,
    deepcopy,
    dict_items_recursive_apply,
    merge_mappings,
    slugify,
    sort_dict,
    string_to_jsonpath,
    update_nested_dict,
    uri_to_path,
)
from eodag.utils.exceptions import ValidationError

if TYPE_CHECKING:
    from typing import ItemsView, Iterator, ValuesView

    from typing_extensions import Self

logger = logging.getLogger("eodag.config")

EXT_COLLECTIONS_CONF_URI = (
    "https://cs-si.github.io/eodag/eodag/resources/ext_collections.json"
)


class SimpleYamlProxyConfig:
    """A simple configuration class acting as a proxy to an underlying dict object
    as returned by yaml.load"""

    def __init__(self, conf_file_path: str) -> None:
        try:
            self.source: dict[str, Any] = cached_yaml_load(conf_file_path)
        except yaml.parser.ParserError as e:
            print("Unable to load user configuration file")
            raise e

    def __getitem__(self, item: Any) -> Any:
        return self.source[item]

    def __contains__(self, item: Any) -> Any:
        return item in self.source

    def __iter__(self) -> Iterator[str]:
        return iter(self.source)

    def items(self) -> ItemsView[str, Any]:
        """Iterate over keys and values of source"""
        return self.source.items()

    def values(self) -> ValuesView[Any]:
        """Iterate over values of source"""
        return self.source.values()

    def update(self, other: "SimpleYamlProxyConfig") -> None:
        """Update a :class:`~eodag.config.SimpleYamlProxyConfig`"""
        if not isinstance(other, self.__class__):
            raise ValueError("'{}' must be of type {}".format(other, self.__class__))
        self.source.update(other.source)


class PluginConfig(yaml.YAMLObject):
    """Representation of a plugin config.

    This class variables describe available plugins configuration parameters.
    """

    class Pagination(TypedDict):
        """Search pagination configuration"""

        #: The maximum number of items per page that the provider can handle
        max_limit: int
        #: Key path for the number of total items in the provider result
        total_items_nb_key_path: Union[str, JSONPath]
        #: Key path for the next page URL
        next_page_url_key_path: Union[str, JSONPath]
        #: Key path for the next page POST request query-object (body)
        next_page_query_obj_key_path: Union[str, JSONPath]
        # TODO: change this typing to bool and adapt code to it
        next_page_merge_key_path: Union[str, JSONPath]
        #: Template to add to :attr:`~eodag.config.PluginConfig.Pagination.next_page_url_tpl` to enable count in
        #: search request
        count_tpl: str
        #: The f-string template for pagination requests.
        next_page_url_tpl: str
        #: The query-object for POST pagination requests.
        next_page_query_obj: str
        #: Next page token key used in pagination. Can be guessed from ``KNOWN_NEXT_PAGE_TOKEN_KEYS`` (but needed by
        # ``stac-fastapi-eodag`` that cannot guess and will use ``page`` as default).
        next_page_token_key: str
        #: The endpoint for counting the number of items satisfying a request
        count_endpoint: str
        #: Index of the starting page
        start_page: int
        #: Key in the current page URL for the next page URL
        parse_url_key: str

    class Sort(TypedDict):
        """Configuration for sort during search"""

        #: Default sort settings
        sort_by_default: list[tuple[str, str]]
        #: F-string template to add to :attr:`~eodag.config.PluginConfig.Pagination.next_page_url_tpl` to sort search
        #: results
        sort_by_tpl: str
        #: Mapping between eodag and provider query parameters used for sort
        sort_param_mapping: dict[str, str]
        #: Mapping between eodag and provider sort-order parameters
        sort_order_mapping: dict[Literal["ascending", "descending"], str]
        #: Maximum number of allowed sort parameters per request
        max_sort_params: Annotated[int, Gt(0)]

    class DiscoverMetadata(TypedDict):
        """Configuration for metadata discovery (search result properties)"""

        #: Whether metadata discovery is enabled or not
        auto_discovery: bool
        #: Metadata regex pattern used for discovery in search result properties
        metadata_pattern: str
        #: Configuration/template that will be used to query for a discovered parameter
        search_param: Union[str, dict[str, Any]]
        #: list search parameters to send as is to the provider
        search_param_unparsed: list[str]
        #: Path to the metadata in search result
        metadata_path: str
        #: Use as STAC extension prefix if it does not have one already
        metadata_prefix: str
        #: Whether an error must be raised when using a search parameter which is not queryable or not
        raise_mtd_discovery_error: bool

    class DiscoverCollections(TypedDict, total=False):
        """Configuration for collections discovery"""

        #: URL from which the collections can be fetched
        fetch_url: Optional[str]
        #: HTTP method used to fetch collections
        fetch_method: str
        #: Request body to fetch collections using POST method
        fetch_body: dict[str, Any]
        #: Maximum number of connections for concurrent HTTP requests
        max_connections: int
        #: The f-string template for pagination requests.
        next_page_url_tpl: str
        #: Index of the starting page for pagination requests.
        start_page: int
        #: Type of the provider result
        result_type: str
        #: JsonPath to the list of collections
        results_entry: Union[str, JSONPath]
        #: Mapping for the collection id
        generic_collection_id: str
        #: Mapping for collection metadata (e.g. ``description``, ``license``) which can be parsed from the provider
        #: result
        generic_collection_parsable_metadata: dict[str, str]
        #: Mapping for collection properties which can be parsed from the result and are not collection metadata
        generic_collection_parsable_properties: dict[str, str]
        #: Mapping for collection properties which cannot be parsed from the result and are not collection metadata
        generic_collection_unparsable_properties: dict[str, Any]
        #: URL to fetch data for a single collection
        single_collection_fetch_url: str
        #: Query string to be added to the fetch_url to filter for a collection
        single_collection_fetch_qs: str
        #: Mapping for collection metadata returned by the endpoint given in single_collection_fetch_url. If ``id``
        #: is redefined in this mapping, it will replace ``generic_collection_id`` value
        single_collection_parsable_metadata: dict[str, str]

    class DiscoverQueryables(TypedDict, total=False):
        """Configuration for queryables discovery"""

        #: URL to fetch the queryables valid for all collections
        fetch_url: Optional[str]
        #: URL to fetch the queryables for a specific collection
        collection_fetch_url: Optional[str]
        #: Type of the result
        result_type: str
        #: JsonPath to retrieve the queryables from the provider result
        results_entry: str
        #: :class:`~eodag.plugins.search.base.Search` URL of the constraint file used to build queryables
        constraints_url: str
        #: :class:`~eodag.plugins.search.base.Search` Key in the json result where the constraints can be found
        constraints_entry: str

    class CollectionSelector(TypedDict, total=False):
        """Define the criteria to select a collection in :class:`~eodag.config.PluginConfig.DynamicDiscoverQueryables`.

        The selector matches if the field value starts with the given prefix,
        i.e. it matches if ``parameters[field].startswith(prefix)==True``"""

        #: Field in the search parameters to match
        field: str
        #: Prefix to match in the field
        prefix: str

    class DynamicDiscoverQueryables(TypedDict, total=False):
        """Configuration for queryables dynamic discovery.

        The given configuration for queryables discovery is used if any collection selector
        matches the search parameters.
        """

        #: List of collection selection criterias
        collection_selector: list[PluginConfig.CollectionSelector]
        #: Configuration for queryables discovery to use
        discover_queryables: PluginConfig.DiscoverQueryables

    class OrderOnResponse(TypedDict):
        """Configuration for order on-response during download"""

        #: Parameters metadata-mapping to apply to the order response
        metadata_mapping: dict[str, Union[str, list[str]]]

    class OrderStatusSuccess(TypedDict):
        """
        Configuration to identify order status success during download

        Order status response matching the following parameters are considered success
        At least one is required
        """

        #: Success value for ``status``
        status: str
        #: Success value for ``message``
        message: str
        #: Success value for status response HTTP code
        http_code: int

    class OrderStatusOrdered(TypedDict, total=False):
        """
        Configuration to identify order status ordered during download
        """

        #: HTTP code of the order status response
        http_code: int

    class OrderStatusRequest(TypedDict, total=False):
        """
        Order status request configuration
        """

        #: Request HTTP method
        method: str
        #: Request hearders
        headers: dict[str, Any]

    class OrderStatusOnSuccess(TypedDict, total=False):
        """Configuration for order status on-success during download"""

        #: Whether a new search is needed on success or not
        need_search: bool
        #: Return type of the success result
        result_type: str
        #: Key in the success response that gives access to the result
        results_entry: str
        #: Metadata-mapping to apply to the success status result
        metadata_mapping: dict[str, Union[str, list[str]]]

    class OrderStatus(TypedDict, total=False):
        """Configuration for order status during download"""

        #: Order status request configuration
        request: PluginConfig.OrderStatusRequest
        #: Metadata-mapping used to parse order status response
        metadata_mapping: dict[str, Union[str, list[str]]]
        #: Configuration to identify order status success during download
        success: PluginConfig.OrderStatusSuccess
        #: Part of the order status response that tells there is an error
        error: dict[str, Any]
        #: Configuration to identify order status ordered during download
        ordered: PluginConfig.OrderStatusOrdered
        #: Configuration for order status on-success during download
        on_success: PluginConfig.OrderStatusOnSuccess

    class MetadataPreMapping(TypedDict, total=False):
        """Configuration which can be used to simplify further metadata extraction"""

        #: JsonPath of the metadata entry
        metadata_path: str
        #: Key to get the metadata id
        metadata_path_id: str
        #: Key to get the metadata value
        metadata_path_value: str

    #: :class:`~eodag.plugins.base.PluginTopic` The name of the plugin class to use to instantiate the plugin object
    name: str
    #: :class:`~eodag.plugins.base.PluginTopic` Plugin type
    type: str
    #: :class:`~eodag.plugins.base.PluginTopic` Whether the ssl certificates should be verified in the request or not
    ssl_verify: bool
    #: :class:`~eodag.plugins.base.PluginTopic` Default s3 bucket
    s3_bucket: str
    #: :class:`~eodag.plugins.base.PluginTopic` Authentication error codes
    auth_error_code: Union[int, list[int]]
    #: :class:`~eodag.plugins.base.PluginTopic` Time to wait until request timeout in seconds
    timeout: float
    #: :class:`~eodag.plugins.base.PluginTopic` :class:`urllib3.util.Retry` ``total`` parameter,
    #: total number of retries to allow
    retry_total: int
    #: :class:`~eodag.plugins.base.PluginTopic` :class:`urllib3.util.Retry` ``backoff_factor`` parameter,
    #: backoff factor to apply between attempts after the second try
    retry_backoff_factor: int
    #: :class:`~eodag.plugins.base.PluginTopic` :class:`urllib3.util.Retry` ``status_forcelist`` parameter,
    #: list of integer HTTP status codes that we should force a retry on
    retry_status_forcelist: list[int]

    # search & api -----------------------------------------------------------------------------------------------------
    # copied from ProviderConfig in PluginManager.get_search_plugins()
    priority: int
    # per collection metadata-mapping, set in core._prepare_search
    collection_config: dict[str, Any]

    #: :class:`~eodag.plugins.search.base.Search` Plugin API endpoint
    api_endpoint: str
    #: :class:`~eodag.plugins.search.base.Search` Whether Search plugin needs authentification or not
    need_auth: bool
    #: :class:`~eodag.plugins.search.base.Search` Return type of the provider result
    result_type: str
    #: :class:`~eodag.plugins.search.base.Search`
    #: Key in the provider search result that gives access to the result entries
    results_entry: str
    #: :class:`~eodag.plugins.search.base.Search` Dict containing parameters for pagination
    pagination: PluginConfig.Pagination
    #: :class:`~eodag.plugins.search.base.Search` Configuration for sorting the results
    sort: PluginConfig.Sort
    #: :class:`~eodag.plugins.search.base.Search` Configuration for the metadata auto-discovery
    discover_metadata: PluginConfig.DiscoverMetadata
    #: :class:`~eodag.plugins.search.base.Search` Configuration for the collections auto-discovery
    discover_collections: PluginConfig.DiscoverCollections
    #: :class:`~eodag.plugins.search.base.Search` Configuration for the queryables auto-discovery
    discover_queryables: PluginConfig.DiscoverQueryables
    #: :class:`~eodag.plugins.search.base.Search` The mapping between eodag metadata and the plugin specific metadata
    metadata_mapping: dict[str, Union[str, list[str]]]
    #: :class:`~eodag.plugins.search.base.Search` :attr:`~eodag.config.PluginConfig.metadata_mapping` got from the given
    #: collection
    metadata_mapping_from_product: str
    #: :class:`~eodag.plugins.search.base.Search` A mapping for the metadata of individual assets
    assets_mapping: dict[str, dict[str, Any]]
    #: :class:`~eodag.plugins.search.base.Search` Parameters to remove from queryables
    remove_from_queryables: list[str]
    #: :class:`~eodag.plugins.search.base.Search` Parameters to be passed as is in the search url query string
    literal_search_params: dict[str, str]
    #: :class:`~eodag.plugins.search.qssearch.QueryStringSearch` Characters that should not be quoted in the url params
    dont_quote: list[str]
    #: :class:`~eodag.plugins.search.qssearch.QueryStringSearch` Guess assets keys using their ``href``.
    #: Use their original key if ``False``
    asset_key_from_href: bool
    #: :class:`~eodag.plugins.search.qssearch.ODataV4Search` Dict describing free text search request build
    free_text_search_operations: dict[str, Any]
    #: :class:`~eodag.plugins.search.qssearch.ODataV4Search` Set to ``True`` if the metadata is not given in the search
    #: result and a two step search has to be performed
    per_product_metadata_query: bool
    #: :class:`~eodag.plugins.search.qssearch.ODataV4Search` Dict used to simplify further metadata extraction
    metadata_pre_mapping: PluginConfig.MetadataPreMapping
    #: :class:`~eodag.plugins.search.csw.CSWSearch` Search definition dictionary
    search_definition: dict[str, Any]
    #: :class:`~eodag.plugins.search.qssearch.PostJsonSearch` Whether to merge responses or not (`aws_eos` specific)
    merge_responses: bool
    #: :class:`~eodag.plugins.search.qssearch.PostJsonSearch` Collections names (`aws_eos` specific)
    _collection: list[str]
    #: :class:`~eodag.plugins.search.static_stac_search.StaticStacSearch`
    #: Maximum number of connections for concurrent HTTP requests
    max_connections: int
    #: :class:`~eodag.plugins.search.build_search_result.ECMWFSearch`
    #: Whether end date should be excluded from search request or not
    end_date_excluded: bool
    #: :class:`~eodag.plugins.search.build_search_result.ECMWFSearch`
    #: List of parameters used to parse metadata but that must not be included to the query
    remove_from_query: list[str]
    #: :class:`~eodag.plugins.search.csw.CSWSearch`
    #: OGC Catalogue Service version
    version: str
    #: :class:`~eodag.plugins.apis.ecmwf.EcmwfApi` url of the authentication endpoint
    auth_endpoint: str
    #: :class:`~eodag.plugins.search.build_search_result.WekeoECMWFSearch`
    #: Configurations for the queryables dynamic auto-discovery.
    #: A configuration is used based on the given selection criterias. The first match is used.
    #: If no match is found, it falls back to standard behaviors (e.g. discovery using
    #: :attr:`~eodag.config.PluginConfig.discover_queryables`).
    dynamic_discover_queryables: list[PluginConfig.DynamicDiscoverQueryables]

    # download ---------------------------------------------------------------------------------------------------------
    #: :class:`~eodag.plugins.download.base.Download` Default endpoint url
    base_uri: str
    #: :class:`~eodag.plugins.download.base.Download` Where to store downloaded products, as an absolute file path
    output_dir: str
    #: :class:`~eodag.plugins.download.base.Download`
    #: Whether the content of the downloaded file should be extracted or not
    extract: bool
    #: :class:`~eodag.plugins.download.base.Download` Which extension should be used for the downloaded file
    output_extension: str
    #: :class:`~eodag.plugins.download.base.Download` Whether the directory structure should be flattened or not
    flatten_top_dirs: bool
    #: :class:`~eodag.plugins.download.base.Download` Level in extracted path tree where to find data
    archive_depth: int
    #: :class:`~eodag.plugins.download.base.Download` Whether ignore assets and download using ``eodag:download_link``
    #: or not
    ignore_assets: bool
    #: :class:`~eodag.plugins.download.base.Download` Collection specific configuration
    products: dict[str, dict[str, Any]]
    #: :class:`~eodag.plugins.download.base.Download` Number of maximum workers allowed for parallel downloads
    max_workers: int
    #: :class:`~eodag.plugins.download.http.HTTPDownload` Whether the product has to be ordered to download it or not
    order_enabled: bool
    #: :class:`~eodag.plugins.download.http.HTTPDownload` HTTP request method for the order request
    order_method: str
    #: :class:`~eodag.plugins.download.http.HTTPDownload` Headers to be added to the order request
    order_headers: dict[str, str]
    #: :class:`~eodag.plugins.download.http.HTTPDownload`
    #: Dictionary containing the key :attr:`~eodag.config.PluginConfig.metadata_mapping` which can be used to add new
    #: product properties based on the data in response to the order request
    order_on_response: PluginConfig.OrderOnResponse
    #: :class:`~eodag.plugins.download.http.HTTPDownload` Order status handling
    order_status: PluginConfig.OrderStatus
    #: :class:`~eodag.plugins.download.http.HTTPDownload`
    #: Do not authenticate the download request but only the order and order status ones
    no_auth_download: bool
    #: :class:`~eodag.plugins.download.http.HTTPDownload` Parameters to be added to the query params of the request
    dl_url_params: dict[str, str]
    #: :class:`~eodag.plugins.download.aws.AwsDownload`
    #: At which level of the path part of the url the bucket can be found
    bucket_path_level: int
    #: :class:`~eodag.plugins.download.aws.AwsDownload` Whether download is done from a requester-pays bucket or not
    requester_pays: bool
    #: :class:`~eodag.plugins.download.aws.AwsDownload` S3 endpoint
    s3_endpoint: str

    # auth -------------------------------------------------------------------------------------------------------------
    #: :class:`~eodag.plugins.authentication.base.Authentication` Authentication credentials dictionary
    credentials: dict[str, str]
    #: :class:`~eodag.plugins.authentication.base.Authentication` Authentication URL
    auth_uri: str
    #: :class:`~eodag.plugins.authentication.base.Authentication`
    #: Dictionary containing all keys/value pairs that should be added to the headers
    headers: dict[str, str]
    #: :class:`~eodag.plugins.authentication.base.Authentication`
    #: Dictionary containing all keys/value pairs that should be added to the headers for token retrieve only
    retrieve_headers: dict[str, str]
    #: :class:`~eodag.plugins.authentication.base.Authentication`
    #: The key pointing to the token in the response from the token server
    token_key: str
    #: :class:`~eodag.plugins.authentication.base.Authentication`
    #: Key to get the refresh token in the response from the token server
    refresh_token_key: str
    #: :class:`~eodag.plugins.authentication.base.Authentication` URL pattern to match with search plugin endpoint or
    #: download link
    matching_url: str
    #: :class:`~eodag.plugins.authentication.base.Authentication` Part of the search or download plugin configuration
    #: that needs authentication
    matching_conf: dict[str, Any]
    #: :class:`~eodag.plugins.authentication.openid_connect.OIDCRefreshTokenBase`
    #: How the token should be used in the request
    token_provision: str
    #: :class:`~eodag.plugins.authentication.openid_connect.OIDCRefreshTokenBase` The OIDC provider's client ID
    client_id: str
    #: :class:`~eodag.plugins.authentication.openid_connect.OIDCRefreshTokenBase` The OIDC provider's client secret
    client_secret: str
    #: :class:`~eodag.plugins.authentication.openid_connect.OIDCRefreshTokenBase`
    #: The OIDC provider's ``.well-known/openid-configuration`` url.
    oidc_config_url: str
    #: :class:`~eodag.plugins.authentication.openid_connect.OIDCRefreshTokenBase` The OIDC token audiences
    allowed_audiences: list[str]
    #: :class:`~eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth`
    #: Whether a user consent is needed during the authentication or not
    user_consent_needed: str
    #: :class:`~eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth`
    #: Where to look for the :attr:`~eodag.config.PluginConfig.authorization_uri`
    authentication_uri_source: str
    #: :class:`~eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth`
    #: The callback url that will handle the code given by the OIDC provider
    authentication_uri: str
    #: :class:`~eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth`
    #: The URL of the authentication backend of the OIDC provider
    redirect_uri: str
    #: :class:`~eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth`
    #: The authorization url of the server (where to query for grants)
    authorization_uri: str
    #: :class:`~eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth`
    #: The xpath to the HTML form element representing the user login form
    login_form_xpath: str
    #: :class:`~eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth`
    #: The xpath to the user consent form
    user_consent_form_xpath: str
    #: :class:`~eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth`
    #: The data that will be passed with the POST request on the form 'action' URL
    user_consent_form_data: dict[str, str]
    #: :class:`~eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth`
    #: Additional data to be passed to the login POST request
    additional_login_form_data: dict[str, str]
    #: :class:`~eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth`
    #: Key/value pairs of patterns/messages used for Authentication errors
    exchange_url_error_pattern: dict[str, str]
    #: :class:`~eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth`
    #: A mapping between OIDC url query string and token handler query string params
    token_exchange_params: dict[str, str]
    #: :class:`~eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth`
    #: Refers to the name of the query param to be used in the query request
    token_qs_key: str
    #: :class:`~eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth`
    #: Way to pass the data to the POST request that is made to the token server
    token_exchange_post_data_method: str
    #: :class:`~eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth`
    #: The url to query to get the authorized token
    token_uri: str
    #: :class:`~eodag.plugins.authentication.sas_auth.SASAuth` Key to get the signed url
    signed_url_key: str
    #: :class:`~eodag.plugins.authentication.token.TokenAuth`
    #: If expected, list of keys to be sent as a tuple through the 'auth' parameter of the request
    auth_tuple: list[str]
    #: :class:`~eodag.plugins.authentication.token.TokenAuth`
    #: Credentials json structure if they should be sent as POST data
    req_data: dict[str, Any]
    #: :class:`~eodag.plugins.authentication.token.TokenAuth`
    #: Whether to send credentials as POST data. If ``True``, always sent; if ``False``, never sent;
    #: if not set, sent only when credentials are not embedded in ``auth_uri``
    post_credentials: bool
    #: :class:`~eodag.plugins.authentication.token.TokenAuth`
    #: URL used to fetch the access token with a refresh token
    refresh_uri: str
    #: :class:`~eodag.plugins.authentication.token.TokenAuth`
    #: type of the token
    token_type: str
    #: :class:`~eodag.plugins.authentication.token.TokenAuth`
    #: key to get the expiration time of the token
    token_expiration_key: str
    #: :class:`~eodag.plugins.authentication.token.TokenAuth`
    #: HTTP method to use
    request_method: str
    #: :class:`~eodag.plugins.authentication.token_exchange.OIDCTokenExchangeAuth`
    #: The full :class:`~eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth` plugin configuration
    #: used to retrieve subject token
    subject: dict[str, Any]
    #: :class:`~eodag.plugins.authentication.token_exchange.OIDCTokenExchangeAuth`
    #: Identifies the issuer of the `subject_token`
    subject_issuer: str
    #: :class:`~eodag.plugins.authentication.token.TokenAuth`
    #: :class:`~eodag.plugins.authentication.openid_connect.OIDCRefreshTokenBase`
    #: Safety buffer to prevent token rejection from unexpected expiry between validity check and request.
    token_expiration_margin: int
    #: :class:`~eodag.plugins.authentication.token_exchange.OIDCTokenExchangeAuth`
    #: Audience that the token ID is intended for. :attr:`~eodag.config.PluginConfig.client_id` of the Relying Party
    audience: str
    #: :class:`~eodag.plugins.authentication.generic.GenericAuth`
    #: which authentication method should be used
    method: str

    yaml_loader = yaml.Loader
    yaml_dumper = yaml.SafeDumper
    yaml_tag = "!plugin"

    def __or__(self, other: Union[Self, dict[str, Any]]) -> Self:
        """Return a new PluginConfig with merged values."""
        new_config = self.__class__.from_mapping(self.__dict__)
        new_config.update(other)
        return new_config

    def __ior__(self, other: Union[Self, dict[str, Any]]) -> Self:
        """In-place update of the PluginConfig."""
        self.update(other)
        return self

    def __contains__(self, item: str) -> bool:
        """Check if a key is in the PluginConfig."""
        return item in self.__dict__

    @classmethod
    def from_yaml(cls, loader: yaml.Loader, node: Any) -> Self:
        """Build a :class:`~eodag.config.PluginConfig` from Yaml"""
        cls.validate(tuple(node_key.value for node_key, _ in node.value))
        return loader.construct_yaml_object(node, cls)

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> Self:
        """Build a :class:`~eodag.config.PluginConfig` from a mapping"""
        cls.validate(tuple(mapping.keys()))
        c = cls()
        c.__dict__.update(deepcopy(mapping))
        return c

    @staticmethod
    def validate(config_keys: tuple[Any, ...]) -> None:
        """Validate a :class:`~eodag.config.PluginConfig`"""
        # credentials may be set without type when the provider uses search_auth plugin.
        if "type" not in config_keys and "credentials" not in config_keys:
            raise ValidationError(
                "A Plugin config must specify the type of Plugin it configures"
            )

    def update(self, config: Optional[Union[Self, dict[Any, Any]]]) -> None:
        """Update the configuration parameters with values from `mapping`

        :param mapping: The mapping from which to override configuration parameters
        """
        if config is None:
            return
        source = config if isinstance(config, dict) else config.__dict__
        merge_mappings(
            self.__dict__, {k: v for k, v in source.items() if v is not None}
        )

    def matches_target_auth(self, target_config: Self):
        """Check if the target auth configuration matches this one"""
        target_matching_conf = getattr(target_config, "matching_conf", {})
        target_matching_url = getattr(target_config, "matching_url", None)

        matching_conf = getattr(self, "matching_conf", {})
        matching_url = getattr(self, "matching_url", None)

        # both match
        if (
            target_matching_conf
            and sort_dict(target_matching_conf) == sort_dict(matching_conf)
            and target_matching_url
            and target_matching_url == matching_url
        ):
            return True

        # conf matches and no matching_url expected
        if (
            target_matching_conf
            and sort_dict(target_matching_conf) == sort_dict(matching_conf)
            and not target_matching_url
        ):
            return True

        # url matches and no matching_conf expected
        if (
            target_matching_url
            and target_matching_url == matching_url
            and not target_matching_conf
        ):
            return True

        return False


class ProviderConfig(yaml.YAMLObject):
    """EODAG configuration for a provider.

    :param name: The name of the provider
    :param priority: (optional) The priority of the provider while searching a product.
                     Lower value means lower priority. (Default: 0)
    :param roles: The roles of the provider (e.g. "host", "producer", "licensor", "processor")
    :param description: (optional) A short description of the provider
    :param url: URL to the webpage representing the provider
    :param api: (optional) The configuration of a plugin of type Api
    :param search: (optional) The configuration of a plugin of type Search
    :param products: (optional) The collections supported by the provider
    :param download: (optional) The configuration of a plugin of type Download
    :param auth: (optional) The configuration of a plugin of type Authentication
    :param search_auth: (optional) The configuration of a plugin of type Authentication for search
    :param download_auth: (optional) The configuration of a plugin of type Authentication for download
    :param kwargs: Additional configuration variables for this provider
    """

    name: str
    group: str
    priority: int = 0
    enabled: bool
    roles: list[str]
    description: str
    url: str
    api: PluginConfig
    search: PluginConfig
    products: dict[str, dict[str, Any]]
    download: PluginConfig
    auth: PluginConfig
    search_auth: PluginConfig
    download_auth: PluginConfig

    yaml_loader = yaml.Loader
    yaml_dumper = yaml.SafeDumper
    yaml_tag = "!provider"

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Apply defaults when building from yaml."""
        self.__dict__.update(state)
        self._apply_defaults()

    def __contains__(self, key):
        """Check if a key is in the ProviderConfig."""
        return key in self.__dict__

    @classmethod
    def from_yaml(cls, loader: yaml.Loader, node: Any) -> "Iterator[Self]":
        """Build a :class:`~eodag.config.ProviderConfig` from Yaml"""
        cls.validate(tuple(node_key.value for node_key, _ in node.value))
        for node_key, node_value in node.value:
            if node_key.value == "name":
                node_value.value = slugify(node_value.value).replace("-", "_")
                break
        return loader.construct_yaml_object(node, cls)

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> "Self":
        """Build a :class:`~eodag.config.ProviderConfig` from a mapping"""
        cls.validate(mapping)
        # Create a deep copy to avoid modifying the input dict or its nested structures
        mapping_copy = deepcopy(mapping)
        for key in PLUGINS_TOPIC_KEYS:
            if not (_mapping := mapping_copy.get(key)):
                continue

            if not isinstance(_mapping, dict):
                _mapping = _mapping.__dict__

            mapping_copy[key] = PluginConfig.from_mapping(_mapping)
        c = cls()
        c.__dict__.update(mapping_copy)
        c._apply_defaults()
        return c

    @staticmethod
    def validate(config_keys: Union[tuple[str, ...], dict[str, Any]]) -> None:
        """Validate a :class:`~eodag.config.ProviderConfig`

        :param config_keys: The configurations keys to validate
        """
        if "name" not in config_keys:
            raise ValidationError("Provider config must have name key")
        if not any(k in config_keys for k in PLUGINS_TOPIC_KEYS):
            raise ValidationError("A provider must implement at least one plugin")
        non_api_keys = [k for k in PLUGINS_TOPIC_KEYS if k != "api"]
        if "api" in config_keys and any(k in config_keys for k in non_api_keys):
            raise ValidationError(
                "A provider implementing an Api plugin must not implement any other "
                "type of plugin"
            )

    def update(self, config: Union["Self", dict[str, Any]]) -> None:
        """Update the configuration parameters with values from `mapping`

        :param config: The config from which to override configuration parameters
        """
        source = config if isinstance(config, dict) else config.__dict__

        merge_mappings(
            self.__dict__,
            {
                key: value
                for key, value in source.items()
                if key not in PLUGINS_TOPIC_KEYS and value is not None
            },
        )
        for key in PLUGINS_TOPIC_KEYS:
            current_value: Optional[PluginConfig] = getattr(self, key, None)
            config_value = source.get(key, {})
            if current_value is not None:
                current_value |= config_value
            elif isinstance(config_value, PluginConfig):
                setattr(self, key, config_value)
            elif config_value:
                try:
                    setattr(self, key, PluginConfig.from_mapping(config_value))
                except ValidationError as e:
                    logger.warning(
                        (
                            "Could not add %s Plugin config to %s configuration: %s. "
                            "Try updating existing %s Plugin configs instead."
                        ),
                        key,
                        self.name,
                        str(e),
                        ", ".join([k for k in PLUGINS_TOPIC_KEYS if hasattr(self, k)]),
                    )
        self._apply_defaults()

    def _apply_defaults(self: "Self") -> None:
        """Applies some default values to provider config."""
        if getattr(self, "priority", None) is None:
            self.priority = 0

        stac_search_default_conf = load_stac_provider_config()

        # For the provider, set the default output_dir of its download plugin
        # as tempdir in a portable way
        for download_topic_key in ("download", "api"):
            if download_topic_key in vars(self):
                download_conf = getattr(self, download_topic_key)
                if not getattr(download_conf, "output_dir", None):
                    download_conf.output_dir = tempfile.gettempdir()
                if not getattr(download_conf, "delete_archive", None):
                    download_conf.delete_archive = True

        try:
            if (
                stac_search_default_conf is not None
                and self.search
                and self.search.type in STAC_SEARCH_PLUGINS
            ):
                # search config set to stac defaults overriden with provider config
                per_provider_stac_provider_config = deepcopy(stac_search_default_conf)
                self.search.__dict__ = update_nested_dict(
                    per_provider_stac_provider_config["search"],
                    self.search.__dict__,
                    allow_empty_values=True,
                )
        except AttributeError:
            pass


def credentials_in_auth(auth_conf: PluginConfig) -> bool:
    """Checks if credentials are set for this Authentication plugin configuration

    :param auth_conf: Authentication plugin configuration
    :returns: True if credentials are set, else False
    """
    return any(
        c is not None for c in (getattr(auth_conf, "credentials", {}) or {}).values()
    )


def load_default_config() -> dict[str, ProviderConfig]:
    """Load the providers configuration into a dictionary.

    Load from eodag `resources/providers.yml` or `EODAG_PROVIDERS_CFG_FILE` environment
    variable if exists.

    :returns: The default provider's configuration
    """
    eodag_providers_cfg_file = os.getenv("EODAG_PROVIDERS_CFG_FILE") or str(
        res_files("eodag") / "resources" / "providers.yml"
    )

    return load_config(eodag_providers_cfg_file)


def load_config(config_path: str) -> dict[str, ProviderConfig]:
    """Load the providers configuration into a dictionary from a given file

    If EODAG_PROVIDERS_WHITELIST is set, only load listed providers.

    :param config_path: The path to the provider config file
    :returns: The default provider's configuration
    """
    logger.debug("Loading configuration from %s", config_path)

    try:
        # Providers configs are stored in this file as separated yaml documents
        # Load all of it
        providers_configs: list[ProviderConfig] = cached_yaml_load_all(config_path)
    except yaml.parser.ParserError as e:
        logger.error("Unable to load configuration")
        raise e

    return {p.name: p for p in providers_configs if p is not None}


def load_yml_config(yml_path: str) -> dict[Any, Any]:
    """Load a conf dictionary from given yml absolute path

    :returns: The yml configuration file
    """
    config = SimpleYamlProxyConfig(yml_path)
    return dict_items_recursive_apply(config.source, string_to_jsonpath)


def load_stac_config() -> dict[str, Any]:
    """Load the stac configuration into a dictionary

    :returns: The stac configuration
    """
    return load_yml_config(str(res_files("eodag") / "resources" / "stac.yml"))


def load_stac_api_config() -> dict[str, Any]:
    """Load the stac API configuration into a dictionary

    :returns: The stac API configuration
    """
    return load_yml_config(str(res_files("eodag") / "resources" / "stac_api.yml"))


def load_stac_provider_config() -> dict[str, Any]:
    """Load the stac provider configuration into a dictionary

    :returns: The stac provider configuration
    """
    return SimpleYamlProxyConfig(
        str(res_files("eodag") / "resources" / "stac_provider.yml")
    ).source


def extract_credentials(
    providers_config: list[ProviderConfig],
) -> CredsStoreType:
    """Extract credentials from provider configs (to keep in memory only).

    :returns: {provider_name: {auth_key: credentials_dict}}
    """
    store: CredsStoreType = {}

    for p in providers_config:
        provider_creds: dict[str, dict[str, Any]] = {}

        for auth_key in AUTH_TOPIC_KEYS:
            auth_conf = getattr(p, auth_key, None)
            if not auth_conf:
                continue

            if credentials_in_auth(auth_conf):
                provider_creds[auth_key] = dict(auth_conf.credentials)

        if provider_creds:
            store[p.name] = provider_creds

    return store


def get_ext_collections_conf(
    conf_uri: str = EXT_COLLECTIONS_CONF_URI,
) -> dict[str, Any]:
    """Read external collections conf

    :param conf_uri: URI to local or remote configuration file
    :returns: The external collections configuration
    """
    logger.info("Fetching external collections from %s", conf_uri)
    if conf_uri.lower().startswith("http"):
        # read from remote
        try:
            response = requests.get(
                conf_uri, headers=USER_AGENT, timeout=HTTP_REQ_TIMEOUT
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.debug(e)
            logger.warning(
                "Could not read remote external collections conf from %s", conf_uri
            )
            return {}
    elif conf_uri.lower().startswith("file"):
        conf_uri = uri_to_path(conf_uri)

    # read from local
    try:
        with open(conf_uri, "rb") as f:
            return orjson.loads(f.read())
    except (orjson.JSONDecodeError, FileNotFoundError) as e:
        logger.debug(e)
        logger.warning(
            "Could not read local external collections conf from %s", conf_uri
        )
        return {}


def _get_whitelisted_configs(
    configs: Mapping[str, Union[ProviderConfig, dict[str, Any]]],
) -> Mapping[str, Union[ProviderConfig, dict[str, Any]]]:
    """Filter configs according to the ``EODAG_PROVIDERS_WHITELIST`` env var."""
    whitelist = set(os.getenv("EODAG_PROVIDERS_WHITELIST", "").split(","))
    if not whitelist or whitelist == {""}:
        return configs
    return {name: conf for name, conf in configs.items() if name in whitelist}


def _share_credentials(configs: dict[str, ProviderConfig]) -> None:
    """Share credentials between plugins with matching criteria."""
    auth_confs_with_creds: list[PluginConfig] = []
    for conf in configs.values():
        for auth_key in AUTH_TOPIC_KEYS:
            auth_conf = getattr(conf, auth_key, None)
            if auth_conf is not None and credentials_in_auth(auth_conf):
                auth_confs_with_creds.append(auth_conf)
    if not auth_confs_with_creds:
        return
    for conf in configs.values():
        for key in AUTH_TOPIC_KEYS:
            provider_auth_config = getattr(conf, key, None)
            if provider_auth_config and not credentials_in_auth(provider_auth_config):
                for conf_with_creds in auth_confs_with_creds:
                    if conf_with_creds.matches_target_auth(provider_auth_config):
                        getattr(conf, key).credentials = conf_with_creds.credentials
                        break


def merge_provider_configs(
    configs: dict[str, ProviderConfig],
    new_configs: Mapping[str, Union[ProviderConfig, dict[str, Any]]],
) -> None:
    """Merge *new_configs* into *configs* in-place.

    Existing configs are updated; new ones are created.  Respects the
    ``EODAG_PROVIDERS_WHITELIST`` env-var when set.

    :param configs: Mutable dict to update.
    :param new_configs: Provider name → config mapping.
    """
    new_configs = _get_whitelisted_configs(new_configs)
    for name, conf in new_configs.items():
        if isinstance(conf, dict) and conf.get("name") != name:
            if "name" in conf:
                logger.debug(
                    "%s: config name '%s' overridden by dict key", name, conf["name"]
                )
            conf = {**conf, "name": name}
        elif isinstance(conf, ProviderConfig) and conf.name != name:
            raise ValidationError(
                f"ProviderConfig name '{conf.name}' must match dict key '{name}'"
            )

        try:
            if name in configs:
                configs[name].update(conf)
            elif isinstance(conf, ProviderConfig):
                configs[name] = conf
            else:
                configs[name] = ProviderConfig.from_mapping(conf)
        except Exception:
            import traceback

            operation = "updating" if name in configs else "creating"
            logger.warning("%s: skipped %s due to invalid config", name, operation)
            logger.debug("Traceback:\n%s", traceback.format_exc())

    _share_credentials(configs)


def _parse_env_provider_configs() -> dict[str, dict[str, Any]]:
    """Parse ``EODAG__*`` environment variables into a config mapping."""

    def _build_mapping(env_var: str, env_value: str, mapping: dict[str, Any]) -> None:
        parts = env_var.split("__")
        iter_parts = iter(parts)
        env_type = get_type_hints(PluginConfig).get(next(iter_parts, ""), str)
        child_env_type = (
            get_type_hints(env_type).get(next(iter_parts, ""))
            if isclass(env_type)
            else None
        )
        if len(parts) == 2 and child_env_type:
            try:
                env_value = cast_scalar_value(env_value, child_env_type)
            except TypeError:
                logger.warning(
                    f"Could not convert {parts} value {env_value} to {child_env_type}"
                )
            mapping.setdefault(parts[0], {})
            mapping[parts[0]][parts[1]] = env_value
        elif len(parts) == 1:
            try:
                env_value = cast_scalar_value(env_value, env_type)
            except TypeError:
                logger.warning(
                    f"Could not convert {parts[0]} value {env_value} to {env_type}"
                )
            mapping[parts[0]] = env_value
        else:
            new_map = mapping.setdefault(parts[0], {})
            _build_mapping("__".join(parts[1:]), env_value, new_map)

    logger.debug("Loading configuration from environment variables")
    result: dict[str, dict[str, Any]] = {}
    for env_var in os.environ:
        if env_var.startswith("EODAG__"):
            _build_mapping(
                env_var[len("EODAG__") :].lower(),
                os.environ[env_var],
                result,
            )
    return result


def build_provider_configs(
    configs: Mapping[str, Union[ProviderConfig, dict[str, Any]]],
) -> dict[str, ProviderConfig]:
    """Build a ``dict[str, ProviderConfig]`` from a configuration mapping."""
    result: dict[str, ProviderConfig] = {}
    merge_provider_configs(result, configs)
    return result


def load_provider_configs(
    default_config: Mapping[str, Union[ProviderConfig, dict[str, Any]]],
    *extra_configs: Mapping[str, Union[ProviderConfig, dict[str, Any]]],
    user_conf_file: Optional[str] = None,
    env_override: bool = True,
) -> dict[str, ProviderConfig]:
    """Build provider configs by merging default, extra, user-file and env configs.

    :param default_config: The base provider configuration mapping.
    :param extra_configs: Additional config mappings to merge (e.g. external plugins).
    :param user_conf_file: Path to a YAML user configuration file.
    :param env_override: Whether to apply ``EODAG__*`` environment variable overrides.
    :returns: A plain dict of provider configs.
    """
    configs = build_provider_configs(default_config)

    for cfg in extra_configs:
        merge_provider_configs(configs, cfg)

    if user_conf_file:
        logger.info(
            "Loading user configuration from: %s", os.path.abspath(user_conf_file)
        )
        try:
            with open(os.path.abspath(os.path.realpath(user_conf_file)), "r") as fh:
                config_in_file = yaml.safe_load(fh)
        except yaml.parser.ParserError as e:
            logger.error("Unable to load configuration file %s", user_conf_file)
            raise e
        if config_in_file:
            merge_provider_configs(configs, config_in_file)

    if env_override:
        env_configs = _parse_env_provider_configs()
        if env_configs:
            merge_provider_configs(configs, env_configs)

    return configs


def disable_providers(
    configs: dict[str, ProviderConfig],
    skipped_plugins: list[str],
):
    """Determine which providers should be disabled.

    Returns a set of provider names that should be marked as disabled
    because they lack credentials, auth plugins, or use skipped plugins.

    :param configs: Provider configs dict.
    :param skipped_plugins: Plugin class names that failed to load.
    :returns: Set of provider names to disable.
    """
    for name, conf in configs.items():
        # disable providers using skipped plugins
        if any(
            isinstance(v, PluginConfig) and getattr(v, "type", None) in skipped_plugins
            for v in conf.__dict__.values()
        ):
            conf["enabled"] = False
            logger.debug(
                "%s: provider needing unavailable plugin has been disabled", name
            )
            continue

        # check authentication
        if hasattr(conf, "api") and getattr(conf.api, "need_auth", False):
            if not credentials_in_auth(conf.api):
                conf["enabled"] = False
                logger.info(
                    "%s: provider needing auth for search has been disabled because no credentials could be found",
                    name,
                )

        elif hasattr(conf, "search") and getattr(conf.search, "need_auth", False):
            if not hasattr(conf, "auth") and not hasattr(conf, "search_auth"):
                conf["enabled"] = False
                logger.info(
                    "%s: provider needing auth for search has been disabled because no auth plugin could be found",
                    name,
                )
                continue

            credentials_exist = (
                hasattr(conf, "search_auth") and credentials_in_auth(conf.search_auth)
            ) or (
                not hasattr(conf, "search_auth")
                and hasattr(conf, "auth")
                and credentials_in_auth(conf.auth)
            )
            if not credentials_exist:
                conf["enabled"] = False
                logger.info(
                    "%s: provider needing auth for search has been disabled because no credentials could be found",
                    name,
                )

        elif not hasattr(conf, "api") and not hasattr(conf, "search"):
            conf["enabled"] = False
            logger.info(
                "%s: provider has been disabled because no api or search plugin could be found",
                name,
            )
