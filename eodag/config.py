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
    Annotated,
    Any,
    ItemsView,
    Iterator,
    Literal,
    Optional,
    TypedDict,
    Union,
    ValuesView,
    get_type_hints,
)

import orjson
import requests
import yaml
import yaml.constructor
import yaml.parser
from annotated_types import Gt
from jsonpath_ng import JSONPath

from eodag.api.product.metadata_mapping import mtd_cfg_as_conversion_and_querypath
from eodag.utils import (
    HTTP_REQ_TIMEOUT,
    USER_AGENT,
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

logger = logging.getLogger("eodag.config")

EXT_PRODUCT_TYPES_CONF_URI = (
    "https://cs-si.github.io/eodag/eodag/resources/ext_product_types.json"
)
AUTH_TOPIC_KEYS = ("auth", "search_auth", "download_auth")
PLUGINS_TOPICS_KEYS = ("api", "search", "download") + AUTH_TOPIC_KEYS


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


class ProviderConfig(yaml.YAMLObject):
    """Representation of eodag configuration.

    :param name: The name of the provider
    :param priority: (optional) The priority of the provider while searching a product.
                     Lower value means lower priority. (Default: 0)
    :param api: (optional) The configuration of a plugin of type Api
    :param search: (optional) The configuration of a plugin of type Search
    :param products: (optional) The products types supported by the provider
    :param download: (optional) The configuration of a plugin of type Download
    :param auth: (optional) The configuration of a plugin of type Authentication
    :param search_auth: (optional) The configuration of a plugin of type Authentication for search
    :param download_auth: (optional) The configuration of a plugin of type Authentication for download
    :param kwargs: Additional configuration variables for this provider
    """

    name: str
    group: str
    priority: int = 0  # Set default priority to 0
    roles: list[str]
    description: str
    url: str
    api: PluginConfig
    search: PluginConfig
    products: dict[str, Any]
    download: PluginConfig
    auth: PluginConfig
    search_auth: PluginConfig
    download_auth: PluginConfig
    product_types_fetched: bool  # set in core.update_product_types_list

    yaml_loader = yaml.Loader
    yaml_dumper = yaml.SafeDumper
    yaml_tag = "!provider"

    @classmethod
    def from_yaml(cls, loader: yaml.Loader, node: Any) -> Iterator[ProviderConfig]:
        """Build a :class:`~eodag.config.ProviderConfig` from Yaml"""
        cls.validate(tuple(node_key.value for node_key, _ in node.value))
        for node_key, node_value in node.value:
            if node_key.value == "name":
                node_value.value = slugify(node_value.value).replace("-", "_")
                break
        return loader.construct_yaml_object(node, cls)

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> ProviderConfig:
        """Build a :class:`~eodag.config.ProviderConfig` from a mapping"""
        cls.validate(mapping)
        for key in PLUGINS_TOPICS_KEYS:
            if key in mapping:
                mapping[key] = PluginConfig.from_mapping(mapping[key])
        c = cls()
        c.__dict__.update(mapping)
        return c

    @staticmethod
    def validate(config_keys: Union[tuple[str, ...], dict[str, Any]]) -> None:
        """Validate a :class:`~eodag.config.ProviderConfig`

        :param config_keys: The configurations keys to validate
        """
        if "name" not in config_keys:
            raise ValidationError("Provider config must have name key")
        if not any(k in config_keys for k in PLUGINS_TOPICS_KEYS):
            raise ValidationError("A provider must implement at least one plugin")
        non_api_keys = [k for k in PLUGINS_TOPICS_KEYS if k != "api"]
        if "api" in config_keys and any(k in config_keys for k in non_api_keys):
            raise ValidationError(
                "A provider implementing an Api plugin must not implement any other "
                "type of plugin"
            )

    def update(self, mapping: Optional[dict[str, Any]]) -> None:
        """Update the configuration parameters with values from `mapping`

        :param mapping: The mapping from which to override configuration parameters
        """
        if mapping is None:
            mapping = {}
        merge_mappings(
            self.__dict__,
            {
                key: value
                for key, value in mapping.items()
                if key not in PLUGINS_TOPICS_KEYS and value is not None
            },
        )
        for key in PLUGINS_TOPICS_KEYS:
            current_value: Optional[dict[str, Any]] = getattr(self, key, None)
            mapping_value = mapping.get(key, {})
            if current_value is not None:
                current_value.update(mapping_value)
            elif mapping_value:
                setattr(self, key, PluginConfig.from_mapping(mapping_value))


class PluginConfig(yaml.YAMLObject):
    """Representation of a plugin config.

    This class variables describe available plugins configuration parameters.
    """

    class Pagination(TypedDict):
        """Search pagination configuration"""

        #: The maximum number of items per page that the provider can handle
        max_items_per_page: int
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
        #: The endpoint for counting the number of items satisfying a request
        count_endpoint: str
        #: Index of the starting page
        start_page: int

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
        search_param: str
        #: Path to the metadata in search result
        metadata_path: str

    class DiscoverProductTypes(TypedDict, total=False):
        """Configuration for product types discovery"""

        #: URL from which the product types can be fetched
        fetch_url: Optional[str]
        #: HTTP method used to fetch product types
        fetch_method: str
        #: Request body to fetch product types using POST method
        fetch_body: dict[str, Any]
        #: Maximum number of connections for concurrent HTTP requests
        max_connections: int
        #: The f-string template for pagination requests.
        next_page_url_tpl: str
        #: Index of the starting page for pagination requests.
        start_page: int
        #: Type of the provider result
        result_type: str
        #: JsonPath to the list of product types
        results_entry: Union[JSONPath, str]
        #: Mapping for the product type id
        generic_product_type_id: str
        #: Mapping for product type metadata (e.g. ``abstract``, ``licence``) which can be parsed from the provider
        #: result
        generic_product_type_parsable_metadata: dict[str, str]
        #: Mapping for product type properties which can be parsed from the result and are not product type metadata
        generic_product_type_parsable_properties: dict[str, str]
        #: Mapping for product type properties which cannot be parsed from the result and are not product type metadata
        generic_product_type_unparsable_properties: dict[str, str]
        #: URL to fetch data for a single collection
        single_collection_fetch_url: str
        #: Query string to be added to the fetch_url to filter for a collection
        single_collection_fetch_qs: str
        #: Mapping for product type metadata returned by the endpoint given in single_collection_fetch_url
        single_product_type_parsable_metadata: dict[str, str]

    class DiscoverQueryables(TypedDict, total=False):
        """Configuration for queryables discovery"""

        #: URL to fetch the queryables valid for all product types
        fetch_url: Optional[str]
        #: URL to fetch the queryables for a specific product type
        product_type_fetch_url: Optional[str]
        #: Type of the result
        result_type: str
        #: JsonPath to retrieve the queryables from the provider result
        results_entry: str
        #: :class:`~eodag.plugins.search.base.Search` URL of the constraint file used to build queryables
        constraints_url: str
        #: :class:`~eodag.plugins.search.base.Search` Key in the json result where the constraints can be found
        constraints_entry: str

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
    # per product type metadata-mapping, set in core._prepare_search
    product_type_config: dict[str, Any]

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
    #: :class:`~eodag.plugins.search.base.Search` Configuration for the product types auto-discovery
    discover_product_types: PluginConfig.DiscoverProductTypes
    #: :class:`~eodag.plugins.search.base.Search` Configuration for the queryables auto-discovery
    discover_queryables: PluginConfig.DiscoverQueryables
    #: :class:`~eodag.plugins.search.base.Search` The mapping between eodag metadata and the plugin specific metadata
    metadata_mapping: dict[str, Union[str, list[str]]]
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
    #: :class:`~eodag.plugins.search.data_request_search.DataRequestSearch` URL to which the data request shall be sent
    data_request_url: str
    #: :class:`~eodag.plugins.search.data_request_search.DataRequestSearch` URL to fetch the status of the data request
    status_url: str
    #: :class:`~eodag.plugins.search.data_request_search.DataRequestSearch`
    #: URL to fetch the search result when the data request is done
    result_url: str
    #: :class:`~eodag.plugins.search.data_request_search.DataRequestSearch`
    #: if date parameters are mandatory in the request
    dates_required: bool
    #: :class:`~eodag.plugins.search.csw.CSWSearch` Search definition dictionary
    search_definition: dict[str, Any]
    #: :class:`~eodag.plugins.search.qssearch.PostJsonSearch` Whether to merge responses or not (`aws_eos` specific)
    merge_responses: bool
    #: :class:`~eodag.plugins.search.qssearch.PostJsonSearch` Collections names (`aws_eos` specific)
    collection: list[str]
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
    #: :class:`~eodag.plugins.download.base.Download` Whether ignore assets and download using ``downloadLink`` or not
    ignore_assets: bool
    #: :class:`~eodag.plugins.download.base.Download` Product type specific configuration
    products: dict[str, dict[str, Any]]
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
    #: :class:`~eodag.plugins.download.s3rest.S3RestDownload`
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
    #: Credentials json structure if they should be sent as POST data
    req_data: dict[str, Any]
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
    #: :class:`~eodag.plugins.authentication.token_exchange.OIDCTokenExchangeAuth`
    #: Audience that the token ID is intended for. :attr:`~eodag.config.PluginConfig.client_id` of the Relying Party
    audience: str
    #: :class:`~eodag.plugins.authentication.generic.GenericAuth`
    #: which authentication method should be used
    method: str

    yaml_loader = yaml.Loader
    yaml_dumper = yaml.SafeDumper
    yaml_tag = "!plugin"

    @classmethod
    def from_yaml(cls, loader: yaml.Loader, node: Any) -> PluginConfig:
        """Build a :class:`~eodag.config.PluginConfig` from Yaml"""
        cls.validate(tuple(node_key.value for node_key, _ in node.value))
        return loader.construct_yaml_object(node, cls)

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> PluginConfig:
        """Build a :class:`~eodag.config.PluginConfig` from a mapping"""
        c = cls()
        c.__dict__.update(mapping)
        return c

    @staticmethod
    def validate(config_keys: tuple[Any, ...]) -> None:
        """Validate a :class:`~eodag.config.PluginConfig`"""
        if "type" not in config_keys:
            raise ValidationError(
                "A Plugin config must specify the Plugin it configures"
            )

    def update(self, mapping: Optional[dict[Any, Any]]) -> None:
        """Update the configuration parameters with values from `mapping`

        :param mapping: The mapping from which to override configuration parameters
        """
        if mapping is None:
            mapping = {}
        merge_mappings(
            self.__dict__, {k: v for k, v in mapping.items() if v is not None}
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

    :param config_path: The path to the provider config file
    :returns: The default provider's configuration
    """
    logger.debug("Loading configuration from %s", config_path)
    config: dict[str, ProviderConfig] = {}
    try:
        # Providers configs are stored in this file as separated yaml documents
        # Load all of it
        providers_configs: list[ProviderConfig] = cached_yaml_load_all(config_path)
    except yaml.parser.ParserError as e:
        logger.error("Unable to load configuration")
        raise e
    stac_provider_config = load_stac_provider_config()
    for provider_config in providers_configs:
        provider_config_init(provider_config, stac_provider_config)
        config[provider_config.name] = provider_config
    return config


def credentials_in_auth(auth_conf: PluginConfig) -> bool:
    """Checks if credentials are set for this Authentication plugin configuration

    :param auth_conf: Authentication plugin configuration
    :returns: True if credentials are set, else False
    """
    return any(
        c is not None for c in (getattr(auth_conf, "credentials", {}) or {}).values()
    )


def share_credentials(
    providers_config: dict[str, ProviderConfig],
) -> None:
    """Share credentials between plugins having the same matching criteria

    :param providers_configs: eodag providers configurations
    """
    auth_confs_with_creds = [
        getattr(p, k)
        for p in providers_config.values()
        for k in AUTH_TOPIC_KEYS
        if hasattr(p, k) and credentials_in_auth(getattr(p, k))
    ]
    for provider, provider_config in providers_config.items():
        if auth_confs_with_creds:
            for auth_topic_key in AUTH_TOPIC_KEYS:
                provider_config_auth = getattr(provider_config, auth_topic_key, None)
                if provider_config_auth and not credentials_in_auth(
                    provider_config_auth
                ):
                    # no credentials set for this provider
                    provider_matching_conf = getattr(
                        provider_config_auth, "matching_conf", {}
                    )
                    provider_matching_url = getattr(
                        provider_config_auth, "matching_url", None
                    )
                    for conf_with_creds in auth_confs_with_creds:
                        # copy credentials between plugins if `matching_conf` or `matching_url` are matching
                        if (
                            provider_matching_conf
                            and sort_dict(provider_matching_conf)
                            == sort_dict(getattr(conf_with_creds, "matching_conf", {}))
                        ) or (
                            provider_matching_url
                            and provider_matching_url
                            == getattr(conf_with_creds, "matching_url", None)
                        ):
                            getattr(
                                providers_config[provider], auth_topic_key
                            ).credentials = conf_with_creds.credentials


def provider_config_init(
    provider_config: ProviderConfig,
    stac_search_default_conf: Optional[dict[str, Any]] = None,
) -> None:
    """Applies some default values to provider config

    :param provider_config: An eodag provider configuration
    :param stac_search_default_conf: default conf to overwrite with provider_config if STAC
    """
    # For the provider, set the default output_dir of its download plugin
    # as tempdir in a portable way
    for download_topic_key in ("download", "api"):
        if download_topic_key in vars(provider_config):
            download_conf = getattr(provider_config, download_topic_key)
            if not getattr(download_conf, "output_dir", None):
                download_conf.output_dir = tempfile.gettempdir()
            if not getattr(download_conf, "delete_archive", None):
                download_conf.delete_archive = True

    try:
        if (
            stac_search_default_conf is not None
            and provider_config.search
            and provider_config.search.type
            in [
                "StacSearch",
                "StacListAssets",
                "StaticStacSearch",
            ]
        ):
            # search config set to stac defaults overriden with provider config
            per_provider_stac_provider_config = deepcopy(stac_search_default_conf)
            provider_config.search.__dict__ = update_nested_dict(
                per_provider_stac_provider_config["search"],
                provider_config.search.__dict__,
                allow_empty_values=True,
            )
    except AttributeError:
        pass


def override_config_from_file(config: dict[str, Any], file_path: str) -> None:
    """Override a configuration with the values in a file

    :param config: An eodag providers configuration dictionary
    :param file_path: The path to the file from where the new values will be read
    """
    logger.info("Loading user configuration from: %s", os.path.abspath(file_path))
    with open(os.path.abspath(os.path.realpath(file_path)), "r") as fh:
        try:
            config_in_file = yaml.safe_load(fh)
            if config_in_file is None:
                return
        except yaml.parser.ParserError as e:
            logger.error("Unable to load user configuration file")
            raise e
    override_config_from_mapping(config, config_in_file)


def override_config_from_env(config: dict[str, Any]) -> None:
    """Override a configuration with environment variables values

    :param config: An eodag providers configuration dictionary
    """

    def build_mapping_from_env(
        env_var: str, env_value: str, mapping: dict[str, Any]
    ) -> None:
        """Recursively build a dictionary from an environment variable.

        The environment variable must respect the pattern: KEY1__KEY2__[...]__KEYN.
        It will be transformed to::

            {
                "key1": {
                    "key2": {
                        {...}
                    }
                }
            }

        :param env_var: The environment variable to be transformed into a dictionary
        :param env_value: The value from environment variable
        :param mapping: The mapping in which the value will be created
        """
        parts = env_var.split("__")
        iter_parts = iter(parts)
        env_type = get_type_hints(PluginConfig).get(next(iter_parts, ""), str)
        child_env_type = (
            get_type_hints(env_type).get(next(iter_parts, ""), None)
            if isclass(env_type)
            else None
        )
        if len(parts) == 2 and child_env_type:
            # for nested config (pagination, ...)
            # try converting env_value type from type hints
            try:
                env_value = cast_scalar_value(env_value, child_env_type)
            except TypeError:
                logger.warning(
                    f"Could not convert {parts} value {env_value} to {child_env_type}"
                )
            mapping.setdefault(parts[0], {})
            mapping[parts[0]][parts[1]] = env_value
        elif len(parts) == 1:
            # try converting env_value type from type hints
            try:
                env_value = cast_scalar_value(env_value, env_type)
            except TypeError:
                logger.warning(
                    f"Could not convert {parts[0]} value {env_value} to {env_type}"
                )
            mapping[parts[0]] = env_value
        else:
            new_map = mapping.setdefault(parts[0], {})
            build_mapping_from_env("__".join(parts[1:]), env_value, new_map)

    mapping_from_env: dict[str, Any] = {}
    for env_var in os.environ:
        if env_var.startswith("EODAG__"):
            build_mapping_from_env(
                env_var[len("EODAG__") :].lower(),  # noqa
                os.environ[env_var],
                mapping_from_env,
            )

    override_config_from_mapping(config, mapping_from_env)


def override_config_from_mapping(
    config: dict[str, Any], mapping: dict[str, Any]
) -> None:
    """Override a configuration with the values in a mapping

    :param config: An eodag providers configuration dictionary
    :param mapping: The mapping containing the values to be overriden
    """
    for provider, new_conf in mapping.items():
        # check if metada-mapping as already been built as jsonpath in providers_config
        if not isinstance(new_conf, dict):
            continue
        new_conf_search = new_conf.get("search", {}) or {}
        new_conf_api = new_conf.get("api", {}) or {}
        if provider in config and "metadata_mapping" in {
            **new_conf_search,
            **new_conf_api,
        }:
            search_plugin_key = (
                "search" if "metadata_mapping" in new_conf_search else "api"
            )
            # get some already configured value
            configured_metadata_mapping = getattr(
                config[provider], search_plugin_key
            ).metadata_mapping
            some_configured_value = next(iter(configured_metadata_mapping.values()))
            # check if the configured value has already been built as jsonpath
            if (
                isinstance(some_configured_value, list)
                and isinstance(some_configured_value[1], tuple)
                or isinstance(some_configured_value, tuple)
            ):
                # also build as jsonpath the incoming conf
                mtd_cfg_as_conversion_and_querypath(
                    deepcopy(mapping[provider][search_plugin_key]["metadata_mapping"]),
                    mapping[provider][search_plugin_key]["metadata_mapping"],
                )

        # try overriding conf
        old_conf: Optional[dict[str, Any]] = config.get(provider)
        if old_conf is not None:
            old_conf.update(new_conf)
        else:
            logger.info(
                "%s: unknown provider found in user conf, trying to use provided configuration",
                provider,
            )
            try:
                new_conf["name"] = new_conf.get("name", provider)
                config[provider] = ProviderConfig.from_mapping(new_conf)
            except Exception:
                logger.warning(
                    "%s skipped: could not be loaded from user configuration", provider
                )

                import traceback as tb

                logger.debug(tb.format_exc())


def merge_configs(config: dict[str, Any], other_config: dict[str, Any]) -> None:
    """Override a configuration with the values of another configuration

    :param config: An eodag providers configuration dictionary
    :param other_config: An eodag providers configuration dictionary
    """
    # configs union with other_config values as default
    other_config = dict(config, **other_config)

    for provider, new_conf in other_config.items():
        old_conf = config.get(provider, None)

        if old_conf:
            # update non-objects values
            new_conf = dict(old_conf.__dict__, **new_conf.__dict__)

            for conf_k, conf_v in new_conf.items():
                old_conf_v = getattr(old_conf, conf_k, None)

                if isinstance(conf_v, PluginConfig) and isinstance(
                    old_conf_v, PluginConfig
                ):
                    old_conf_v.update(conf_v.__dict__)
                    new_conf[conf_k] = old_conf_v
                elif isinstance(old_conf_v, PluginConfig):
                    new_conf[conf_k] = old_conf_v

                setattr(config[provider], conf_k, new_conf[conf_k])
        else:
            config[provider] = new_conf


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


def get_ext_product_types_conf(
    conf_uri: str = EXT_PRODUCT_TYPES_CONF_URI,
) -> dict[str, Any]:
    """Read external product types conf

    :param conf_uri: URI to local or remote configuration file
    :returns: The external product types configuration
    """
    logger.info("Fetching external product types from %s", conf_uri)
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
                "Could not read remote external product types conf from %s", conf_uri
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
            "Could not read local external product types conf from %s", conf_uri
        )
        return {}
