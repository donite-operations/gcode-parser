# dialects/num/writer.py
"""IR -> NUM / Huber-Grimme writer."""

from base import Writer
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

    def __init__(self, line_numbers: bool = False, line_number_start: int = 10,
                 line_number_step: int = 10):
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

    def reset(self) -> None:
        self.state = ModalState()
        self._next_n = self.line_number_start

    def write(self, program: list[list[Operation]]) -> str:
        lines = [self._write_block(block) for block in program]
        return "\n".join(line for line in lines if line)

    def _write_block(self, block: list[Operation]) -> str:
        words: list[Word] = []
        seen: set[tuple[str, str]] = set()

        for operation in block:
            for word in self._dispatch_words(operation):
                key = (word.address, word.value)

                if key in seen:
                    continue

                seen.add(key)
                words.append(word)

        return self._render_block(words)

    def _dispatch_words(self, operation: Operation) -> list[Word]:
        handler = self._handlers.get(type(operation))

        if handler is None:
            raise NotImplementedError(
                f"NumWriter no tiene handler para {type(operation).__name__}"
            )

        return handler(operation)

    def _render_block(self, words: list[Word]) -> str:
        if not words:
            return ""

        parts: list[str] = []

        if self.line_numbers:
            parts.append(f"N{self._next_n}")
            self._next_n += self.line_number_step

        parts.extend(f"{word.address}{word.value}" for word in words)
        return " ".join(parts)

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
            code = GCodes.WCS[op.wcs]
            words.append(Word("G", str(code)))
            self.state.wcs = op.wcs

        # The supplied Huber/Grimme file is A/C.
        # The IR exposes the two rotary coordinates as b/c, so for this
        # dialect IR.b is rendered as A and IR.c as C.
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

    def _write_rapid_move(self, op: RapidMove) -> list[Word]:
        words: list[Word] = []

        if self.state.active_g != GCodes.MOTION_RAPID:
            words.append(Word("G", str(GCodes.MOTION_RAPID)))
            self.state.active_g = GCodes.MOTION_RAPID

        words.extend(self._axis_words(op))
        return words

    def _write_linear_move(self, op: LinearMove) -> list[Word]:
        words: list[Word] = []

        if self.state.active_g != GCodes.MOTION_LINEAR:
            words.append(Word("G", str(GCodes.MOTION_LINEAR)))
            self.state.active_g = GCodes.MOTION_LINEAR

        words.extend(self._axis_words(op))

        if op.feed is not None and op.feed != self.state.last_feed:
            words.append(Word("F", self._fmt(op.feed)))
            self.state.last_feed = op.feed

        return words

    def _write_tool_change(self, op: ToolChange) -> list[Word]:
        return [
            Word("T", op.tool_number),
            Word("M", MCodes.TOOL_CHANGE),
        ]

    def _write_spindle_control(self, op: SpindleControl) -> list[Word]:
        code = MCodes.SPINDLE[op.mode]
        return [Word("M", str(code))]

    def _write_spindle_speed(self, op: SpindleSpeed) -> list[Word]:
        return [Word("S", str(int(op.rpm)))]

    def _write_coolant(self, op: CoolantControl) -> list[Word]:
        code = MCodes.COOLANT[op.mode]
        return [Word("M", str(code))]

    def _write_cutter_comp(self, op: CutterCompensation) -> list[Word]:
        return [Word("G", str(GCodes.CUTTER_COMP[op.mode]))]

    def _write_tool_comp(self, op: ToolCompensation) -> list[Word]:
        words: list[Word] = []

        if op.mode == ToolCompensationMode.LENGTH:
            if op.offset is None:
                raise ValueError("NUM necesita D<n> para la corrección de longitud")

            words.append(Word(GCodes.TOOL_LENGTH, str(op.offset)))
            return words

        if op.mode == ToolCompensationMode.TCP:
            words.extend(
                [
                    Word("G", str(GCodes.TCP)),
                    Word("S", str(GCodes.TCP_ON)),
                ]
            )

            if op.offset is not None:
                words.append(Word(GCodes.TOOL_LENGTH, str(op.offset)))

            return words

        # OFF: cancel both the active D correction and RTCP.
        words.extend(
            [
                Word("G", str(GCodes.TCP)),
                Word("S", str(GCodes.TCP_OFF)),
                Word(GCodes.TOOL_LENGTH, "0"),
            ]
        )
        return words

    def _write_wcs(self, op: WorkCoordinate) -> list[Word]:
        self.state.wcs = op.wcs
        return [Word("G", str(GCodes.WCS[op.wcs]))]

    def _write_local_offset(self, op: LocalOffset) -> list[Word]:
        words = [Word("G", str(GCodes.LOCAL_OFFSET))]

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
            Word("G", str(GCodes.LOCAL_OFFSET)),
            Word("X", "0"),
            Word("Y", "0"),
        ]

    def _write_absolute(self, op: Absolute) -> list[Word]:
        self.state.absolute_mode = (
            op.mode == AbsoluteMode.ABSOLUTE
        )
        return [Word("G", str(GCodes.ABSOLUTE[op.mode]))]

    def _write_rotation(self, op: CoordinateRotation) -> list[Word]:
        return [Word("G", str(GCodes.ROTATION[op.enabled]))]

    def _write_contour_control(self, op: ContourControlMode) -> list[Word]:
        words = [
            Word("G", GCodes.CONTOUR_CONTROL),
            Word("Q", str(op.q)),
        ]

        self.state.last_contour_tolerance = op.tolerance

        if op.tolerance is not None:
            words.append(Word("R", self._fmt(op.tolerance)))

        return words

    def _write_canned_cycle(self, op: CannedCycle) -> list[Word]:
        words = [Word("G", str(GCodes.CYCLE[op.cycle]))]

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
            Word("G", str(GCodes.DWELL)),
            Word("F", self._fmt(op.time)),
        ]

    def _write_feed_rate(self, op: FeedRate) -> list[Word]:
        self.state.last_feed = op.value
        return [Word("F", self._fmt(op.value))]

    def _write_unit_mode(self, op: UnitMode) -> list[Word]:
        self.state.units_mm = op.value == Unit.MM
        return [Word("G", str(GCodes.UNIT[op.value]))]

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

    def _write_not_identified(self, op: NotIdentifyOperation) -> list[Word]:
        return [
            Word(
                "(",
                f"UNMAPPED L{op.line_number}: {op.operation})",
            )
        ]
