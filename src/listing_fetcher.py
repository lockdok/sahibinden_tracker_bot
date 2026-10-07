"""Получение и разбор страниц объявлений Sahibinden, присланных пользователем."""
import asyncio, hashlib, json, logging, random, re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Literal
from urllib.parse import urlparse, urlunparse
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
USER_AGENTS = ["Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"]

@dataclass(frozen=True)
class ListingDetails:
    listing_id: str; url: str; title: str; summary: str; price: int; currency: str

@dataclass(frozen=True)
class FetchResult:
    status: Literal["ok", "unavailable", "error"]
    listing: ListingDetails | None = None
    error: str | None = None

def canonicalize_url(raw_url: str) -> str:
    parsed = urlparse(raw_url.strip())
    is_listing_path = re.search(r"/(?:ilan|listing)/", parsed.path, re.IGNORECASE)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower().removeprefix("www.") != "sahibinden.com" or not is_listing_path:
        raise ValueError("Please send a valid sahibinden.com listing URL.")
    return urlunparse(("https", "www.sahibinden.com", re.sub(r"/+", "/", parsed.path).rstrip("/"), "", "", ""))

def listing_id_from_url(url: str) -> str:
    path = urlparse(url).path
    for pattern in (
        r"-(\d+)(?:/|$)",
        r"/(\d+)(?:/)?(?:\?.*)?$",
        r"(?<!\d)(\d{5,})(?!\d)",
    ):
        match = re.search(pattern, path)
        if match:
            return match.group(1)
    return "url-" + hashlib.sha256(url.encode()).hexdigest()[:20]

def parse_price(raw: str) -> tuple[int, str]:
    text = str(raw).strip()
    currency = "USD" if "$" in text or "USD" in text.upper() else "EUR" if "€" in text or "EUR" in text.upper() else "TRY"
    number_match = re.search(r"[-+]?\d[\d\s.,]*\d", text)
    if not number_match:
        raise ValueError("No numeric price found")
    digits = number_match.group(0).replace(" ", "")
    if not digits or not re.search(r"\d", digits):
        raise ValueError("No numeric price found")

    if "," in digits and "." in digits:
        decimal_sep = "," if digits.rfind(",") > digits.rfind(".") else "."
        thousands_sep = "." if decimal_sep == "," else ","
        digits = digits.replace(thousands_sep, "").replace(decimal_sep, ".")
    elif "," in digits:
        parts = digits.split(",")
        if len(parts) > 1 and len(parts[-1]) <= 2:
            digits = ".".join(parts)
        else:
            digits = "".join(parts)
    elif "." in digits:
        parts = digits.split(".")
        if len(parts) > 1 and len(parts[-1]) <= 2:
            digits = ".".join(parts)
        else:
            digits = "".join(parts)

    try:
        value = Decimal(digits)
    except InvalidOperation as exc:
        raise ValueError("No numeric price found") from exc
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)), currency

def parse_listing_page(html: str, url: str) -> ListingDetails:
    url = canonicalize_url(url); soup = BeautifulSoup(html, "html.parser")
    title = raw_price = summary = None
    for script in soup.select('script[type="application/ld+json"]'):
        try: items = json.loads(script.get_text(strip=True))
        except json.JSONDecodeError: continue
        for item in items if isinstance(items, list) else [items]:
            if not isinstance(item, dict): continue
            offers = item.get("offers", {}); offers = offers[0] if isinstance(offers, list) and offers else offers
            if isinstance(offers, dict) and offers.get("price") is not None:
                title, raw_price, summary = item.get("name"), f"{offers['price']} {offers.get('priceCurrency', 'TRY')}", item.get("description"); break
        if raw_price: break
    title = title or (soup.select_one('meta[property="og:title"]') or {}).get("content")
    summary = summary or (soup.select_one('meta[name="description"]') or {}).get("content") or ""
    node = soup.select_one(".classifiedInfo h3, .classifiedInfo .price, [class*='classifiedInfo'] [class*='price']")
    raw_price = raw_price or (node.get_text(" ", strip=True) if node else None)
    if not title or not raw_price: raise ValueError("Listing title or price was not found")
    price, currency = parse_price(raw_price)
    return ListingDetails(listing_id_from_url(url), url, title.strip(), summary.strip()[:500], price, currency)

async def _fetch_curl(url: str) -> tuple[int, str]:
    from curl_cffi.requests import AsyncSession
    async with AsyncSession(impersonate="chrome124") as session:
        response = await session.get(url, headers={"User-Agent": random.choice(USER_AGENTS), "Accept-Language": "tr-TR,tr;q=0.9"}, timeout=30, allow_redirects=True)
        return response.status_code, response.text

async def _fetch_browser(url: str) -> tuple[int, str]:
    import nodriver as uc
    browser = await uc.start(headless=True, browser_args=["--lang=tr-TR"])
    try:
        page = await browser.get(url); await asyncio.sleep(random.uniform(2, 4)); return 200, await page.get_content()
    finally: browser.stop()

async def fetch_listing(url: str, browser_fallback: bool = True) -> FetchResult:
    try:
        url = canonicalize_url(url); status, html = await _fetch_curl(url)
        if status in {404, 410}: return FetchResult("unavailable")
        if status == 200:
            try: return FetchResult("ok", parse_listing_page(html, url))
            except ValueError as exc:
                if not browser_fallback: return FetchResult("error", error=str(exc))
        elif not browser_fallback: return FetchResult("error", error=f"HTTP {status}")
        status, html = await _fetch_browser(url)
        if status in {404, 410}: return FetchResult("unavailable")
        return FetchResult("ok", parse_listing_page(html, url)) if status == 200 else FetchResult("error", error=f"Browser HTTP {status}")
    except Exception as exc:
        logger.warning("Could not fetch %s: %s", url, exc); return FetchResult("error", error=str(exc))
