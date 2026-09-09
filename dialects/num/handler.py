from dialects.num.mapping import GCodes, MCodes
from typing import Callable
from core.ir import (
    Block, Word, Program, ModalState, Operation, LinearMove,
    RapidMove, ProgramEnd, VariableRef, Expression,
    VariableAssignment, AbsoluteMode, ToolCompensation, CoordinateRotation, Dwell
)


class CodeDispatcher:
    DISPATCH: dict[int, Callable[[int, ModalState], Operation | None]] = {}

    @classmethod
    def dispatch(cls, code: int, state: ModalState) -> Operation | None:
        handler = cls.DISPATCH.get(code)
        print(cls.DISPATCH)
        print(handler)
        if handler is None:
            return None
        return handler(code, state)


class GCodeHandler(CodeDispatcher):
    @staticmethod
    def _motion(g: int, state: ModalState) -> Operation | None:
        state.active_g = g
        return None

    @staticmethod
    def _absolute_mode(g: int, state: ModalState) -> Operation | None:
        state.absolute_mode = GCodes.MODE[g]
        return None

    @staticmethod
    def _unit(g: int, state: ModalState) -> Operation | None:
        state.units_mm = (GCodes.UNIT[g] == "mm")
        return None

    @staticmethod
    def _tool_comp(g: int, state: ModalState) -> Operation | None:
        return ToolCompensation(mode=GCodes.TOOL_COMP[g])

    @staticmethod
    def _rotation(g: int, state: ModalState) -> Operation | None:
        return CoordinateRotation(enabled=GCodes.ROTATION[g])


class MCodeHandler(CodeDispatcher):
    @staticmethod
    def _operation(m: int, state: ModalState) -> Operation | None:
        # TODO: idealmente esto arma y devuelve un CoolantControl(...)
        # en vez de solo tocar estado — revisar contra tu IR.
        state.active_m = m
        return None


class NumHandler:
    @staticmethod
    def parse_value(raw: str) -> Expression:
        if raw.startswith("#"):
            return VariableRef(number=int(raw[1:]))
        return float(raw)

    @staticmethod
    def handle_variable_assignment(raw: str, state: ModalState) -> VariableAssignment:
        number_str, value_str = raw.split("=", 1)
        number, value = int(number_str), float(value_str)
        state.variables[number] = value
        return VariableAssignment(number=number, value=value)

    @staticmethod
    def handle_t_code(value: int, state: ModalState) -> Operation | None:
        return None

    @classmethod
    def dispatch(cls, address: str, value, state: ModalState):
        handler = cls._HANDLERS.get(address)
        return handler(value, state) if handler else None

NumHandler._HANDLERS = {
    "G": GCodeHandler.dispatch,
    "M": MCodeHandler.dispatch,
    "T": NumHandler.handle_t_code,
    # "#": NumHandler.handle_variable_assignment
}

GCodeHandler.DISPATCH = {
    **{g_code: GCodeHandler._motion for g_code in GCodes.MOTION},
    **{g_code: GCodeHandler._absolute_mode for g_code in GCodes.MODE},
    **{g_code: GCodeHandler._unit for g_code in GCodes.UNIT},
    **{g_code: GCodeHandler._tool_comp for g_code in GCodes.TOOL_COMP},
    **{g_code: GCodeHandler._rotation for g_code in GCodes.ROTATION},
}

MCodeHandler.DISPATCH = {
    **{m_code: MCodeHandler._operation for m_code in MCodes.COOLANT},
}
