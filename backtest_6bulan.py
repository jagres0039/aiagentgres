import time
from datetime import datetime, timedelta

import pandas as pd
import requests


def get_6_months_data(symbol="BNBUSDT", interval="1h"):
    print(f"🚀 Memulai penarikan data 6 bulan untuk {symbol}...")
    url = "https://api.binance.com/api/v3/klines"

    # Hitung waktu 6 bulan lalu (dalam milidetik)
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(days=180)).timestamp() * 1000)

    all_candles = []
    while start_time < end_time:
        params = {
            'symbol': symbol,
            'interval': interval,
            'startTime': start_time,
            'limit': 1000
        }
        res = requests.get(url, params=params).json()
        if not res: break

        all_candles.extend(res)
        # Update start_time ke candle terakhir yang didapet + 1ms
        start_time = res[-1][0] + 1
        print(f"📦 Terambil {len(all_candles)} candle...")
        time.sleep(0.1) # Biar gak kena banned Binance

    df = pd.DataFrame(all_candles, columns=['ts', 'o', 'h', 'l', 'c', 'v', 'ct', 'qa', 'nt', 'tb', 'tq', 'i'])
    df[['o', 'h', 'l', 'c']] = df[['o', 'h', 'l', 'c']].astype(float)
    return df

def run_backtest_v8(df):
    # --- INDIKATOR V8 ---
    df['ema_50'] = df['c'].ewm(span=50).mean()
    df['ema_200'] = df['c'].ewm(span=200).mean()
    df['atr'] = (df['h'] - df['l']).rolling(14).mean()

    trades = []
    in_position = False

    print("📊 Menghitung simulasi trading...")

    for i in range(200, len(df)):
        last_c, last_o, last_h, last_l = df['c'].iloc[i], df['o'].iloc[i], df['h'].iloc[i], df['l'].iloc[i]
        last_atr = df['atr'].iloc[i]

        # Trend Filter
        trend = "BULL" if df['ema_50'].iloc[i] > df['ema_200'].iloc[i] else "BEAR"

        # Cari High/Low buat Fibonacci 61.8% (OTE)
        lookback = df.iloc[i-100:i]
        highest, lowest = lookback['h'].max(), lookback['l'].min()

        if not in_position:
            # LOGIKA BUY (V8)
            if trend == "BULL":
                ote_zone = highest - (0.618 * (highest - lowest))
                wick = min(last_c, last_o) - last_l
                body = abs(last_c - last_o)

                if last_l <= ote_zone and wick > (1.5 * body) and last_c > last_o:
                    entry_price = last_c
                    sl = last_l - (last_atr * 0.5)
                    tp = entry_price + abs(entry_price - sl)
                    trades.append({'type': 'LONG', 'entry': entry_price, 'sl': sl, 'tp': tp, 'result': None})
                    in_position = True

        else:
            # Cek Exit (TP/SL)
            current_trade = trades[-1]
            if last_h >= current_trade['tp']:
                current_trade['result'] = 'WIN'
                in_position = False
            elif last_l <= current_trade['sl']:
                current_trade['result'] = 'LOSS'
                in_position = False

    # --- HITUNG STATISTIK ---
    results = pd.DataFrame(trades)
    if results.empty: return "Gak ada trade yang terdeteksi bro."

    win_rate = (len(results[results['result'] == 'WIN']) / len(results)) * 100
    return {
        'Total Trades': len(results),
        'Win Rate': f"{win_rate:.2f}%",
        'Wins': len(results[results['result'] == 'WIN']),
        'Losses': len(results[results['result'] == 'LOSS'])
    }

# EKSEKUSI
data_6_bulan = get_6_months_data("BNBUSDT", "1h")
hasil = run_backtest_v8(data_6_bulan)
print("\n🏁 HASIL BACKTEST 6 BULAN (V8):")
print(hasil)
