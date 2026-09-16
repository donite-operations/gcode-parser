from dialects.num.mapping import GCodes, MCodes
from typing import Callable
from core.ir import (
    Operation, Expression,
    LinearMove, RapidMove, ProgramEnd, VariableRef, ToolChange, CutterCompensation,
    VariableAssignment, ToolCompensation, CoordinateRotation, Dwell, SpindleSpeed,
    CannedCycle, HandlerContext,Absolute, UnitMode, FeedRate, SpindleControl, CoolantControl,
    WorkCoordinate
)
import time

def _to_float_or_none(value):
    return float(value) if value is not None else None

def get_parameter_ctx(search_word: str, father_ctx: HandlerContext, look_for: list[str] = []) -> HandlerContext | None:
    #! father_ctx.block. 
    word_value = father_ctx.block.get(search_word)
    if word_value is None:
        return None

    return HandlerContext(command=search_word, value=word_value, state=father_ctx.state) # Need to build HandlerContext because the ctx is for the motion

class CodeDispatcher:
    DISPATCH: dict[str, Callable[[HandlerContext], Operation | None]] = {}

    @classmethod
    def dispatch(cls, ctx: HandlerContext) -> Operation | None:
        handler = cls.DISPATCH.get(ctx.value)
        return handler(ctx) if handler else None


class GCodeHandler(CodeDispatcher):

    @staticmethod
    def _motion(ctx : HandlerContext) -> Operation:
        x, y, z, b, c = (
            _to_float_or_none(ctx.block.get(axis))
            for axis in ("X", "Y", "Z", "B", "C")
        )
        ctx_feedrate = get_parameter_ctx(search_word="F", father_ctx=ctx)
        ParameterHandler._feedrate(ctx_feedrate)
        ctx_wcs = get_parameter_ctx(search_word="G", father_ctx=ctx)
        GCodeHandler._work_coordinate_system(search_)
        #! take in count that if there's no movement it is not necessary to have the motion movement on the line

        op_class = GCodes.MOTION[ctx.value]
        if op_class is LinearMove:
            return LinearMove(x=x, y=y, z=z, b=b, c=c, feed=ctx.state.last_feed, wcs=ctx.state.wcs)
        elif op_class is RapidMove:
            return RapidMove(x=x, y=y, z=z, b=b, c=c, wcs=ctx.state.wcs)

    @staticmethod
    def _absolute_mode(ctx : HandlerContext) -> Operation:
        ctx.state.absolute_mode = GCodes.ABSOLUTE[ctx.value]
        return Absolute(mode=ctx.state.absolute_mode)

    @staticmethod
    def _unit(ctx : HandlerContext) -> Operation:
        ctx.state.units_mm = GCodes.UNIT[ctx.value]
        return UnitMode(value=ctx.state.units_mm)

    @staticmethod
    def _cutter_compensation(ctx : HandlerContext) -> Operation:
        return CutterCompensation(mode=GCodes.CUTTER_COMPENSATION[ctx.value])

    @staticmethod
    def _tool_compensation(ctx: HandlerContext) -> Operation:
        return ToolCompensation(mode=GCodes.TOOL_COMPENSATION[ctx.value], offset=ctx.block.get("H"))

    @staticmethod
    def _rotation(ctx : HandlerContext) -> Operation:
        return CoordinateRotation(enabled=GCodes.ROTATION[ctx.value])

    @staticmethod
    def _canned_cycle(ctx : HandlerContext):
        return CannedCycle(cycle=GCodes.CANNED_CYCLE[ctx.value])

    @staticmethod
    def _work_coordinate_system(ctx: HandlerContext):
        ctx.state.wcs = WorkCoordinate[ctx.value]
        return WorkCoordinate(wcs=ctx.state.wcs)

class MCodeHandler(CodeDispatcher):

    @staticmethod
    def _tool_change(ctx: HandlerContext)-> Operation:
        # ctx_tool_number = get_parameter_ctx(search_word="T", father_ctx=ctx)
        ToolAction = MCodes.TOOL[ctx.value]
        if ToolAction is ToolChange:
            return ToolChange(tool_number=ctx.block.get("T"))

        return None

    @staticmethod
    def _coolant_control(ctx: HandlerContext)-> Operation:
        return CoolantControl(mode=MCodes.COOLANT[ctx.value])

    @staticmethod
    def _spindle_control(ctx: HandlerContext) -> Operation :
        return SpindleControl(mode=MCodes.SPINDLE_DIRECTION[ctx.value])

    @staticmethod
    def _operation(ctx : HandlerContext) -> Operation :
        # TODO: idealmente esto arma y devuelve un CoolantControl(...)
        # en vez de solo tocar estado — revisar contra tu IR.
        ctx.state.active_m = ctx.value
        return None

    @staticmethod
    def _program_end(ctx: HandlerContext) -> Operation  :
        return ProgramEnd()

class ParameterHandler(CodeDispatcher):

    @staticmethod
    def _parse_variable_expression(raw: str) -> Expression:
        if raw.startswith("#"):
            return VariableRef(number=int(raw[1:]))
        return float(raw)

    @staticmethod
    def _variable_assignment(ctx: HandlerContext) -> VariableAssignment:
        number_str, value_str = ctx.value.split("=", 1)
        number, value = int(number_str), float(value_str)
        ctx.state.variables[number] = value
        return VariableAssignment(number=number, value=value)

    @staticmethod
    def _feedrate(ctx : HandlerContext):
        if (ctx is None): return
        #! Remeber if ParameterHandler is not working use cls with the decorator @classmethod
        expression = ParameterHandler._parse_variable_expression(ctx.value)
        if isinstance(expression, VariableRef):
            value = ctx.state.variables[expression.number]
        else:
            value = expression

        ctx.state.last_feed = value
        return FeedRate(value=value)

    @staticmethod
    def _tool_number(ctx: HandlerContext):
        ctx_feedrate = get_parameter_ctx(search_word="T", father_ctx=ctx)
        return

    @staticmethod
    def _spindle_speed(ctx: HandlerContext):
        return SpindleSpeed(rpm=float(ctx.value))

class NumHandler:

    @classmethod
    def dispatch(cls, ctx: HandlerContext):
        handler = cls.COMMAND_HANDLERS.get(ctx.command)
        return handler(ctx) if handler else None

NumHandler.COMMAND_HANDLERS = {
    "G": GCodeHandler.dispatch,
    "M": MCodeHandler.dispatch,
    "#": ParameterHandler._variable_assignment,
    "F": ParameterHandler._feedrate,
    "S": ParameterHandler._spindle_speed
}

GCodeHandler.DISPATCH = {
    **{g_code: GCodeHandler._motion for g_code in GCodes.MOTION},
    **{g_code: GCodeHandler._absolute_mode for g_code in GCodes.ABSOLUTE},
    **{g_code: GCodeHandler._unit for g_code in GCodes.UNIT},
    **{g_code: GCodeHandler._cutter_compensation for g_code in GCodes.CUTTER_COMPENSATION},
    **{g_code: GCodeHandler._rotation for g_code in GCodes.ROTATION},
    **{g_code: GCodeHandler._canned_cycle for g_code in GCodes.CANNED_CYCLE},
    **{g_code: GCodeHandler._tool_compensation for g_code in GCodes.TOOL_COMPENSATION},


}

MCodeHandler.DISPATCH = {
    **{m_code: MCodeHandler._spindle_control for m_code in MCodes.SPINDLE_DIRECTION},
    **{m_code: MCodeHandler._coolant_control for m_code in MCodes.COOLANT},
    **{m_code: MCodeHandler._tool_change for m_code in MCodes.TOOL},
    **{m_code: MCodeHandler._program_end for m_code in MCodes.PROGRAM_END},

}

ParameterHandler.DISPATCH = {
    "#": ParameterHandler._variable_assignment,
    "F": ParameterHandler._feedrate
}