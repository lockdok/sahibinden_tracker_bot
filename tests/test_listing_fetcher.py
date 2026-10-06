import unittest
from src.listing_fetcher import canonicalize_url, listing_id_from_url, parse_listing_page, parse_price
from src.notifier import change_message
from src.bot import is_authorized_chat

URL = "https://www.sahibinden.com/ilan/emlak-konut-satilik-nice-home-123456789/detay?foo=bar"

class ListingFetcherTests(unittest.TestCase):
    def test_canonical_url_and_id(self):
        url = canonicalize_url(URL)
        self.assertEqual(url, "https://www.sahibinden.com/ilan/emlak-konut-satilik-nice-home-123456789/detay")
        self.assertEqual(listing_id_from_url(url), "123456789")
    def test_rejects_non_listing_url(self):
        with self.assertRaises(ValueError): canonicalize_url("https://example.com/ilan/x")
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
