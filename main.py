import os, requests, html, datetime, pytz
from deep_translator import GoogleTranslator

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
MARKETAUX_API_KEY = os.getenv("MARKETAUX_API_KEY")

KEYWORDS = ["Bitcoin","Ethereum","Ripple","XRP","BNB","Solana","TON","crypto","DeFi","ETF","SEC","binance","coinbase","hack","scam","price"]

def translate(text):
    try:
        return GoogleTranslator(source='en', target='fa').translate(text)
    except:
        return text

def send_to_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': TELEGRAM_CHANNEL_ID,
        'text': msg,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True
    }
    r = requests.post(url, data=data)
    print("Telegram:", r.status_code, r.text)

def fetch_news():
    url = f"https://api.marketaux.com/v1/news/all?categories=crypto&language=en&api_token={MARKETAUX_API_KEY}"
    r = requests.get(url, timeout=20)
    if r.status_code == 200:
        return r.json().get("data", [])
    return []

def is_important(title):
    t = title.lower()
    return any(k.lower() in t for k in KEYWORDS)

def run_once():
    now = datetime.datetime.now(datetime.timezone.utc)
    window_minutes = 25   # اگر workflow هر 15 دقیقه اجرا میشه، 25 دقیقه ایمنه
    cutoff = now - datetime.timedelta(minutes=window_minutes)

    news = fetch_news()
    posted = 0
    for item in news:
        title = html.unescape(item.get("title",""))
        pub = item.get("published_at") or item.get("created_at") or ""
        try:
            pub_dt = datetime.datetime.fromisoformat(pub.replace("Z","+00:00"))
        except:
            continue
        if pub_dt < cutoff:
            continue
        if not is_important(title):
            continue

        url = item.get("url","")
        fa_title = translate(title)
        msg = f"📢 {fa_title}\n\n🔗 <a href='{url}'>ادامه مطلب</a>\n\n👥 {TELEGRAM_CHANNEL_ID}\nبه ما بپیوندید 🦈"
        send_to_telegram(msg)
        posted += 1

    print(f"Done. Posted: {posted}")

if __name__ == "__main__":
    run_once()
