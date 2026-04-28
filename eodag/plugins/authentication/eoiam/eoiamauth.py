# -*- coding: utf-8 -*-
# Copyright 2026, CS GROUP - France, https://www.csgroup.eu/
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

from urllib.parse import parse_qs, urljoin

import requests
from lxml import html
from requests.auth import AuthBase

from eodag.utils.exceptions import AuthenticationError, MisconfiguredError

from ..base import Authentication
from .eoiamsessionauth import EOIAMSessionAuth


class EOIAMAuth(Authentication):
    """
    Authentication plugin for EOIAM.
    """

    def __init__(self, provider, config) -> None:
        """Initialize the plugin with provider and config,
        and set up a requests.Session for SAML login."""
        super().__init__(provider, config)
        self.session = requests.Session()

    def validate_config_credentials(self) -> None:
        """Validate configured credentials"""
        required = ["username", "password"]
        missing = [
            k for k in required if k not in getattr(self.config, "credentials", {})
        ]
        if missing:
            msg = f"Missing credentials for {self.provider}: {', '.join(missing)}"
            raise MisconfiguredError(msg)

    def authenticate(self) -> AuthBase:
        """Return a requests.AuthBase object using the session with SAML login."""
        self.validate_config_credentials()
        return EOIAMSessionAuth(self)

    def _extract_input_value(self, tree, name: str) -> str:
        """Extract the value of an input field from the HTML tree."""
        inputs = tree.xpath(f"//input[@name='{name}']")
        if not inputs:
            msg = f"{name} input not found"
            raise MisconfiguredError(msg)
        value = inputs[0].get("value")
        if not value:
            msg = f"{name} has no value"
            raise MisconfiguredError(msg)
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

    def _login_from_html(self, html_content: str, req_url: str) -> requests.Response:
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
        resp.raise_for_status()

        if "consent.do" in resp.url:
            redirect_url = resp.url
            service_names = parse_qs(redirect_url).get("sp", [""])
            service_name = service_names[0] if service_names else ""
            msg = (
                f"Consent required for service {service_name}, "
                f"please fill the following form and try again {req_url}"
            )
            raise AuthenticationError(msg)

        if "login.do" in resp.url:
            raise MisconfiguredError("Login failed: please check your credentials")

        if "Earth Observation Identity and Access Management System" in resp.text:
            msg = f"Login failed: {resp.url}"
            raise MisconfiguredError(msg)

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
            msg = f"Unexpected response after SAML login: {resp_post.status_code}"
            raise AuthenticationError(msg)

        final_url = resp_post.headers.get("Location")
        if not final_url:
            raise AuthenticationError("Final redirect URL not found after SAML login")

        resp_final = self.session.get(final_url, stream=True)

        content_type = resp_final.headers.get("Content-Type", "")

        if content_type.startswith(("text/html", "text/xml")):
            error_text = resp_final.text

            if "wants to access your account" in error_text:
                msg = (
                    "Consent required: please log in to the EOIAM portal "
                    f"and grant consent through this link {final_url}"
                )
                raise AuthenticationError(msg)

            if (
                "not yet performed the necessary steps in order to access this data."
                in error_text
            ):
                msg = (
                    f"Data access request required: please log in to the EOIAM portal "
                    f"and request access to the data through this link {final_url}"
                )
                raise AuthenticationError(msg)

            raise AuthenticationError("Unexpected HTML response after SAML login")

        return resp_final


__all__ = ["EOIAMAuth"]
