# dialects/fanuc/writer.py
"""
FANUC writer: traduce el programa (list[list[Operation]] — una lista de
bloques, cada bloque la lista de Operations que van juntas en una misma
línea) a texto FANUC.

GCodes/MCodes ahora viven en mapping.py, este archivo solo los usa.
"""

from core.ir import (
    Absolute,
    AbsoluteMode,
    CancelOffset,
    CannedCycle,
    CoolantControl,
    CoordinateRotation,
    ContourControlMode,
    CutterCompensation,
    Dwell,
    FeedRate,
    LinearMove,
    LocalOffset,
    ModalState,
    NotIdentifyOperation,
    Operation,
    ProgramEnd,
    RapidMove,
    SpindleControl,
    SpindleSpeed,
    ToolChange,
    ToolCompensation,
    ToolCompensationMode,
    Unit,
    UnitMode,
    VariableAssignment,
    Word,
    WorkCoordinate,
    WorkCoordinateSystem,
)

from dialects.fanuc.ir_writer.mapping import GCodes, MCodes
from base import Writer

class FanucWriter():
    """
    Use:
        writer = FanucWriter()
        texto = writer.write(program)   # program: list[list[Operation]]
    """

    PRECISION_MM = 3
    PRECISION_INCH = 4
    LINE_NUMBER_STEP: int | None = 10

    G_CODE = GCodes
    M_CODES = MCodes

    def __init__(self):
        self.state = ModalState()
        self._next_n = self.LINE_NUMBER_STEP
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
        self._next_n = self.LINE_NUMBER_STEP

    # -- API pública -----------------------------------------------------

    def write(self, program: list[list[Operation]]) -> str:
        lines = [self._write_block(block) for block in program]
        return "\n".join(line for line in lines if line)

    def _write_block(self, block: list[Operation]) -> str:
        words: list[Word] = []
        seen: set[tuple[str, str]] = set()
        for op in block:
            for w in self._dispatch_words(op):
                key = (w.address, w.value)
                if key in seen:
                    # dos operations del mismo bloque piden el mismo word
                    # (p.ej. WCS embebido en el RapidMove + un WorkCoordinate
                    # aparte para el mismo G57) — se emite una sola vez
                    continue
                seen.add(key)
                words.append(w)
        return self._render_block(words)

    def _dispatch_words(self, operation: Operation) -> list[Word]:
        handler = self._handlers.get(type(operation))
        if handler is None:
            raise NotImplementedError(
                f"FanucWriter no tiene handler para {type(operation).__name__}"
            )
        return handler(operation)

    def _render_block(self, words: list[Word]) -> str:
        if not words:
            return ""
        parts = []
        if self.LINE_NUMBER_STEP is not None:
            parts.append(f"N{self._next_n}")
            self._next_n += self.LINE_NUMBER_STEP
        parts.extend(f"{w.address}{w.value}" for w in words)
        return " ".join(parts) + " ;"

    # -- formateo de números -------------------------------------------------

    def _fmt(self, value: float) -> str:
        precision = self.PRECISION_MM if self.state.units_mm else self.PRECISION_INCH
        return f"{value:.{precision}f}".rstrip("0")

    def _axis_words(self, op) -> list[Word]:
        words = []
        if getattr(op, "wcs", None) is not None and op.wcs != self.state.wcs:
            words.append(Word("G", str(GCodes.WCS[op.wcs])))
            self.state.wcs = op.wcs
        for address in ("x", "y", "z", "b", "c"):
            value = getattr(op, address)
            if value is not None:
                words.append(Word(address.upper(), self._fmt(value)))
        return words

    # -- handlers por operación --------------------------------------------

    def _write_rapid_move(self, op: RapidMove) -> list[Word]:
        words = []
        if self.state.active_g != GCodes.MOTION_RAPID:
            words.append(Word("G", str(GCodes.MOTION_RAPID)))
            self.state.active_g = GCodes.MOTION_RAPID
        words.extend(self._axis_words(op))
        return words

    def _write_linear_move(self, op: LinearMove) -> list[Word]:
        words = []
        if self.state.active_g != GCodes.MOTION_LINEAR:
            words.append(Word("G", str(GCodes.MOTION_LINEAR)))
            self.state.active_g = GCodes.MOTION_LINEAR
        words.extend(self._axis_words(op))
        if op.feed is not None and op.feed != self.state.last_feed:
            words.append(Word("F", self._fmt(op.feed)))
            self.state.last_feed = op.feed
        return words

    def _write_tool_change(self, op: ToolChange) -> list[Word]:
        return [Word("T", op.tool_number), Word("M", str(MCodes.TOOL_CHANGE))]

    def _write_spindle_control(self, op: SpindleControl) -> list[Word]:
        return [Word("M", str(MCodes.SPINDLE[op.mode]))]

    def _write_spindle_speed(self, op: SpindleSpeed) -> list[Word]:
        return [Word("S", str(int(op.rpm)))]

    def _write_coolant(self, op: CoolantControl) -> list[Word]:
        return [Word("M", str(MCodes.COOLANT[op.mode]))]

    def _write_cutter_comp(self, op: CutterCompensation) -> list[Word]:
        return [Word("G", str(GCodes.CUTTER_COMP[op.mode]))]

    def _write_tool_comp(self, op: ToolCompensation) -> list[Word]:
        words = [Word("G", str(GCodes.TOOL_COMP[op.mode]))]
        if op.offset is not None:
            words.append(Word("H", op.offset))
        return words

    def _write_wcs(self, op: WorkCoordinate) -> list[Word]:
        self.state.wcs = op.wcs
        return [Word("G", str(GCodes.WCS[op.wcs]))]

    def _write_local_offset(self, op: LocalOffset) -> list[Word]:
        words = [Word("G", str(GCodes.LOCAL_OFFSET))]
        for address in ("x", "y", "z", "b", "c"):
            value = getattr(op, address)
            if value is not None:
                words.append(Word(address.upper(), self._fmt(value)))
        return words

    def _write_cancel_offset(self, op: CancelOffset) -> list[Word]:
        return [Word("G", str(GCodes.CANCEL_OFFSET))]

    def _write_absolute(self, op: Absolute) -> list[Word]:
        self.state.absolute_mode = op.mode == AbsoluteMode.ABSOLUTE
        return [Word("G", str(GCodes.ABSOLUTE[op.mode]))]

    def _write_rotation(self, op: CoordinateRotation) -> list[Word]:
        return [Word("G", str(GCodes.ROTATION[op.enabled]))]

    def _write_contour_control(self, op: ContourControlMode) -> list[Word]:
        words = [Word("G", GCodes.CONTOUR_CONTROL), Word("Q", str(op.q))]
        if op.tolerance is not None:
            words.append(Word("R", self._fmt(op.tolerance)))
        return words

    def _write_canned_cycle(self, op: CannedCycle) -> list[Word]:
        words = [Word("G", str(GCodes.CYCLE[op.cycle]))]
        if op.z is not None:
            words.append(Word("Z", self._fmt(op.z)))
        if op.r is not None:
            words.append(Word("R", self._fmt(op.r)))
        if op.peck is not None:
            words.append(Word("Q", self._fmt(op.peck)))
        if op.dwell is not None:
            words.append(Word("P", self._fmt(op.dwell)))
        if op.feed is not None and op.feed != self.state.last_feed:
            words.append(Word("F", self._fmt(op.feed)))
            self.state.last_feed = op.feed
        return words

    def _write_dwell(self, op: Dwell) -> list[Word]:
        return [Word("G", "4"), Word("P", self._fmt(op.time))]

    def _write_feed_rate(self, op: FeedRate) -> list[Word]:
        self.state.last_feed = op.value
        return [Word("F", self._fmt(op.value))]

    def _write_unit_mode(self, op: UnitMode) -> list[Word]:
        self.state.units_mm = op.value == Unit.MM
        return [Word("G", str(GCodes.UNIT[op.value]))]

    def _write_variable_assignment(self, op: VariableAssignment) -> list[Word]:
        return [Word(f"#{op.number}", f"={self._fmt(op.value)}")]

    def _write_program_end(self, op: ProgramEnd) -> list[Word]:
        return [Word("M", str(MCodes.PROGRAM_END))]

    def _write_not_identified(self, op: NotIdentifyOperation) -> list[Word]:
        return [Word("(", f"UNMAPPED L{op.line_number}: {op.operation})")]

    def test_writer():
        program = [
            [ContourControlMode(q=0, tolerance=5)],
            [VariableAssignment(1, 2000.0)],
            [ToolCompensation(mode=ToolCompensationMode.OFF, offset=None)],
            [
                RapidMove(b=0.0, c=0.0, wcs=WorkCoordinateSystem.G57),
                WorkCoordinate(wcs=WorkCoordinateSystem.G57),
                Absolute(mode=AbsoluteMode.ABSOLUTE),
            ],
            [
                Absolute(mode=AbsoluteMode.INCREMENTAL),
                ToolCompensation(mode=ToolCompensationMode.TCP, offset="3"),
            ],
        ]
        print(FanucWriter().write(program))