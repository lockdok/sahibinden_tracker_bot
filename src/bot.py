"""Приватный интерфейс Telegram на основе long polling."""
import re
from telegram import Update
from telegram.ext import Application,CommandHandler,ContextTypes,MessageHandler,filters
from . import db
from .listing_fetcher import canonicalize_url,fetch_listing,listing_id_from_url
from .notifier import listing_summary
URL_RE=re.compile(r"https?://[^\s]+",re.I)
def is_authorized_chat(chat_id: int | str | None, allowed_chat: str) -> bool:
    return chat_id is not None and str(chat_id) == str(allowed_chat)
def build_application(config: dict) -> Application:
    allowed=str(config["telegram"]["chat_id"]); fallback=config["watchlist"].get("browser_fallback",True)
    async def auth(update): return is_authorized_chat(update.effective_chat.id if update.effective_chat else None, allowed)
    async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
        if await auth(update): await update.effective_message.reply_text("Send a Sahibinden listing URL to track it.\n/list — active listings\n/remove <ID or URL> — stop tracking")
    async def list_items(update:Update,context:ContextTypes.DEFAULT_TYPE):
        if not await auth(update): return
        rows=await db.active_listings()
        if not rows: await update.effective_message.reply_text("No active listings."); return
        text="\n\n".join(f"{r['id']} — {r['title']}\n{r['current_price']:,} {r['current_currency']}\n{r['url']}" for r in rows)
        for offset in range(0,len(text),3900): await update.effective_message.reply_text(text[offset:offset+3900],disable_web_page_preview=True)
    async def remove(update:Update,context:ContextTypes.DEFAULT_TYPE):
        if not await auth(update): return
        if not context.args: await update.effective_message.reply_text("Usage: /remove <listing ID or URL>"); return
        ident=" ".join(context.args)
        try:
            if ident.startswith("http"): ident=canonicalize_url(ident)
        except ValueError as exc: await update.effective_message.reply_text(str(exc)); return
        await update.effective_message.reply_text("Tracking stopped." if await db.remove_listing(ident) else "Active listing not found.")
    async def add_url(update:Update,context:ContextTypes.DEFAULT_TYPE):
        if not await auth(update): return
        match=URL_RE.search(update.effective_message.text or "")
        if not match: return
        try: url=canonicalize_url(match.group(0).rstrip(".,!"))
        except ValueError as exc: await update.effective_message.reply_text(str(exc)); return
        existing=await db.get_listing(listing_id_from_url(url))
        if existing and existing["active"]:
            await update.effective_message.reply_text("Already tracked:\n"+listing_summary(existing["title"],existing["summary"],existing["current_price"],existing["current_currency"],existing["url"]),parse_mode="HTML"); return
        await update.effective_message.reply_text("Checking listing…")
        result=await fetch_listing(url,fallback)
        if result.status!="ok" or not result.listing: await update.effective_message.reply_text("I could not read that listing right now. Please try again later."); return
        if await db.add_listing(result.listing): await update.effective_message.reply_text("Tracking started:\n"+listing_summary(result.listing.title,result.listing.summary,result.listing.price,result.listing.currency,result.listing.url),parse_mode="HTML",disable_web_page_preview=True)
        else: await update.effective_message.reply_text("That listing is already known but inactive.")
    app=Application.builder().token(config["telegram"]["bot_token"]).build()
    app.add_handler(CommandHandler("start",start)); app.add_handler(CommandHandler("list",list_items)); app.add_handler(CommandHandler("remove",remove)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,add_url)); return app
