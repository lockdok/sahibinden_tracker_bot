"""Ежедневная последовательная проверка явно добавленных объявлений."""
import asyncio, logging, random
from html import escape
import json
from telegram import Bot
from . import db
from .listing_fetcher import fetch_listing
from .notifier import change_message, send
logger=logging.getLogger(__name__)

async def _send_pending_notifications(bot: Bot, chat_id: str) -> int:
    errors = 0
    for notification in await db.pending_notifications():
        payload = json.loads(notification["payload"])
        if notification["kind"] == "price_change":
            message = change_message(payload)
        elif notification["kind"] == "retired":
            message = (
                f"Listing retired after {payload['threshold']} unavailable checks:\n"
                f"{escape(payload['title'])}\n{escape(payload['url'])}"
            )
        else:
            raise ValueError(f"Unknown notification kind: {notification['kind']}")
        try:
            await send(bot, chat_id, message)
        except Exception:
            logger.exception("Could not send notification %s", notification["id"])
            errors += 1
        else:
            await db.mark_notification_sent(notification["id"])
    return errors

async def run_daily_check(config: dict) -> dict[str,int]:
    await db.init_db(); bot=Bot(config["telegram"]["bot_token"]); chat_id=str(config["telegram"]["chat_id"]); watch=config["watchlist"]
    stats={"checked":0,"changed":0,"retired":0,"errors":0}
    await bot.initialize()
    try:
        for row in await db.active_listings():
            if stats["checked"]: await asyncio.sleep(random.uniform(*watch["delay_between_ads_s"]))
            result=await fetch_listing(row["url"],watch.get("browser_fallback",True)); stats["checked"]+=1
            if result.status=="ok" and result.listing:
                change=await db.record_success(result.listing)
                if change: stats["changed"]+=1
            elif result.status=="unavailable":
                retired=await db.record_unavailable(row["id"],watch["unavailable_after_checks"])
                if retired: stats["retired"]+=1
            else: logger.warning("Could not check %s: %s",row["id"],result.error); stats["errors"]+=1
        stats["errors"] += await _send_pending_notifications(bot, chat_id)
        return stats
    finally:
        await bot.shutdown()
