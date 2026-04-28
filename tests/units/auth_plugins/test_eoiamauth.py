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

from unittest import mock

import requests
import responses
from requests import Request
from requests.auth import AuthBase

from eodag.api.provider import ProvidersDict
from eodag.plugins.authentication.eoiam import EOIAMSessionAuth
from eodag.plugins.manager import PluginManager
from eodag.utils.exceptions import AuthenticationError, MisconfiguredError
from tests.units.auth_plugins.base import BaseAuthPluginTest


class TestAuthPluginEOIAMAuth(BaseAuthPluginTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        providers = ProvidersDict.from_configs(
            {
                "foo_provider": {
                    "products": {"foo_product": {}},
                    "auth": {
                        "type": "EOIAMAuth",
                        "auth_uri": "http://foo.bar",
                    },
                },
            }
        )
        cls.plugins_manager = PluginManager(providers)

    def test_plugins_auth_eoiam_validate_credentials_empty(self):
        """EOIAMAuth.validate_config_credentials must raise an error on empty credentials"""
        auth_plugin = self.get_auth_plugin("foo_provider")
        self.assertRaises(
            MisconfiguredError,
            auth_plugin.validate_config_credentials,
        )

    def test_plugins_auth_eoiam_validate_credentials_missing_password(self):
        """EOIAMAuth.validate_config_credentials must raise an error when password is missing"""
        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {"username": "test_user"}
        self.assertRaises(
            MisconfiguredError,
            auth_plugin.validate_config_credentials,
        )

    def test_plugins_auth_eoiam_validate_credentials_missing_username(self):
        """EOIAMAuth.validate_config_credentials must raise an error when username is missing"""
        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {"password": "test_pass"}
        self.assertRaises(
            MisconfiguredError,
            auth_plugin.validate_config_credentials,
        )

    def test_plugins_auth_eoiam_validate_credentials_ok(self):
        """EOIAMAuth.validate_config_credentials must be ok with valid credentials"""
        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {
            "username": "test_user",
            "password": "test_pass",
        }
        auth_plugin.validate_config_credentials()

    def test_plugins_auth_eoiam_authenticate_returns_authbase(self):
        """EOIAMAuth.authenticate must return a requests.AuthBase object"""
        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {
            "username": "test_user",
            "password": "test_pass",
        }
        auth = auth_plugin.authenticate()
        self.assertIsInstance(auth, AuthBase)

    @responses.activate
    def test_plugins_auth_eoiam_authenticate_no_login_required(self):
        """EOIAMAuth should not login if not an EOIAM page"""
        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {
            "username": "test_user",
            "password": "test_pass",
        }

        # Response without EOIAM login page
        responses.add(
            responses.GET,
            "http://test.url",
            body="<html><body>Some content</body></html>",
        )

        auth = auth_plugin.authenticate()
        req = mock.Mock(headers={})
        req.url = "http://test.url"
        with mock.patch.object(auth_plugin, "_login_from_html") as mock_login_from_html:
            auth(req)
            mock_login_from_html.assert_not_called()

    @responses.activate
    def test_plugins_auth_eoiam_login_from_html_success(self):
        """EOIAMAuth._login_from_html should perform SAML login successfully"""
        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {
            "username": "test_user",
            "password": "test_pass",
        }

        # HTML with login form
        login_html = """
        <html>
            <body>
                <form action="/commonauth" method="post">
                    <input name="sessionDataKey" value="test_session_key" />
                    <input name="username" />
                    <input name="password" />
                </form>
            </body>
        </html>
        """

        # SAML response HTML
        saml_html = """
        <html>
            <body>
                <form action="http://service.provider/acs" method="post">
                    <input name="SAMLResponse" value="base64_saml_response" />
                    <input name="RelayState" value="relay_state_value" />
                </form>
            </body>
        </html>
        """

        # POST credentials -> SAML HTML response
        responses.add(
            responses.POST,
            "http://foo.bar/commonauth",
            body=saml_html,
        )
        # POST SAML -> redirect
        responses.add(
            responses.POST,
            "http://service.provider/acs",
            status=302,
            headers={"Location": "http://final.url"},
        )
        # GET final URL -> JSON
        responses.add(
            responses.GET,
            "http://final.url",
            body="{}",
            headers={"Content-Type": "application/json"},
        )

        result = auth_plugin._login_from_html(login_html, req_url="http://test.url")
        self.assertEqual(result.text, "{}")

    def test_plugins_auth_eoiam_extract_input_value_missing(self):
        """EOIAMAuth._extract_input_value should raise MisconfiguredError if input not found"""
        from lxml import html

        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {
            "username": "test_user",
            "password": "test_pass",
        }

        tree = html.fromstring("<html><body><form></form></body></html>")
        with self.assertRaisesRegex(
            MisconfiguredError, "sessionDataKey input not found"
        ):
            auth_plugin._extract_input_value(tree, "sessionDataKey")

    def test_plugins_auth_eoiam_extract_input_value_no_value(self):
        """EOIAMAuth._extract_input_value should raise MisconfiguredError if input has no value"""
        from lxml import html

        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {
            "username": "test_user",
            "password": "test_pass",
        }

        tree = html.fromstring(
            '<html><body><input name="sessionDataKey" /></body></html>'
        )
        with self.assertRaisesRegex(MisconfiguredError, "sessionDataKey has no value"):
            auth_plugin._extract_input_value(tree, "sessionDataKey")

    def test_plugins_auth_eoiam_extract_first_form_missing(self):
        """EOIAMAuth._extract_first_form should raise MisconfiguredError if no form found"""
        from lxml import html

        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {
            "username": "test_user",
            "password": "test_pass",
        }

        tree = html.fromstring("<html><body><div>No form here</div></body></html>")
        with self.assertRaisesRegex(MisconfiguredError, "Form not found"):
            auth_plugin._extract_first_form(tree)

    def test_plugins_auth_eoiam_resolve_action_missing(self):
        """EOIAMAuth._resolve_action should raise MisconfiguredError if action not found"""
        from lxml import html

        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {
            "username": "test_user",
            "password": "test_pass",
        }

        tree = html.fromstring("<html><body><form></form></body></html>")
        form = tree.xpath("//form")[0]
        with self.assertRaisesRegex(MisconfiguredError, "Form action not found"):
            auth_plugin._resolve_action(form, "http://foo.bar")

    def test_plugins_auth_eoiam_resolve_action_relative(self):
        """EOIAMAuth._resolve_action should resolve relative action URLs"""
        from lxml import html

        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {
            "username": "test_user",
            "password": "test_pass",
        }

        tree = html.fromstring(
            '<html><body><form action="/login"></form></body></html>'
        )
        form = tree.xpath("//form")[0]
        result = auth_plugin._resolve_action(form, "http://foo.bar")
        self.assertEqual(result, "http://foo.bar/login")

    @responses.activate
    def test_plugins_auth_eoiam_login_consent_required(self):
        """EOIAMAuth._login_from_html should raise AuthenticationError if consent is required"""
        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {
            "username": "test_user",
            "password": "test_pass",
        }

        login_html = """
        <html>
            <body>
                <form action="/commonauth" method="post">
                    <input name="sessionDataKey" value="test_session_key" />
                </form>
            </body>
        </html>
        """

        # POST redirects to consent page
        responses.add(
            responses.POST,
            "http://foo.bar/commonauth",
            status=302,
            headers={"Location": "http://foo.bar/consent.do?sp=TestService"},
        )
        responses.add(
            responses.GET,
            "http://foo.bar/consent.do?sp=TestService",
            body="",
        )

        with self.assertRaisesRegex(
            AuthenticationError, "Consent required for service"
        ):
            auth_plugin._login_from_html(login_html, req_url="http://test.url")

    @responses.activate
    def test_plugins_auth_eoiam_login_failed_wrong_credentials(self):
        """EOIAMAuth._login_from_html should raise MisconfiguredError on wrong credentials"""
        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {
            "username": "test_user",
            "password": "wrong_pass",
        }

        login_html = """
        <html>
            <body>
                <form action="/commonauth" method="post">
                    <input name="sessionDataKey" value="test_session_key" />
                </form>
            </body>
        </html>
        """

        # POST redirects to login page (wrong credentials)
        responses.add(
            responses.POST,
            "http://foo.bar/commonauth",
            status=302,
            headers={"Location": "http://foo.bar/login.do"},
        )
        responses.add(
            responses.GET,
            "http://foo.bar/login.do",
            body="",
        )

        with self.assertRaisesRegex(
            MisconfiguredError, "Login failed: please check your credentials"
        ):
            auth_plugin._login_from_html(login_html, req_url="http://test.url")

    @responses.activate
    def test_plugins_auth_eoiam_login_failed_eoiam_page(self):
        """EOIAMAuth._login_from_html should raise MisconfiguredError if still on EOIAM page"""
        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {
            "username": "test_user",
            "password": "test_pass",
        }

        login_html = """
        <html>
            <body>
                <form action="/commonauth" method="post">
                    <input name="sessionDataKey" value="test_session_key" />
                </form>
            </body>
        </html>
        """

        # POST stays on EOIAM page
        responses.add(
            responses.POST,
            "http://foo.bar/commonauth",
            body="Earth Observation Identity and Access Management System",
        )

        with self.assertRaisesRegex(MisconfiguredError, "Login failed"):
            auth_plugin._login_from_html(login_html, req_url="http://test.url")

    @responses.activate
    def test_plugins_auth_eoiam_saml_no_redirect(self):
        """EOIAMAuth._login_from_html should raise AuthenticationError if SAML response is not a redirect"""
        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {
            "username": "test_user",
            "password": "test_pass",
        }

        login_html = """
        <html>
            <body>
                <form action="/commonauth" method="post">
                    <input name="sessionDataKey" value="test_session_key" />
                </form>
            </body>
        </html>
        """

        saml_html = """
        <html>
            <body>
                <form action="http://service.provider/acs" method="post">
                    <input name="SAMLResponse" value="base64_saml_response" />
                </form>
            </body>
        </html>
        """

        # POST credentials -> SAML HTML
        responses.add(
            responses.POST,
            "http://foo.bar/commonauth",
            body=saml_html,
        )
        # POST SAML -> not a redirect (200)
        responses.add(
            responses.POST,
            "http://service.provider/acs",
            status=200,
        )

        with self.assertRaisesRegex(
            AuthenticationError, "Unexpected response after SAML login"
        ):
            auth_plugin._login_from_html(login_html, req_url="http://test.url")

    @responses.activate
    def test_plugins_auth_eoiam_final_redirect_missing(self):
        """EOIAMAuth._login_from_html should raise AuthenticationError if final redirect URL is missing"""
        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {
            "username": "test_user",
            "password": "test_pass",
        }

        login_html = """
        <html>
            <body>
                <form action="/commonauth" method="post">
                    <input name="sessionDataKey" value="test_session_key" />
                </form>
            </body>
        </html>
        """

        saml_html = """
        <html>
            <body>
                <form action="http://service.provider/acs" method="post">
                    <input name="SAMLResponse" value="base64_saml_response" />
                </form>
            </body>
        </html>
        """

        # POST credentials -> SAML HTML
        responses.add(
            responses.POST,
            "http://foo.bar/commonauth",
            body=saml_html,
        )
        # POST SAML -> redirect with empty Location
        responses.add(
            responses.POST,
            "http://service.provider/acs",
            status=302,
            headers={"Location": ""},
        )

        with self.assertRaisesRegex(
            AuthenticationError, "Final redirect URL not found"
        ):
            auth_plugin._login_from_html(login_html, req_url="http://test.url")

    @responses.activate
    def test_plugins_auth_eoiam_consent_required_after_redirect(self):
        """EOIAMAuth._login_from_html should raise AuthenticationError if consent required after redirect"""
        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {
            "username": "test_user",
            "password": "test_pass",
        }

        login_html = """
        <html>
            <body>
                <form action="/commonauth" method="post">
                    <input name="sessionDataKey" value="test_session_key" />
                </form>
            </body>
        </html>
        """

        saml_html = """
        <html>
            <body>
                <form action="http://service.provider/acs" method="post">
                    <input name="SAMLResponse" value="base64_saml_response" />
                </form>
            </body>
        </html>
        """

        # POST credentials -> SAML HTML
        responses.add(
            responses.POST,
            "http://foo.bar/commonauth",
            body=saml_html,
        )
        # POST SAML -> redirect
        responses.add(
            responses.POST,
            "http://service.provider/acs",
            status=302,
            headers={"Location": "http://final.url"},
        )
        # GET final URL -> consent page
        final_url = "http://final.url"
        responses.add(
            responses.GET,
            final_url,
            body="wants to access your account",
            headers={"Content-Type": "text/html"},
        )

        with self.assertRaisesRegex(
            AuthenticationError, f"Consent required: .* {final_url}"
        ):
            auth_plugin._login_from_html(login_html, req_url="http://test.url")

    @responses.activate
    def test_plugins_auth_eoiam_data_access_required(self):
        """EOIAMAuth._login_from_html should raise AuthenticationError if data access is required"""
        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {
            "username": "test_user",
            "password": "test_pass",
        }

        login_html = """
        <html>
            <body>
                <form action="/commonauth" method="post">
                    <input name="sessionDataKey" value="test_session_key" />
                </form>
            </body>
        </html>
        """

        saml_html = """
        <html>
            <body>
                <form action="http://service.provider/acs" method="post">
                    <input name="SAMLResponse" value="base64_saml_response" />
                </form>
            </body>
        </html>
        """

        # POST credentials -> SAML HTML
        responses.add(
            responses.POST,
            "http://foo.bar/commonauth",
            body=saml_html,
        )
        # POST SAML -> redirect
        responses.add(
            responses.POST,
            "http://service.provider/acs",
            status=302,
            headers={"Location": "http://final.url"},
        )
        # GET final URL -> data access required page
        final_url = "http://final.url"
        responses.add(
            responses.GET,
            final_url,
            body="not yet performed the necessary steps in order to access this data.",
            headers={"Content-Type": "text/html"},
        )

        with self.assertRaisesRegex(
            AuthenticationError, f"Data access request required: .* {final_url}"
        ):
            auth_plugin._login_from_html(login_html, req_url="http://test.url")

    def test_eoiam_session_auth_call_triggers_login_and_prepares_cookies(self):
        """_EOIAMSessionAuth.__call__ should trigger login when landing on EOIAM page"""
        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {
            "username": "test_user",
            "password": "test_pass",
        }

        # prepare a requests PreparedRequest
        req = Request("GET", "http://service.test/resource").prepare()

        # initial session.get returns EOIAM page
        initial_resp = requests.Response()
        initial_resp._content = (
            b"Earth Observation Identity and Access Management System"
        )
        initial_resp.url = "http://login"

        # login result is a normal response
        login_result = requests.Response()
        login_result._content = b"{}"

        old_session = auth_plugin.session

        with mock.patch.object(auth_plugin.session, "get", return_value=initial_resp):
            with mock.patch.object(
                auth_plugin, "_login_from_html", return_value=login_result
            ) as mock_login:
                # ensure there is a cookie jar so prepare_cookies can operate
                jar = requests.cookies.RequestsCookieJar()
                jar.set("sid", "1234", domain="service.test", path="/")
                auth_plugin.session.cookies = jar

                auth = EOIAMSessionAuth(auth_plugin)
                returned = auth(req)

                mock_login.assert_called_once_with(initial_resp.text, req.url)
                self.assertIs(returned, req)

        self.assertIsInstance(auth_plugin.session, requests.Session)
        self.assertIsNot(auth_plugin.session, old_session)

    def test_eoiam_session_auth_call_resets_session_on_login_error(self):
        """_EOIAMSessionAuth.__call__ should reset session even when login fails"""
        auth_plugin = self.get_auth_plugin("foo_provider")
        auth_plugin.config.credentials = {
            "username": "test_user",
            "password": "test_pass",
        }

        req = Request("GET", "http://service.test/resource").prepare()
        initial_resp = requests.Response()
        initial_resp._content = (
            b"Earth Observation Identity and Access Management System"
        )
        initial_resp.url = "http://login"

        old_session = auth_plugin.session
        with mock.patch.object(auth_plugin.session, "get", return_value=initial_resp):
            with mock.patch.object(
                auth_plugin,
                "_login_from_html",
                side_effect=AuthenticationError("boom"),
            ):
                auth = EOIAMSessionAuth(auth_plugin)
                with self.assertRaises(AuthenticationError):
                    auth(req)

        self.assertIsInstance(auth_plugin.session, requests.Session)
        self.assertIsNot(auth_plugin.session, old_session)
