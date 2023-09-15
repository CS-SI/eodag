import json
import logging
from copy import deepcopy
from datetime import time
from typing import Any, Dict, Iterable, List, Optional, Union
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import requests
from requests.adapters import HTTPAdapter

from eodag.config import USER_AGENT
from eodag.utils.exceptions import AuthenticationError, RequestError

logger = logging.getLogger("eodag.utils.http")


class HttpResponse:
    """
    A class representing an HTTP response.
    """

    def __init__(
        self,
        status_code: int,
        headers: dict,
        content: str,
        stream: Optional[Iterable[bytes]] = None,
    ):
        """
        Initializes an instance of the HttpResponse class.

        :param status_code: The HTTP status code of the response.
        :type status_code: int
        :param headers: The HTTP headers of the response.
        :type headers: dict
        :param content: The content of the response.
        :type content: str
        :param stream: An iterator over the response data.
        :type stream: Optional[Iterable[bytes]]
        """
        self.status_code = status_code
        self.headers = headers
        self.content = content
        self.stream = stream

    def iter_content(self, chunk_size=1) -> Iterable[bytes]:
        """
        Iterates over the response data.

        When stream=True is set on the request, this avoids reading the content at once into memory for large responses.

        :param chunk_size: Number of bytes it should read into memory.
        :type chunk_size: int
        """
        if self.stream is not None:
            for chunk in self.stream:
                yield chunk
        else:
            for i in range(0, len(self.content), chunk_size):
                yield self.content[i : i + chunk_size]

    def json(self) -> dict:
        """
        Attempts to parse the content of the response as JSON and return it as a dictionary.

        :return: A dictionary representing the parsed JSON content.
        :rtype: dict
        """
        return json.loads(self.content)

    def __str__(self) -> str:
        """
        Returns a human-readable string representation of the HttpResponse object.

        :return: A human-readable string representation of the HttpResponse object.
        :rtype: str
        """
        return f"HttpResponse(status_code={self.status_code}, headers={self.headers}, content={self.content})"

    def __repr__(self) -> str:
        """
        Returns a string representation of the HttpResponse object that can be used to recreate the object.

        :return: A string representation of the HttpResponse object that can be used to recreate the object.
        :rtype: str
        """
        return f"HttpResponse({self.status_code!r}, {self.headers!r}, {self.content!r})"


class HttpRequests:
    """
    A class for sending HTTP requests.
    """

    def __init__(self, default_headers: Optional[Dict[str, str]] = None) -> None:
        """
        Initialize the HttpRequests instance with default headers.

        :param default_headers: A dictionary of default HTTP headers to send with each request.
        """
        self.session = requests.Session()
        self.default_headers = default_headers or deepcopy(USER_AGENT)

    def _send_request(
        self,
        method: str,
        url: str,
        data: Optional[Union[Dict[str, Any], bytes]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 10,
        unquoted_params: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> HttpResponse:

        if headers is None:
            headers = {}

        # Merge default headers with custom headers
        headers = {**self.default_headers, **headers}

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
                data=data,
                json=json,
                headers=headers,
                timeout=timeout,
                **kwargs,
            )

        if response.status_code in [401, 403]:
            # handle HTTP 401 Unauthorized and HTTP 403 Forbidden errors
            raise AuthenticationError(f"{response.text}", response.status_code)
        elif 400 <= response.status_code < 600:
            raise RequestError(f"{response.text}", response.status_code)

        stream = response.iter_content() if kwargs.get("stream") else None
        return HttpResponse(
            response.status_code, response.headers, response.text, stream
        )

    def _request(
        self,
        method: str,
        url: str,
        data: Optional[Union[Dict[str, Any], bytes]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        retries: int = 3,
        delay: int = 1,
        unquoted_params: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> HttpResponse:

        for i in range(retries):
            try:
                # Call _send_request method instead of sending request directly
                return self._send_request(
                    method, url, data, json, headers, unquoted_params, **kwargs
                )
            except (requests.RequestException, URLError) as e:
                if i < retries - 1:  # i is zero indexed
                    time.sleep(delay * (2**i))  # exponential backoff
                else:
                    raise RequestError(
                        f"{method} {url} with data={data} and json={json} failed after {retries} attempts. {e}"
                    )  # raise an exception if all attempts fail

    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        retries: int = 3,
        delay: int = 1,
        unquoted_params: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """
        Sends an HTTP GET request to the specified URL.

        Args:
            url (str): The URL to send the request to.
            headers (dict, optional): Dictionary of HTTP headers to send with the request.
            retries (int): The number of times to attempt the request before giving up.
            delay (int): The number of seconds to wait between attempts.
            unquoted_params (List[str], optional): A list of URL parameters that should not be quoted.
            **kwargs: Optional arguments that `requests.request` takes.

        Returns:
            HttpResponse: The response from the server.

        Raises:
            AuthenticationError: If the server returns an HTTP 401 Unauthorized or HTTP 403 Forbidden error.
            RequestError: If all attempts fail due to a requests.exceptions.RequestException.
        """
        return self._request(
            "GET",
            url,
            headers=headers,
            retries=retries,
            delay=delay,
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
        unquoted_params: Optional[List[str]] = None,
        **kwargs,
    ) -> HttpResponse:
        """
        Sends an HTTP POST request to the specified URL.

        Args:
            url (str): The URL to send the request to.
            data (dict, optional): Dictionary, list of tuples or bytes to send in the body of the request.
            headers (dict, optional): Dictionary of HTTP headers to send with the request.
            json (dict, optional): JSON data to send in the body of the request.
            retries (int): The number of times to attempt the request before giving up.
            delay (int): The number of seconds to wait between attempts.
            unquoted_params (List[str], optional): A list of URL parameters that should not be quoted.
            **kwargs: Optional arguments that `requests.request` takes.

        Returns:
            HttpResponse: The response from the server.

        Raises:
            AuthenticationError: If the server returns an HTTP 401 Unauthorized or HTTP 403 Forbidden error.
            RequestError: If all attempts fail due to a requests.exceptions.RequestException.
        """
        return self._request(
            "POST",
            url,
            data=data,
            json=json,
            headers=headers,
            retries=retries,
            delay=delay,
            unquoted_params=unquoted_params,
            **kwargs,
        )

    def head(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        retries: int = 3,
        delay: int = 1,
        unquoted_params: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """
        Sends an HTTP HEAD request to the specified URL.

        Args:
            url (str): The URL to send the request to.
            headers (dict, optional): Dictionary of HTTP headers to send with the request.
            retries (int): The number of times to attempt the request before giving up.
            delay (int): The number of seconds to wait between attempts.
            unquoted_params (List[str], optional): A list of URL parameters that should not be quoted.
            **kwargs: Optional arguments that `requests.request` takes.

        Returns:
            HttpResponse: The response from the server.

        Raises:
            AuthenticationError: If the server returns an HTTP 401 Unauthorized or HTTP 403 Forbidden error.
            RequestError: If all attempts fail due to a requests.exceptions.RequestException.
        """
        return self._request(
            "HEAD",
            url,
            headers=headers,
            retries=retries,
            delay=delay,
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
        unquoted_params: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """
        Sends an HTTP request with the specified method to the specified URL.

        Args:
            method (str): The HTTP method to use for the request (e.g., "GET" or "POST").
            url (str): The URL to send the request to.
            data (dict, optional): Dictionary, list of tuples or bytes to send in the body of the request.
            json (dict, optional): JSON data to send in the body of the request.
            headers (dict, optional): Dictionary of HTTP headers to send with the request.
            retries (int): The number of times to attempt the request before giving up.
            delay (int): The number of seconds to wait between attempts.
            unquoted_params (List[str], optional): A list of URL parameters that should not be quoted.
            **kwargs: Optional arguments that `requests.request` takes.

        Returns:
            HttpResponse: The response from the server.

        Raises:
            AuthenticationError: If the server returns an HTTP 401 Unauthorized or HTTP 403 Forbidden error.
            RequestError: If all attempts fail due to a requests.exceptions.RequestException.
        """
        return self._request(
            method,
            url,
            data=data,
            json=json,
            headers=headers,
            retries=retries,
            delay=delay,
            unquoted_params=unquoted_params,
            **kwargs,
        )


http = HttpRequests()
