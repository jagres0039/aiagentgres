import sys
sys.path.insert(0, '/root/aiagent')
import requests
import pandas as pd
from datetime import datetime

# ==========================================
# CONFIG BACKTEST
# ==========================================
TOTAL_MODAL = 100
RESIKO_PERSEN = 1.0
LEVERAGE = 5
PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "SUIUSDT"]

# Mode: "scalping" (15m) atau "swing" (4h)
TRADING_MODE = "scalping"

if TRADING_MODE == "scalping":
    TIMEFRAME = "15m"
    ATR_MULT = 1.5
    RSI_LONG_MIN, RSI_LONG_MAX = 45, 65
    RSI_SHORT_MIN, RSI_SHORT_MAX = 35, 55
else:
    TIMEFRAME = "4h"
    ATR_MULT = 2.5
    RSI_LONG_MIN, RSI_LONG_MAX = 50, 70
    RSI_SHORT_MIN, RSI_SHORT_MAX = 30, 50

# ==========================================
# DATA
# ==========================================
def get_binance_data(sym, interval, limit=1000):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": sym, "interval": interval, "limit": limit}
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        if isinstance(data, dict):
            return None
        df = pd.DataFrame(data, columns=['ts','o','h','l','c','v','ct','qa','nt','tb','tq','i'])
        df[['o','h','l','c','v']] = df[['o','h','l','c','v']].astype(float)
        df['ts'] = pd.to_datetime(df['ts'], unit='ms')
        return df
    except:
        return None

# ==========================================
# BACKTEST ENGINE
# ==========================================
def backtest(symbol: str) -> dict:
    df = get_binance_data(symbol, TIMEFRAME, limit=1000)
    if df is None or len(df) < 200:
        return None

    # Indicators
    df['ema_9'] = df['c'].ewm(span=9, adjust=False).mean()
    df['ema_21'] = df['c'].ewm(span=21, adjust=False).mean()
    df['ema_200'] = df['c'].ewm(span=200, adjust=False).mean()
    delta = df['c'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / loss)))
    df['atr'] = (df['h'] - df['l']).rolling(14).mean()
    df['vol_ma'] = df['v'].rolling(20).mean()
    df['cross_up'] = (df['ema_9'] > df['ema_21']) & (df['ema_9'].shift(1) <= df['ema_21'].shift(1))
    df['cross_down'] = (df['ema_9'] < df['ema_21']) & (df['ema_9'].shift(1) >= df['ema_21'].shift(1))

    # Backtest
    trades = []
    modal = TOTAL_MODAL
    peak_modal = TOTAL_MODAL

    for i in range(210, len(df)-1):
        curr = df.iloc[i]
        price = curr['c']

        candle_range = curr['h'] - curr['l']
        is_solid = candle_range > 0 and (abs(curr['c'] - curr['o']) >= candle_range * 0.5)
        vol_up = curr['v'] > df.iloc[i-1]['v']
        is_bullish = curr['c'] > curr['o']

        signal = None
        entry = sl = tp = None

        # LONG
        if (price > curr['ema_200'] and curr['cross_up'] and
                RSI_LONG_MIN < curr['rsi'] < RSI_LONG_MAX and
                is_solid and vol_up):
            signal = "LONG"
            entry = price
            sl = entry - (curr['atr'] * ATR_MULT)
            tp = entry + (entry - sl)

        # SHORT
        elif (price < curr['ema_200'] and curr['cross_down'] and
              RSI_SHORT_MIN < curr['rsi'] < RSI_SHORT_MAX and
              is_solid and not is_bullish and vol_up):
            signal = "SHORT"
            entry = price
            sl = entry + (curr['atr'] * ATR_MULT)
            tp = entry - (sl - entry)

        if not signal:
            continue

        # Simulasi exit — cek candle berikutnya sampai kena SL/TP
        result = "RUNNING"
        exit_price = None
        exit_idx = None

        for j in range(i+1, min(i+50, len(df))):
            future = df.iloc[j]
            if signal == "LONG":
                if future['l'] <= sl:
                    result = "LOSS"
                    exit_price = sl
                    exit_idx = j
                    break
                elif future['h'] >= tp:
                    result = "WIN"
                    exit_price = tp
                    exit_idx = j
                    break
            else:  # SHORT
                if future['h'] >= sl:
                    result = "LOSS"
                    exit_price = sl
                    exit_idx = j
                    break
                elif future['l'] <= tp:
                    result = "WIN"
                    exit_price = tp
                    exit_idx = j
                    break

        if result == "RUNNING":
            continue

        # Kalkulasi PnL
        jarak_sl_pct = abs(entry - sl) / entry * 100
        resiko_usd = modal * (RESIKO_PERSEN / 100)
        position_size = resiko_usd / (jarak_sl_pct / 100) if jarak_sl_pct > 0 else 0

        if result == "WIN":
            pnl = resiko_usd * LEVERAGE
        else:
            pnl = -resiko_usd

        modal += pnl
        if modal > peak_modal:
            peak_modal = modal

        trades.append({
            "symbol": symbol,
            "signal": signal,
            "entry": round(entry, 4),
            "exit": round(exit_price, 4),
            "result": result,
            "pnl": round(pnl, 2),
            "modal": round(modal, 2),
            "date": curr['ts'].strftime("%Y-%m-%d %H:%M"),
        })

    if not trades:
        return None

    wins = [t for t in trades if t['result'] == "WIN"]
    losses = [t for t in trades if t['result'] == "LOSS"]
    total_profit = sum(t['pnl'] for t in wins)
    total_loss = sum(t['pnl'] for t in losses)
    net_pnl = total_profit + total_loss
    win_rate = (len(wins) / len(trades) * 100) if trades else 0
    max_dd = round(((peak_modal - modal) / peak_modal * 100), 2) if peak_modal > 0 else 0

    return {
        "symbol": symbol,
        "total_trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 2),
        "total_profit": round(total_profit, 2),
        "total_loss": round(total_loss, 2),
        "net_pnl": round(net_pnl, 2),
        "final_modal": round(modal, 2),
        "max_drawdown": max_dd,
        "best_trade": round(max((t['pnl'] for t in trades), default=0), 2),
        "worst_trade": round(min((t['pnl'] for t in trades), default=0), 2),
        "trades": trades[-5:],  # 5 trade terakhir
    }

# ==========================================
# MAIN
# ==========================================
def run_backtest():
    print(f"\n{'='*50}")
    print(f"  GODZILLA BACKTEST ENGINE")
    print(f"  Mode: {TRADING_MODE.upper()} | TF: {TIMEFRAME}")
    print(f"  Modal: ${TOTAL_MODAL} | Risk: {RESIKO_PERSEN}%")
    print(f"  Leverage: {LEVERAGE}x")
    print(f"{'='*50}\n")

    all_results = []

    for pair in PAIRS:
        print(f"Backtesting {pair}...")
        result = backtest(pair)

        if not result:
            print(f"  {pair}: Data tidak cukup\n")
            continue

        all_results.append(result)

        emoji = "✅" if result['net_pnl'] > 0 else "❌"
        print(f"\n{emoji} {result['symbol']}")
        print(f"  Total Trade : {result['total_trades']}")
        print(f"  Win/Loss    : {result['wins']}/{result['losses']}")
        print(f"  Win Rate    : {result['win_rate']}%")
        print(f"  Total Profit: ${result['total_profit']}")
        print(f"  Total Loss  : ${result['total_loss']}")
        print(f"  Net PnL     : ${result['net_pnl']}")
        print(f"  Final Modal : ${result['final_modal']}")
        print(f"  Max DD      : {result['max_drawdown']}%")
        print(f"  Best Trade  : ${result['best_trade']}")
        print(f"  Worst Trade : ${result['worst_trade']}")

    # Summary semua pairs
    if all_results:
        total_trades = sum(r['total_trades'] for r in all_results)
        total_wins = sum(r['wins'] for r in all_results)
        total_net = sum(r['net_pnl'] for r in all_results)
        avg_wr = sum(r['win_rate'] for r in all_results) / len(all_results)

        print(f"\n{'='*50}")
        print(f"  SUMMARY SEMUA PAIRS")
        print(f"{'='*50}")
        print(f"  Total Trade : {total_trades}")
        print(f"  Total Win   : {total_wins}")
        print(f"  Avg Win Rate: {avg_wr:.2f}%")
        print(f"  Total Net   : ${total_net:.2f}")
        print(f"  Modal Awal  : ${TOTAL_MODAL}")
        print(f"  ROI         : {(total_net/TOTAL_MODAL*100):.2f}%")
        print(f"{'='*50}\n")

if __name__ == "__main__":
    run_backtest()
