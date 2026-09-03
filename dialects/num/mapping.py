from core.ir import RapidMove, LinearMove, ProgramEnd, ToolChange, SpindleDirection, CoolantState, DistanceMode


COMMAND_CODES = {"G", "M", "T", "S", "#"}

class GCodes:
    MOTION = {
        0: RapidMove,
        1: LinearMove,
    }

    MODE = {
        90: DistanceMode.ABSOLUTE,
        91: DistanceMode.INCREMENTAL,
    }

    UNIT = {
        20: "inch",
        21: "mm",
    }


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
    }