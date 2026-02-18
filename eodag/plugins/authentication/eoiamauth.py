from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag
from requests.auth import AuthBase

from eodag.plugins.authentication.base import Authentication
from eodag.utils.exceptions import MisconfiguredError


class EOIAMAuth(Authentication):
    """
    Authentication plugin for EOIAM.
    """

    def __init__(self, provider, config):
        """Initialize the plugin with provider and config,
        and set up a requests.Session for SAML login."""
        super().__init__(provider, config)
        self.session = requests.Session()
        self._logged_in = False

    def validate_config_credentials(self):
        """Validate configured credentials"""
        required = ["username", "password"]
        missing = [k for k in required if k not in self.config.credentials]
        if missing:
            raise MisconfiguredError(
                f"Missing credentials for {self.provider}: {', '.join(missing)}"
            )

    def authenticate(self) -> AuthBase:
        """Return a requests.AuthBase object using the session with SAML login."""
        self.validate_config_credentials()
        return _EOIAMSessionAuth(self)

    def _login_from_html(self, html: str):
        """Perform SAML login from HTML page."""
        creds = self.config.credentials
        username = creds["username"]
        password = creds["password"]

        login_page_url = self.config.auth_uri

        soup = BeautifulSoup(html, "html.parser")

        session_input = soup.find("input", {"name": "sessionDataKey"})
        if not isinstance(session_input, Tag):
            raise MisconfiguredError("sessionDataKey input not found")
        session_key = session_input.get("value")
        if not session_key:
            raise MisconfiguredError("sessionDataKey has no value")

        form = soup.find("form")
        if not isinstance(form, Tag):
            raise MisconfiguredError("Login form not found")
        idp_url = form.get("action")
        if not idp_url:
            raise MisconfiguredError("IDP URL not found in form")
        idp_url = urljoin(login_page_url, str(idp_url))
        # POST login
        payload = {
            "tocommonauth": "true",
            "username": username,
            "password": password,
            "sessionDataKey": session_key,
        }
        resp_get = self.session.post(idp_url, data=payload, allow_redirects=True)

        if "Earth Observation Identity and Access Management System" in resp_get.text:
            raise MisconfiguredError("Login failed: check credentials or consent")

        # Handle SAML redirect form
        soup = BeautifulSoup(resp_get.text, "html.parser")
        form = soup.find("form")
        if not isinstance(form, Tag):
            raise MisconfiguredError("SAML redirect form not found")
        saml_url = form.get("action")
        if not saml_url:
            raise MisconfiguredError("SAML URL not found in form")
        saml_url = urljoin(login_page_url, str(saml_url))
        saml_data = {
            inp.get("name"): inp.get("value")
            for inp in form.find_all("input")
            if isinstance(inp, Tag) and inp.get("name") and inp.get("value")
        }

        resp_post = self.session.post(saml_url, data=saml_data, allow_redirects=False)
        final_url = resp_post.headers.get("Location")
        if not final_url:
            raise MisconfiguredError("Final redirect URL not found after SAML login")

        resp_get = self.session.get(final_url, stream=True)


class _EOIAMSessionAuth(AuthBase):
    """AuthBase wrapper using a requests.Session with lazy SAML login."""

    def __init__(self, auth_plugin: EOIAMAuth):
        """Initialize with the EOIAMAuth plugin to access its session and login method."""
        self.auth_plugin = auth_plugin

    def __call__(self, request):
        """
        This is called by requests before sending a request.
        We use the session's get/post to ensure login happens if needed.
        """
        session = self.auth_plugin.session

        # Lazy login
        if not self.auth_plugin._logged_in:
            resp = session.get(request.url, allow_redirects=True)
            if "Earth Observation Identity and Access Management System" in resp.text:
                self.auth_plugin._login_from_html(resp.text)
            self.auth_plugin._logged_in = True

        # Copy cookies from session to the request
        request.prepare_cookies(self.auth_plugin.session.cookies)

        return request
