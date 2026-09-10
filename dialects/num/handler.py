from dialects.num.mapping import GCodes, MCodes
from typing import Callable
from core.ir import (
    Block, Word, Program, ModalState, Operation, LinearMove,
    RapidMove, ProgramEnd, VariableRef, Expression,
    VariableAssignment, ToolCompensation, CoordinateRotation, Dwell,
    CannedCycle, HandlerContext,Absolute, UnitMode, FeedRate
)

def _to_float_or_none(value):
    return float(value) if value is not None else None

class CodeDispatcher:
    DISPATCH: dict[str, Callable[[HandlerContext], Operation | None]] = {}

    @classmethod
    def dispatch(cls, ctx: HandlerContext) -> Operation | None:
        handler = cls.DISPATCH.get(ctx.value)
        return handler(ctx) if handler else None


class GCodeHandler(CodeDispatcher):

    @staticmethod
    def _motion(ctx : HandlerContext) -> Operation | None:
        x, y, z, c, d = (
            _to_float_or_none(ctx.block.get(axis))
            for axis in ("X", "Y", "Z", "C", "D")
        )

        # TODO: Tengo que crear la funcion que extraiga de la variable ve a FeedRate
        feedrate = ctx.block.get('F')
        if feedrate is not None:
            feedrate_ctx = HandlerContext(command="F", value=feedrate, state=ctx.state) # Need to build HandlerContext because the ctx is for the motion
            ParameterHandler._feedrate(feedrate_ctx)
        if x is not None or y is not None or z is not None:
            op_class = GCodes.MOTION[ctx.value]
            if op_class is LinearMove:
                return LinearMove(x=x, y=y, z=z, feed=ctx.state.last_feed)
            elif op_class is RapidMove:
                return RapidMove(x=x, y=y, z=z)

        return None

    @staticmethod
    def _absolute_mode(ctx : HandlerContext) -> Operation | None:
        ctx.state.absolute_mode = GCodes.ABSOLUTE[ctx.value]
        return Absolute(mode=ctx.state.absolute_mode)

    @staticmethod
    def _unit(ctx : HandlerContext) -> Operation | None:
        ctx.state.units_mm = (GCodes.UNIT[ctx.value] == "mm")
        return UnitMode(value=ctx.state.units_mm)

    @staticmethod
    def _tool_comp(ctx : HandlerContext) -> Operation | None:
        return ToolCompensation(mode=GCodes.TOOL_COMP[ctx.value])

    @staticmethod
    def _rotation(ctx : HandlerContext) -> Operation | None:
        return CoordinateRotation(enabled=GCodes.ROTATION[ctx.value])

    @staticmethod
    def _canned_cycle(ctx : HandlerContext):
        return CannedCycle(cycle=GCodes.CANNED_CYCLE[ctx.value])


class MCodeHandler(CodeDispatcher):
    @staticmethod
    def _operation(ctx : HandlerContext) -> Operation | None:
        # TODO: idealmente esto arma y devuelve un CoolantControl(...)
        # en vez de solo tocar estado — revisar contra tu IR.
        ctx.state.active_m = ctx.value
        return None

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
        #! Remeber if ParameterHandler is not Working use cls with the decorator @classmethod
        expression = ParameterHandler._parse_variable_expression(ctx.value)
        if isinstance(expression, VariableRef):
            value = ctx.state.variables[expression.number]
        else:
            value = expression

        ctx.state.last_feed = value
        return FeedRate(value=value)

class NumHandler:
    @staticmethod
    def parse_value(raw: str) -> Expression:
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
    def handle_t_code(ctx : HandlerContext) -> Operation | None:
        return None

    @classmethod
    def dispatch(cls, ctx: HandlerContext):
        handler = cls.COMMAND_HANDLERS.get(ctx.command)
        return handler(ctx) if handler else None

NumHandler.COMMAND_HANDLERS = {
    "G": GCodeHandler.dispatch,
    "M": MCodeHandler.dispatch,
    "T": NumHandler.handle_t_code,
    "#": ParameterHandler._variable_assignment,
    "F": ParameterHandler._feedrate
}

GCodeHandler.DISPATCH = {
    **{g_code: GCodeHandler._motion for g_code in GCodes.MOTION},
    **{g_code: GCodeHandler._absolute_mode for g_code in GCodes.ABSOLUTE},
    **{g_code: GCodeHandler._unit for g_code in GCodes.UNIT},
    **{g_code: GCodeHandler._tool_comp for g_code in GCodes.TOOL_COMP},
    **{g_code: GCodeHandler._rotation for g_code in GCodes.ROTATION},
}

MCodeHandler.DISPATCH = {
    **{m_code: MCodeHandler._operation for m_code in MCodes.COOLANT},
}

ParameterHandler.DISPATCH = {
    "#": ParameterHandler._variable_assignment,
    "F": ParameterHandler._feedrate
}