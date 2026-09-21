# dialects/num/writer.py
"""IR -> NUM / Huber-Grimme writer."""

from dialects.base import Writer
from core.ir import (
    Absolute, AbsoluteMode, CancelOffset, CannedCycle, CoolantControl, CoordinateRotation, 
    ContourControlMode, CutterCompensation, Dwell, FeedRate, LinearMove, LocalOffset, 
    ModalState, NotIdentifyOperation, Operation, ProgramEnd, RapidMove, SpindleControl,
    SpindleSpeed, ToolChange, ToolCompensation, ToolCompensationMode, Unit, 
    UnitMode, VariableAssignment, Word, WorkCoordinate
)
from .mapping import GCodes, MCodes


class NumWriter(Writer):
    """
    Usage:

        writer = NumWriter()
        text = writer.write(program)

    By default this writer does NOT generate N10/N20/N30 sequence numbers.
    That matches the supplied Huber/Grimme .xpi, where N1 and N9980...
    are explicit labels rather than normal block numbering.
    """

    PRECISION_MM = 3
    PRECISION_INCH = 4

    G_CODE = GCodes
    M_CODE = MCodes

    def __init__(self, line_numbers: bool = False, line_number_start: int = 1, line_number_step: int = 1):
        self.state = ModalState()
        self.line_numbers = line_numbers
        self.line_number_start = line_number_start
        self.line_number_step = line_number_step
        self._next_n = line_number_start

        self._handlers = {
            RapidMove: self._write_rapid_move,
            LinearMove: self._write_linear_move,
            ToolChange: self._write_tool_change,
            SpindleControl: self._write_spindle_control,
            SpindleSpeed: self._write_spindle_speed,
            CoolantControl: self._write_coolant,
            CutterCompensation: self._write_cutter_comp,
            ToolCompensation: self._write_tool_comp,
            WorkCoordinate: self._write_wcs,
            LocalOffset: self._write_local_offset,
            CancelOffset: self._write_cancel_offset,
            Absolute: self._write_absolute,
            CoordinateRotation: self._write_rotation,
            ContourControlMode: self._write_contour_control,
            CannedCycle: self._write_canned_cycle,
            Dwell: self._write_dwell,
            FeedRate: self._write_feed_rate,
            UnitMode: self._write_unit_mode,
            VariableAssignment: self._write_variable_assignment,
            ProgramEnd: self._write_program_end,
            NotIdentifyOperation: self._write_not_identified,
        }

    def _fmt(self, value: float) -> str:
        precision = (
            self.PRECISION_MM
            if self.state.units_mm
            else self.PRECISION_INCH
        )

        text = f"{value:.{precision}f}".rstrip("0").rstrip(".")

        if text in {"", "-0"}:
            return "0"

        return text

    def _fmt_variable(self, value: float) -> str:
        """NUM variable style: keep a decimal point for integer values."""
        text = f"{value:.6f}".rstrip("0")

        if "." not in text:
            text += "."

        if text == "-0.":
            return "0."

        return text

    def _axis_words(self, op) -> list[Word]:
        words: list[Word] = []

        if getattr(op, "wcs", None) is not None and op.wcs != self.state.wcs:
            code = self.G_CODE.WCS[op.wcs]
            words.append(Word("G", str(code)))
            self.state.wcs = op.wcs

        axes = (
            ("x", "X"),
            ("y", "Y"),
            ("z", "Z"),
            ("b", "A"),
            ("c", "C"),
        )

        for attribute, address in axes:
            value = getattr(op, attribute)

            if value is not None:
                words.append(Word(address, self._fmt(value)))

        return words

    def _write_linear_move(self, op: LinearMove) -> list[Word]:
        words: list[Word] = []

        if self.state.active_g != self.G_CODE.MOTION_LINEAR:
            words.append(Word("G", str(self.G_CODE.MOTION_LINEAR)))
            self.state.active_g = self.G_CODE.MOTION_LINEAR

        words.extend(self._axis_words(op))

        if op.feed is not None and op.feed != self.state.last_feed:
            words.append(Word("F", self._fmt(op.feed)))
            self.state.last_feed = op.feed

        return words

    def _write_tool_comp(self, op: ToolCompensation) -> list[Word]:
        words: list[Word] = []

        if op.mode == ToolCompensationMode.LENGTH:
            if op.offset is None:
                raise ValueError("NUM necesita D<n> para la corrección de longitud")

            words.append(Word(self.G_CODE.TOOL_LENGTH, str(op.offset)))
            return words

        if op.mode == ToolCompensationMode.TCP:
            words.extend(
                [
                    Word("G", str(self.G_CODE.TCP)),
                    Word("S", str(self.G_CODE.TCP_ON)),
                ]
            )

            if op.offset is not None:
                words.append(Word(self.G_CODE.TOOL_LENGTH, str(op.offset)))

            return words

        # OFF: cancel both the active D correction and RTCP.
        words.extend(
            [
                Word("G", str(self.G_CODE.TCP)),
                Word("S", str(self.G_CODE.TCP_OFF)),
                Word(self.G_CODE.TOOL_LENGTH, "0"),
            ]
        )
        return words

    def _write_wcs(self, op: WorkCoordinate) -> list[Word]:
        self.state.wcs = op.wcs
        return [Word("G", str(self.G_CODE.WCS[op.wcs]))]

    def _write_local_offset(self, op: LocalOffset) -> list[Word]:
        words = [Word("G", str(self.G_CODE.LOCAL_OFFSET))]

        axes = (
            ("x", "X"),
            ("y", "Y"),
            ("z", "Z"),
            ("b", "A"),
            ("c", "C"),
        )

        for attribute, address in axes:
            value = getattr(op, attribute)

            if value is not None:
                words.append(Word(address, self._fmt(value)))

        return words

    def _write_cancel_offset(self, op: CancelOffset) -> list[Word]:
        # The supplied Grimme-style program uses G52 X0 Y0 to return the
        # local/measurement offset to zero.
        return [
            Word("G", str(self.G_CODE.LOCAL_OFFSET)),
            Word("X", "0"),
            Word("Y", "0"),
        ]

    def _write_canned_cycle(self, op: CannedCycle) -> list[Word]:
        words = [Word("G", str(self.G_CODE.CYCLE[op.cycle]))]

        # NUM 1060 uses ER for the retract/reference plane.
        if op.z is not None:
            words.append(Word("Z", self._fmt(op.z)))

        if op.r is not None:
            words.append(Word("ER", self._fmt(op.r)))

        # NUM G83 uses P for the penetration/peck value.
        if op.peck is not None:
            words.append(Word("P", self._fmt(op.peck)))

        # NUM drilling cycles use EF for the dwell/timer parameter.
        if op.dwell is not None:
            words.append(Word("EF", self._fmt(op.dwell)))

        if op.feed is not None and op.feed != self.state.last_feed:
            words.append(Word("F", self._fmt(op.feed)))
            self.state.last_feed = op.feed

        return words

    def _write_dwell(self, op: Dwell) -> list[Word]:
        # Supplied Grimme examples: G4 F2 / G4 F1.5
        return [
            Word("G", str(self.G_CODE.DWELL)),
            Word("F", self._fmt(op.time)),
        ]

    def _write_variable_assignment(self, op: VariableAssignment) -> list[Word]:
        self.state.variables[op.number] = op.value

        # NUM uses L variables rather than the #<number> style used by
        # Fanuc-like controls.
        return [
            Word(
                f"L{op.number}",
                f"={self._fmt_variable(op.value)}",
            )
        ]

    def _write_program_end(self, op: ProgramEnd) -> list[Word]:
        return [Word("M", MCodes.PROGRAM_END)]
