import requests
import time
import html
import datetime
import pytz
import statistics
import feedparser
from apscheduler.schedulers.background import BackgroundScheduler

# --- اطلاعات ربات و توکن‌ها ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")  # optional

LIBRE_URL = "https://libretranslate.de/translate"

# --- منابع RSS ---
RSS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss"
]

# --- کلمات کلیدی برای فیلتر ---
KEYWORDS = [
    "bitcoin", "btc", "ethereum", "eth", "solana", "sol", "toncoin", "ton",
    "ripple", "xrp", "binance", "bnb", "crypto", "cryptocurrency", "exchange",
    "sec", "etf", "lawsuit", "hack", "listing", "delisting", "regulation",
    "defi", "nft", "web3", "airdrop", "whale", "market", "bullish", "bearish"
]

# --- ارزهای مهم ---
COINS = {
    'bitcoin': 'BTC',
    'ethereum': 'ETH',
    'solana': 'SOL',
    'toncoin': 'TON',
    'ripple': 'XRP',
    'binancecoin': 'BNB'
}

# --- ترجمه ---
def translate_text(text):
    try:
        payload = {"q": text, "source": "en", "target": "fa", "format": "text"}
        r = requests.post(LIBRE_URL, json=payload, timeout=15)
        if r.status_code == 200:
            return r.json()["translatedText"]
        else:
            print("❗️ Translation failed:", r.text)
            return "ترجمه ناموفق بود."
    except Exception as e:
        print("❗️ Translation error:", e)
        return "ترجمه ناموفق بود."

# --- خلاصه‌سازی با Hugging Face ---
def summarize_text(text):
    try:
        headers = {"Authorization": f"Bearer {HUGGINGFACE_TOKEN}"}
        payload = {"inputs": text, "parameters": {"max_length": 80, "min_length": 30}}
        r = requests.post(
            "https://api-inference.huggingface.co/models/facebook/bart-large-cnn",
            headers=headers, json=payload, timeout=25
        )
        if r.status_code == 200:
            summary = r.json()[0]["summary_text"]
            return summary
        else:
            print("❗️ Summarization failed:", r.text)
            return text
    except Exception as e:
        print("❗️ HuggingFace error:", e)
        return text

# --- ارسال پیام به تلگرام ---
def send_to_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHANNEL_ID,
        'text': msg,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True
    }
    r = requests.post(url, data=payload)
    if r.status_code != 200:
        print("Telegram error:", r.text)

# --- بررسی اهمیت ---
def is_important(title):
    return any(k.lower() in title.lower() for k in KEYWORDS)

# --- دریافت و ارسال اخبار ---
posted = set()

def fetch_and_send_news():
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            title = html.unescape(entry.title)
            summary = entry.summary if hasattr(entry, 'summary') else ''
            link = entry.link

            if title in posted or not is_important(title):
                continue

            short_summary = summarize_text(summary or title)
            fa_title = translate_text(title)
            fa_summary = translate_text(short_summary)

            msg = f"📢 {fa_title}\n\n📝 {fa_summary}\n\n🔗 <a href='{link}'>ادامه مطلب</a>\n\n👥 {TELEGRAM_CHANNEL_ID}\nبه ما بپیوندید 🦈"
            send_to_telegram(msg)
            posted.add(title)
            time.sleep(5)

# --- تحلیل تکنیکال ---
def fetch_history(coin, days=30):
    url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart?vs_currency=usd&days={days}"
    r = requests.get(url)
    if r.status_code == 200:
        return [p[1] for p in r.json().get("prices", [])]
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
    zone = "اشباع فروش 📉" if rsi < 30 else "اشباع خرید 📈" if rsi > 70 else "نرمال"
    return f"MA7: {ma7}, MA30: {ma30}, RSI: {rsi} ({zone}), {trend}\n🔸 مسئولیت استفاده با تریدر است."

def send_all_analysis():
    now = datetime.datetime.now(pytz.timezone("Asia/Tehran")).strftime("%Y/%m/%d %H:%M")
    msg = f"📊 تحلیل تکنیکال روزانه ({now})\n\n"
    for cid, symbol in COINS.items():
        prices = fetch_history(cid)
        msg += f"{symbol}: {analyze(prices)}\n\n"
    msg += f"👥 {TELEGRAM_CHANNEL_ID}\nبه ما بپیوندید 🦈"
    send_to_telegram(msg)

# --- زمان‌بندی ---
scheduler = BackgroundScheduler(timezone="Asia/Tehran")
scheduler.add_job(fetch_and_send_news, 'interval', minutes=10)
scheduler.add_job(send_all_analysis, 'cron', hour=8, minute=0)
scheduler.start()

print("✅ ربات با خلاصه‌سازی Hugging Face و ترجمه فارسی فعال شد...")

while True:
    time.sleep(60)
try:
    # اجرای اصلی ربات
    run_news()
except Exception as e:
    import traceback
    print("❗️ Error:", e)
    traceback.print_exc()