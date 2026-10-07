import unittest
from unittest.mock import AsyncMock, patch

from src.checker import run_daily_check


class CheckerTests(unittest.IsolatedAsyncioTestCase):
    async def test_notification_failure_keeps_pending_and_shuts_down_bot(self):
        notification = {
            "id": 1,
            "kind": "price_change",
            "payload": '{"old_price":100,"old_currency":"TRY","new_price":90,"new_currency":"TRY","title":"Home","url":"https://example.com"}',
        }
        config = {
            "telegram": {"bot_token": "token", "chat_id": "123"},
            "watchlist": {"unavailable_after_checks": 7, "delay_between_ads_s": [0, 0]},
        }
        with (
            patch("src.checker.Bot") as bot_factory,
            patch("src.checker.db.init_db", new_callable=AsyncMock),
            patch("src.checker.db.active_listings", new_callable=AsyncMock, return_value=[]),
            patch("src.checker.db.pending_notifications", new_callable=AsyncMock, return_value=[notification]),
            patch("src.checker.db.mark_notification_sent", new_callable=AsyncMock) as mark_sent,
            patch("src.checker.send", new_callable=AsyncMock, side_effect=RuntimeError("Telegram unavailable")),
        ):
            bot = bot_factory.return_value
            bot.initialize = AsyncMock()
            bot.shutdown = AsyncMock()

            stats = await run_daily_check(config)

        bot.initialize.assert_awaited_once()
        bot.shutdown.assert_awaited_once()
        mark_sent.assert_not_awaited()
        self.assertEqual(stats["errors"], 1)
