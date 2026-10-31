# AlphaLens Batch 6U — Final Evidence Review

Status: **PARTIAL / NOT ACCEPTED as a 24-hour observation**.

The original Batch 6U resources were inspected separately from Batch 6Z. The retained evidence identifies PID `17902`, PostgreSQL `127.0.0.1:55446`, Redis `127.0.0.1:56394`, and checkpoint `/private/tmp/alphalens-batch6u-checkpoint-20261026.json`. No final report exists at the referenced `/private/tmp/alphalens-batch6u-report-20261026.json`, and the process/ports are no longer live.

The final retained checkpoint is:

- status: `READY`;
- sequence: `43`;
- last committed candle: `2026-10-26T21:05:00Z`;
- last error: none;
- missing interval: none;
- source dataset hash: `ab09e18c05fc8b2aa5ae1d7b4b1eb03839c1df3fef9969bf15f57809a1a1b48f`.

The supervised run began at approximately `2026-10-26T17:34:29Z`; sequence 43 was recorded at approximately `2026-10-26T21:10:00Z`, about 3 hours 35 minutes after start and well before the expected 24-hour endpoint (`2026-10-27T17:34:29Z`). The retained evidence therefore demonstrates genuine early closed-candle/checkpoint progression, but not 24-hour continuity, reconnect/restart recovery, final resource stability, final API/frontend evidence, or thesis/economic acceptance.

The separate short startup artifact is not substituted for this trial: it lasted 23.03 seconds, processed no finalized candle, and is labeled `alphalens.batch6t.public.binance.btcusdt.5m.operational.v1`.

Conclusion: Batch 6U is **not a PASS**. No replacement trial was started.
