# dialects/base.py
from abc import ABC, abstractmethod
from typing import Callable
from core.ir import (
    Absolute, AbsoluteMode, CancelOffset, CannedCycle, CoolantControl, CoordinateRotation, 
    ContourControlMode, CutterCompensation, Dwell, FeedRate, LinearMove, LocalOffset, 
    ModalState, NotIdentifyOperation, Operation, ProgramEnd, RapidMove, SpindleControl,
    SpindleSpeed, ToolChange, ToolCompensation, ToolCompensationMode, Unit, 
    UnitMode, VariableAssignment, Word, WorkCoordinate, Block, Program, HandlerContext
)
def _to_float_or_none(value):
    return float(value) if value is not None else None

def get_parameter_ctx(search_word: str, father_ctx: HandlerContext, look_for: list[str] = []) -> HandlerContext | None:
    #! father_ctx.block. 

    if len(look_for) == 0 :
        word_value = father_ctx.block.get(search_word)
    else:
        word_value =  father_ctx.block.get_from(search_word, look_for)

    if word_value is None:
        return None

    return HandlerContext(command=search_word, value=word_value, state=father_ctx.state) # Need to build HandlerContext because the ctx is for the motion

class CodeDispatcher:
    DISPATCH: dict[str, Callable[[HandlerContext], Operation | None]] = {}

    @classmethod
    def dispatch(cls, ctx: HandlerContext) -> Operation | None:
        handler = cls.DISPATCH.get(ctx.value)
        return handler(ctx) if handler else None

class Parser(ABC):

    def _tokenize(self, line: str) -> list[tuple[str, str]]:
        return self.TOKEN_PATTERN.findall(line)

    def _parse_line(self, raw_line: str) -> Block:
        line = raw_line.strip()

        comment = None
        match = self.COMMENT_PATTERN.search(line)
        if match:
            comment = match.group(1)
            line = self.COMMENT_PATTERN.sub('', line)

        line_number = None
        match = self.LINE_NUMBER_PATTERN.match(line)
        if match:
            line_number = int(match.group(1))
            line = self.LINE_NUMBER_PATTERN.sub('', line)

        tokens = self._tokenize(line)

        words = []
        for addr, val in tokens:
            words.append(Word(address=addr, value=val))

        return Block(
            line_number=line_number,
            words=words,
            comment=comment,
        )

    def _parse_program(self, text: str) -> Program:
        program = Program()
        for raw_line in text.splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            program.blocks.append(self._parse_line(raw_line))
        return program

    def parse(self, text: str) -> list[Operation]:
        program = self._parse_program(text)

        return self._interpret_program(program)

class Writer(ABC):
    def reset(self) -> None:
        self.state = ModalState()
        self._next_n = self.LINE_NUMBER_STEP

    def write(self, program: list[list[Operation]]) -> str:
        """From Operations list to a G-Code text"""
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

    def _render_block(self, words: list[Word]) -> str:
        if not words:
            return ""

        parts: list[str] = []

        if self.line_numbers:
            parts.append(f"N{self._next_n}")
            self._next_n += self.line_number_step

        parts.extend(f"{word.address}{word.value}" for word in words)
        return " ".join(parts)

    def _dispatch_words(self, operation: Operation) -> list[Word]:
        handler = self._handlers.get(type(operation))

        if handler is None:
            raise NotImplementedError(
                f"{self.__class__.__name__} no tiene handler para {type(operation).__name__}"
            )

        return handler(operation)

    def _fmt(self, value: float) -> str:
        """Format values to a float value """
        precision = self.PRECISION_MM if self.state.units_mm else self.PRECISION_INCH
        return f"{value:.{precision}f}".rstrip("0")

# * Operations

    @abstractmethod
    def _axis_words(self, op) -> list[Word]:
        """Manipulate coordinates"""

    def _write_rapid_move(self, op: RapidMove) -> list[Word]:
        words: list[Word] = []

        if self.state.active_g != self.G_CODE.MOTION_RAPID:
            words.append(Word("G", str(self.G_CODE.MOTION_RAPID)))
            self.state.active_g = self.G_CODE.MOTION_RAPID
        words.extend(self._axis_words(op))

        return words

    def _write_tool_change(self, op: ToolChange) -> list[Word]:
        return [Word("T", op.tool_number), Word("M", str(self.M_CODE.TOOL_CHANGE))]

    def _write_cutter_comp(self, op: CutterCompensation) -> list[Word]:
        return [Word("G", str(self.G_CODE.CUTTER_COMP[op.mode]))]

    def _write_spindle_control(self, op: SpindleControl) -> list[Word]:
        return [Word("M", str(self.M_CODE.SPINDLE[op.mode]))]

    def _write_spindle_speed(self, op: SpindleSpeed) -> list[Word]:
        return [Word("S", str(int(op.rpm)))]
        
    def _write_coolant(self, op: CoolantControl) -> list[Word]:
        return [Word("M", str(self.M_CODE.COOLANT[op.mode]))]

    def _write_absolute(self, op: Absolute) -> list[Word]:
        self.state.absolute_mode = op.mode == AbsoluteMode.ABSOLUTE
        return [Word("G", str(self.G_CODE.ABSOLUTE[op.mode]))]

    def _write_rotation(self, op: CoordinateRotation) -> list[Word]:
        return [Word("G", str(self.G_CODE.ROTATION[op.enabled]))]

    def _write_contour_control(self, op: ContourControlMode) -> list[Word]:
        words = [Word("G", self.G_CODE.CONTOUR_CONTROL), Word("Q", str(op.q))]

        self.state.last_contour_tolerance = op.tolerance

        if op.tolerance is not None:
            words.append(Word("R", self._fmt(op.tolerance)))
        return words

    def _write_feed_rate(self, op: FeedRate) -> list[Word]:
        self.state.last_feed = op.value
        return [Word("F", self._fmt(op.value))]

    def _write_unit_mode(self, op: UnitMode) -> list[Word]:
        self.state.units_mm = op.value == Unit.MM
        return [Word("G", str(self.G_CODE.UNIT[op.value]))]

    def _write_coolant(self, op: CoolantControl) -> list[Word]:
        return [Word("M", str(self.M_CODE.COOLANT[op.mode]))]

    def _write_not_identified(self, op: NotIdentifyOperation) -> list[Word]:
        return [Word("(", f"UNMAPPED L{op.line_number}: {op.operation})")]

class GcodeIR(CodeDispatcher):

    def _absolute_mode(self, ctx : HandlerContext) -> Operation:
        ctx.state.absolute_mode = self.G_CODES.ABSOLUTE[ctx.value]
        return Absolute(mode=ctx.state.absolute_mode)

    def _unit(self, ctx : HandlerContext) -> Operation:
        ctx.state.units_mm = self.G_CODES.UNIT[ctx.value]
        return UnitMode(value=ctx.state.units_mm)

    def _cutter_compensation(self, ctx : HandlerContext) -> Operation:
        return CutterCompensation(mode=self.G_CODES.CUTTER_COMPENSATION[ctx.value])

    def _tool_compensation(self, ctx: HandlerContext) -> Operation:
        return ToolCompensation(mode=self.G_CODES.TOOL_COMPENSATION[ctx.value], offset=ctx.block.get("H"))

    def _rotation(self, ctx : HandlerContext) -> Operation:
        return CoordinateRotation(enabled=self.G_CODES.ROTATION[ctx.value])

    def _canned_cycle(self, ctx : HandlerContext):
        return CannedCycle(cycle=self.G_CODES.CANNED_CYCLE[ctx.value])

    def _work_coordinate_system(self, ctx: HandlerContext):
        if (ctx is None): return
        ctx.state.wcs = self.G_CODES.WORK_COORDINATE_SYSTEM[ctx.value]
        return WorkCoordinate(wcs=ctx.state.wcs)

    def _contour_control_mode(self, ctx: HandlerContext):
        q_countour = int(ctx.block.get("Q"))
        r_countor = ctx.block.get("R")

        if r_countor :
            ctx.state.last_contour_tolerance = int(r_countor)
        return ContourControlMode(q=q_countour, tolerance=ctx.state.last_contour_tolerance)

    def _cancel_offset(self, ctx: HandlerContext):
        ctx.state.wcs = None
        return CancelOffset()

    def _temporary_offset(self, ctx: HandlerContext):
        x, y, z, b, c = (
            _to_float_or_none(ctx.block.get(axis))
            for axis in ("X", "Y", "Z", "B", "C")
        )

        return LocalOffset(x=x, y=y, z=z, b=b, c=c)


class MCodeIR(CodeDispatcher):

    def _tool_change(self, ctx: HandlerContext)-> Operation:
        # ctx_tool_number = get_parameter_ctx(search_word="T", father_ctx=ctx)
        ToolAction = self.M_CODES.TOOL[ctx.value]
        if ToolAction is ToolChange:
            return ToolChange(tool_number=ctx.block.get("T"))

        return None

    def _coolant_control(self, ctx: HandlerContext)-> Operation:
        return CoolantControl(mode=self.M_CODES.COOLANT[ctx.value])

    def _spindle_control(self, ctx: HandlerContext) -> Operation :
        return SpindleControl(mode=self.M_CODES.SPINDLE_DIRECTION[ctx.value])

    def _program_end(self, ctx: HandlerContext) -> Operation  :
        return ProgramEnd()