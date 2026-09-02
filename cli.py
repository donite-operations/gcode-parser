# cli.py
import argparse
import sys
from pathlib import Path

# from converter import convert

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gcode-converter",
        description="Convierte código G-code entre dialectos NUM y FANUC."
    )
    parser.add_argument("input_file", type=Path, help="Archivo de entrada")
    parser.add_argument("output_file", type=Path, help="Archivo de salida")
    parser.add_argument(
        "--from", dest="source_dialect",
        choices=["num", "fanuc"], required=True,
        help="Dialecto de origen"
    )
    parser.add_argument(
        "--to", dest="target_dialect",
        choices=["num", "fanuc"], required=True,
        help="Dialecto de destino"
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    print(parser)
    # if not args.input_file.exists():
    #     print(f"Error: no se encontró el archivo {args.input_file}", file=sys.stderr)
    #     return 1

    texto_entrada = args.input_file.read_text(encoding="utf-8")

main()