# EURGBP Donchian(20) — Forward Test (Fresh Start)

Baseline reversal system, no filters. Backtest: Sharpe 0.58, CAGR 3.5%,
max DD -14.4%, profit factor 1.94 (2016-2026 daily). Tested stop-losses,
trend filters, vol-sizing, and long-only variants — none beat this plain
version, so it's logged exactly as backtested.

**This is a signal logger only. It places no trades.**

## How the system works

- Always in the market once triggered (long or short) — a REVERSAL
  system, not enter/exit-to-flat. Price touching the 20-day high flips
  to short; touching the 20-day low flips to long. No stop-loss (tested,
  made it worse), no trend filter (tested, made it worse).

## Fresh start

`eurgbp_signal_log.csv` is seeded with price/Donchian history (needed
so day one isn't a cold start), but the **position state is reset to 0
(flat)** — not inherited from the backtest. The first real signal is
decided live, going forward, matching the same honest approach as the
NAS100 forward test.

## Setup (same pattern as nas100-pivot-signal)

1. Push this folder as a new GitHub repo.
2. Add repo secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (reuse from your NAS100 repo).
3. Settings → Actions → General → Workflow permissions → "Read and write permissions" → Save (needed for the daily commit-back step).
4. Actions tab → "EURGBP Donchian Signal Log" → Run workflow (manual test first).
5. Once green, it runs automatically every weekday after the FX daily close.

## Data source

Yahoo Finance, ticker `EURGBP=X` — the standard FX spot ticker. FX spot
rates are far more standardized across venues than index CFDs, so this
should track your broker's EURGBP quote more closely than the NAS100/QQQ
situation did — but still verify against your own chart once live.

## Files

- `daily_signal_update.py` — the daily job
- `eurgbp_signal_log.csv` — persistent log (price/Donchian history seeded, state reset to flat)
- `eurgbp_state.json` — current position (-1 short, 0 flat, 1 long), reset to 0
- `.github/workflows/eurgbp_signal.yml` — the cron job
