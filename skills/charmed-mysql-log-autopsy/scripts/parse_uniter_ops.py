#!/usr/bin/env python3
"""Parse juju uniter operation lifecycle lines from a debug-log file.

Reads a `juju debug-log` capture (or an extracted bundle's debug-log.txt)
and reports per-operation durations, inter-operation gaps, and continuous
busy stretches for one or more units. Used to diagnose "unit never settles
idle" timeouts: if operation duration approaches the dispatch tick period,
the uniter queue saturates and idle gaps collapse to ~0s.

Usage:
    python3 parse_uniter_ops.py <debug-log.txt> [--unit NAME] [--merge-gap SECS]

`--unit` filters to one unit (default: all units found, merged).
`--merge-gap` merges operations whose inter-op gap is <= SECS seconds
(default 10) into continuous busy stretches.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime

# Matches:  2026-07-13 15:48:59 DEBUG juju.worker.uniter.operation
#           preparing operation "run commands" for target/0
LINE = re.compile(
    r"^(?P<src>[\w.-]+):\s+(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+"
    r"DEBUG juju\.worker\.uniter\.operation\s+"
    r"(?P<phase>preparing|executing|committing) operation \"(?P<op>[^\"]+)\" "
    r"for (?P<unit>[\w/.-]+)"
)

TS_FMT = "%Y-%m-%d %H:%M:%S"


def parse(path: str):
    """Yield (start_ts, end_ts, op_name, unit) for each completed operation."""
    pending = {}  # unit -> (ts, op)
    for line_no, line in enumerate(open(path, errors="replace"), 1):
        m = LINE.match(line)
        if not m:
            continue
        unit, phase = m.group("unit"), m.group("phase")
        ts = datetime.strptime(m.group("ts"), TS_FMT)
        op = m.group("op")
        if phase == "executing":
            pending[unit] = (ts, op, line_no)
        elif phase == "committing" and pending.get(unit):
            start, pop, line_no0 = pending.pop(unit)
            if pop == op:  # commit for the operation we tracked
                yield start, ts, op, unit
            else:
                print(
                    f"warning: line {line_no}: commit for {op!r} but pending "
                    f"was {pop!r} (line {line_no0}) — operation skipped",
                    file=sys.stderr,
                )
                pending[unit] = (start, op, line_no0)


def fmt_delta(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 60}m{seconds % 60:02d}s" if seconds >= 60 else f"{seconds}s"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("logfile")
    ap.add_argument("--unit", default=None, help="filter by unit name (e.g. target/0)")
    ap.add_argument(
        "--merge-gap",
        type=float,
        default=10.0,
        help="merge ops with gaps <= this many seconds into busy stretches (default 10)",
    )
    args = ap.parse_args()

    ops = [o for o in parse(args.logfile) if args.unit is None or o[3] == args.unit]
    if not ops:
        print("No uniter operation lifecycle lines found.", file=sys.stderr)
        print(
            "Note: RunCommands lines are absent on some rigs; absence here does "
            "not prove absence of scheduled dispatches.",
            file=sys.stderr,
        )
        return 1

    ops.sort()
    print(f"{len(ops)} operations parsed from {args.logfile}")
    print(f"{'start':<19} {'end':<19} {'dur':>7}  {'gap before':>10}  op  unit")
    prev_end = None
    merged = []
    for start, end, op, unit in ops:
        gap = (start - prev_end).total_seconds() if prev_end else 0.0
        print(
            f"{start:%Y-%m-%d %H:%M:%S} {end:%Y-%m-%d %H:%M:%S} "
            f"{fmt_delta((end - start).total_seconds()):>7}  "
            f"{fmt_delta(gap):>10}  {op}  {unit}"
        )
        if prev_end is not None and gap <= args.merge_gap and merged:
            last = merged[-1]
            if (start - last[1]).total_seconds() <= args.merge_gap:
                merged[-1] = (last[0], max(end, last[1]), last[2] + 1)
                prev_end = end
                continue
        merged.append((start, end, 1))
        prev_end = end

    print(f"\nContinuous busy stretches (gaps <= {fmt_delta(args.merge_gap)}):")
    for start, end, count in merged:
        dur = (end - start).total_seconds()
        print(
            f"  {start:%H:%M:%S} → {end:%H:%M:%S}  {fmt_delta(dur)}  "
            f"({count} operation{'s' if count != 1 else ''})"
        )
    total_busy = sum((e - s).total_seconds() for s, e, _ in merged)
    span = (ops[-1][1] - ops[0][0]).total_seconds() or 1
    print(f"\nBusy fraction: {total_busy / span:.0%} over {fmt_delta(span)}")
    longest = max((e - s).total_seconds() for s, e, _ in merged)
    print(f"Longest continuous executing stretch: {fmt_delta(longest)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
