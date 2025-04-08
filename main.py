import time
import pandas as pd
import requests
from binance.client import Client
from binance.enums import *
import ta

# CONFIG
API_KEY = "6lAhRHQE0KTj0mM0fP6RtjqhqQCcgkpJn5bDAj1V3mkaWuALUOcRiP8fG2xOXiVL"
API_SECRET = "3wNYSA97CJ4CWPSowmQiVUL5amTWObia1MacP7JTvDKfRkWnnAuobX10hAHpjyT1"
client = Client(API_KEY, API_SECRET)
client.API_URL = "https://testnet.binance.vision/api"

TELEGRAM_TOKEN = "7979519144:AAHD-wfu9Rm93Hiv3gWFOQfcRruJEnYoUIw"
CHAT_ID = "6212530288"
SYMBOL = "BTCUSDT"
TRADE_PORTION = 0.1  # Use 10% of balance per trade
STOP_LOSS_PCT = 0.97  # 3% Loss
TAKE_PROFIT_PCT = 1.03  # 3% Profit
TIMEFRAME = '1m'
LOG_FILE = "trade_log.txt"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=data)

def log(text):
    with open(LOG_FILE, "a") as f:
        f.write(text + "\n")

def get_candles():
    try:
        klines = client.get_klines(symbol=SYMBOL, interval=TIMEFRAME, limit=100)
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'num_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        df['close'] = pd.to_numeric(df['close'])
        return df
    except Exception as e:
        send_telegram(f"Error fetching data: {e}")
        return None

def calculate_indicators(df):
    df['EMA20'] = ta.trend.EMAIndicator(df['close'], window=20).ema_indicator()
    df['EMA50'] = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator()
    df['RSI'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    df['MACD'] = ta.trend.MACD(df['close']).macd()
    return df

def should_buy(df):
    last = df.iloc[-1]
    return (
        last['EMA20'] > last['EMA50'] and
        last['RSI'] < 30 and
        last['MACD'] > 0
    )

def get_quantity():
    balance = float(client.get_asset_balance(asset="USDT")['free'])
    price = float(client.get_symbol_ticker(symbol=SYMBOL)['price'])
    amount = (balance * TRADE_PORTION) / price
    return round(amount, 6)

def place_order():
    qty = get_quantity()
    order = client.create_order(
        symbol=SYMBOL,
        side=SIDE_BUY,
        type=ORDER_TYPE_MARKET,
        quantity=qty
    )
    buy_price = float(order['fills'][0]['price'])
    send_telegram(f"✅ Bought {qty} {SYMBOL} at {buy_price}")
    log(f"BUY: {qty} {SYMBOL} at {buy_price}")
    return qty, buy_price

def monitor_trade(qty, buy_price):
    while True:
        time.sleep(10)
        current_price = float(client.get_symbol_ticker(symbol=SYMBOL)['price'])
        if current_price <= buy_price * STOP_LOSS_PCT:
            client.create_order(symbol=SYMBOL, side=SIDE_SELL, type=ORDER_TYPE_MARKET, quantity=qty)
            send_telegram(f"❌ Stop-loss hit! Sold at {current_price}")
            log(f"STOP-LOSS SELL: {qty} at {current_price}")
            break
        elif current_price >= buy_price * TAKE_PROFIT_PCT:
            client.create_order(symbol=SYMBOL, side=SIDE_SELL, type=ORDER_TYPE_MARKET, quantity=qty)
            send_telegram(f"✅ Take-profit hit! Sold at {current_price}")
            log(f"TAKE-PROFIT SELL: {qty} at {current_price}")
            break

def run_bot():
    print("🤖 Bot Started and Running...")
    while True:
        df = get_candles()
        if df is None:
            time.sleep(30)
            continue
        df = calculate_indicators(df)
        if should_buy(df):
            qty, buy_price = place_order()
            monitor_trade(qty, buy_price)
        time.sleep(60)

run_bot()
