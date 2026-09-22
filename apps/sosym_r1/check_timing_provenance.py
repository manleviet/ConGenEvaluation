#!/usr/bin/env python
"""Gate: refuse to build tables from timings measured on a shared machine.

Runtime is a REPORTED quantity in the SoSyM tables, so a cell measured while another job
held a core is not comparable with one measured alone. Nothing in the result filenames
carries that distinction and nothing should — the ledger records when every unit ran, so
the property is computable. This makes it enforced instead of remembered.

Two checks, and only the first is automatable from the record alone.

1. LEDGER x LEDGER. Two sweep units whose [started_utc, finished_utc] intervals overlap
   ran at the same time. The window lock is supposed to make this impossible; it held for
   the whole sweep (0 overlaps in 238 units at the time of writing), so any overlap means
   the lock was bypassed and the timings on both units are suspect.

2. LEDGER x NON-LEDGER. A unit can also share the machine with something the ledger never
   sees — a measurement re-run, a scoring pass, a probe. Those jobs are not in the record,
   so their intervals are listed below as DATA. They were recovered from the launch logs'
   creation and modification times under the session scratch directory, not from anyone's
   recollection; a future job must add its interval here or this check cannot see it.
   That is the honest limit of this gate and the reason the list is explicit rather than
   inferred.

THE ANSWER HAS A SHELF LIFE. A unit is only testable once it has BOTH timestamps, so a
unit still running is invisible to the overlap test and joins the contended set the moment
it finishes. Read at 01:30 this check said five units; read at 01:55, six — one fold had
closed its interval in between, under a job that was still running. Re-run it at the moment
the re-timing list is drawn up. A count carried over from an earlier run is a list that is
short by however many units finished since, and nothing downstream can tell.

AFTER the 6 contended units are re-timed sequentially this check is expected to pass with
nothing flagged. It is then a guard against recurrence, NOT leftover cleanup — do not
remove it because it reports nothing. Reporting nothing is the state it exists to protect.

    check_timing_provenance.py            # exit 1 if any unit's timing is contended
    check_timing_provenance.py --list     # show the non-ledger intervals and exit 0
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LEDGER = REPO / 'tools' / 'sosym_r1' / 'sweep-ledger.json'

# Jobs that ran outside the ledger, as (start, end, what). Times are Europe/Vienna local,
# converted below; recovered from the scratch launch logs' birth/modification times.
# APPEND to this list when running anything heavy alongside a sweep, or the gate goes blind.
NON_LEDGER_JOBS = [
    ('2026-08-27 18:02', '2026-08-27 20:13', 'NE-split re-run, 24 cells'),
    ('2026-08-27 23:41', '2026-08-27 23:45', 'run_compare scoring pass'),
    ('2026-08-27 23:51', '2026-08-28 02:02', 'attribution sweep, ordering reverted'),
    ('2026-08-28 02:04', '2026-08-28 02:10', 'run_compare scoring pass'),
    ('2026-08-28 09:21', '2026-08-28 11:51', 'busybox NE measurement, 3 cells'),
    ('2026-08-28 09:30', '2026-08-28 09:40', 'Reduce order-sensitivity study'),
    ('2026-08-28 12:29', '2026-08-29 01:06', 'busybox rs_1n NE measurement'),
]

_LOCAL_OFFSET_H = 2  # Europe/Vienna, CEST


def _local(text: str) -> datetime:
    return (datetime.fromisoformat(text)
            .replace(tzinfo=timezone.utc)).timestamp() - _LOCAL_OFFSET_H * 3600


def _utc(text: str) -> float:
    return datetime.fromisoformat(text.replace('Z', '+00:00')).timestamp()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--ledger', default=str(LEDGER))
    args = ap.parse_args()

    if args.list:
        print("non-ledger jobs on record:")
        for s, e, what in NON_LEDGER_JOBS:
            print(f"  {s} -> {e or '(open)':<16}  {what}")
        return 0

    raw = json.loads(Path(args.ledger).read_text()).get('units', {})
    all_units = [u for u in (raw.values() if isinstance(raw, dict) else raw)
                 if isinstance(u, dict) and u.get('started_utc')]
    units = [u for u in all_units if u.get('finished_utc')]
    # Started but not finished: no interval to test yet, so this check cannot see them.
    # They are named rather than skipped silently — a unit running right now alongside
    # something else will be contended, and leaving it out of the re-time list is the
    # error this gate exists to prevent.
    in_flight = [u['id'] for u in all_units if not u.get('finished_utc')]
    iv = [(_utc(u['started_utc']), _utc(u['finished_utc']), u['id']) for u in units]

    pairs = []
    for i, (s1, e1, a) in enumerate(iv):
        for s2, e2, b in iv[i + 1:]:
            if s1 < e2 and s2 < e1:
                pairs.append((a, b))

    now = datetime.now(timezone.utc).timestamp()
    external = []
    for s, e, what in NON_LEDGER_JOBS:
        js, je = _local(s), (_local(e) if e else now)
        for us, ue, uid in iv:
            if us < je and js < ue:
                external.append((uid, what))

    # external holds (unit, job) PAIRS — one unit can overlap several jobs — so the
    # re-time list is the DISTINCT units, not the pair count. Conflating the two would
    # silently shorten or lengthen that list, and nothing downstream would notice.
    contended = sorted({uid for uid, _ in external})
    print(f"units with a completed interval: {len(iv)}")
    print(f"ledger x ledger overlaps (pairs): {len(pairs)}")
    print(f"unit x non-ledger-job overlaps (pairs): {len(external)}")
    print(f"DISTINCT UNITS TO RE-TIME: {len(contended)}")
    for uid in contended:
        jobs = sorted({w for u, w in external if u == uid})
        print(f"  {uid}")
        for w in jobs:
            print(f"      <-> {w}")
    if in_flight:
        print(f"\nstill running, interval not yet closed — check again when they finish: "
              f"{len(in_flight)}")
        for uid in in_flight:
            print(f"  {uid}")
    for a, b in pairs:
        print(f"  OVERLAP {a}  <->  {b}")

    if pairs or contended or in_flight:
        print("\nFAIL: at least one unit's timing was measured on a shared machine. "
              "Re-time those units alone, or build the runtime table from the units that "
              "were not affected and say so.", file=sys.stderr)
        return 1
    print("\nOK: every timing comes from an exclusive run.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
