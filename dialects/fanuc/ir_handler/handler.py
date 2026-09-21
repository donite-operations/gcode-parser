import time

from dataclasses import replace
from dialects.fanuc.ir_handler.mapping import GCodes, MCodes
from dialects.base import GcodeIR, MCodeIR, CodeDispatcher, _to_float_or_none, get_parameter_ctx
from core.ir import (
    Operation, Expression,
    LinearMove, RapidMove, ProgramEnd, VariableRef, ToolChange, CutterCompensation,
    VariableAssignment, ToolCompensation, CoordinateRotation, Dwell, SpindleSpeed,
    CannedCycle, HandlerContext,Absolute, UnitMode, FeedRate, SpindleControl, CoolantControl,
    WorkCoordinate, NotIdentifyOperation, ContourControlMode, CancelOffset, LocalOffset
)
 

class GCodeHandler(GcodeIR):
    G_CODES = GCodes

    def _motion(self, ctx : HandlerContext) -> Operation:
        x, y, z, b, c = (
            _to_float_or_none(ctx.block.get(axis))
            for axis in ("X", "Y", "Z", "B", "C")
        )
        ctx_feedrate = get_parameter_ctx(search_word="F", father_ctx=ctx)
        ParameterHandler._feedrate(ctx_feedrate)

        #! take in count that if there's no movement it is not necessary to have the motion movement on the line
        ctx_wcs = get_parameter_ctx(search_word="G", father_ctx=ctx, look_for=GCodes.WORK_COORDINATE_SYSTEM)
        self._work_coordinate_system(ctx=ctx_wcs)

        op_class = GCodes.MOTION[ctx.value]
        if op_class is LinearMove:
            return LinearMove(x=x, y=y, z=z, b=b, c=c, feed=ctx.state.last_feed, wcs=ctx.state.wcs)
        elif op_class is RapidMove:
            return RapidMove(x=x, y=y, z=z, b=b, c=c, wcs=ctx.state.wcs)


class MCodeHandler(MCodeIR):

    M_CODES = MCodes

    def _tool_change(self, ctx: HandlerContext)-> Operation:
        # ctx_tool_number = get_parameter_ctx(search_word="T", father_ctx=ctx)
        ToolAction = self.M_CODES.TOOL[ctx.value]
        if ToolAction is ToolChange:
            return ToolChange(tool_number=ctx.block.get("T"))

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

class FanucHandler:

    @classmethod
    def dispatch(cls, ctx: HandlerContext):
        handler = cls.COMMAND_HANDLERS.get(ctx.command)
        operation = None
        not_Identified = False

        if handler :
            operation = handler(ctx)

        return NotIdentifyOperation(
            line_number=ctx.block.line_number, operation=ctx.command+ctx.value
        ) if operation and not_Identified is None else operation

        # return handler(ctx) if handler else None

gcode_handler = GCodeHandler()
mcode_handler = MCodeHandler()
parameter_handler = ParameterHandler()

FanucHandler.COMMAND_HANDLERS = {
    "G": gcode_handler.dispatch,
    "M": mcode_handler.dispatch,
    "#": parameter_handler._variable_assignment,
    "F": parameter_handler._feedrate,
    "S": parameter_handler._spindle_speed,
}

GCodeHandler.DISPATCH = {
    **{g_code: gcode_handler._motion for g_code in GCodes.MOTION},
    **{g_code: gcode_handler._absolute_mode for g_code in GCodes.ABSOLUTE},
    **{g_code: gcode_handler._unit for g_code in GCodes.UNIT},
    **{g_code: gcode_handler._cutter_compensation for g_code in GCodes.CUTTER_COMPENSATION},
    **{g_code: gcode_handler._rotation for g_code in GCodes.ROTATION},
    **{g_code: gcode_handler._canned_cycle for g_code in GCodes.CANNED_CYCLE},
    **{g_code: gcode_handler._tool_compensation for g_code in GCodes.TOOL_COMPENSATION},
    **{g_code: gcode_handler._work_coordinate_system for g_code in GCodes.WORK_COORDINATE_SYSTEM},
    **{g_code: gcode_handler._contour_control_mode for g_code in GCodes.CONTOUR_MODE},
    **{g_code: gcode_handler._cancel_offset for g_code in GCodes.CANCEL_OFFSET},
    **{g_code: gcode_handler._temporary_offset for g_code in GCodes.TEMPORARY_OFFSET},
}

MCodeHandler.DISPATCH = {
    **{m_code: mcode_handler._spindle_control for m_code in MCodes.SPINDLE_DIRECTION},
    **{m_code: mcode_handler._coolant_control for m_code in MCodes.COOLANT},
    **{m_code: mcode_handler._tool_change for m_code in MCodes.TOOL},
    **{m_code: mcode_handler._program_end for m_code in MCodes.PROGRAM_END},
}


ParameterHandler.DISPATCH = {
    "#": parameter_handler._variable_assignment,
    "F": parameter_handler._feedrate,
}
