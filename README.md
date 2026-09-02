# G-code Converter NUM ↔ FANUC

Converts G-code between NUM and FANUC dialects using a neutral intermediate representation (IR).

## Structure

```
gcode_converter/
├── core/
│   └── ir.py
├── dialects/
│   ├── base.py
│   ├── num/
│   │   ├── parser.py
│   │   ├── writer.py
│   │   └── mapping.py
│   └── fanuc/
│       ├── parser.py
│       ├── writer.py
│       └── mapping.py
└── converter.py
```

## Requirements

Standard library only, no packages to install:

- `re`
- `dataclasses`
- `enum`
- `abc`

Requires **Python 3.10+** (uses `X | None` syntax).

## Usage (no CLI yet)

Run directly from `converter.py`, from the project root:

```bash
cd gcode_converter
python converter.py
```

Example:

```python
from converter import convert

num_code = """
N10 G1 X100 Y50 F200
N20 M30
"""

result = convert(num_code, source_dialect="num", target_dialect="fanuc")
print(result)
```
