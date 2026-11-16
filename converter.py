# converter.py
"""Orchestrates: source text --parser--> IR --writer--> target text."""
from pathlib import Path

from dialects.fanuc_ares.parser import FanucAresParser
from dialects.fanuc_ares.writer import FanucAresWriter
from dialects.fanuc_grimme.parser import FanucGrimmeParser
from dialects.fanuc_grimme.writer import FanucGrimmeWriter
from dialects.num_grimme.parser import NumGrimmeParser
from dialects.num_grimme.writer import NumGrimmeWriter
import math
import warnings
from dataclasses import dataclass, field
from core.ir import (Absolute, AbsoluteMode, CircularMove, LinearMove, Operation, RapidMove,
                     Rewind, ToolCompensation)

# To add a dialect: create dialects/<name>/{mapping,parser,writer}.py and register it here.
DIALECTS = {
    "fanuc-ares": (FanucAresParser, FanucAresWriter),
    "num-grimme": (NumGrimmeParser, NumGrimmeWriter),
    "fanuc-grimme": (FanucGrimmeParser, FanucGrimmeWriter),
}

MOVES = (RapidMove, LinearMove, CircularMove)
FEEDS = (LinearMove, CircularMove)

# Rotary limits of each target machine (degrees). "b" only if the head tilts both ways:
# then C can also move 180° by flipping the sign of B.
# ARES: CMS spec sheet (C ±270, B ±120). TODO: confirm on our machine.
ROTARY_LIMITS = {
    "fanuc-ares": {"c": (-270.0, 270.0), "b": (-120.0, 120.0)},
}


@dataclass
class _Cut:
    start: int                        # first block of the cut
    end: int                          # one past its last block
    air: tuple | None                 # (x, y, z, b, c) in the air just before it, if a rewind can go there
    bs: list = field(default_factory=list)
    cs: list = field(default_factory=list)

def fit_rotary(program: list[list[Operation]], limits: dict) -> None:
    """Moves C into the machine's range without changing where the tool points.
    C + 360 is the same orientation; C + 180 with -B too (head tilting the other way).
    Normally one shift fits the whole program. If not, C changes between cuts: at an
    operation change for free, otherwise with a Rewind in the air.
    A warning says when the program was outside the limits and how it was fixed."""
    cuts = _split_cuts(program)
    shifts = _choose_shifts(cuts, limits)
    lo, hi = limits["c"]
    cs = [c for cut in cuts for c in cut.cs]          # C before shifting
    rewinds = 0
    for n in reversed(range(len(cuts))):          # backwards: inserting keeps the earlier indexes valid
        cut, shift = cuts[n], shifts[n]
        flip = shift % 360 != 0
        for block in program[cut.start:cut.end]:
            for op in block:
                if isinstance(op, MOVES):
                    if op.c is not None:
                        op.c += shift
                    if flip and op.b is not None:
                        op.b = 0.0 - op.b         # 0.0 - x avoids writing B-0.
        if n > 0 and shift != shifts[n - 1] and cut.air:
            x, y, z, b, c = cut.air
            b = 0.0 - b if flip and b is not None else b
            program.insert(cut.start, [Rewind(x, y, z, b, c + shift)])
            rewinds += 1
    if cs and (min(cs) < lo or max(cs) > hi):
        used = ", ".join(f"{s:+d}" for s in sorted(set(shifts)))
        changes = sum(a != b for a, b in zip(shifts, shifts[1:]))
        warnings.warn(f"C goes from {min(cs):.3f} to {max(cs):.3f}, outside {lo}..{hi}. "
                      f"Fixed with C shift(s) {used} (180 inverts B): {changes} change(s) "
                      f"between cuts, {rewinds} of them with a rewind", stacklevel=2)

def _split_cuts(program: list[list[Operation]]) -> list[_Cut]:
    """Cuts the program where C is allowed to change:
    - an operation change (tool compensation in the air moves): the program goes to its own
      safety point there, so no rewind is needed;
    - the air moves at the program's safety height (the highest point it goes up to between
      cuts, Z240 in 0022613): a rewind can go after any of them.
    Anywhere else the tool may be close to the part, so the cuts stay together."""
    # Modal x, y, z, b, c after each block
    state, states = [None] * 5, []
    for block in program:
        for op in block:
            if isinstance(op, MOVES):
                for i, value in enumerate((op.x, op.y, op.z, op.b, op.c)):
                    if value is not None:
                        state[i] = value
        states.append(tuple(state))

    # Air moves: the blocks between two cutting moves
    runs, air, cutting = [], [], False
    for i, block in enumerate(program):
        if any(isinstance(op, FEEDS) for op in block):
            if cutting and air:
                runs.append(air)
            cutting, air = True, []
        elif cutting:
            air.append(i)

    def has(j: int, kind) -> bool:
        return any(isinstance(op, kind) for op in program[j])

    def height(run: list[int]) -> float | None:
        return max((states[j][2] for j in run if any(isinstance(op, RapidMove) and op.z is not None
                                                     for op in program[j])), default=None)

    in_operation = [run for run in runs if not any(has(j, ToolCompensation) for j in run)]
    safe_z = max((h for h in map(height, in_operation) if h is not None), default=None)

    starts = [(0, None)]
    for run in runs:
        tool_change = [j for j in run if has(j, ToolCompensation)]
        if tool_change:
            starts.append((tool_change[0], None))
        elif safe_z is not None and height(run) == safe_z:
            starts += [(j + 1, states[j]) for j in run if states[j][2] == safe_z]

    cuts = []
    for (start, before), (end, _) in zip(starts, starts[1:] + [(len(program), None)]):
        cut = _Cut(start, end, before)
        if before:                                 # the cut starts with this orientation
            cut.bs += [before[3]] if before[3] is not None else []
            cut.cs += [before[4]] if before[4] is not None else []
        for block in program[start:end]:
            for op in block:
                if isinstance(op, MOVES):
                    cut.bs += [op.b] if op.b is not None else []
                    cut.cs += [op.c] if op.c is not None else []
        cuts.append(cut)
    return cuts


def _choose_shifts(cuts: list[_Cut], limits: dict) -> list[int]:
    """One shift per cut. The same shift is kept for as many cuts in a row as possible,
    so C changes (and rewinds) as few times as possible."""
    lo, hi = limits["c"]
    step = 180 if "b" in limits else 360

    def fits(cut: _Cut, shift: int) -> bool:
        if not all(lo <= c + shift <= hi for c in cut.cs):
            return False
        if shift % 360 == 0:
            return True
        b_lo, b_hi = limits["b"]
        return all(b_lo <= -b <= b_hi for b in cut.bs)

    def run(n: int, shift: int) -> int:           # how many cuts in a row fit with this shift
        k = n
        while k < len(cuts) and fits(cuts[k], shift):
            k += 1
        return k - n

    shifts = []
    while len(shifts) < len(cuts):
        n, cut = len(shifts), cuts[len(shifts)]
        ks = range(math.ceil((lo - min(cut.cs)) / step), math.floor((hi - max(cut.cs)) / step) + 1) if cut.cs else [0]
        options = [s for s in sorted((k * step for k in ks), key=abs) if fits(cut, s)]
        if not options:
            raise ValueError(f"C goes from {min(cut.cs):.3f} to {max(cut.cs):.3f} without going up to the "
                             f"safety height: it does not fit in {lo}..{hi}, not even with rewinds. "
                             f"Split that cut in the CAM.")
        best = max(options, key=lambda s: run(n, s))   # ties: the smallest change (first in options)
        shifts += [best] * run(n, best)
    return shifts


# ---------------------------------------------------------------- rotary axes
# ARES (B/C) and Grimme (A/C) tilt differently, so the same orientation has other
# numbers on each machine. The IR keeps the source machine's numbers; they are
# converted here because only here are both machines known.

def ares_to_grimme(b: float, c: float | None) -> tuple[float, float | None]:
    """Rule confirmed with real programs: A = -|B| ; C + 90 if B < 0 ; C - 90 if B > 0 ; C same if B = 0."""
    if b == 0:
        return 0.0, c
    return -abs(b), (c + 90 if b < 0 else c - 90)


def grimme_to_ares(a: float, c: float | None) -> tuple[float, float | None]:
    """Inverse: B = A ; C - 90 if A != 0 ; C same if A = 0.
    Exact inverse for A < 0. A > 0 (only in Grimme's own programs) gives B > 0,
    the equivalent orientation."""
    if a == 0:
        return 0.0, c
    return a, c - 90


def convert_rotary(program: list[list[Operation]], rule) -> None:
    """Applies a rotary rule to every move with B/C (IR 'b' = ARES B / Grimme A).
    Both axes are modal: a block with only one of them uses the last value of the other.
    Both are always written together, because a change of one can also change the other."""
    b = c = None
    absolute = True
    for block in program:
        for op in block:
            if isinstance(op, Absolute):
                absolute = op.mode is AbsoluteMode.ABSOLUTE
            if not isinstance(op, (RapidMove, LinearMove, CircularMove)) or (op.b is None and op.c is None):
                continue
            if not absolute:
                raise ValueError(f"Rotary axes in incremental mode (G91) cannot be converted: {op}")
            b = op.b if op.b is not None else b
            c = op.c if op.c is not None else c
            if b is None or (c is None and b != 0):
                raise ValueError(f"Rotary conversion needs the last value of both rotary axes: {op}")
            op.b, op.c = rule(b, c)


ROTARY_RULES = {
    ("fanuc-ares", "num-grimme"): ares_to_grimme,
    ("fanuc-ares", "fanuc-grimme"): ares_to_grimme,
    ("num-grimme", "fanuc-ares"): grimme_to_ares,
    ("fanuc-grimme", "fanuc-ares"): grimme_to_ares,
}


def convert(text: str, source_dialect: str, target_dialect: str) -> str:
    parser_cls, _ = DIALECTS[source_dialect]
    _, writer_cls = DIALECTS[target_dialect]
    sections = parser_cls().parse_sections(text)
    rotary_rule = ROTARY_RULES.get((source_dialect, target_dialect))
    if rotary_rule:
        # The header too: the last B/C (A/C) set there is still active in the body
        convert_rotary(sections.header + sections.body, rotary_rule)

    limits = ROTARY_LIMITS.get(target_dialect)

    if limits:
        fit_rotary(sections.body, limits)
    return writer_cls().write(sections.body)


def read_file(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def write_file(path: str | Path, text: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text + "\n", encoding="utf-8")


def dump_ir(text: str, source_dialect: str, output: str | Path) -> None:
    """Debug: one IR block per line."""
    parser_cls, _ = DIALECTS[source_dialect]
    write_file(output, "\n".join(str(block) for block in parser_cls().parse(text)))


if __name__ == "__main__":
    # Quick manual test: converts every example into every dialect (same dialect = round trip), in ./output
    examples = [
        ("examples/fanuc_ares.nc", "fanuc-ares"),
        ("examples/num_grimme.xpi", "num-grimme"),
        ("examples/Plate_NUM_GRIMME.XPI", "num-grimme"),
        ("examples/Platte_FANUC_GRIMME.nc", "fanuc-grimme"),
        ("examples/WRIGHTBUS PMF-00224.nc", "fanuc-ares"),
        ("examples/XL02-05-029-03-P-REV-C.nc", "fanuc-ares"),
        ("examples/403-P1763-TrimTool.xpi", "num-grimme"),
        ("examples/0022613-2 Rev-B.xpi", "num-grimme"),
        ("examples/0022613-1 Rev-B.xpi", "num-grimme"),
        ("examples/PCG-02129-Rev-1.xpi", "num-grimme")
    ]

    examples = [
        ("examples/0018008-2_Rev - C.xpi", "num-grimme"),
    ]

    extension = {"fanuc-ares": "nc", "fanuc-grimme": "nc", "num-grimme": "xpi"}

    for source, src in examples:
        for dst in DIALECTS:
            target = f"test/{Path(source).stem}_to_{dst}.{extension[dst]}"
            result = convert(read_file(source), src, dst)
            write_file(target, result)
            unmapped = result.count("UNMAPPED")
            print(f"{source} ({src}) -> {target} ({dst}): {len(result.splitlines())} lines, {unmapped} UNMAPPED")
