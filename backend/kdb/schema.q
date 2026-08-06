/ schema.q — Meridian's KDB-X tick store: schema + OHLCV aggregation
/
/ Loaded from Python via: kx.q(f'\l {path/to/schema.q}')
/ (or interactively: q schema.q)
/
/ NOTE ON TESTING: this q code follows standard, well-established kdb+/q
/ idiom (the `xbar` time-bucketing pattern below is the textbook way to
/ build OHLCV bars in kdb+) but was written and reviewed without access to
/ a running KDB-X instance -- verify it against your own install before
/ relying on it. See backend/app/kdb_tick_engine.py for the honest caveat
/ on the Python integration side too.

/ Tick table: one row per simulated trade
ticks:([] time:`timestamp$(); sym:`symbol$(); price:`float$(); volume:`long$())

/ Bulk-insert a batch of ticks. Called from Python as:
/   kx.q('insertTicks', kx.toq(df))
insertTicks:{[t] `ticks insert t}

/ Aggregate the tick table into OHLCV bars using kdb+'s `xbar` time-bucketing
/ operator -- this single line is doing the same work as the ~15-line pandas
/ groupby + custom aggregation function in tick_simulator.py's fallback path.
/ barSize is a q timespan, e.g. 0D00:01:00 for 1-minute bars.
ohlcvBars:{[barSize]
    select open:first price, high:max price, low:min price, close:last price,
           volume:sum volume, trades:count i
    by sym, bar:barSize xbar time
    from ticks
    }

/ Clears the tick table between benchmark runs so timings aren't skewed by
/ data left over from a previous request.
clearTicks:{[] delete from `ticks}

/ Row count, exposed for a quick sanity check from Python without pulling
/ the whole table across the IPC/embedded boundary.
tickCount:{[] count ticks}
