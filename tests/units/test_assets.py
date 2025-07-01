from unittest import mock

from eodag.api.product._assets import Asset
from tests import EODagTestCase


class TestAssets(EODagTestCase):
    def test_asset_register_downloader(self):
        """eoproduct.register_donwloader must set download and auth plugins"""
        product = self._dummy_product()
        asset = Asset(
            product=product,
            key="a1",
            **{"title": "a1", "href": "https://assets.test.com/a1"}
        )

        self.assertIsNone(asset.downloader)
        self.assertIsNone(asset.downloader_auth)

        downloader = mock.MagicMock()
        downloader_auth = mock.MagicMock()

        asset.register_downloader(downloader, downloader_auth)

        self.assertEqual(asset.downloader, downloader)
        self.assertEqual(asset.downloader_auth, downloader_auth)
