# converter.py
"""Orchestrates: source text --parser--> IR --writer--> target text."""
from pathlib import Path

from core.ir import Absolute, AbsoluteMode, CircularMove, LinearMove, Operation, RapidMove
from dialects.fanuc_ares.parser import FanucAresParser
from dialects.fanuc_ares.writer import FanucAresWriter
from dialects.fanuc_grimme.parser import FanucGrimmeParser
from dialects.fanuc_grimme.writer import FanucGrimmeWriter
from dialects.num_grimme.parser import NumGrimmeParser
from dialects.num_grimme.writer import NumGrimmeWriter

# To add a dialect: create dialects/<name>/{mapping,parser,writer}.py and register it here.
DIALECTS = {
    "fanuc-ares": (FanucAresParser, FanucAresWriter),
    "num-grimme": (NumGrimmeParser, NumGrimmeWriter),
    "fanuc-grimme": (FanucGrimmeParser, FanucGrimmeWriter),
}


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
        ("examples/XL02-05-029-03-P-REV-C.nc", "fanuc-ares")
    ]
    extension = {"fanuc-ares": "nc", "fanuc-grimme": "nc", "num-grimme": "xpi"}

    for source, src in examples:
        for dst in DIALECTS:
            target = f"output/{Path(source).stem}_to_{dst}.{extension[dst]}"
            result = convert(read_file(source), src, dst)
            write_file(target, result)
            unmapped = result.count("UNMAPPED")
            print(f"{source} ({src}) -> {target} ({dst}): {len(result.splitlines())} lines, {unmapped} UNMAPPED")
