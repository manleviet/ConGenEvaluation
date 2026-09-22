"""The frozen vocabulary every paper table shares.

FROZEN means frozen. The knowledge bases are printed as $KB_1$..$KB_5$ and that
numbering is cited in the paper's prose; renumbering it would silently move every
sentence that names a KB. The sampling order is the paper's reading order and is
the same in every table, so a reader comparing two tables compares rows that line up.

Neither list is derived from the filesystem. Deriving them would make the tables
follow whatever happens to be on disk -- a unit that failed to run would vanish
from the table rather than appear as ``n/a``, and an absence that renders as a
missing row is indistinguishable from a unit that was never planned.
"""
from __future__ import annotations

# (stem on disk, label in the paper, short name the caption uses, domain)
#
# The domain column is editorial: it is nowhere in the data, and inventing it from
# a file name would be worse than declaring it. It is declared here so that the one
# hand-written column in the whole table set lives in exactly one place.
KNOWLEDGE_BASES: tuple[tuple[str, str, str, str], ...] = (
    ("REAL-FM-7",      r"$KB_1$", "REAL-FM-7", "IDE plugins"),
    ("fqa",            r"$KB_2$", "FQA",       "quality attributes"),
    ("arcade-game",    r"$KB_3$", "Arcade",    "arcade game SPL"),
    ("REAL-FM-4",      r"$KB_4$", "REAL-FM-4", "e-shop"),
    ("busybox-1.18.0", r"$KB_5$", "BusyBox",   "embedded Unix tool suite"),
)

KB_STEMS: tuple[str, ...] = tuple(k[0] for k in KNOWLEDGE_BASES)
KB_LABELS: tuple[str, ...] = tuple(k[1] for k in KNOWLEDGE_BASES)

# (stem on disk, label in the paper)
SAMPLINGS: tuple[tuple[str, str], ...] = (
    ("rs_1n", r"RS($n$)"),
    ("rs_2n", r"RS($2n$)"),
    ("rs_3n", r"RS($3n$)"),
    ("rs_m",  r"RS($m$)"),
    ("2cov",  r"2-COV"),
    ("ff",    r"FF"),
)

SAMPLING_STEMS: tuple[str, ...] = tuple(s[0] for s in SAMPLINGS)

# Units that were never run. Declared, not inferred from a missing file: a unit
# absent because it was never run and a unit absent because a result was lost
# look identical on disk, and only one of them is honest to print as ``n/a``.
#
# busybox RS(2n)/RS(3n): a single RS(n) fold on busybox is 4.1-4.3 h, and the
# REAL-FM-4 growth factors (3.6x to RS(2n), 8.3x to RS(3n)) put three folds of
# each at roughly two and four days. The paper says so in the setup section.
NOT_RUN: frozenset[tuple[str, str]] = frozenset({
    ("busybox-1.18.0", "rs_2n"),
    ("busybox-1.18.0", "rs_3n"),
})

# The two cell markers. Generated, never typed, and never a zero: a zero is a
# measurement and both of these are the absence of one.
NA = r"n/a"          # the unit was not run
UNDEFINED = r"--"    # the unit ran, but this quantity is not defined there

# The three comparison tiers, in the order the paper introduces them.
TIERS: tuple[tuple[str, str], ...] = (
    ("description", "Desc"),
    ("clause", "Clause"),
    ("semantic", "Sem"),
)

# The two iterative-baseline modes, in the paper's order, plus ConGen itself.
MODES: tuple[str, ...] = ("example_only", "example_first")
METHODS: tuple[tuple[str, str], ...] = (
    ("congen", r"\textsc{ConGen}"),
    ("example_only", "example-only"),
    ("example_first", "example-first"),
)

# Rule learners, in the order the baselines runner reports them.
LEARNERS: tuple[tuple[str, str], ...] = (
    ("ripper", "RIPPER"),
    ("cn2", "CN2"),
    ("decision_tree", "Decision tree"),
)


def is_not_run(stem: str, sampling: str) -> bool:
    return (stem, sampling) in NOT_RUN
