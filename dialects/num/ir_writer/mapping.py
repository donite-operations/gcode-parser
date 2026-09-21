# dialects/num/mapping.py
"""IR -> NUM / Huber-Grimme mapping.

The mapping combines:
- the current IR model;
- the supplied Grimme .xpi program;
- the other supplied Grimme-style program;
- NUM 1060 programming conventions for generic NUM functions.

Some functions are machine/postprocessor dependent (especially G151 and
G68/G69), so those values are kept centralized here.
"""

from core.ir import (
    AbsoluteMode,
    CoolantState,
    CutterCompensationMode,
    CycleType,
    RotationMode,
    SpindleDirection,
    ToolCompensationMode,
    Unit,
    WorkCoordinateSystem,
)


class GCodes:
    # Interpolation
    MOTION_RAPID = 0
    MOTION_LINEAR = 1

    # Positioning
    ABSOLUTE = {
        AbsoluteMode.ABSOLUTE: 90,
        AbsoluteMode.INCREMENTAL: 91,
    }

    # NUM 1060 uses G70/G71 for unit selection.
    UNIT = {
        Unit.INCH: 70,
        Unit.MM: 71,
    }

    # Tool radius compensation
    CUTTER_COMP = {
        CutterCompensationMode.OFF: 40,
        CutterCompensationMode.LEFT: 41,
        CutterCompensationMode.RIGHT: 42,
    }

    # Tool length correction is selected with D.. on NUM.
    TOOL_LENGTH = "D"

    # Huber/Grimme 5-axis examples use G151 for RTCP.
    # G151 S1 -> RTCP on
    # G151 S0 -> RTCP off
    TCP = 151
    TCP_ON = 1
    TCP_OFF = 0

    # The other supplied Grimme-style program uses G68/G69.
    # Keep this here because it is a postprocessor-dependent function.
    ROTATION = {
        RotationMode.ON: 68,
        RotationMode.OFF: 69,
    }

    WCS = {
        WorkCoordinateSystem.G54: 54,
        WorkCoordinateSystem.G55: 55,
        WorkCoordinateSystem.G56: 56,
        WorkCoordinateSystem.G57: 57,
    }

    # NUM 1060 milling cycles.
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

    # G52 is used by the supplied Grimme programs for measurement/local
    # coordinate programming.
    LOCAL_OFFSET = 52

    # NUM 1060 also has G59 for programmed-origin shifts.  The current IR
    # models CancelOffset separately, so keep this available for the writer.
    PROGRAM_OFFSET = 59

    # G5.1 appears in the other supplied Grimme-style program as contour/
    # look-ahead control: G5.1 Q1 R5 / G5.1 Q0.
    CONTOUR_CONTROL = "5.1"

    # Dwell in the supplied Grimme program: G4 F2 / G4 F1.5.
    DWELL = 4

    # Useful NUM functions even though the current IR has no dedicated
    # operation for them yet.
    MACHINE_COORDINATE = 53
    PLANE_XY = 17
    PLANE_ZX = 18
    PLANE_YZ = 19
    SPACE_TOOL_CORRECTION = 29


class MCodes:
    SPINDLE = {
        SpindleDirection.CLOCKWISE: 3,
        SpindleDirection.COUNTERCLOCKWISE: 4,
        SpindleDirection.STOP: 5,
    }

    # The supplied Huber/Grimme program uses M7 for coolant ON and M9 OFF.
    # NUM 1060 supports M7/M8 as the two coolant outputs.
    COOLANT = {
        CoolantState.ON: 7,
        CoolantState.OFF: 9,
    }

    # Exact formatting used by the supplied program is T1 M06.
    TOOL_CHANGE = "06"

    # Supplied Grimme program ends with M02.
    PROGRAM_END = "02"
