import os, requests, html, time, datetime, pytz, statistics

# --- خواندن کلیدها از Secrets ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
MARKETAUX_API_KEY = os.getenv("MARKETAUX_API_KEY")
LIBRE_URL = "https://libretranslate.de/translate"

# --- کلیدواژه‌ها ---
KEYWORDS = [
    "bitcoin", "ethereum", "crypto", "cryptocurrency", "blockchain",
    "defi", "altcoin", "solana", "ripple", "xrp", "bnb", "ton", "market",
    "price", "exchange", "trading", "binance", "regulation", "etf", "sec"
]

COINS = {
    'bitcoin': 'BTC',
    'ethereum': 'ETH',
    'solana': 'SOL',
    'toncoin': 'TON',
    'ripple': 'XRP',
    'binancecoin': 'BNB'
}

def translate(text):
    try:
        res = requests.post(LIBRE_URL, json={"q": text, "source": "en", "target": "fa"}, timeout=10)
        if res.status_code == 200:
            return res.json().get("translatedText", "")
    except Exception as e:
        print("❗️Translate error:", e)
    return text

def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHANNEL_ID, 'text': message, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
    r = requests.post(url, data=payload)
    if r.status_code != 200:
        print("❗️Telegram error:", r.text)

def fetch_news():
    url = f"https://api.marketaux.com/v1/news/all?categories=crypto&language=en&api_token={MARKETAUX_API_KEY}"
    r = requests.get(url)
    if r.status_code == 200:
        return r.json().get("data", [])
    print("❗️News fetch failed:", r.text)
    return []

def is_important(title):
    return any(k.lower() in title.lower() for k in KEYWORDS)

def fetch_history(coin, days=30):
    url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart?vs_currency=usd&days={days}"
    r = requests.get(url)
    return [p[1] for p in r.json().get("prices", [])] if r.status_code == 200 else []

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
    return f"MA7: {ma7}, MA30: {ma30}, RSI: {rsi}, {trend}\n🔸 مسئولیت استفاده با تریدر است."

def send_analysis(coin_id, symbol):
    prices = fetch_history(coin_id)
    msg = f"📊 تحلیل تکنیکال {symbol}\n\n{analyze(prices)}\n\n👥 {TELEGRAM_CHANNEL_ID}\nبه ما بپیوندید 🦈"
    send_to_telegram(msg)

def main():
    print("🚀 Running bot...")
    news = fetch_news()
    for n in news:
        title = html.unescape(n["title"])
        desc = n.get("description", "")
        url = n.get("url", "")
        if not is_important(title):
            continue
        fa_title = translate(title)
        fa_desc = translate(desc) if desc else ""
        msg = f"📢 {fa_title}\n\n📝 {fa_desc}\n\n🔗 <a href='{url}'>ادامه مطلب</a>\n\n👥 {TELEGRAM_CHANNEL_ID}\nبه ما بپیوندید 🦈"
        send_to_telegram(msg)
        time.sleep(3)

    # تحلیل تکنیکال روزانه
    for coin_id, symbol in COINS.items():
        send_analysis(coin_id, symbol)
        time.sleep(2)

if __name__ == "__main__":
    main()

