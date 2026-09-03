
from dialects.num.mapping import GCodes, MCodes

from core.ir import (
    Block, Word, Program, ModalState, Operation, LinearMove, 
    RapidMove, ProgramEnd, VariableRef, Expression,
    VariableAssignment
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

    @staticmethod
    def handle_g_code(g:int, state: ModalState) -> Operation | None :
        if g in GCodes.MOTION:
            state.absolute_mode = GCodes.MODE[g]
            return None
        if g in GCodes.UNIT:
            state.units_mm = (GCodes.MODE[g] == "mm")
            return None
        if g in GCodes.MODE:
            state.active_g = g

    @staticmethod
    def handle_m_code(m:int) -> Operation | None :
        return 
        pass

    @staticmethod
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
