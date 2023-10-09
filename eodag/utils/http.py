import logging
import time
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Union
from urllib.error import URLError
from urllib.parse import parse_qs, quote, urlencode, urlparse
from urllib.request import Request, urlopen

import requests
from requests import Response as HttpResponse
from requests.adapters import HTTPAdapter
from requests_ftp import FTPAdapter

from eodag.utils import USER_AGENT
from eodag.utils.exceptions import AuthenticationError, RequestError

logger = logging.getLogger("eodag.utils.http")

HTTP_TIMEOUT_REQUEST = 5


@dataclass
class HttpRequestParams:
    """
    A dataclass for storing HTTP request parameters.

    :ivar str method: The HTTP method for the request.
    :ivar str url: The URL for the request.
    :ivar dict headers: A dictionary of headers to send with the request. Defaults to an empty dictionary.
    :ivar int timeout: The timeout for the request in seconds. Defaults to None.
    :ivar list unquoted_params: A list of parameters that should not be URL encoded. Defaults to None.
    :ivar dict extra_params: A dictionary of extra parameters to include in the request. Defaults to an empty
        dictionary.
    """

    method: str
    url: str
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: Optional[int] = None
    unquoted_params: Optional[List[str]] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the HttpRequestParams instance to a dictionary.

        If 'extra_params' is not None, its keys and values are added to the resulting dictionary at the same level as
        the main keys.

        :return: A dictionary representation of the HttpRequestParams instance.
        :rtype: dict
        """
        result = asdict(self)
        if self.extra_params:
            result.update(self.extra_params)
            del result["extra_params"]
        return result


class HttpRequests:
    """
    A class for sending HTTP requests with optional default headers and timeout.

    :ivar requests.Session session: A Session object from the requests library.
    :ivar dict default_headers: A dictionary of default HTTP headers to send with each request.
    :ivar int timeout: The default timeout for each request in seconds.
    """

    def __init__(
        self,
        default_headers: Optional[Dict[str, str]] = None,
        timeout: int = HTTP_TIMEOUT_REQUEST,
    ) -> None:
        """
        Initialize the HttpRequests instance with default headers and timeout.

        :param dict default_headers: A dictionary of default HTTP headers to send with each request.
        :param int timeout: The default timeout for each request in seconds.
        """
        self.session = requests.Session()
        self.default_headers = default_headers or deepcopy(USER_AGENT)
        self.timeout = timeout

        # url where data is downloaded from can be ftp -> add ftp adapter
        self.session.mount("ftp://", FTPAdapter())

    def _send_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        unquoted_params: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """
        Send an HTTP request and return the response.

        This method sends an HTTP request using either the urllib or requests library, depending on whether unquoted URL
        parameters are provided.
        It handles HTTP 401 Unauthorized and HTTP 403 Forbidden errors by raising an AuthenticationError, and other 4xx
        and 5xx status codes by raising a RequestError.

        :param str method: The HTTP method to use for the request.
        :param str url: The URL to send the request to.
        :param dict headers: Additional headers to include in the request. These will be merged with the default
            headers.
        :param int timeout: The timeout for the request in seconds. If not provided, self.timeout will be used.
        :param list unquoted_params: A list of URL parameters that should not be URL-encoded.
        :param kwargs: Additional keyword arguments to pass to the _send_request method.

        :return: An HttpResponse object representing the response to the request.

        :raises AuthenticationError: If the server returns a 401 Unauthorized or 403 Forbidden status code.

        :raises RequestError: If the server returns any other 4xx or 5xx status code.
        """
        if headers is None:
            headers = {}

        # Merge default headers with custom headers
        headers = {**self.default_headers, **headers}

        timeout = timeout or self.timeout

        # Handle unquoted URL parameters
        if unquoted_params:
            # Keep unquoted desired params
            base_url, params = url.split("?") if "?" in url else (url, "")
            qry = quote(params)
            for keep_unquoted in unquoted_params:
                qry = qry.replace(quote(keep_unquoted), keep_unquoted)

            # Prepare request for Response building
            req = requests.Request(
                method=method, url=base_url, headers=headers, **kwargs
            )
            prep = req.prepare()
            prep.url = base_url + "?" + qry

            # Send urllib request
            urllib_req = Request(prep.url, headers=headers)
            urllib_response = urlopen(urllib_req, timeout=timeout)

            # Build Response
            adapter = HTTPAdapter()
            response = adapter.build_response(prep, urllib_response)
        else:
            # Send request using requests library
            response = self.session.request(
                method,
                url,
                headers=headers,
                timeout=timeout,
                **kwargs,
            )

        if response.status_code in [401, 403]:
            # handle HTTP 401 Unauthorized and HTTP 403 Forbidden errors
            raise AuthenticationError(f"{response.text}", response.status_code)
        elif 400 <= response.status_code < 600:
            raise RequestError(f"{response.text}", response.status_code)

        return response

    def _request(
        self,
        method: str,
        url: str,
        retries: int = 3,
        delay: int = 1,
        **kwargs: Any,
    ) -> HttpResponse:
        """
        Sends an HTTP request and returns the response. If the request fails due to a network error, it will be retried
        a specified number of times before finally raising an exception.

        :param str method: The HTTP method to use for the request. This should be a string, like 'GET', 'POST', etc.
        :param str url: The URL to send the request to. This should be a string containing a valid URL.
        :param int retries: The number of times to retry the request if it fails due to a network error. Defaults to 3.
        :param int delay: The initial delay between retries in seconds. For each retry, the delay is lengthened by
            doubling it (exponential backoff). Defaults to 1.
        :param kwargs: Additional keyword arguments to pass to the _send_request method.

        :return: An HttpResponse object representing the response to the request.

        :raises RequestError: If all attempts to send the request fail.
        """
        for i in range(retries):
            try:
                # Call _send_request method instead of sending request directly
                return self._send_request(
                    method=method,
                    url=url,
                    **kwargs,
                )
            except (requests.RequestException, URLError) as e:
                if i < retries - 1:  # i is zero indexed
                    time.sleep(delay * (2**i))  # exponential backoff
                else:
                    raise RequestError(
                        f"{method} {url} failed after {retries} attempts. {e}"
                    )  # raise an exception if all attempts fail
        # we should never arrive here
        raise RequestError(f"{method} {url} failed with no response and no exception")

    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        retries: int = 3,
        delay: int = 1,
        timeout: Optional[int] = None,
        unquoted_params: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """
        Sends an HTTP GET request to the specified URL.

        :param str url: The URL to send the request to.
        :param dict headers: Additional headers to include in the request. These will be merged with the default
            headers.
        :param int retries: The number of times to retry the request if it fails due to a network error. Defaults to 3.
        :param int delay: The initial delay between retries in seconds. For each retry, the delay is lengthened by
            doubling it (exponential backoff). Defaults to 1.
        :param int timeout: The timeout for the request in seconds. If not provided, self.timeout will be used.
        :param list unquoted_params: A list of URL parameters that should not be URL-encoded.
        :param kwargs: Additional keyword arguments to pass to the _send_request method.

        :return: An HttpResponse object representing the response to the request.

        :raises AuthenticationError: If the server returns a 401 Unauthorized or 403 Forbidden status code.

        :raises RequestError: If all attempts to send the request fail.
        """
        return self._request(
            "GET",
            url,
            headers=headers,
            retries=retries,
            delay=delay,
            timeout=timeout,
            unquoted_params=unquoted_params,
            **kwargs,
        )

    def post(
        self,
        url: str,
        data: Optional[Union[Dict[str, Any], bytes]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        retries: int = 3,
        delay: int = 1,
        timeout: Optional[int] = None,
        unquoted_params: Optional[List[str]] = None,
        **kwargs,
    ) -> HttpResponse:
        """
        Sends an HTTP POST request to the specified URL.

        :param str url: The URL to send the request to.
        :param data: Dictionary, list of tuples or bytes to send in the body of the request. Defaults to None.
        :type data: Union[Dict[str, Any], bytes], optional
        :param headers: Dictionary of HTTP headers to send with the request. Defaults to None.
        :type headers: Dict[str, str], optional
        :param json: JSON data to send in the body of the request. Defaults to None.
        :type json: Dict[str, Any], optional
        :param int retries: The number of times to attempt the request before giving up. Defaults to 3.
        :param int delay: The number of seconds to wait between attempts. Defaults to 1.
        :param timeout: The maximum number of seconds to wait for a response. Defaults to self.timeout if not set.
        :type timeout: int, optional
        :param unquoted_params: A list of URL parameters that should not be quoted. Defaults to None.
        :type unquoted_params: List[str], optional
        :param kwargs: Optional arguments that `requests.request` takes.

        :return: The response from the server.
        :rtype: HttpResponse

        :raises AuthenticationError: If the server returns an HTTP 401 Unauthorized or HTTP 403 Forbidden error.
        :raises RequestError: If all attempts to send the request fail.
        """
        return self._request(
            "POST",
            url,
            data=data,
            json=json,
            headers=headers,
            retries=retries,
            delay=delay,
            timeout=timeout,
            unquoted_params=unquoted_params,
            **kwargs,
        )

    def head(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        retries: int = 3,
        delay: int = 1,
        timeout: Optional[int] = None,
        unquoted_params: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """
        Sends an HTTP HEAD request to the specified URL.

        :param url: The URL to send the request to.
        :type url: str
        :param headers: Dictionary of HTTP headers to send with the request, defaults to None
        :type headers: dict, optional
        :param retries: The number of times to attempt the request before giving up, defaults to 3
        :type retries: int
        :param delay: The number of seconds to wait between attempts, defaults to 1
        :type delay: int
        :param timeout: The maximum number of seconds to wait for a response. Defaults to self.timeout if not set,
            defaults to None
        :type timeout: int, optional
        :param unquoted_params: A list of URL parameters that should not be quoted, defaults to None
        :type unquoted_params: List[str], optional
        :param kwargs: Optional arguments that `requests.request` takes.

        :return: The response from the server.
        :rtype: HttpResponse

        :raises AuthenticationError: If the server returns an HTTP 401 Unauthorized or HTTP 403 Forbidden error.
        :raises RequestError: If all attempts to send the request fail.

        """
        return self._request(
            "HEAD",
            url,
            headers=headers,
            retries=retries,
            delay=delay,
            timeout=timeout,
            unquoted_params=unquoted_params,
            **kwargs,
        )

    def request(
        self,
        method: str,
        url: str,
        data: Optional[Union[Dict[str, Any], bytes]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        retries: int = 3,
        delay: int = 1,
        timeout: Optional[int] = None,
        unquoted_params: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """
        Sends an HTTP request with the specified method to the specified URL.

        :param str method: The HTTP method to use for the request (e.g., "GET" or "POST").
        :param str url: The URL to send the request to.
        :param data: Dictionary, list of tuples or bytes to send in the body of the request. Defaults to None.
        :type data: Union[Dict[str, Any], bytes], optional
        :param json: JSON data to send in the body of the request. Defaults to None.
        :type json: Dict[str, Any], optional
        :param headers: Dictionary of HTTP headers to send with the request. Defaults to None.
        :type headers: Dict[str, str], optional
        :param int retries: The number of times to attempt the request before giving up. Defaults to 3.
        :param int delay: The number of seconds to wait between attempts. Defaults to 1.
        :param timeout: The maximum number of seconds to wait for a response. Defaults to self.timeout if not set.
        :type timeout: int, optional
        :param unquoted_params: A list of URL parameters that should not be quoted. Defaults to None.
        :type unquoted_params: List[str], optional
        :param kwargs: Optional arguments that `requests.request` takes.

        :return: The response from the server.
        :rtype: HttpResponse

        :raises AuthenticationError: If the server returns an HTTP 401 Unauthorized or HTTP 403 Forbidden error.
        :raises RequestError: If all attempts to send the request fail.
        """
        return self._request(
            method,
            url,
            data=data,
            json=json,
            headers=headers,
            retries=retries,
            delay=delay,
            timeout=timeout,
            unquoted_params=unquoted_params,
            **kwargs,
        )


def add_qs_params(url: str, params: dict[str, List[str]]) -> str:
    """
    Adds query parameters to a URL.

    This function parses the given URL and its query parameters, updates the query parameters with the new parameters,
    and then reconstructs the URL.

    :param url: The URL to which the credentials should be added.
    :type url: str
    :param params: The new parameters to be added to the URL.
    :type params: dict[str, List[str]]

    :return: The updated URL with the new parameters added to its query parameters.
    :rtype: str
    """
    url_parts = urlparse(url)
    query_params = parse_qs(url_parts.query)
    query_params.update(**params)
    url_parts = url_parts._replace(query=urlencode(query_params, doseq=True))
    return url_parts.geturl()


http = HttpRequests()
