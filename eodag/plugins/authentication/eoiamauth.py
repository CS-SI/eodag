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
