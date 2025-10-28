import os
import requests
import feedparser
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HF_TOKEN = os.getenv("HF_TOKEN")
LIBRE_URL = "https://libretranslate.com/translate"

# Scheduler setup
scheduler = BackgroundScheduler(timezone=pytz.timezone("Asia/Tehran"))


# ===== Helper Functions =====

def summarize_text(text):
    """Summarize using HuggingFace"""
    try:
        response = requests.post(
            "https://api-inference.huggingface.co/models/facebook/bart-large-cnn",
            headers={"Authorization": f"Bearer {HF_TOKEN}"},
            json={"inputs": text[:2000]},
            timeout=20
        )
        data = response.json()
        if isinstance(data, list) and len(data) > 0:
            return data[0]["summary_text"]
    except Exception as e:
        print("HF summarize error:", e)
    return text


def translate_to_farsi(text):
    """Translate summary to Persian via LibreTranslate"""
    try:
        res = requests.post(
            LIBRE_URL,
            json={"q": text, "source": "en", "target": "fa"},
            timeout=15
        )
        return res.json().get("translatedText", text)
    except Exception as e:
        print("Translation error:", e)
        return text


def send_message(text):
    """Send message to Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        })
    except Exception as e:
        print("Telegram send error:", e)


def fetch_crypto_news():
    """Fetch and return list of crypto news from RSS"""
    print("🛰 شروع بررسی RSS فیدها...")
    RSS_URL = os.getenv("NEWS_FEED_URL", "https://cryptonews.com/news/feed")
    feed = feedparser.parse(RSS_URL)

    news_items = []
    for entry in feed.entries[:5]:  # limit to 5 latest
        news_items.append({
            "title": entry.title,
            "summary": getattr(entry, "summary", ""),
            "link": entry.link
        })
    print(f"📡 تعداد خبر دریافت‌شده: {len(news_items)}")
    return news_items


# ===== Scheduled Jobs =====

@scheduler.scheduled_job("interval", minutes=5)
def post_news():
    """Every 5 minutes: fetch, summarize, translate, and send news"""
    print("Fetching latest news...")
    try:
        for n in fetch_crypto_news():
            summary = summarize_text(n["summary"])
            translated = translate_to_farsi(summary)
            msg = f"🗞 *{n['title']}*\n\n{translated}\n\n🔗 [منبع خبر]({n['link']})\n\n🦈 @Crypto_Zone360"
            send_message(msg)
    except Exception as e:
        print("News job error:", e)


def get_technical_analysis(symbol):
    """Simple technical analysis"""
    try:
        url = f"https://min-api.cryptocompare.com/data/pricemultifull?fsyms={symbol}&tsyms=USD"
        data = requests.get(url, timeout=10).json()
        price = data["RAW"][symbol]["USD"]["PRICE"]
        change = data["RAW"][symbol]["USD"]["CHANGEPCT24HOUR"]
        status = "📈 صعودی" if change > 0 else "📉 نزولی"
        return f"{symbol}: ${price:,.2f} ({change:.2f}%) {status}"
    except:
        return f"{symbol}: داده در دسترس نیست"


@scheduler.scheduled_job("cron", hour=21, minute=0)
def post_daily_analysis():
    """Send daily technical analysis at 21:00"""
    print("Sending daily analysis...")
    coins = ["BTC", "ETH", "SOL", "TON", "XRP", "BNB"]
    results = [get_technical_analysis(c) for c in coins]
    msg = "📊 *تحلیل تکنیکال روزانه بازار:*\n\n" + "\n".join(results) + "\n\n⚠️ مسئولیت استفاده با کاربر است.\n\n🦈 @Crypto_Zone360"
    send_message(msg)


# ===== Run Bot =====

if __name__ == "__main__":
    print("🚀 Bot started...")
    post_news()  # Run once immediately
    scheduler.start()