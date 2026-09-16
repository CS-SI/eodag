import unittest
from types import SimpleNamespace
from unittest import mock

from tests.context import (
    GENERIC_COLLECTION,
    Authentication,
    Download,
    FilterDate,
    MisconfiguredError,
    PluginManager,
    ProvidersDict,
    UnsupportedProvider,
)


class TestPluginManager(unittest.TestCase):
    def setUp(self):
        self.providers = ProvidersDict.from_configs(
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
        self.manager = PluginManager(self.providers)

    def test_rebuild_replaces_provider_mapping_and_cache(self):
        """Rebuilding replaces the provider map and clears cached plugins."""
        self.manager._built_plugins_cache[("low", "Search", "")] = mock.sentinel.plugin

        replacement = ProvidersDict.from_configs(
            {
                "replacement": {
                    "products": {"BAR": {}},
                    "search": {
                        "type": "QueryStringSearch",
                        "api_endpoint": "https://replacement.example",
                        "metadata_mapping": {"title": "$.title"},
                    },
                }
            }
        )
        self.manager.rebuild(replacement)

        self.assertIs(self.manager.providers, replacement)
        self.assertEqual(list(self.manager.collection_to_provider_config_map), ["BAR"])
        self.assertEqual(self.manager._built_plugins_cache, {})

    def test_build_collection_map_sorts_by_priority(self):
        """Collection providers are ordered by descending priority."""
        configs = self.manager.collection_to_provider_config_map["FOO"]

        self.assertEqual([config.name for config in configs], ["high", "low"])

    def test_get_skipped_plugin_messages(self):
        """Skipped plugin messages are returned for configured plugin types."""
        provider_config = self.providers["low"].config
        provider_config.search.type = "MissingSearch"
        self.manager.skipped_plugins = {"MissingSearch": "missing dependency"}

        self.assertEqual(
            self.manager.get_skipped_plugin_messages(provider_config),
            ["missing dependency"],
        )

    def test_check_provider_available(self):
        """Provider availability checks accept known and reject unknown providers."""
        self.manager.check_provider_available("low")

        with self.assertRaises(UnsupportedProvider):
            self.manager.check_provider_available("unknown")

    def test_get_search_plugins_uses_collection_and_priority(self):
        """Search plugins use collection settings and priority ordering."""
        plugins = list(self.manager.get_search_plugins(collection="FOO"))

        self.assertEqual([plugin.provider for plugin in plugins], ["high", "low"])

    def test_get_search_plugins_uses_generic_collection_fallback(self):
        """Unsupported collections fall back to generic collection settings."""
        generic_provider = ProvidersDict.from_configs(
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
        manager = PluginManager(generic_provider)

        plugins = list(manager.get_search_plugins(collection="missing"))

        self.assertEqual([plugin.provider for plugin in plugins], ["generic"])

    def test_get_search_plugins_rejects_provider_without_search_or_api(self):
        """Search plugin construction fails for providers without a search plugin."""
        providers = ProvidersDict.from_configs(
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
        manager = PluginManager(providers)
        manager.providers["broken"].config.search = None

        with self.assertRaisesRegex(MisconfiguredError, "No search plugin configured"):
            list(manager.get_search_plugins(collection="FOO"))

    @mock.patch.object(PluginManager, "_build_plugin")
    def test_get_download_plugin_builds_download_plugin(self, build_plugin):
        """Download selection builds the configured download plugin type."""
        expected = mock.sentinel.download
        build_plugin.return_value = expected
        product = SimpleNamespace(provider="download")

        self.assertIs(self.manager.get_download_plugin(product), expected)
        build_plugin.assert_called_once()
        self.assertIs(build_plugin.call_args.args[2], Download)

    def test_get_download_plugin_rejects_unknown_provider(self):
        """Download selection rejects products from unknown providers."""
        with self.assertRaisesRegex(UnsupportedProvider, "Provider unknown not found"):
            self.manager.get_download_plugin(SimpleNamespace(provider="unknown"))

    @mock.patch.object(PluginManager, "_build_plugin")
    def test_get_auth_plugins_matches_url(self, build_plugin):
        """Authentication plugins match a configured URL pattern."""
        auth_type = "TokenAuth"
        matching_pattern = "provider-a"
        matching_url = "provider-a-endpoint"
        auth_config = SimpleNamespace(type=auth_type, matching_url=matching_pattern)
        self.providers["low"].config.auth = auth_config
        build_plugin.return_value = mock.sentinel.auth

        plugins = list(self.manager.get_auth_plugins("low", matching_url=matching_url))

        self.assertEqual(plugins, [mock.sentinel.auth])
        build_plugin.assert_called_once_with("low", auth_config, Authentication)

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

    def test_set_priority_updates_configs_and_cached_plugins(self):
        """Setting priority updates provider configuration and cached plugins."""
        plugin = next(self.manager.get_search_plugins(provider="low"))
        self.assertEqual(plugin.config.priority, 1)

        self.manager.set_priority("low", 10)

        self.assertEqual(plugin.priority, 10)
        self.assertEqual(
            self.manager.collection_to_provider_config_map["FOO"][1].priority, 2
        )
