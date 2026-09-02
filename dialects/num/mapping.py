from core.ir import RapidMove, LinearMove, ProgramEnd, ToolChange, SpindleDirection, CoolantState


COMMAND_CODES = {"G", "M", "T", "S"}

#! G-Codes

PARSE_MOTION_CODES = {
    0: RapidMove,
    1: LinearMove,
}

# G-Code Absolute Position 
ABSOLUTE_MODE_CODES = {
    90: True, 
    91: False
}

# G-Code Measurement unit 
UNIT_CODES = {
    21: "mm", 
    20: "inch"
}

#! M-Codes

TOOL_CODES = {
    6: ToolChange
}

SPINDLE_CODES = {
    3: SpindleDirection.CLOCKWISE,
    4: SpindleDirection.COUNTERCLOCKWISE,
    5: SpindleDirection.STOP,
}

COOLANT_CODES = {
    8: CoolantState.ON,
    9: CoolantState.OFF,
}

PROGRAM_END_CODES = {30, 2}

