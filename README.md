# G-code Converter GRIMME NUM ↔ FANUC ARES

Converts G-code between dialects through a neutral intermediate representation (IR).

```
text --Parser--> IR (list[list[Operation]], one list per block) --Writer--> text
```

## Structure

```
core/ir.py              IR: operations, enums, ModalState (dialect-neutral)
dialects/base.py        Parser + Writer base classes (all shared logic)
dialects/fanuc/
    mapping.py          FANUC code -> IR meaning (parser AND writer use it)
    parser.py           FanucParser  (inherits everything)
    writer.py           FanucWriter  (inherits everything)
dialects/num/
    mapping.py          GRIMME NUM code -> IR meaning
    parser.py           NumParser    (token syntax, G4 F, D, L variables)
    writer.py           NumWriter    (number format, D, G4 F, cycles, L variables)
converter.py            convert() + dialect registry
cli.py                  command line
```

## Rules

- **One mapping per dialect.** Tables go `code -> IR meaning`; the writer inverts them.
  If several codes share a meaning, the first listed is the one written.
- **Base = ISO/FANUC behaviour.** A dialect overrides only what differs.
- **Never guess.** Unknown codes become `NotIdentifyOperation` in the parser and
  `(UNMAPPED ...)` comments in the writer, so the operator can review them.
- `CODE_PARAMETERS` says which words belong to a code in the same block
  (e.g. `H` of `G43.4`, NUM `F` of `G4`), so they are not read as moves or commands.

## Adding a dialect

1. `dialects/<name>/mapping.py`: `GCodes`, `MCodes`, `AXES`, `CODE_PARAMETERS`.
2. `parser.py` / `writer.py`: subclass `Parser` / `Writer`, set `MAPPING`, override differences.
3. Register it in `DIALECTS` in `converter.py`.

## Usage

Standard library only, Python 3.10+.

```bash
python converter.py                                          # converts examples/ into output/
python cli.py examples/fanuc_ares.nc out.xpi --from fanuc --to num
```

```python
from converter import convert
print(convert(text, source_dialect="num", target_dialect="fanuc"))
```