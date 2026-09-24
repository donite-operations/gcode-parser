# dialects/fanuc/writer.py
"""IR -> FANUC (ARES) text. Everything FANUC-specific lives here."""
from dialects.base import Writer
from dialects.fanuc_ares import mapping


class FanucWriter(Writer):
    MAPPING = mapping
    OMIT = set()
    PROGRAM_NUMBER = 1  # O1

    # Start / end sequence of the ARES machine (taken from examples/fanuc_ares.nc).

    def _program_header(self) -> list[str]:
        return [
            "%",
            f"O{self.PROGRAM_NUMBER}",
            "G21",
            "G0 G40 G80 G90",
            "G49",
            "G69",
            "G0 G53 Z-250.",  # tool change position (sP_TC.txt)
            "G0 G53 B0.",
            "G0 G53 Z-250.",
            "(--- DEFAULT START, CHANGE PARAMETER IF REQUIRED ---)",
        ]

    def _program_footer(self) -> list[str]:
        return [
            "G49",
            "G0 G53 Z-250.",  # sP_end.txt
            "G0 G53 B0.",
            "G0 G53 Z0.",
            "M99",
            "%",
        ]