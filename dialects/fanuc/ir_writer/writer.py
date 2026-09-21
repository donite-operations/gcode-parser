# dialects/fanuc/writer.py
"""
FANUC writer: traduce el programa (list[list[Operation]] — una lista de
bloques, cada bloque la lista de Operations que van juntas en una misma
línea) a texto FANUC.

GCodes/MCodes ahora viven en mapping.py, este archivo solo los usa.
"""
from dialects.base import Writer
from dialects.fanuc.ir_writer.mapping import GCodes, MCodes
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

class FanucWriter(Writer):
    """
    Use:
        writer = FanucWriter()
        texto = writer.write(program)   # program: list[list[Operation]]
    """

    PRECISION_MM = 3
    PRECISION_INCH = 4

    G_CODE = GCodes
    M_CODE = MCodes

    def __init__(self, line_numbers: bool = True, line_number_start: int = 1, line_number_step: int = 1):
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

    def _axis_words(self, op) -> list[Word]:
        words = []
        if getattr(op, "wcs", None) is not None and op.wcs != self.state.wcs:
            words.append(Word("G", str(self.G_CODE.WCS[op.wcs])))
            self.state.wcs = op.wcs
        for address in ("x", "y", "z", "b", "c"):
            value = getattr(op, address)
            if value is not None:
                words.append(Word(address.upper(), self._fmt(value)))
        return words

    # -- handlers per operation --------------------------------------------

    def _write_linear_move(self, op: LinearMove) -> list[Word]:
        words = []

        words.append(Word("G", str(self.G_CODE.MOTION_LINEAR)))
        self.state.active_g = self.G_CODE.MOTION_LINEAR

        words.extend(self._axis_words(op))

        if op.feed is not None and op.feed != self.state.last_feed:
            words.append(Word("F", self._fmt(op.feed)))
            self.state.last_feed = op.feed

        return words

    def _write_tool_comp(self, op: ToolCompensation) -> list[Word]:
        words = [Word("G", str(self.G_CODE.TOOL_COMP[op.mode]))]
        if op.offset is not None:
            words.append(Word("H", op.offset))
        return words

    def _write_wcs(self, op: WorkCoordinate) -> list[Word]:
        self.state.wcs = op.wcs
        return [Word("G", str(self.G_CODE.WCS[op.wcs]))]

    def _write_local_offset(self, op: LocalOffset) -> list[Word]:
        words = [Word("G", str(self.G_CODE.LOCAL_OFFSET))]
        for address in ("x", "y", "z", "b", "c"):
            value = getattr(op, address)
            if value is not None:
                words.append(Word(address.upper(), self._fmt(value)))
        return words

    def _write_cancel_offset(self, op: CancelOffset) -> list[Word]:
        return [Word("G", str(self.G_CODE.CANCEL_OFFSET))]

    def _write_contour_control(self, op: ContourControlMode) -> list[Word]:
        words = [Word("G", self.G_CODE.CONTOUR_CONTROL), Word("Q", str(op.q))]

        if op.tolerance is not None:
            words.append(Word("R", self._fmt(op.tolerance)))
        return words

    def _write_canned_cycle(self, op: CannedCycle) -> list[Word]:
        words = [Word("G", str(self.G_CODE.CYCLE[op.cycle]))]
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

    def _write_variable_assignment(self, op: VariableAssignment) -> list[Word]:
        return [Word(f"#{op.number}", f"={self._fmt(op.value)}")]

    def _write_program_end(self, op: ProgramEnd) -> list[Word]:
        return [Word("M", str(self.M_CODE.PROGRAM_END))]

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