# Paper Trading Playbook

Run this stage for 1-3 months before any broker integration.

## Daily Checks

1. Confirm `watch` is running.
2. Review `data/logs/watch.log`.
3. Review new JSON files in `data/runs/`.
4. Add each actionable event to `data/paper_trades.csv`.

## Event Rules

- `MIXED` or confidence below 70: no paper trade unless manually overridden.
- `STRONG_NEGATIVE`: paper bearish options strategy only, never naked short.
- `STRONG_POSITIVE`: paper bullish equity/call strategy only after checking IV.
- Missing `questions`, `efficacy`, or `safety` sections: manual review required.
- FDA errata documents: update the existing event instead of creating a new thesis.

## Paper Trading Rules

- MIXED signals are observation-only.
- Confidence below 70 is observation-only.
- STRONG_NEGATIVE does not mean naked shorting.
- Negative signals must use defined-risk paper structures only.
- Record the briefing document release date.
- Track 1-day, 3-day, and 5-day reactions.
- Every paper trade must include a thesis and reject condition.
- The purpose is forward-testing, not live trading.

## Required Review Fields

- FDA top concerns
- FDA top positives
- Whether primary endpoint was met
- Whether safety issue can drive CRL or REMS
- Whether disease is rare/severe enough for regulatory flexibility
- Whether the final questions frame approval, uncertainty, or rejection

## Weekly Review

Every week, summarize:

- number of detected events
- number of actionable signals
- paper win/loss
- average reaction after 1 day and 5 days
- biggest model miss
- prompt or parser changes needed
