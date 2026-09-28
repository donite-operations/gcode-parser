# dialects/num/writer.py
"""IR -> GRIMME NUM text. Only what differs from the base (FANUC-style) writer."""
from core.ir import WorkCoordinate, CannedCycle, Dwell, ToolChange, ToolCompensation, ToolCompensationMode, VariableAssignment, Word
from dialects.base import UnsupportedOperation, Writer
from dialects.num_grimme import mapping


class NumGrimmeWriter(Writer):
    MAPPING = mapping

    # In Grimme programs N numbers are jump labels (N1, N9980), not block numbering.
    LINE_NUMBERS = False
    OMIT = {VariableAssignment}

    PROGRAM_NUMBER = 28  # %28

    # "T1 D1": D goes after T (sample: G151 EA0 EC0 EU0 T1 D1)
    WORD_ORDER = {**Writer.WORD_ORDER, "D": 4.5}

    # Work offset NPV-1 written with G501 (E6x001 parameters).
    # ! JOB DATA: these are the values of examples/num_grimme.xpi. Check them per part.
    WORK_OFFSET = {"X": 0, "Y": 0, "Z": 206700, "A": 0, "C": 0}

    # Safe position written for a SafetyPoint (same as the header/footer below).
    # Before a tool change Grimme goes to the loading position X540 Y-600 Z650 A0 C0.
    SAFETY_PREFIX = "G52 G17 G90 G0"
    SAFE_POSITION = {"x": 540, "y": -600, "z": 650, "b": 0, "c": 0}
    TOOL_CHANGE_SAFE_AXES = frozenset({"x", "y", "z", "b", "c"})


    # Start / end sequence of the GRIMME machine (taken from examples/num_grimme.xpi).
    # The G79 jumps of the header need the N9980 / N9990 labels of the footer:
    # always change both together.

    def _program_header(self) -> list[str]:

        e = self.WORK_OFFSET
        return [
            f"%{self.PROGRAM_NUMBER}",
            "(--- SET ZEROPOINT WORKOFFSET NP-1 ---)",
            "G54",
            "(--- SET WORKOFFSET NPV-1 ---)",
            "G501",
            f"E60001= {e['X']}",
            f"E61001= {e['Y']}",
            f"E62001= {e['Z']} ",
            f"E66001= {e['A']}",
            f"E68001= {e['C']}",
            "G151 S0",
            "N1",
            "(--- LOADING POSITION IN REL TO ORIGIN MACHINE ---)",
            "G52 G17 G90 G0 Z650",
            "G52 G17 G90 G0 X540 Y-600 Z650 A0 C0",
            "(CHECK TOOL LENGTH)",
            "VAR",
            "[TOOL_L_T1]=E50001/1000",
            "[TOOL_L_T2]=E50002/1000",
            "ENDV",
            "G79 [TOOL_L_T1]< 20 N9980",
            "G79 [TOOL_L_T2]< 20 N9990",
            "(TC_end.txt)",
            "S18000 M3 (DEFAULT VALUE, CHANGE IF REQUIRED)",
            "G4 F2	(DWELL TIME)",
            "G52 G17 G90 G0 Z650",
            "G52 G17 G90 G0 X540",
            "D1",
            "G0 G54 G90 A-12.094 C60.625 ",
            "(--- DEFAULT START ---)",
        ]

    def _program_footer(self) -> list[str]:
        return [
            "G151 S0",
            "(--- LOADING POSITION IN REL TO ORIGIN MACHINE ---)",
            "G52 G17 G90 G0 Z650",
            "G52 G17 G90 G0 X540 Y-600 A0 C0",
            "M72 (OPEN DOOR)",
            "G4 F1.5",
            "M02",
            "N9980 $ TOOL-1 TOO SHORT !!",
            "N9981 G4 F2",
            "N9982 $",
            "N9983 G79 N9980",
            "N9990 $ TOOL-2 TOO SHORT !!",
            "N9991 G4 F2",
            "N9992 $",
            "N9993 G79 N9990",
        ]

    def _fmt(self, value: float) -> str:
        """NUM style: no trailing decimal point (650, -0.01, 0)."""
        text = super()._fmt(value).rstrip(".")
        return "0" if text in ("", "-0") else text

    def _fmt_variable(self, value: float) -> str:
        """Variables keep the decimal point: L1=3000."""
        text = f"{value:.6f}".rstrip("0")
        return "0." if text == "-0." else text

    def reset(self) -> None:
        super().reset()
        self._active_tool = None  # needed for "G151 ... T<n>"

    def _write_tool_change(self, op: ToolChange) -> list[Word]:
        words = super()._write_tool_change(op)
        self._active_tool = op.tool_number
        return words

    def _write_wcs(self, op: WorkCoordinate) -> list[Word]:
        word = self._g("WORK_COORDINATE_SYSTEM", self.MAPPING.GCodes.WORK_COORDINATE_SYSTEM.get("54"))
        self.state.wcs = op.wcs
        return [word]

    def _write_tool_comp(self, op: ToolCompensation) -> list[Word]:
        """D<n> = length correction ; G151 = TCP on / off (FANUC G43.4 H<n> / G49)."""
        if op.mode is ToolCompensationMode.LENGTH and op.offset is not None:
            return [Word("D", str(op.offset))]

        g151 = self._g("TOOL_COMPENSATION", ToolCompensationMode.TCP)  # same code for on and off
        if op.mode is ToolCompensationMode.OFF:
            return [g151, Word("S", "0")]
        if op.mode is ToolCompensationMode.TCP:
            return [g151, Word("EA", "0"), Word("EC", "0"), Word("EU", "0"),
                    Word("T", str(op.tool)), Word("D", str(1))]

        # Word("D", str(op.offset))
        raise UnsupportedOperation  # e.g. TCP without offset or without a tool change before

    def _write_dwell(self, op: Dwell) -> list[Word]:
        return [self._g("DWELL", Dwell), Word("F", self._fmt(op.time))]  # seconds

    def _write_canned_cycle(self, op: CannedCycle) -> list[Word]:
        words = [self._g("CANNED_CYCLE", op.cycle)]
        for address, value in (("Z", op.z), ("ER", op.r), ("P", op.peck), ("EF", op.dwell)):
            if value is not None:
                words.append(Word(address, self._fmt(value)))
        if op.feed is not None and op.feed != self.state.last_feed:
            words.append(Word("F", self._fmt(op.feed)))
            self.state.last_feed = op.feed
        return words

    def _write_variable_assignment(self, op: VariableAssignment) -> list[Word]:
        self.state.variables[op.number] = op.value
        return [Word(f"L{op.number}", f"={self._fmt_variable(op.value)}")]