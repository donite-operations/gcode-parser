# dialects/fanuc_grimme/writer.py
"""IR -> FANUC GRIMME text. Start / end sequence taken from Platte_FANUC_GRIMME.nc."""
from core.ir import ToolCompensation, ToolCompensationMode, Word, Dwell
from dialects.base import Writer
from dialects.fanuc_grimme import mapping


class FanucGrimmeWriter(Writer):
    MAPPING = mapping

    # As on NUM Grimme, N numbers are labels, not block numbering.
    LINE_NUMBERS = False

    PROGRAM_NAME = "PROGRAM"  # example: <SCHULUNGSPLATTE-01>

    # G54 written with G10 L2 P1, in mm.
    # ! JOB DATA: values of Platte_FANUC_GRIMME.nc. Check them per part.
    WORK_OFFSET = {"X": -148.1, "Y": -198.56, "Z": 408.0}

    SAFETY_LINES = ["G53 Z665.", "G53 X540. Y-800."]
    TOOL_CHANGE_LINES = ["G53 Z665.", "G53 X540. Y-800. A0. C0."]

    def _program_header(self) -> list[str]:
        e = {axis: self._fmt(value) for axis, value in self.WORK_OFFSET.items()}
        return [
            "%",
            f"<{self.PROGRAM_NAME}>",
            "(--- Starting point in G54 ---)",
            f"G90 G10 L2 P1 X{e['X']} Y{e['Y']} Z{e['Z']}",  # G90: in G91 G10 adds to the offset
            *self.TOOL_CHANGE_LINES,
            "M3 S30000 (DEFAULT VALUE, CHANGE IF REQUIRED)",
            "G54",
        ]

    def _program_footer(self) -> list[str]:
        return [
            "G91 G40 X0. Y0.",
            "G90",
            "G69",
            "G49",
            *self.SAFETY_LINES,
            "G4 X1.",
            "M300",
            "M30",
            "%",
        ]

    def _write_tool_comp(self, op: ToolCompensation) -> list[Word]:
        """This machine always uses offset 99 for the active tool:
            correction D<n>  -> G43 H99 D99  (NUM: D1 = length + radius, D99 is for G41/G42)
            TCP on           -> G43.4 H99    (NUM: G151 EA0 EC0 EU0 T1 D1)
            off              -> G49          (NUM: G151 S0)"""
        if op.mode is ToolCompensationMode.OFF:
            return [self._g("TOOL_COMPENSATION", op.mode)]
        words = [self._g("TOOL_COMPENSATION", op.mode), Word("H", "99")]
        if op.mode is ToolCompensationMode.LENGTH:
            words.append(Word("D", "99"))
        return words

    def _write_dwell(self, op: Dwell) -> list[Word]:
        # X in seconds with decimal point: with P the unit depends on parameter DWT (No. 1015#7)
        return [self._g("DWELL", Dwell), Word("X", self._fmt(op.time))]
