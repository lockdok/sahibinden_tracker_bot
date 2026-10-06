"""Ежедневная последовательная проверка явно добавленных объявлений."""
import asyncio, logging, random
from telegram import Bot
from . import db
from .listing_fetcher import fetch_listing
from .notifier import change_message, send
logger=logging.getLogger(__name__)
async def run_daily_check(config: dict) -> dict[str,int]:
    await db.init_db(); bot=Bot(config["telegram"]["bot_token"]); chat_id=str(config["telegram"]["chat_id"]); watch=config["watchlist"]
    stats={"checked":0,"changed":0,"retired":0,"errors":0}
    for row in await db.active_listings():
        if stats["checked"]: await asyncio.sleep(random.uniform(*watch["delay_between_ads_s"]))
        result=await fetch_listing(row["url"],watch.get("browser_fallback",True)); stats["checked"]+=1
        if result.status=="ok" and result.listing:
            change=await db.record_success(result.listing)
            if change: await send(bot,chat_id,change_message(change)); stats["changed"]+=1
        elif result.status=="unavailable":
            retired=await db.record_unavailable(row["id"],watch["unavailable_after_checks"])
            if retired:
                await send(bot,chat_id,f"Listing retired after {watch['unavailable_after_checks']} unavailable checks:\n{retired['title']}\n{retired['url']}"); stats["retired"]+=1
        else: logger.warning("Could not check %s: %s",row["id"],result.error); stats["errors"]+=1
    await bot.close(); return stats
