import sys
sys.path.insert(0, '/root/aiagent')
import os
import time
import requests
import pandas as pd
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('/root/aiagent/.env')

# ==========================================
# CONFIG UTAMA
# ==========================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_TELEGRAM_ID", "0"))
TOTAL_MODAL = 4
RESIKO_PERSEN = 1.0
LEVERAGE = 55
PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "SUIUSDT", "AVAXUSDT", "XRPUSDT"]

# ==========================================
# AUTO EXECUTE CONFIG
# ==========================================
AUTO_EXECUTE = True
MAX_SLIPPAGE = 0.3

# ==========================================
# SWITCH MODE
# ==========================================
TRADING_MODE = "scalping"

if TRADING_MODE == "scalping":
    TIMEFRAME = "15m"
    HTF = "4h"
    ATR_MULT = 1.5
    RSI_LONG_MIN, RSI_LONG_MAX = 45, 65
    RSI_SHORT_MIN, RSI_SHORT_MAX = 35, 55
    CHECK_INTERVAL = 300
    MODE_LABEL = "⚡ SCALPING (15m)"
else:
    TIMEFRAME = "4h"
    HTF = "1d"
    ATR_MULT = 2.0
    RSI_LONG_MIN, RSI_LONG_MAX = 50, 70
    RSI_SHORT_MIN, RSI_SHORT_MAX = 30, 50
    CHECK_INTERVAL = 3600
    MODE_LABEL = "🌊 SWING (4h)"

# RR Ratio
RR_RATIO = 1.5  # Risk:Reward 1:1.5
ADX_MIN = 20    # Min ADX buat konfirmasi trend

# ==========================================
# TELEGRAM
# ==========================================
def send_telegram(msg: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": OWNER_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except:
        pass

def send_approve_buttons(msg, symbol, side, sl, tp, qty):
    try:
        keyboard = {
            "inline_keyboard": [[
                {"text": "✅ EXECUTE", "callback_data": f"trade_yes_{symbol}_{side}_{sl}_{tp}_{qty}"},
                {"text": "❌ SKIP", "callback_data": f"trade_no_{symbol}"}
            ]]
        }
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": OWNER_ID, "text": msg,
                  "parse_mode": "HTML", "reply_markup": keyboard},
            timeout=10
        )
    except Exception as e:
        print(f"Error: {e}")

def send_close_button(msg, symbol):
    try:
        keyboard = {
            "inline_keyboard": [[
                {"text": "🔴 CLOSE POSITION", "callback_data": f"trade_close_{symbol}"}
            ]]
        }
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": OWNER_ID, "text": msg,
                  "parse_mode": "HTML", "reply_markup": keyboard},
            timeout=10
        )
    except:
        pass

# ==========================================
# DATA
# ==========================================
def get_binance_data(sym, interval="1h", limit=300):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": sym, "interval": interval, "limit": limit}
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        if isinstance(data, dict) and 'code' in data:
            return None
        df = pd.DataFrame(data,
            columns=['ts','o','h','l','c','v','ct','qa','nt','tb','tq','i'])
        df[['o','h','l','c','v']] = df[['o','h','l','c','v']].astype(float)
        return df
    except:
        return None

def get_current_price(symbol: str) -> float:
    try:
        res = requests.get(
            f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}",
            timeout=5
        ).json()
        return float(res['price'])
    except:
        return 0

def get_fng():
    try:
        res = requests.get(
            "https://api.alternative.me/fng/?limit=1", timeout=5
        ).json()
        return int(res['data'][0]['value']), res['data'][0]['value_classification']
    except:
        return 50, "Neutral"

def get_sentiment(keyword):
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        query = urllib.parse.quote(keyword)
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=7)
        root = ET.fromstring(res.content)
        analyzer = SentimentIntensityAnalyzer()
        score, count = 0, 0
        for item in root.findall('.//item'):
            title = item.find('title').text
            score += analyzer.polarity_scores(title)['compound']
            count += 1
            if count >= 3:
                break
        avg = score / count if count > 0 else 0
        if avg > 0.15: return "BULLISH"
        elif avg < -0.15: return "BEARISH"
        else: return "NETRAL"
    except:
        return "N/A"

# ==========================================
# IMPROVED INDICATORS
# ==========================================
def calc_adx(df, period=14):
    """Hitung ADX manual"""
    try:
        high = df['h']
        low = df['l']
        close = df['c']

        plus_dm = high.diff()
        minus_dm = low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0

        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.rolling(period).mean()
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (abs(minus_dm).rolling(period).mean() / atr)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(period).mean()
        return adx
    except:
        return pd.Series([0] * len(df))

def check_rsi_divergence(df, lookback=5):
    """Deteksi RSI divergence"""
    try:
        prices = df['c'].values[-lookback:]
        rsi_vals = df['rsi'].values[-lookback:]

        price_hh = prices[-1] > max(prices[:-1])
        rsi_lh = rsi_vals[-1] < max(rsi_vals[:-1])
        bearish_div = price_hh and rsi_lh

        price_ll = prices[-1] < min(prices[:-1])
        rsi_hl = rsi_vals[-1] > min(rsi_vals[:-1])
        bullish_div = price_ll and rsi_hl

        return bullish_div, bearish_div
    except:
        return False, False

def check_htf_trend(symbol: str) -> str:
    """Cek trend di Higher Timeframe"""
    try:
        df = get_binance_data(symbol, HTF, 250)
        if df is None or len(df) < 200:
            return "NEUTRAL"

        df['ema_200'] = df['c'].ewm(span=200, adjust=False).mean()
        df['ema_50'] = df['c'].ewm(span=50, adjust=False).mean()
        curr = df.iloc[-1]

        if curr['c'] > curr['ema_200'] and curr['ema_50'] > curr['ema_200']:
            return "BULLISH"
        elif curr['c'] < curr['ema_200'] and curr['ema_50'] < curr['ema_200']:
            return "BEARISH"
        else:
            return "NEUTRAL"
    except:
        return "NEUTRAL"

def detect_market_structure(df):
    highs, lows = df['h'].values, df['l'].values
    sh, sl = [], []
    for i in range(5, len(df)-5):
        if highs[i] == max(highs[i-5:i+5]): sh.append((i, highs[i]))
        if lows[i] == min(lows[i-5:i+5]): sl.append((i, lows[i]))
    rh = sh[-3:] if len(sh) >= 3 else sh
    rl = sl[-3:] if len(sl) >= 3 else sl
    structure = "SIDEWAYS"
    if len(rh) >= 2 and len(rl) >= 2:
        if rh[-1][1] > rh[-2][1] and rl[-1][1] > rl[-2][1]:
            structure = "UPTREND (HH/HL)"
        elif rh[-1][1] < rh[-2][1] and rl[-1][1] < rl[-2][1]:
            structure = "DOWNTREND (LH/LL)"
        else:
            structure = "RANGING"
    return structure

def detect_bos(df):
    curr = df.iloc[-1]
    rh = max(df['h'].values[-20:-1])
    rl = min(df['l'].values[-20:-1])
    bos = "None"
    if curr['c'] > rh: bos = f"BULLISH Break"
    elif curr['c'] < rl: bos = f"BEARISH Break"
    return bos, rh, rl

# ==========================================
# MAIN SIGNAL ANALYZER (UPGRADED)
# ==========================================
def analyze_signal(symbol: str) -> dict:
    if not symbol.upper().endswith("USDT"):
        symbol = symbol.upper() + "USDT"

    # 1. Cek HTF trend dulu
    htf_trend = check_htf_trend(symbol)
    if htf_trend == "NEUTRAL":
        print(f"    {symbol}: Skip — HTF Neutral")
        return None

    # 2. Ambil data LTF
    df = get_binance_data(symbol, interval=TIMEFRAME, limit=300)
    if df is None or len(df) < 50:
        return None

    # 3. Hitung indikator
    df['ema_9'] = df['c'].ewm(span=9, adjust=False).mean()
    df['ema_21'] = df['c'].ewm(span=21, adjust=False).mean()
    df['ema_200'] = df['c'].ewm(span=200, adjust=False).mean()
    delta = df['c'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / loss)))
    df['atr'] = (df['h'] - df['l']).rolling(14).mean()
    df['vol_ma'] = df['v'].rolling(20).mean()
    df['adx'] = calc_adx(df)
    df['cross_up'] = (
        (df['ema_9'] > df['ema_21']) &
        (df['ema_9'].shift(1) <= df['ema_21'].shift(1))
    )
    df['cross_down'] = (
        (df['ema_9'] < df['ema_21']) &
        (df['ema_9'].shift(1) >= df['ema_21'].shift(1))
    )

    curr = df.iloc[-1]
    prev = df.iloc[-2]
    price = curr['c']

    # 4. ADX filter — skip kalau sideways
    adx_val = round(float(curr['adx']), 2) if not pd.isna(curr['adx']) else 0
    if adx_val < ADX_MIN:
        print(f"    {symbol}: Skip — ADX {adx_val:.1f} < {ADX_MIN} (sideways)")
        return None

    candle_range = curr['h'] - curr['l']
    is_solid = (candle_range > 0 and
                abs(curr['c'] - curr['o']) >= candle_range * 0.5)
    vol_up = curr['v'] > prev['v']
    is_bullish = curr['c'] > curr['o']

    structure = detect_market_structure(df)
    bos, res_level, sup_level = detect_bos(df)

    # 5. RSI Divergence check
    bullish_div, bearish_div = check_rsi_divergence(df)

    signal = None
    entry = sl = tp = None
    skip_reason = None

    # 6. LONG — hanya kalau HTF bullish
    if htf_trend == "BULLISH":
        if (price > curr['ema_200'] and curr['cross_up'] and
                RSI_LONG_MIN < curr['rsi'] < RSI_LONG_MAX and
                is_solid and vol_up):
            if bearish_div:
                skip_reason = "Bearish RSI divergence"
            else:
                signal = "LONG"
                entry = round(price, 4)
                sl = round(entry - (curr['atr'] * ATR_MULT), 4)
                tp = round(entry + (entry - sl) * RR_RATIO, 4)

    # 7. SHORT — hanya kalau HTF bearish
    elif htf_trend == "BEARISH":
        if (price < curr['ema_200'] and curr['cross_down'] and
                RSI_SHORT_MIN < curr['rsi'] < RSI_SHORT_MAX and
                is_solid and not is_bullish and vol_up):
            if bullish_div:
                skip_reason = "Bullish RSI divergence"
            else:
                signal = "SHORT"
                entry = round(price, 4)
                sl = round(entry + (curr['atr'] * ATR_MULT), 4)
                tp = round(entry - (sl - entry) * RR_RATIO, 4)

    if skip_reason:
        print(f"    {symbol}: Skip — {skip_reason}")
        return None

    if not signal:
        return None

    # 8. Money Management
    jarak_sl_pct = abs(entry - sl) / entry * 100
    resiko_usd = TOTAL_MODAL * (RESIKO_PERSEN / 100)
    position_size = resiko_usd / (jarak_sl_pct / 100) if jarak_sl_pct > 0 else 0
    qty_usdt = round(max(position_size, 5.0), 2)
    rr_actual = round((abs(tp - entry) / abs(sl - entry)), 2)

    return {
        "symbol": symbol,
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "rsi": round(curr['rsi'], 2),
        "atr": round(curr['atr'], 4),
        "adx": adx_val,
        "htf_trend": htf_trend,
        "structure": structure,
        "bos": bos,
        "resistance": res_level,
        "support": sup_level,
        "qty_usdt": qty_usdt,
        "resiko_usd": round(resiko_usd, 2),
        "sl_pct": round(jarak_sl_pct, 2),
        "rr": rr_actual,
    }

# ==========================================
# TRAILING SL MONITOR
# ==========================================
def monitor_trailing_sl():
    """Monitor posisi terbuka dan trailing SL"""
    try:
        from tools.binance_trader import get_open_positions
        from binance.client import Client
        from dotenv import load_dotenv
        load_dotenv('/root/aiagent/.env')

        client = Client(
            os.getenv("BINANCE_API_KEY"),
            os.getenv("BINANCE_SECRET_KEY")
        )

        positions = get_open_positions()
        if not isinstance(positions, list):
            return

        for pos in positions:
            symbol = pos['symbol']
            side = pos['side']
            entry = pos['entry']
            pnl = pos['pnl']

            current_price = get_current_price(symbol)
            if current_price == 0:
                continue

            # Ambil ATR untuk trailing
            df = get_binance_data(symbol, TIMEFRAME, 50)
            if df is None:
                continue

            atr = float((df['h'] - df['l']).rolling(14).mean().iloc[-1])
            risk = entry * (RESIKO_PERSEN / 100)

            # Kalau profit >= 1R → geser SL ke breakeven
            if side == "LONG":
                profit_r = (current_price - entry) / risk
                if profit_r >= 1.0:
                    new_sl = round(entry + (atr * 0.5), 4)  # Breakeven + buffer
                    try:
                        # Cancel SL lama
                        client.futures_cancel_all_open_orders(symbol=symbol)
                        # Set SL baru
                        client.futures_create_order(
                            symbol=symbol,
                            side="SELL",
                            type="STOP_MARKET",
                            stopPrice=new_sl,
                            closePosition=True
                        )
                        if profit_r >= 1.0 and profit_r < 1.1:
                            send_telegram(
                                f"🔄 <b>TRAILING SL UPDATE</b>\n"
                                f"🪙 {symbol} LONG\n"
                                f"SL digeser ke breakeven: ${new_sl:,}\n"
                                f"Profit: +{profit_r:.1f}R"
                            )
                    except:
                        pass

            elif side == "SHORT":
                profit_r = (entry - current_price) / risk
                if profit_r >= 1.0:
                    new_sl = round(entry - (atr * 0.5), 4)
                    try:
                        client.futures_cancel_all_open_orders(symbol=symbol)
                        client.futures_create_order(
                            symbol=symbol,
                            side="BUY",
                            type="STOP_MARKET",
                            stopPrice=new_sl,
                            closePosition=True
                        )
                        if profit_r >= 1.0 and profit_r < 1.1:
                            send_telegram(
                                f"🔄 <b>TRAILING SL UPDATE</b>\n"
                                f"🪙 {symbol} SHORT\n"
                                f"SL digeser ke breakeven: ${new_sl:,}\n"
                                f"Profit: +{profit_r:.1f}R"
                            )
                    except:
                        pass
    except Exception as e:
        print(f"Trailing SL error: {e}")

# ==========================================
# EXECUTE
# ==========================================
def execute_trade(result: dict) -> bool:
    from tools.binance_trader import open_position

    exec_result = open_position(
        symbol=result['symbol'],
        side=result['signal'],
        usdt_amount=result['qty_usdt'],
        sl_price=result['sl'],
        tp_price=result['tp'],
        leverage=LEVERAGE
    )

    if "error" in exec_result:
        send_telegram(
            f"❌ <b>EXECUTE FAILED</b>\n"
            f"🪙 {result['symbol']}\n"
            f"Error: {exec_result['error']}"
        )
        return False

    emoji = "🟢" if result['signal'] == "LONG" else "🔴"
    send_close_button(
        f"✅ <b>AUTO EXECUTED!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🪙 <b>{result['symbol']}</b> | {MODE_LABEL}\n"
        f"{emoji} <b>{result['signal']}</b>\n\n"
        f"💰 Entry  : ${exec_result['entry']:,}\n"
        f"🛑 SL     : ${result['sl']:,} ({result['sl_pct']}%)\n"
        f"✅ TP     : ${result['tp']:,}\n"
        f"⚖️ RR     : 1:{result['rr']}\n"
        f"📦 Qty    : {exec_result['qty']}\n\n"
        f"📊 HTF    : {result['htf_trend']}\n"
        f"📈 ADX    : {result['adx']}\n"
        f"📉 RSI    : {result['rsi']}\n"
        f"🔀 BOS    : {result['bos']}\n\n"
        f"⚠️ Max Loss: ${result['resiko_usd']}\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')}",
        result['symbol']
    )
    return True

# ==========================================
# MAIN LOOP
# ==========================================
def run_auto_trader():
    print(f"🤖 JAGRESMAN AUTO TRADE — {datetime.now()}")
    mode_str = "AUTO EXECUTE" if AUTO_EXECUTE else "MANUAL APPROVE"
    send_telegram(
        f"🤖 <b>GODZILLA AUTO TRADER v2.0</b>\n\n"
        f"📊 Pairs: {', '.join(PAIRS)}\n"
        f"🎯 Mode: {MODE_LABEL}\n"
        f"⚙️ Execute: {mode_str}\n"
        f"💵 Modal: ${TOTAL_MODAL} | Risk: {RESIKO_PERSEN}%\n"
        f"⚡ Leverage: {LEVERAGE}x\n"
        f"⚖️ RR: 1:{RR_RATIO}\n"
        f"📉 ADX Min: {ADX_MIN}\n"
        f"📊 HTF: {HTF}\n"
        f"📉 Max Slippage: {MAX_SLIPPAGE}%\n"
        f"⏰ Scan tiap: {CHECK_INTERVAL//60} menit\n\n"
        f"✅ Upgrades:\n"
        f"• HTF Filter ({HTF})\n"
        f"• ADX Filter (min {ADX_MIN})\n"
        f"• RSI Divergence Filter\n"
        f"• RR 1:{RR_RATIO}\n"
        f"• Trailing SL ke Breakeven\n"
        f"🕐 {datetime.now().strftime('%d %b %Y %H:%M WIB')}"
    )

    from tools.binance_trader import get_futures_balance, get_open_positions

    scan_count = 0

    while True:
        try:
            now = datetime.now().strftime("%H:%M:%S")
            scan_count += 1
            print(f"\n[{now}] Scan #{scan_count} | Mode: {TRADING_MODE}")

            # Cek balance
            balance = get_futures_balance()
            if "error" in balance:
                print(f"Balance error: {balance['error']}")
                time.sleep(60)
                continue

            bal = balance['balance']
            pnl = balance['unrealized_pnl']
            print(f"Balance: ${bal:.2f} | PnL: ${pnl:.2f}")

            # Monitor trailing SL setiap scan
            monitor_trailing_sl()

            # Cek posisi terbuka
            open_pos = get_open_positions()
            open_symbols = (
                [p['symbol'] for p in open_pos]
                if isinstance(open_pos, list) else []
            )

            if open_symbols:
                print(f"Open positions: {', '.join(open_symbols)}")

            # Sentiment sekali per loop
            fng_val, fng_label = get_fng()
            sent_trump = get_sentiment("Trump crypto economy")

            # Skip scanning kalau F&G extreme fear < 15
            if fng_val < 15:
                print(f"  F&G = {fng_val} (Extreme Fear) — Skip scan")
                time.sleep(CHECK_INTERVAL)
                continue

            signals_found = 0

            for pair in PAIRS:
                if pair in open_symbols:
                    print(f"  {pair}: Skip (posisi terbuka)")
                    continue

                print(f"  Analyzing {pair}...")
                result = analyze_signal(pair)

                if not result:
                    continue

                signals_found += 1
                print(f"  {pair}: {result['signal']} SIGNAL! HTF={result['htf_trend']} ADX={result['adx']}")

                emoji = "🟢" if result['signal'] == "LONG" else "🔴"

                if AUTO_EXECUTE:
                    current_price = get_current_price(pair)
                    slippage = (
                        abs(current_price - result['entry']) /
                        result['entry'] * 100
                    )

                    if slippage > MAX_SLIPPAGE:
                        print(f"  {pair}: Expired! Slippage {slippage:.2f}%")
                        send_telegram(
                            f"⚠️ <b>SIGNAL EXPIRED</b>\n"
                            f"🪙 {result['symbol']}\n"
                            f"Slippage: {slippage:.2f}% > {MAX_SLIPPAGE}%\n"
                            f"❌ Skip"
                        )
                        continue

                    print(f"  {pair}: Executing...")
                    execute_trade(result)

                else:
                    msg = (
                        f"🔥 <b>GODZILLA v2.0 SIGNAL!</b>\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"🪙 <b>{result['symbol']}</b> | {MODE_LABEL}\n"
                        f"{emoji} <b>{result['signal']}</b>\n\n"
                        f"💰 Entry : <b>${result['entry']:,}</b>\n"
                        f"🛑 SL    : <b>${result['sl']:,}</b> ({result['sl_pct']}%)\n"
                        f"✅ TP    : <b>${result['tp']:,}</b>\n"
                        f"⚖️ RR    : 1:{result['rr']}\n\n"
                        f"📊 HTF   : {result['htf_trend']}\n"
                        f"📈 ADX   : {result['adx']}\n"
                        f"📉 RSI   : {result['rsi']}\n"
                        f"🔀 BOS   : {result['bos']}\n"
                        f"📊 Struct: {result['structure']}\n\n"
                        f"💵 Modal : ${TOTAL_MODAL} | {LEVERAGE}x\n"
                        f"⚠️ Loss  : ${result['resiko_usd']}\n"
                        f"📦 Size  : ${result['qty_usdt']}\n\n"
                        f"😱 F&G  : {fng_val} ({fng_label})\n"
                        f"🦅 Trump: {sent_trump}\n"
                        f"⏰ {now}"
                    )
                    send_approve_buttons(
                        msg, result['symbol'], result['signal'],
                        result['sl'], result['tp'], result['qty_usdt']
                    )

            if signals_found == 0:
                print(f"  No signals. Next scan in {CHECK_INTERVAL//60} menit.")

            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n[!] Auto trader dihentikan.")
            send_telegram("⚠️ <b>JAGRESMAN Auto Trader dihentikan.</b>")
            break
        except Exception as e:
            print(f"Loop error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_auto_trader()
