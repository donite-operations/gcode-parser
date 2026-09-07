from core.ir import (
    RapidMove, LinearMove, ProgramEnd, ToolChange, 
    SpindleDirection, CoolantState, 

    AbsoluteMode, CompensationMode, RotationMode
)


COMMAND_CODES = {"G", "M", "T", "S", "#"}

class GCodes:
    MOTION = {
        0: RapidMove,
        1: LinearMove,
    }

    MODE = {
        90: AbsoluteMode.ABSOLUTE,
        91: AbsoluteMode.INCREMENTAL,
    }

    UNIT = {
        20: "inch",
        21: "mm",
    }

    ROTATION = {
        68:RotationMode.ON,
        69:RotationMode.OFF
    }

    TOOL_COMP = {
        40: CompensationMode.OFF,
        41: CompensationMode.ON,
    }

    DWELL = {4}

class MCodes:
    TOOL = {
        6: ToolChange,
    }

    SPINDLE = {
        3: SpindleDirection.CLOCKWISE,
        4: SpindleDirection.COUNTERCLOCKWISE,
        5: SpindleDirection.STOP,
    }

    COOLANT = {
        8: CoolantState.ON,
        9: CoolantState.OFF,
    }

    PROGRAM_END = {
        2,
        30,
        99
    }