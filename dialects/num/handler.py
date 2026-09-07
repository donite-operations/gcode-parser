
from dialects.num.mapping import GCodes, MCodes

from core.ir import (
    Block, Word, Program, ModalState, Operation, LinearMove, 
    RapidMove, ProgramEnd, VariableRef, Expression,
    VariableAssignment,AbsoluteMode, ToolCompensation, CoordinateRotation, Dwell
)

class NumHandler:
    _HANDLERS = {}

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

    @classmethod
    def handle_g_code(cls, g: int, state: ModalState) -> Operation | None:
        handler = GCodeHandler.DISPATCH.get(g)
        if handler is None:
            return None  # Not code-g supported
        return handler(g, state)

    @classmethod
    def handle_m_code(m:int) -> Operation | None :
        return 
        pass

    @classmethod
    def handle_t_code(f:int) -> Operation | None:
        pass

    _HANDLERS = {
        "G": handle_g_code,
        "M": handle_m_code,
        "T": handle_t_code,
        "#": handle_variable_assignment
    }

    @classmethod
    def dispatch(cls, adress: str, value, state):
        handler = cls._HANDLERS.get(adress)
        return handler(value, state) if handler else None

class GCodeHandler:
    @staticmethod
    def _motion(g: int, state: ModalState) -> Operation | None:
        state.active_g = g
        return None

    @staticmethod
    def _distance_mode(g: int, state: ModalState) -> Operation | None:
        state.absolute_mode = GCodes.MODE[g]
        return None

    @staticmethod
    def _unit(g: int, state: ModalState) -> Operation | None:
        state.units_mm = (GCodes.UNIT[g] == "mm")
        return None

    @staticmethod
    def _tool_comp(g: int, state: ModalState) -> Operation | None:
        return ToolCompensation(mode=GCodes.CUTTER_COMP[g])

    @staticmethod
    def _rotation(g: int, state: ModalState) -> Operation | None:
        return CoordinateRotation(enabled=GCodes.ROTATION[g])

    @staticmethod
    def _canned_cycle(g: int, state: ModalState) -> Operation | None:
        return Dwell(type=GCodes.CANNED_CYCLE[g])

    @classmethod
    def handle_g_code(cls, g: int, state: ModalState) -> Operation | None:
        if cls.DISPATCH is None:
            cls.DISPATCH = {
                **{g_code: cls._motion for g_code in GCodes.MOTION},
                **{g_code: cls._distance_mode for g_code in GCodes.MODE},
                **{g_code: cls._unit for g_code in GCodes.UNIT},
                **{g_code: cls._tool_comp for g_code in GCodes.CUTTER_COMP},
                **{g_code: cls._rotation for g_code in GCodes.ROTATION},
                **{g_code: cls._canned_cycle for g_code in GCodes.CANNED_CYCLE},
            }

        handler = cls.DISPATCH.get(g)
        if handler is None:
            return None #Not Supported code
        return handler(g, state)
