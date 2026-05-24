import time
from datetime import datetime, timedelta

import pandas as pd
import requests


# --- STEP 1: DATA FETCHER (6 BULAN) ---
def get_multi_data(symbols):
    all_data = {}
    for symbol in symbols:
        print(f"🚀 Menarik data 6 bulan untuk {symbol}...")
        url = "https://api.binance.com/api/v3/klines"
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=180)).timestamp() * 1000)
        candles = []
        while start_time < end_time:
            params = {'symbol': symbol, 'interval': "1h", 'startTime': start_time, 'limit': 1000}
            res = requests.get(url, params=params).json()
            if not res: break
            candles.extend(res)
            start_time = res[-1][0] + 1
            time.sleep(0.05)
        df = pd.DataFrame(candles, columns=['ts', 'o', 'h', 'l', 'c', 'v', 'ct', 'qa', 'nt', 'tb', 'tq', 'i'])
        df[['o', 'h', 'l', 'c', 'v']] = df[['o', 'h', 'l', 'c', 'v']].astype(float)
        df['datetime'] = pd.to_datetime(df['ts'], unit='ms')
        all_data[symbol] = df
    return all_data

# --- STEP 2: LOGIKA BACKTEST V42 (HYBRID SNIPER) ---
def run_backtest_v42(all_data):
    all_trades = []
    active_trades = {}

    for symbol in all_data:
        df = all_data[symbol]
        # V42 Indicators
        df['ema_anchor'] = df['c'].ewm(span=200).mean() # Arus Gajah
        delta = df['c'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['rsi'] = 100 - (100 / (1 + (gain / loss)))
        df['vol_ma'] = df['v'].rolling(20).mean()
        df['atr'] = (df['h'] - df['l']).rolling(14).mean()

    for i in range(50, len(all_data['BTCUSDT'])):
        for symbol in all_data:
            df = all_data[symbol]
            curr = df.iloc[i]

            if symbol in active_trades:
                t = active_trades[symbol]
                if t['type'] == 'LONG':
                    if curr['h'] >= t['tp']: t['result'] = 'WIN'; t['exit_time'] = curr['datetime']; all_trades.append(t); del active_trades[symbol]
                    elif curr['l'] <= t['sl']: t['result'] = 'LOSS'; t['exit_time'] = curr['datetime']; all_trades.append(t); del active_trades[symbol]
                else:
                    if curr['l'] <= t['tp']: t['result'] = 'WIN'; t['exit_time'] = curr['datetime']; all_trades.append(t); del active_trades[symbol]
                    elif curr['h'] >= t['sl']: t['result'] = 'LOSS'; t['exit_time'] = curr['datetime']; all_trades.append(t); del active_trades[symbol]
                continue

            # --- ENTRY LOGIC V42 ---
            # LONG: Trend UP + RSI < 45 + Volume Spike + Candle Ijo
            if curr['c'] > curr['ema_anchor'] and curr['rsi'] < 45:
                if curr['v'] > curr['vol_ma'] and curr['c'] > curr['o']:
                    entry = curr['c']
                    sl = entry - (curr['atr'] * 2.5)
                    tp = entry + (abs(entry - sl) * 1.0) # RR 1:1
                    active_trades[symbol] = {'symbol': symbol, 'type': 'LONG', 'entry': entry, 'sl': sl, 'tp': tp, 'time': curr['datetime'], 'result': None}

            # SHORT: Trend DOWN + RSI > 55 + Volume Spike + Candle Merah
            elif curr['c'] < curr['ema_anchor'] and curr['rsi'] > 55:
                if curr['v'] > curr['vol_ma'] and curr['c'] < curr['o']:
                    entry = curr['c']
                    sl = entry + (curr['atr'] * 2.5)
                    tp = entry - (abs(sl - entry) * 1.0) # RR 1:1
                    active_trades[symbol] = {'symbol': symbol, 'type': 'SHORT', 'entry': entry, 'sl': sl, 'tp': tp, 'time': curr['datetime'], 'result': None}

    return pd.DataFrame(all_trades)

# --- STEP 3: LAPORAN PERIODE ---
def analyze_periods(df_trades):
    if df_trades.empty: return "No trades."
    now = df_trades['time'].max()
    periods = {'1 Bulan': 30, '3 Bulan': 90, '6 Bulan': 180}
    summary = []
    for label, days in periods.items():
        cutoff = now - timedelta(days=days)
        df_p = df_trades[df_trades['time'] >= cutoff]
        wins = len(df_p[df_p['result'] == 'WIN'])
        losses = len(df_p[df_p['result'] == 'LOSS'])
        total = wins + losses
        wr = (wins / total * 100) if total > 0 else 0
        profit = (wins * 50) - (losses * 50) # RR 1:1
        summary.append({'Periode': label, 'Trades': total, 'Win Rate': f"{wr:.2f}%", 'Net Profit': f"${profit:.2f}"})
    return pd.DataFrame(summary)

# --- RUN EXECUTION ---
symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
print("🔥 Memanggil Kembali Sang Juara: V42 Hybrid Sniper...")
data = get_multi_data(symbols)
trades = run_backtest_v42(data)
report = analyze_periods(trades)

print("\n" + "="*50)
print("📊 LAPORAN KONSISTENSI V42 (THE HYBRID SNIPER)")
print("="*50)
print(report.to_string(index=False))
print("="*50)
