import tempfile
import unittest
from pathlib import Path
from src import db
from src.listing_fetcher import ListingDetails

class DbLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.old = db.DB_PATH; db.DB_PATH = Path(self.temp.name) / "test.db"; await db.init_db()
    async def asyncTearDown(self): db.DB_PATH = self.old; self.temp.cleanup()
    async def test_change_and_retirement_lifecycle(self):
        first = ListingDetails("1", "https://www.sahibinden.com/ilan/x-1", "A", "S", 100, "TRY")
        self.assertTrue(await db.add_listing(first)); self.assertFalse(await db.add_listing(first))
        self.assertIsNone(await db.record_success(first))
        changed = await db.record_success(ListingDetails("1", first.url, "A", "S", 80, "TRY"))
        self.assertEqual(changed["old_price"], 100)
        self.assertIsNone(await db.record_unavailable("1", 2))
        self.assertIsNotNone(await db.record_unavailable("1", 2))
        self.assertEqual(await db.active_listings(), [])
