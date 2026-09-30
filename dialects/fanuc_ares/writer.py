# dialects/fanuc/writer.py
"""IR -> FANUC (ARES) text. Everything FANUC-specific lives here."""
from dialects.base import Writer
from dialects.fanuc_ares import mapping


class FanucAresWriter(Writer):
    MAPPING = mapping
    OMIT = set()
    PROGRAM_NUMBER = 1  # O1

    # Same lines as the header/footer below (old post).
    SAFETY_LINES = ["G0 G53 Z-250.", "G0 G53 B0."]
    TOOL_CHANGE_LINES = SAFETY_LINES

    # Start / end sequence of the ARES machine (taken from examples/fanuc_ares.nc).

    def _program_header(self) -> list[str]:


        first_header = [
            "%",
            f"O{self.PROGRAM_NUMBER}",
            "G21",
            "G0 G40 G80 G90",
            "G49",
            "G69"
        ]

        sp_text = [
            "G0 G53 Z-250 (sP_TC.txt)",
            "G0 G53 B0",
            "G0 G53 Z-250",
            "T3 M6 (DEFAULT VALUE CHANGE IF REQUIRED)"
        ]

        sp = [
            "G0 G53 Z-250 (sP.txt)",
            "G0 G53 B0",
            "G0 G53 Z-250",
            "S16000 M3 (DEFAULT VALUE CHANGE IF REQUIRED)",
            "M8 (DEFAULT VALUE CHANGE IF REQUIRED)",
            "(--- DEFAULT START ---)",
        ]

        return first_header + sp_text + sp

    def _program_footer(self) -> list[str]:
        return [
            "G49",
            "G0 G53 Z-250.",  # sP_end.txt
            "G0 G53 B0.",
            "G0 G53 Z0.",
            "M99",
            "%",
        ]
