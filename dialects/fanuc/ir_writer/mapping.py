from core.ir import (
    RapidMove, LinearMove, ToolChange,
    SpindleDirection, CoolantState, Dwell,
    AbsoluteMode, ToolCompensationMode, RotationMode, Unit, CycleType,
    CutterCompensationMode, WorkCoordinateSystem
)

class GCodes():

    MOTION_RAPID = 0

    MOTION_LINEAR = 1

    ABSOLUTE = {AbsoluteMode.ABSOLUTE: 90, AbsoluteMode.INCREMENTAL: 91}

    UNIT = {Unit.MM: 21, Unit.INCH: 20}

    CUTTER_COMP = {
        CutterCompensationMode.OFF: 40,
        CutterCompensationMode.LEFT: 41,
        CutterCompensationMode.RIGHT: 42,
    }

    TOOL_COMP = {
        ToolCompensationMode.OFF: 49,
        ToolCompensationMode.LENGTH: 43,
        ToolCompensationMode.TCP: "43.4",  # ! revisar: TCP varía según control (G43.4/G43.5)
    }

    ROTATION = {RotationMode.ON: 68, RotationMode.OFF: 69}
    WCS = {
        WorkCoordinateSystem.G54: 54,
        WorkCoordinateSystem.G55: 55,
        WorkCoordinateSystem.G56: 56,
        WorkCoordinateSystem.G57: 57,
    }

    CYCLE = {
        CycleType.CANCEL: 80,
        CycleType.DRILL: 81,
        CycleType.DRILL_DWELL: 82,
        CycleType.PECK_DRILL: 83,
        CycleType.TAP: 84,
        CycleType.BORE: 85,
        CycleType.BORE_STOP: 86,
        CycleType.BORE_MANUAL: 87,
        CycleType.BORE_DWELL_MANUAL: 88,
        CycleType.BORE_DWELL: 89,
    }
    LOCAL_OFFSET = 52
    CANCEL_OFFSET = 53
    CONTOUR_CONTROL = "5.1"

class MCodes():
    SPINDLE = {
        SpindleDirection.CLOCKWISE: 3,
        SpindleDirection.COUNTERCLOCKWISE: 4,
        SpindleDirection.STOP: 5,
    }
    COOLANT = {CoolantState.ON: 8, CoolantState.OFF: 9}
    TOOL_CHANGE = 6
    PROGRAM_END = 30
