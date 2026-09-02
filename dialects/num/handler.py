
from dialects.num.mapping import PARSE_MOTION_CODES, ABSOLUTE_MODE_CODES, UNIT_CODES, PROGRAM_END_CODES
from core.ir import Block, Word, Program, ModalState, Operation, LinearMove, RapidMove, ProgramEnd

def handle_g_code(g:str, state: ModalState):
    if g in ABSOLUTE_MODE_CODES:
        state.absolute_mode = ABSOLUTE_MODE_CODES[g]
        return None
    if g in UNIT_CODES:
        state.units_mm = (UNIT_CODES[g] == "mm")
        return None
    if g in PARSE_MOTION_CODES:
        state.active_g = g
