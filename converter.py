# converter.py
"""Orchestrates: source text --parser--> IR --writer--> target text."""
from pathlib import Path

from dialects.fanuc_ares.parser import FanucParser
from dialects.fanuc_ares.writer import FanucWriter
from dialects.num_grimme.parser import NumParser
from dialects.num_grimme.writer import NumWriter

# To add a dialect: create dialects/<name>/{mapping,parser,writer}.py and register it here.
DIALECTS = {
    "fanuc": (FanucParser, FanucWriter),
    "num": (NumParser, NumWriter),
}


def convert(text: str, source_dialect: str, target_dialect: str) -> str:
    parser_cls, _ = DIALECTS[source_dialect]
    _, writer_cls = DIALECTS[target_dialect]
    operations = parser_cls().parse(text)
    return writer_cls().write(operations)


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
    # Quick manual test: converts the examples into ./output
    jobs = [
        ("examples/fanuc_ares.nc", "fanuc", "num", "output/fanuc_to_num.xpi"),
        ("examples/fanuc_ares.nc", "fanuc", "fanuc", "output/fanuc_to_fanuc.nc"),
        ("examples/num_grimme.xpi", "num", "fanuc", "output/num_to_fanuc.nc"),
        ("examples/num_grimme.xpi", "num", "num", "output/num_to_num.xpi"),
    ]
    for source, src, dst, target in jobs:
        result = convert(read_file(source), src, dst)
        write_file(target, result)
        unmapped = result.count("UNMAPPED")
        print(f"{source} ({src}) -> {target} ({dst}): {len(result.splitlines())} lines, {unmapped} UNMAPPED")
