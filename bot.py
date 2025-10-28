import os
import requests
import feedparser
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HF_TOKEN = os.getenv("HF_TOKEN")
NEWS_FEED_URL = os.getenv("NEWS_FEED_URL")

LIBRE_URL = "https://libretranslate.com/translate"


scheduler = BackgroundScheduler(timezone=pytz.timezone("Asia/Tehran"))


def summarize_text(text):
    """Summarize using HuggingFace model"""
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
        return res.json()["translatedText"]
    except Exception as e:
        print("Translation error:", e)
        return text

def fetch_news():
    try:
        url = "https://cryptonews.com/news/feed/"
        feed = feedparser.parse(url)
        return feed.entries
    except Exception as e:
        print("❗️خطا در گرفتن خبر:", e)
        return []

def send_message(text):
    """Send message to Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True})
    except Exception as e:
        print("Telegram send error:", e)

@scheduler.scheduled_job("interval", minutes=5)
def fetch_news():
    print("🛰 شروع بررسی RSS فیدها...")
    news_list = fetch_news()
    print(f"📡 تعداد خبر دریافت‌شده: {len(news_list)}")
    print("Fetching latest news...")
    try:
        for msg in fetch_news():
            send_message(msg)
    except Exception as e:
        print("News job error:", e)

def get_technical_analysis(symbol):
    """Mock simple technical analysis"""
    try:
        url = f"https://min-api.cryptocompare.com/data/pricemultifull?fsyms={symbol}&tsyms=USD"
        data = requests.get(url, timeout=10).json()
        price = data["RAW"][symbol]["USD"]["PRICE"]
        change = data["RAW"][symbol]["USD"]["CHANGEPCT24HOUR"]
        status = "📈 صعودی" if change > 0 else "📉 نزولی"
        return f"{symbol}: ${price:,.2f} ({change:.2f}%) {status}"
    except:
        return f"{symbol}: داده در دسترس نیست"

@scheduler.scheduled_job("cron", hour=17, minute=30)
def post_daily_analysis():
    print("Sending daily analysis...")
    coins = ["BTC", "ETH", "SOL", "TON", "XRP", "BNB"]
    results = [get_technical_analysis(c) for c in coins]
    msg = "📊 تحلیل تکنیکال روزانه بازار:\n\n" + "\n".join(results) + "\n\n⚠️ مسئولیت استفاده با کاربر است.\n\n🦈 @Crypto_Zone360"
    send_message(msg)

if __name__ == "__main__":
    print("🚀 Bot started...")
    fetch_news()  # first immediate news
    scheduler.start()
