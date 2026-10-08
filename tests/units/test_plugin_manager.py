import unittest
from types import SimpleNamespace
from unittest import mock

from tests.context import (
    GENERIC_COLLECTION,
    Authentication,
    FilterDate,
    MisconfiguredError,
    PluginManager,
    ProviderConfig,
    UnsupportedProvider,
    build_provider_configs,
    make_plugins_manager,
)


class TestPluginManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.providers = build_provider_configs(
            {
                "low": {
                    "products": {"FOO": {"metadata_mapping": {"title": "$.title"}}},
                    "search": {
                        "type": "QueryStringSearch",
                        "api_endpoint": "https://low.example",
                        "metadata_mapping": {"title": "$.title"},
                    },
                    "priority": 1,
                },
                "high": {
                    "products": {"FOO": {"metadata_mapping": {"title": "$.title"}}},
                    "search": {
                        "type": "QueryStringSearch",
                        "api_endpoint": "https://high.example",
                        "metadata_mapping": {"title": "$.title"},
                    },
                    "priority": 2,
                },
                "download": {
                    "products": {"BAR": {}},
                    "download": {"type": "HTTPDownload"},
                },
            }
        )
        cls.manager = make_plugins_manager(cls.providers)

    def test_get_skipped_plugin_messages(self):
        """Skipped plugin messages are returned for configured plugin types."""
        provider_config = self.providers["low"]
        provider_config.search.type = "MissingSearch"
        self.manager.skipped_plugins = {"MissingSearch": "missing dependency"}

        self.assertListEqual(
            self.manager.get_skipped_plugin_messages(provider_config),
            ["missing dependency"],
        )

    def test_check_provider_available(self):
        """Provider availability checks accept known and reject unknown providers."""
        # known provider name: no error
        self.manager.check_provider_available("low")

        # unknown provider: UnsupportedProvider
        with self.assertRaisesRegex(
            UnsupportedProvider, "unknown: provider is not recognised by eodag"
        ):
            self.manager.check_provider_available("unknown")

        # disable the provider "low" until the test ends
        provider = "low"
        cfg = ProviderConfig.from_mapping(self.manager._db.get_fb_config(provider))
        cfg.enabled = False
        self.manager._db.upsert_fb_configs([cfg])
        self.addCleanup(self.manager._db.restore_fbs)

        with self.assertRaisesRegex(
            UnsupportedProvider, "low: provider has been disabled and is not available"
        ):
            self.manager.check_provider_available("low")

        # disabled provider: MisconfiguredError takes precedence over UnsupportedProvider
        self.manager.disabled_providers_reasons["low"] = {
            "reason": "provider needing auth for search has been disabled because no credentials could be found",
            "reason_type": "missing_credentials",
        }
        with self.assertRaisesRegex(
            MisconfiguredError,
            "low: provider needing auth for search has been disabled "
            "because no credentials could be found",
        ):
            self.manager.check_provider_available("low")

        self.manager.disabled_providers_reasons["low"] = {
            "reason": "SkippedSearch plugin skipped",
            "reason_type": "skipped_plugin",
        }
        with self.assertRaisesRegex(
            UnsupportedProvider,
            "low: provider is not available because SkippedSearch plugin skipped",
        ):
            self.manager.check_provider_available("low")

        # Clean up the disabled provider reason for "low" to avoid side effects in other tests.
        del self.manager.disabled_providers_reasons["low"]

    def test_get_search_plugins_uses_collection_and_priority(self):
        """Search plugins use collection settings and priority ordering."""
        plugins = list(self.manager.get_search_plugins(collection="FOO"))

        self.assertEqual([plugin.provider for plugin in plugins], ["high", "low"])

    def test_get_search_plugins_uses_generic_collection_fallback(self):
        """Unsupported collections fall back to generic collection settings."""
        generic_provider = build_provider_configs(
            {
                "generic": {
                    "products": {
                        GENERIC_COLLECTION: {"metadata_mapping": {"title": "$.title"}}
                    },
                    "search": {
                        "type": "QueryStringSearch",
                        "api_endpoint": "https://generic.example",
                        "metadata_mapping": {"title": "$.title"},
                    },
                }
            }
        )
        manager = make_plugins_manager(generic_provider)

        plugins = list(manager.get_search_plugins(collection="missing"))

        self.assertListEqual([plugin.provider for plugin in plugins], ["generic"])

    def test_get_search_plugins_rejects_provider_without_search_or_api(self):
        """Search plugin construction fails for providers without a search plugin."""
        providers = build_provider_configs(
            {
                "broken": {
                    "products": {GENERIC_COLLECTION: {}},
                    "search": {
                        "type": "QueryStringSearch",
                        "api_endpoint": "https://broken.example",
                        "metadata_mapping": {"title": "$.title"},
                    },
                }
            }
        )
        delattr(providers["broken"], "search")
        manager = make_plugins_manager(providers)

        with self.assertRaisesRegex(
            MisconfiguredError,
            "No search or api plugin configured for provider broken.",
        ):
            list(manager.get_search_plugins(collection=GENERIC_COLLECTION))

    def test_get_download_plugin_ok(self):
        """Download selection succeeds for known correctly configured providers having the product collection."""
        product = SimpleNamespace(provider="download", collection="BAR")
        plugin = self.manager.get_download_plugin(product)
        self.assertIsNotNone(plugin)

    def test_get_download_plugin_ko(self):
        """Download selection rejects products from providers that do not pass the check or misconfigured providers."""
        # with a provider that does not pass the check, an error is expected
        unknown_name = "unknown"
        with self.assertRaisesRegex(
            UnsupportedProvider, f"{unknown_name}: provider is not recognised by eodag"
        ):
            self.manager.get_download_plugin(SimpleNamespace(provider=unknown_name))

        # with a provider that does not have a download plugin configured, an error is expected
        with self.assertRaisesRegex(
            MisconfiguredError, "No download plugin configured for provider low."
        ):
            self.manager.get_download_plugin(
                SimpleNamespace(provider="low", collection="FOO")
            )

    @mock.patch.object(PluginManager, "_get_or_create_auth_plugin")
    def test_get_auth_plugins_matches_url(self, get_or_create_auth_plugin):
        """Authentication plugins match a configured URL pattern."""
        auth_type = "TokenAuth"
        matching_pattern = "provider-a"
        matching_url = "provider-a-endpoint"
        auth_config = SimpleNamespace(type=auth_type, matching_url=matching_pattern)
        cfg = ProviderConfig.from_mapping(self.manager._db.get_fb_config("low"))
        cfg.auth = auth_config
        self.manager._db.upsert_fb_configs([cfg])

        get_or_create_auth_plugin.return_value = mock.sentinel.auth

        plugins = list(self.manager.get_auth_plugins("low", matching_url=matching_url))

        self.assertListEqual(plugins, [mock.sentinel.auth])
        get_or_create_auth_plugin.assert_called_once_with(
            "low", auth_config.__dict__, "auth", 1
        )

    @mock.patch.object(PluginManager, "get_auth_plugins")
    def test_get_auth_plugin_uses_associated_plugin(self, get_auth_plugins):
        """Associated plugin settings select the authentication plugin."""
        associated_plugin = SimpleNamespace(
            provider="low", config=SimpleNamespace(api_endpoint="https://low.example")
        )
        get_auth_plugins.return_value = iter([mock.sentinel.auth])

        plugin = self.manager.get_auth_plugin(associated_plugin)

        self.assertIs(plugin, mock.sentinel.auth)
        get_auth_plugins.assert_called_once_with(
            "low",
            matching_url="https://low.example",
            matching_conf=associated_plugin.config,
        )

    def test_get_crunch_plugin(self):
        """Crunch plugin construction returns the requested plugin class."""
        plugin = PluginManager.get_crunch_plugin("FilterDate", start="2024-01-01")

        self.assertIsInstance(plugin, FilterDate)
        self.assertEqual(plugin.config.start, "2024-01-01")

    @mock.patch.object(PluginManager, "get_auth_plugins")
    def test_get_auth_returns_first_successful_authentication(self, get_auth_plugins):
        """Authentication continues until the first plugin succeeds."""
        first = mock.Mock(spec=Authentication)
        first.authenticate.side_effect = MisconfiguredError("not ready")
        second = mock.Mock(spec=Authentication)
        second.authenticate.return_value = mock.sentinel.authenticated
        get_auth_plugins.return_value = iter([first, second])

        result = self.manager.get_auth("low")

        self.assertIs(result, mock.sentinel.authenticated)
        first.authenticate.assert_called_once_with()
        second.authenticate.assert_called_once_with()

    @mock.patch.object(PluginManager, "get_auth_plugins", return_value=iter([]))
    def test_get_auth_returns_none_when_no_plugin_matches(self, get_auth_plugins):
        """Authentication returns None when no plugin matches."""
        self.assertIsNone(self.manager.get_auth("low"))
        get_auth_plugins.assert_called_once_with("low", None, None)
