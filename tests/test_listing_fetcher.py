import asyncio
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from src.listing_fetcher import _browser_executable_path, _fetch_browser, canonicalize_url, listing_id_from_url, parse_listing_page, parse_price
from src.notifier import change_message
from src.bot import is_authorized_chat

URL = "https://www.sahibinden.com/ilan/emlak-konut-satilik-nice-home-123456789/detay?foo=bar"

class ListingFetcherTests(unittest.TestCase):
    def test_canonical_url_and_id(self):
        url = canonicalize_url(URL)
        self.assertEqual(url, "https://www.sahibinden.com/ilan/emlak-konut-satilik-nice-home-123456789/detay")
        self.assertEqual(listing_id_from_url(url), "123456789")
    def test_accepts_shared_listing_urls(self):
        urls = (
            "https://www.sahibinden.com/listing/emlak-konut-satilik-deniz-ve-millet-bahcesi-manzarali-metroya-yakin-bos-iskanli-2-plus1-1341411325/detail?utm_campaign=sahibinden_paylas&utm_medium=ilan_detay&utm_source=paylas&utm_content=174536269",
            "https://www.sahibinden.com/listing/emlak-konut-satilik-pendik-marmara-hastanesi-ve-metro-ya-yakin-satilik-esyali-1-plus1-1343829260/detail",
        )
        expected_ids = ("1341411325", "1343829260")
        for url, expected_id in zip(urls, expected_ids):
            canonical_url = canonicalize_url(url)
            self.assertNotIn("?", canonical_url)
            self.assertEqual(listing_id_from_url(canonical_url), expected_id)
    def test_rejects_non_listing_url(self):
        with self.assertRaises(ValueError): canonicalize_url("https://example.com/ilan/x")
    def test_snap_chromium_path_is_selected_when_available(self):
        def available(path):
            return str(path) == "/snap/bin/chromium"

        with patch("src.listing_fetcher.os.path.isfile", side_effect=available):
            self.assertEqual(_browser_executable_path(), "/snap/bin/chromium")
        with patch("src.listing_fetcher.os.path.isfile", return_value=False):
            self.assertIsNone(_browser_executable_path())
    def test_native_chrome_is_preferred_over_snap_chromium(self):
        def available(path):
            return str(path) in {"/usr/bin/google-chrome", "/snap/bin/chromium"}

        with patch("src.listing_fetcher.os.path.isfile", side_effect=available):
            self.assertEqual(_browser_executable_path(), "/usr/bin/google-chrome")
    def test_parses_json_ld_listing(self):
        html = '''<script type="application/ld+json">{"name":"2+1 <Home>","description":"Kadikoy","offers":{"price":"1250000","priceCurrency":"TRY"}}</script>'''
        item = parse_listing_page(html, URL)
        self.assertEqual((item.price, item.currency, item.title), (1250000, "TRY", "2+1 <Home>"))
    def test_parses_decimal_and_plain_id_urls(self):
        self.assertEqual(parse_price("€ 45.000,00"), (45000, "EUR"))
        self.assertEqual(parse_price("₺ 1.250.000"), (1250000, "TRY"))
        self.assertEqual(listing_id_from_url("https://www.sahibinden.com/ilan/123456789"), "123456789")
    def test_price_and_html_notification(self):
        self.assertEqual(parse_price("$ 45,000"), (45000, "USD"))
        message = change_message({"old_price":100,"old_currency":"TRY","new_price":90,"new_currency":"TRY","title":"<unsafe>","url":"https://x.example/?a=1&b=2","summary":""})
        self.assertIn("&lt;unsafe&gt;", message)
        self.assertIn("-10.0%", message)
    def test_private_chat_guard(self):
        self.assertTrue(is_authorized_chat(123, "123"))
        self.assertFalse(is_authorized_chat(456, "123"))

class BrowserFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_snap_browser_uses_no_sandbox(self):
        page = MagicMock()
        page.get_content = AsyncMock(return_value="<html></html>")
        browser = MagicMock()
        browser.get = AsyncMock(return_value=page)
        nodriver = SimpleNamespace(start=AsyncMock(return_value=browser))
        with (
            patch.dict(sys.modules, {"nodriver": nodriver}),
            patch("src.listing_fetcher._browser_executable_path", return_value="/snap/bin/chromium"),
            patch("src.listing_fetcher.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await _fetch_browser("https://www.sahibinden.com/listing/example-123/detail")

        self.assertEqual(result, (200, "<html></html>"))
        nodriver.start.assert_awaited_once_with(
            headless=True,
            browser_executable_path="/snap/bin/chromium",
            browser_args=["--lang=tr-TR"],
            sandbox=False,
        )
        browser.stop.assert_called_once()
