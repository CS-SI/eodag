from urllib.parse import urljoin

import requests
from lxml import html
from requests.auth import AuthBase

from eodag.plugins.authentication.base import Authentication
from eodag.utils.exceptions import MisconfiguredError


class EOIAMAuth(Authentication):
    """
    Authentication plugin for EOIAM.
    """

    def __init__(self, provider, config) -> None:
        """Initialize the plugin with provider and config,
        and set up a requests.Session for SAML login."""
        super().__init__(provider, config)
        self.session = requests.Session()
        self._logged_in = False

    def validate_config_credentials(self) -> None:
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

    def _extract_input_value(self, tree, name: str) -> str:
        """Extract the value of an input field from the HTML tree."""
        inputs = tree.xpath(f"//input[@name='{name}']")
        if not inputs:
            raise MisconfiguredError(f"{name} input not found")
        value = inputs[0].get("value")
        if not value:
            raise MisconfiguredError(f"{name} has no value")
        return value

    def _extract_first_form(self, tree: html.HtmlElement) -> html.HtmlElement:
        """Extract the first form from the HTML tree."""
        forms = tree.xpath("//form")
        if not forms:
            raise MisconfiguredError("Form not found")
        return forms[0]

    def _resolve_action(self, form: html.HtmlElement, base_url: str) -> str:
        """Resolve the action URL of a form relative to the base URL."""
        action = form.get("action")
        if not action:
            raise MisconfiguredError("Form action not found")
        return urljoin(base_url, action)

    def _login_from_html(self, html_content: str) -> requests.Response:
        """Perform SAML login from HTML page."""
        creds = self.config.credentials
        username = creds["username"]
        password = creds["password"]
        base_url = self.config.auth_uri

        # Parse the HTML to extract the session key and form action
        tree = html.fromstring(html_content)

        session_key = self._extract_input_value(tree, "sessionDataKey")

        form = self._extract_first_form(tree)
        idp_url = self._resolve_action(form, base_url)

        # Submit credentials
        payload = {
            "tocommonauth": "true",
            "username": username,
            "password": password,
            "sessionDataKey": session_key,
        }
        resp = self.session.post(idp_url, data=payload, allow_redirects=True)

        if "Earth Observation Identity and Access Management System" in resp.text:
            raise MisconfiguredError("Login failed: check credentials or consent")

        # Extract SAML form
        tree = html.fromstring(resp.text)
        form = self._extract_first_form(tree)

        saml_url = self._resolve_action(form, base_url)
        saml_data = {
            inp.get("name"): inp.get("value")
            for inp in form.xpath(".//input[@name]")
            if inp.get("name") and inp.get("value")
        }

        # Submit SAML response
        resp_post = self.session.post(saml_url, data=saml_data, allow_redirects=False)

        if not resp_post.is_redirect:
            raise MisconfiguredError(
                f"Unexpected response after SAML login: {resp_post.status_code}"
            )

        final_url = resp_post.headers.get("Location")
        if not final_url:
            raise MisconfiguredError("Final redirect URL not found after SAML login")

        resp_final = self.session.get(final_url, stream=True)

        content_type = resp_final.headers.get("Content-Type", "")

        if content_type.startswith(("text/html", "text/xml")):
            error_text = resp_final.text

            if "wants to access your account" in error_text:
                raise MisconfiguredError(
                    "Consent required: please log in to the EOIAM portal and grant consent to EO Data Access Gateway"
                )

            if (
                "not yet performed the necessary steps in order to access this data."
                in error_text
            ):
                raise MisconfiguredError(
                    "Data access request required: please log in to the EOIAM portal and request access to the data"
                )

            raise MisconfiguredError("Unexpected HTML response after SAML login")

        return resp_final


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
