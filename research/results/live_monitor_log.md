# Live monitor log (demo #198874999, $5,000, Atlas evaluation)

time IST | processes | balance/equity | open | closed | faults
---|---|---|---|---|---
27 Oct 05:05 | ok (restarted on new alert format) | $5000.00 / $5000.00 | 0 | 0 | none; overnight gap 20:52-04:53 was PC sleep
27 Oct 05:16 | ok (3/3, heartbeat 13s) | $5000.00 / $5000.00 | 0 | 0 | none
27 Oct 05:48 | ok, restarted | $5000.00 / $5000.00 | 0 | 0 | FIXED: live Donchian used today's forming D1 bar (backtest uses completed days); test added. No Donchian setup today (close 4005.66 inside 3975-4199)
27 Oct 06:16 | ok (3/3, heartbeat 23s) | $5000.00 / $5000.00 | 0 | 0 | none; Donchian window: no setup (as predicted)
27 Oct 06:22 | ok | $5000.00 / $5000.00 | 0 | 0 | Donchian window: no signal, no block; no setup (close 4005.66 inside 3975.41-4198.81)
27 Oct 06:46 | ok (heartbeat 25s) | $5000.00 / $5000.00 | 0 | 0 | none
27 Oct 07:16 | ok (heartbeat 23s) | $5000.00 / $5000.00 | 0 | 0 | none
27 Oct 07:46 | ok (heartbeat 23s) | $5000.00 / $5000.00 | 0 | 0 | none
27 Oct 08:16 | ok (heartbeat 22s) | $5000.00 / $5000.00 | 0 | 0 | none
27 Oct 08:46 | ok (heartbeat 23s) | $5000.00 / $5000.00 | 0 | 0 | none
27 Oct 09:16 | ok (heartbeat 23s) | $5000.00 / $5000.00 | 0 | 0 | none
27 Oct 09:46 | ok (heartbeat 24s) | $5000.00 / $5000.00 | 0 | 0 | none
27 Oct 10:16 | ok (heartbeat 22s) | $5000.00 / $5000.00 | 0 | 0 | none
27 Oct 10:46 | ok (heartbeat 23s) | $5000.00 / $5000.00 | 0 | 0 | none
27 Oct 11:16 | ok (heartbeat 23s) | $5000.00 / $5000.00 | 0 | 0 | none
27 Oct 11:46 | ok (heartbeat 25s) | $5000.00 / $5000.00 | 0 | 0 | none
27 Oct 12:16 | ok (heartbeat 22s) | $5000.00 / $5000.00 | 0 | 0 | none
27 Oct 12:46 | ok (heartbeat 25s) | $5000.00 / $5000.00 | 0 | 0 | Asian window: no signal, no block; 07:00 UTC bar closed 4004.40 inside range 4000.02-4025.72 (no breakout)
27 Oct 13:16 | ok (heartbeat 26s) | $5000.00 / $5000.00 | 0 | 0 | 1 MT5 broker disconnect at 12:21 (single scan, auto-recovered); 12:45 Asian scan ran normally
27 Oct 13:46 | ok (heartbeat 33s) | $5000.00 / $5000.00 | 0 | 0 | internet outage ~13:28-13:36 (DNS failed, MT5 unresponsive); bot exited after 8 blind scans, watchdog restarted it, back up 13:37. No trades missed (no window)
27 Oct 14:16 | ok (heartbeat 33s) | $5000.00 / $5000.00 | 0 | 0 | none
27 Oct 14:46 | ok (heartbeat 33s) | $5000.00 / $5000.00 | 0 | 0 | 1 brief broker disconnect at 14:40 (single scan, auto-recovered)
27 Oct 15:16 | ok (heartbeat 33s) | $5000.00 / $5000.00 | 0 | 0 | 1 brief broker disconnect at 14:49 (single scan, auto-recovered)
27 Oct 15:46 | ok (heartbeat 21s) | $5000.00 / $5000.00 | 0 | 0 | MT5 terminal closed ~15:41 (no terminal64 process; likely user shutting down) - bot cannot trade until MT5 reopened; not relaunched
