
import os
import requests
import feedparser
import html
import time
import datetime
import pytz
import statistics
import re

from dateutil import parser as dateparser

# --- config (دقیقا از Secrets خوانده می‌شود) ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
LIBRE_URL = os.getenv("LIBRE_URL", "https://libretranslate.de/translate")
HUGGINGFACE_API_TOKEN = os.getenv("HUGGINGFACE_API_TOKEN")  # optional

# --- RSS sources ---
RSS_SOURCES = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss"
]

# --- keywords (همان لیست تاییدشده) ---
KEYWORDS = [
    "bitcoin", "btc", "ethereum", "eth", "solana", "sol", "toncoin", "ton",
    "ripple", "xrp", "binance", "bnb", "coinbase", "exchange", "crypto", "cryptocurrency",
    "defi", "nft", "web3", "token", "blockchain", "layer 2", "staking", "airdrop",
    "sec", "etf", "approval", "lawsuit", "regulation", "ban", "court", "legal",
    "hack", "exploit", "breach", "scam", "security", "phishing",
    "market crash", "bullish", "bearish", "whale", "investment", "funding",
    "listing", "delisting", "partnership", "integration", "update", "upgrade",
    "price surge", "price drop", "federal reserve", "inflation", "interest rate"
]

COINS = {
    'bitcoin': 'BTC',
    'ethereum': 'ETH',
    'solana': 'SOL',
    'toncoin': 'TON',
    'ripple': 'XRP',
    'binancecoin': 'BNB'
}

# --- helpers ------------------------------------------------------------
TZ = pytz.timezone("Asia/Tehran")

def is_important(text):
    if not text:
        return False
    t = text.lower()
    return any(k.lower() in t for k in KEYWORDS)

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, data=payload, timeout=15)
        if r.status_code != 200:
            print("Telegram error:", r.status_code, r.text)
    except Exception as e:
        print("Telegram exception:", e)

# --- summarizer: use HuggingFace inference API if token present, else simple fallback
HF_MODEL = "facebook/bart-large-cnn"  # good summarization model

def hf_summarize(text, max_length=120):
    if not HUGGINGFACE_API_TOKEN:
        return None
    # trim too long text
    if len(text) > 1500:
        text = text[:1500]
    url = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"}
    payload = {"inputs": text, "parameters": {"max_length": max_length, "min_length": 30}}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=25)
        if r.status_code == 200:
            res = r.json()
            # huggingface sometimes returns [{"summary_text": "..."}] or string
            if isinstance(res, dict) and "error" in res:
                print("HF error:", res["error"])
                return None
            if isinstance(res, list):
                out = res[0]
                if isinstance(out, dict) and "summary_text" in out:
                    return out["summary_text"]
                # sometimes output is string
                if isinstance(out, str):
                    return out
            if isinstance(res, str):
                return res
    except Exception as e:
        print("HF summarize exception:", e)
    return None

# simple fallback summarizer: return first 2 meaningful sentences or first 300 chars
_SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')

def simple_summarize(text, max_chars=350):
    if not text:
        return ""
    # remove HTML tags
    text_plain = re.sub('<[^<]+?>', '', text)
    sents = _SENTENCE_RE.split(text_plain)
    # pick first two sentences with enough length
    chosen = []
    for s in sents:
        if len(s.strip()) >= 40:
            chosen.append(s.strip())
        if len(chosen) >= 2:
            break
    if not chosen:
        # fallback to first max_chars
        return text_plain.strip()[:max_chars].rstrip() + ("..." if len(text_plain) > max_chars else "")
    summary = " ".join(chosen)
    if len(summary) > max_chars:
        return summary[:max_chars].rstrip() + "..."
    return summary

# --- translate via LibreTranslate (summarize first in English, then translate) ---
def translate_text(text):
    try:
        payload = {"q": text, "source": "en", "target": "fa", "format": "text"}
        r = requests.post(LIBRE_URL, json=payload, timeout=10)
        if r.status_code == 200:
            return r.json()["translatedText"]
        else:
            print("❗️Translation error:", r.text)
            return "ترجمه ناموفق بود."
    except Exception as e:
        print("❗️Translation error:", e)
        return "ترجمه ناموفق بود."

# --- RSS fetching and parsing ------------------------------------------------
def fetch_rss_entries():
    entries = []
    for url in RSS_SOURCES:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                # unify published time
                pub = None
                if hasattr(e, "published"):
                    pub = e.published
                elif hasattr(e, "updated"):
                    pub = e.updated
                elif "published" in e:
                    pub = e["published"]
                # parse to datetime
                pub_dt = None
                if pub:
                    try:
                        pub_dt = dateparser.parse(pub)
                        if pub_dt.tzinfo is None:
                            pub_dt = pub_dt.replace(tzinfo=datetime.timezone.utc)
                    except:
                        pub_dt = None
                entries.append({
                    "title": e.get("title", ""),
                    "link": e.get("link", ""),
                    "summary": e.get("summary", "") or e.get("description", ""),
                    "published": pub_dt
                })
        except Exception as e:
            print("RSS fetch error for", url, e)
    # sort by published desc (newest first)
    entries.sort(key=lambda x: x.get("published") or datetime.datetime.min, reverse=True)
    return entries

# --- market data (CoinGecko) for analysis -----------------------------------
def fetch_market_data():
    ids = ",".join(COINS.keys())
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true"
    try:
        r = requests.get(url, timeout=12)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print("CoinGecko error:", e)
    return {}

def fetch_history(coin_id, days=30):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days={days}"
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return [p[1] for p in r.json().get("prices", [])]
    except Exception as e:
        print("History fetch error:", coin_id, e)
    return []

def analyze(prices):
    if len(prices) < 14:
        return "اطلاعات کافی نیست."
    ma7 = round(statistics.mean(prices[-7:]), 2)
    ma30 = round(statistics.mean(prices[-30:]), 2)
    delta = [j - i for i, j in zip(prices[:-1], prices[1:])]
    gains = sum(d for d in delta if d > 0)
    losses = -sum(d for d in delta if d < 0)
    rs = gains / losses if losses else 100
    rsi = round(100 - (100 / (1 + rs)), 1)
    trend = "صعودی 🔼" if ma7 > ma30 else "نزولی 🔽"
    return f"MA7: {ma7}, MA30: {ma30}, RSI: {rsi}, {trend}"

def build_analysis_message():
    now = datetime.datetime.now(TZ).strftime("%Y/%m/%d %H:%M")
    lines = [f"📊 تحلیل تکنیکال روزانه — {now}", "--------------------------------"]
    for coin_id, symbol in COINS.items():
        prices = fetch_history(coin_id)
        lines.append(f"{symbol}: {analyze(prices)}")
    lines.append("\n🔸 تحلیل‌ها ممکن است اشتباه باشند. مسئولیت استفاده بر عهده تریدر است.")
    lines.append(f"\n👥 {TELEGRAM_CHANNEL_ID}\nبه ما بپیوندید 🦈")
    return "\n".join(lines)

# --- main logic: window-based dedupe and processing --------------------------
# window_minutes: consider an article "new" if published within this many minutes
WINDOW_MINUTES = 12  # because Actions runs every 5 min; 12 min window is safe

def process_and_send():
    entries = fetch_rss_entries()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now_utc - datetime.timedelta(minutes=WINDOW_MINUTES)
    posted_count = 0

    for e in entries:
        pub = e.get("published")
        if not pub:
            # if no published date, skip (or optionally treat as new)
            continue
        if pub < cutoff:
            # older than window
            continue

        title = html.unescape(e.get("title",""))
        summary_en = re.sub('<[^<]+?>', '', e.get("summary","") or "")  # strip html
        link = e.get("link","")

        # filter by keywords (title OR summary)
        if not (is_important(title) or is_important(summary_en)):
            continue

        # Build english short summary: try HF summarizer, else simple
        summary_src = summary_en or title
        hf_res = hf_summarize(summary_src, max_length=120) if HUGGINGFACE_API_TOKEN else None
        if hf_res:
            eng_summary = hf_res
        else:
            eng_summary = simple_summarize(summary_src, max_chars=450)

        # translate title and summary
        fa_title = translate_text(title)
        fa_summary = translate_text(summary)

        message = (
            f"📢 {fa_title}\n\n"
            f"📝 {fa_summary}\n\n"
            f"🔗 <a href='{link}'>ادامه مطلب</a>\n\n"
            f"👥 {TELEGRAM_CHANNEL_ID}\nبه ما بپیوندید 🦈"
        )

        send_telegram(message)
        posted_count += 1
        # small pause to avoid hitting rate limits
        time.sleep(2)

    print(f"Processed entries. Posted {posted_count} new items.")

# --- scheduled analysis check (run only at 08:00 Tehran) ----------------------
def maybe_send_daily_analysis():
    now = datetime.datetime.now(TZ)
    if now.hour == 8 and now.minute < 6:  # run within first 6 minutes of 8:00
        msg = build_analysis_message()
        send_telegram(msg)
        print("Sent daily analysis.")

# --- entrypoint -------------------------------------------------------------
def main():
    print("Bot run at", datetime.datetime.now(TZ).isoformat())
    try:
        process_and_send()
        maybe_send_daily_analysis()
    except Exception as e:
        print("Main exception:", e)

if __name__ == "__main__":
    main()

