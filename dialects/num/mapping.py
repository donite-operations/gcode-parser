from core.ir import (
    RapidMove, LinearMove, ToolChange,
    SpindleDirection, CoolantState, Dwell,
    AbsoluteMode, ToolCompensationMode, RotationMode, Unit, CycleType,
    CutterCompensationMode, WorkCoordinateSystem
)

COMMAND_CODES = {"G", "M", "T", "S", "F", "#"}


class GCodes():
    MOTION = {
        "0": RapidMove,
        "1": LinearMove,
    }

    ABSOLUTE = {
        "90": AbsoluteMode.ABSOLUTE,
        "91": AbsoluteMode.INCREMENTAL,
    }

    UNIT = {
        "20": Unit.INCH,
        "21": Unit.MM,
    }

    ROTATION = {
        "68": RotationMode.ON,
        "69": RotationMode.OFF,
    }

    CUTTER_COMPENSATION = {
        "40": CutterCompensationMode.OFF,
        "41": CutterCompensationMode.LEFT,
        "42": CutterCompensationMode.RIGHT,
    }


    TOOL_COMPENSATION = {
        "49": ToolCompensationMode.OFF,
        "43": ToolCompensationMode.LENGTH,
        "43.4": ToolCompensationMode.TCP,
    }

    DWELL = {
        "4": Dwell,
    }

    CANNED_CYCLE = {
        "80":CycleType.CANCEL,
        "81":CycleType.DRILL,
        "82":CycleType.DRILL_DWELL,
        "83":CycleType.TAP,
        "84":CycleType.TAP,
        "85":CycleType.BORE,
        "86":CycleType.BORE_STOP,
        "87":CycleType.BORE_MANUAL,
        "88":CycleType.BORE_DWELL_MANUAL,
        "88":CycleType.BORE_DWELL,
    }

    WCS = {
        "54":WorkCoordinateSystem.G54,
        "55":WorkCoordinateSystem.G55,
        "56":WorkCoordinateSystem.G56,
        "57":WorkCoordinateSystem.G57
    }

class MCodes():
    TOOL = {
        "6": ToolChange,
    }

    SPINDLE_DIRECTION = {
        "3": SpindleDirection.CLOCKWISE,
        "4": SpindleDirection.COUNTERCLOCKWISE,
        "5": SpindleDirection.STOP,
    }

    COOLANT = {
        "8": CoolantState.ON,
        "9": CoolantState.OFF,
    }

    PROGRAM_END = {
        "2",
        "30",
        "99",
    }