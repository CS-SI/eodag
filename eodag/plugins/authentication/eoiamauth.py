import requests
from requests.auth import AuthBase

from eodag.plugins.authentication.base import Authentication
from eodag.utils.exceptions import MisconfiguredError


class EOIAMAuth(Authentication):
    """
    Authentication plugin for EOIAM.
    """

    def __init__(self, provider, config):
        super().__init__(provider, config)

    def validate_config_credentials(self):
        """Validate configured credentials"""
        required = ["username", "password"]
        missing = [k for k in required if k not in self.config.credentials]
        if missing:
            raise MisconfiguredError(
                f"Missing credentials for {self.provider}: {', '.join(missing)}"
            )

    def _get_valid_token(self) -> str:
        """
        Perform the EOIAM login request and extract the bearer token.
        Equivalent to the curl:

        curl -b cookiefile -c cookiefile \
             -L -k -f -s -S "$IDP_ADDR" \
             --data "tocommonauth=true" \
             --data-urlencode "username=..." \
             --data-urlencode "password=..." \
             --data "sessionDataKey=..." \
             -o output.html
        """
        if self._token is not None:
            return self._token

        creds = self.config.credentials
        username = creds["username"]
        password = creds["password"]
        idp_url = creds["idp_url"]
        session_key = creds["sessionDataKey"]

        # Create session to manage cookies (curl -b -c)
        session = requests.Session()

        payload = {
            "tocommonauth": "true",
            "username": username,
            "password": password,
            "sessionDataKey": session_key,
        }

        # Send POST request (curl --data)
        resp = session.post(idp_url, data=payload, allow_redirects=True, verify=False)

        if not resp.ok:
            raise MisconfiguredError(
                f"EOIAM authentication failed ({resp.status_code}): {resp.text}"
            )

        # You need to extract the token from the response.
        # Example: if the token is in JSON { "token": "..." }
        # Adapt here according to real API structure:
        try:
            json_resp = resp.json()
            self._token = json_resp.get("token")
        except Exception:
            raise MisconfiguredError(
                "Could not extract token from EOIAM response (expected JSON)"
            )

        if not self._token:
            raise MisconfiguredError("EOIAM authentication returned no token")

        return self._token

    def authenticate(self) -> AuthBase:
        """Return a requests.AuthBase object adding Authorization header."""
        self.validate_config_credentials()
        return _EOIAMBearerToken(self)


class _EOIAMBearerToken(AuthBase):
    """AuthBase adding EOIAM Bearer token to each request."""

    def __init__(self, auth_plugin: EOIAMAuth):
        self.auth_plugin = auth_plugin

    def __call__(self, request):
        token = self.auth_plugin._get_valid_token()
        request.headers["Authorization"] = f"Bearer {token}"
        return request
