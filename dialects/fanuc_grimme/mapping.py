# dialects/fanuc/mapping.py
"""FANUC (ARES) codes -> IR meaning. Single source of truth for parser AND writer.

- Keys are written exactly as the writer emits them ("43.4", "5.1").
  The parser ignores leading zeros ("M06" matches "6").
- If several codes share a meaning, the FIRST one listed is the one written.
- A table name must have a handler in Parser.G_HANDLERS / M_HANDLERS.
"""
from core.ir import (
    Plane, ArcDirection,
    AbsoluteMode, CancelOffset, ContourControlMode, CoolantState,
    CutterCompensationMode, CycleType, Dwell, LinearMove, LocalOffset,
    ProgramEnd, RapidMove, RotationMode, SpindleDirection, ToolChange,
    ToolCompensationMode, Unit, WorkCoordinateSystem,
)


class GCodes:
    MOTION = {"0": RapidMove, "1": LinearMove, "2": ArcDirection.CW, "3": ArcDirection.CCW}

    ABSOLUTE = {"90": AbsoluteMode.ABSOLUTE, "91": AbsoluteMode.INCREMENTAL}

    UNIT = {"21": Unit.MM, "20": Unit.INCH}

    ROTATION = {"68": RotationMode.ON, "69": RotationMode.OFF}

    CUTTER_COMPENSATION = {
        "40": CutterCompensationMode.OFF,
        "41": CutterCompensationMode.LEFT,
        "42": CutterCompensationMode.RIGHT,
    }

    TOOL_COMPENSATION = {
        "49": ToolCompensationMode.OFF,
        "43": ToolCompensationMode.LENGTH,
        "43.4": ToolCompensationMode.TCP,  # ! TCP code depends on the control (G43.4 / G43.5)
    }

    DWELL = {"4": Dwell}  # G4 P<ms> | G4 X<s>

    CANNED_CYCLE = {
        "80": CycleType.CANCEL,
        "81": CycleType.DRILL,
        "82": CycleType.DRILL_DWELL,
        "83": CycleType.PECK_DRILL,
        "84": CycleType.TAP,
        "85": CycleType.BORE,
        "86": CycleType.BORE_STOP,
        "87": CycleType.BORE_MANUAL,
        "88": CycleType.BORE_DWELL_MANUAL,
        "89": CycleType.BORE_DWELL,
    }

    WORK_COORDINATE_SYSTEM = {
        "54": WorkCoordinateSystem.G54,
        "55": WorkCoordinateSystem.G55,
        "56": WorkCoordinateSystem.G56,
        "57": WorkCoordinateSystem.G57,
    }

    CONTOUR_CONTROL = {"5.1": ContourControlMode}  # G5.1 Q1 R5 / G5.1 Q0

    CANCEL_OFFSET = {"53": CancelOffset}  # G53: move in machine coordinates (one block)

    LOCAL_OFFSET = {"52": LocalOffset}  # G52: local offset added to the active WCS

    PLANE = {"17": Plane.XY, "18": Plane.ZX, "19": Plane.YZ}

class MCodes:
    TOOL_CHANGE = {"6": ToolChange}

    SPINDLE_DIRECTION = {
        "3": SpindleDirection.CLOCKWISE,
        "4": SpindleDirection.COUNTERCLOCKWISE,
        "5": SpindleDirection.STOP,
    }

    COOLANT = {"8": CoolantState.ON, "9": CoolantState.OFF}

    PROGRAM_END = {"30": ProgramEnd, "2": ProgramEnd, "99": ProgramEnd}


# Axis address -> IR field.
AXES = {"X": "x", "Y": "y", "Z": "z", "B": "b", "C": "c"}
# Arc words (G2/G3) -> IR field. Only used when the active motion is an arc.
ARC = {"I": "i", "J": "j", "K": "k", "R": "r"}
# Words that belong to a code when both are in the same block. They are handed
# to that code (ctx.params) and are never read as a move or as a command.
_CYCLE_WORDS = {"X", "Y", "Z", "R", "Q", "P", "F", "K", "L"}

CODE_PARAMETERS = {
    "G4": {"P", "X"},
    "G5.1": {"Q", "R"},
    "G43": {"H"},
    "G43.4": {"H"},
    "G52": {"X", "Y", "Z", "B", "C"},
    "G68": {"X", "Y", "Z", "I", "J", "K", "R"},
    **{f"G{n}": _CYCLE_WORDS for n in range(81, 90)},
    "M6": {"T"},
}
