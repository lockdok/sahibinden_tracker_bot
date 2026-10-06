"""Safe Telegram message formatting."""
from html import escape
from telegram import Bot
def money(value: int, currency: str) -> str: return f"{value:,}".replace(",", ".") + f" {currency}"
def listing_summary(title, summary, price, currency, url):
    return f"<b>{escape(title)}</b>\n{money(price,currency)}" + (f"\n{escape(summary[:280])}" if summary else "") + f"\n<a href=\"{escape(url,quote=True)}\">View listing</a>"
def change_message(c):
    same=c["old_currency"]==c["new_currency"]; percent=f" ({(c['new_price']-c['old_price'])/c['old_price']*100:+.1f}%)" if same and c["old_price"] else ""
    label="📉 Price decrease" if same and c["new_price"]<c["old_price"] else "📈 Price change"
    return f"{label}\n<b>{escape(c['title'])}</b>\n{money(c['old_price'],c['old_currency'])} → {money(c['new_price'],c['new_currency'])}{percent}\n<a href=\"{escape(c['url'],quote=True)}\">View listing</a>"
async def send(bot: Bot, chat_id: str, text: str): await bot.send_message(chat_id=chat_id,text=text,parse_mode="HTML",disable_web_page_preview=True)
