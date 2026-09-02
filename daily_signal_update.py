"""
EURGBP Donchian(20) — baseline reversal system — daily forward-test signal logger.

Backtest: Sharpe 0.58, CAGR 3.5%, max DD -14.4%, profit factor 1.94
(2016-2026 daily data, single train/test split). Tested stop-losses,
trend filters, vol-sizing, and long-only variants — none beat this plain
baseline, so it's logged exactly as backtested: always in the market
(long or short), reversing directly at each Donchian breakout, no stops.

Run this once per day, after the EURGBP daily close (FX trades ~24hrs,
so "daily close" here means the standard 22:00 UTC / 17:00 EST FX day
rollover convention). It:
  1. Pulls yesterday's confirmed daily OHLC for EURGBP
  2. Computes the 20-day Donchian ceiling/floor
  3. Determines today's state: LONG, SHORT, or unchanged (reversal system —
     always in the market once the first signal fires)
  4. Appends a row to the persistent log CSV
  5. Sends a Telegram message with the signal
  6. Does NOT place any trades — logging only, for forward-test tracking

Requires env vars (set as GitHub Actions secrets):
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID

DATA SOURCE: Yahoo Finance (direct chart API, no key needed), ticker
"EURGBP=X" — the standard FX spot ticker. Should track your broker's
EURGBP quote closely (unlike the NAS100/QQQ mismatch earlier), since FX
spot rates are far more standardized across venues than index CFDs are.
"""
import os
import json
import requests
import pandas as pd
from pathlib import Path

LOG_PATH = Path(__file__).parent / "eurgbp_signal_log.csv"
STATE_PATH = Path(__file__).parent / "eurgbp_state.json"

DONCHIAN_LOOKBACK = 20

TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

SYMBOL = os.environ.get("SIGNAL_SYMBOL", "EURGBP=X")


def fetch_latest_daily_bar(symbol):
    """Pull the most recent confirmed daily OHLC bar from Yahoo Finance's
    public chart API (no key required)."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"range": "3mo", "interval": "1d"}  # need enough history for context, though rolling calc uses the log
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, params=params, headers=headers, timeout=15)
    r.raise_for_status()
    data = r.json()

    result = data.get("chart", {}).get("result")
    if not result:
        raise RuntimeError(f"Yahoo Finance error: {data}")

    result = result[0]
    timestamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]
    closes, highs, lows = quote["close"], quote["high"], quote["low"]

    valid_idx = [i for i in range(len(closes)) if closes[i] is not None]
    if len(valid_idx) < 1:
        raise RuntimeError("No confirmed daily bars returned from Yahoo Finance")

    latest_i = valid_idx[-1]
    latest_date = pd.to_datetime(timestamps[latest_i], unit="s").strftime("%Y-%m-%d")

    return {
        "date": latest_date,
        "close": float(closes[latest_i]),
        "high": float(highs[latest_i]),
        "low": float(lows[latest_i]),
    }


def load_log():
    if LOG_PATH.exists():
        return pd.read_csv(LOG_PATH, parse_dates=["date"])
    raise FileNotFoundError(f"{LOG_PATH} not found. Seed it before first run.")


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    log = load_log()
    return {"state": int(log.iloc[-1]["state"])}


def send_telegram(msg):
    if not TG_TOKEN or not TG_CHAT_ID:
        print("[warn] Telegram not configured, skipping alert. Message was:\n" + msg)
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "Markdown"})


def main():
    log = load_log()
    state_data = load_state()
    prev_state = state_data["state"]

    bar = fetch_latest_daily_bar(SYMBOL)

    if pd.to_datetime(bar["date"]) in set(log["date"]):
        print(f"{bar['date']} already logged, skipping.")
        return

    # rolling 20-day ceiling/floor, using logged history + today's bar
    recent_closes = pd.concat([log["close"], pd.Series([bar["close"]])], ignore_index=True)
    ceiling = recent_closes.tail(DONCHIAN_LOOKBACK).max()
    floor = recent_closes.tail(DONCHIAN_LOOKBACK).min()
    close = bar["close"]

    # reversal system: always in the market once triggered, flips directly
    new_state = prev_state
    action = "HOLD"
    if close >= ceiling:
        new_state = -1
        action = "REVERSE TO SHORT" if prev_state == 1 else ("ENTER SHORT" if prev_state == 0 else "HOLD SHORT")
    elif close <= floor:
        new_state = 1
        action = "REVERSE TO LONG" if prev_state == -1 else ("ENTER LONG" if prev_state == 0 else "HOLD LONG")
    else:
        action = {1: "HOLD LONG", -1: "HOLD SHORT", 0: "FLAT"}[prev_state]

    row = {
        "date": bar["date"], "close": close,
        "donchian_ceiling_20d": ceiling, "donchian_floor_20d": floor,
        "state": new_state,
    }
    log = pd.concat([log, pd.DataFrame([row])], ignore_index=True)
    log.to_csv(LOG_PATH, index=False)
    STATE_PATH.write_text(json.dumps({"state": new_state}))

    msg = (
        f"*EURGBP Donchian(20) Signal — {bar['date']}*\n"
        f"Close: {close:.5f}\n"
        f"Ceiling: {ceiling:.5f} | Floor: {floor:.5f}\n"
        f"Action: *{action}*\n"
        f"_(signal log only — no trades placed)_"
    )
    send_telegram(msg)
    print(msg)


if __name__ == "__main__":
    main()
