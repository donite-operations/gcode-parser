# dialects/num/mapping.py
"""GRIMME NUM codes -> IR meaning. Single source of truth for parser AND writer.

Same rules as fanuc/mapping.py (keys = written form, first listed wins).

Sources: examples/num_grimme.xpi and the NUM Flexium+ programming manual
(M00040EN-00, chapter 5.1 summary tables).

NOT mapped on purpose (-> NotIdentify / UNMAPPED comment):
    G5.1        not in the manual. Closest is G104 (3D curve smoothing), but it is a
                curve through points, not a tolerance mode like FANUC G5.1 Q R
    G68 / G69   not in the manual (NUM rotates with ED or G24)
    G53         NUM: cancel DAT1/DAT2 shifts (NOT machine coordinates like FANUC G53)
    G86-G88     NUM meanings have no CycleType (indexed-stop boring, chip-breaking
                drilling, boring and facing)
    G501        + E6xxxx= ...  DAT2 origin shift (written by the program header)
    G79 / VAR / ENDV / [NAME]=... / $ ...   jumps, variables, messages
    M72         OEM (open door)
"""
from core.ir import (
    Plane, ArcDirection,
    AbsoluteMode, CancelOffset, CoolantState,
    CutterCompensationMode, CycleType, Dwell, LinearMove, ProgramEnd,
    RapidMove, SpindleDirection, ToolChange, ToolCompensationMode, Unit,
    WorkCoordinateSystem, LocalOffset, CornerType
)


class GCodes:
    MOTION = {"0": RapidMove, "1": LinearMove, "2": ArcDirection.CW, "3": ArcDirection.CCW}

    ABSOLUTE = {"90": AbsoluteMode.ABSOLUTE, "91": AbsoluteMode.INCREMENTAL}

    UNIT = {"71": Unit.MM, "70": Unit.INCH}  # NUM uses G70/G71, not G20/G21

    PLANE = {"17": Plane.XY, "18": Plane.ZX, "19": Plane.YZ}

    CUTTER_COMPENSATION = {
        "40": CutterCompensationMode.OFF,
        "41": CutterCompensationMode.LEFT,
        "42": CutterCompensationMode.RIGHT,
    }

    # G151 is ONE code for TCP on AND off; its words decide which
    # (NumGrimmeParser._tcp):  "G151 EA0 EC0 EU0 T1 D1" -> TCP on, offset D
    #                    "G151 S0"                -> TCP off
    # Same role as FANUC G43.4 H<n> / G49. Plain length correction is D<n> alone.
    TOOL_COMPENSATION = {"151": ToolCompensationMode.TCP}

    DWELL = {"4": Dwell}  # G4 F<seconds>  (sample: "G4 F2 (DWELL TIME)")

    CANNED_CYCLE = {
        "80": CycleType.CANCEL,
        "81": CycleType.DRILL,
        "82": CycleType.DRILL_DWELL,
        "83": CycleType.PECK_DRILL,
        "84": CycleType.TAP,
        "85": CycleType.BORE,        # NUM: reaming
        "89": CycleType.BORE_DWELL,  # NUM: boring with dwell at the bottom
        # 86 / 87 / 88 mean something else on NUM: not mapped (see top of file)
    }

    WORK_COORDINATE_SYSTEM = {
        "54": WorkCoordinateSystem.G54,  # sample: "G54 (NP-1)"
        "55": WorkCoordinateSystem.G55,
        "56": WorkCoordinateSystem.G56,
        "57": WorkCoordinateSystem.G57,
    }

    # NUM G52 = move relative to the MACHINE origin, one block
    # (sample: "LOADING POSITION IN REL TO ORIGIN MACHINE"). Same as FANUC G53.
    CANCEL_OFFSET = {"52": CancelOffset}
    LOCAL_OFFSET = {"59": LocalOffset}  # G52: local offset added to the active WCS

    # No LOCAL_OFFSET table: FANUC G52 has no confirmed Grimme equivalent.


class MCodes:
    TOOL_CHANGE = {"06": ToolChange}  # sample: "T1 M06"

    SPINDLE_DIRECTION = {
        "3": SpindleDirection.CLOCKWISE,
        "4": SpindleDirection.COUNTERCLOCKWISE,
        "5": SpindleDirection.STOP,
    }

    COOLANT = {"7": CoolantState.ON, "8": CoolantState.ON, "9": CoolantState.OFF}  # sample: M7 / M9

    PROGRAM_END = {"02": ProgramEnd}  # sample: "M02"


# Axis address -> IR field. The IR has no 'a': Grimme's A axis is stored in 'b'
# (FANUC ARES writes it as B). Same assumption the previous NUM writer made.
AXES = {"X": "x", "Y": "y", "Z": "z", "A": "b", "C": "c"}

# Arc words (G2/G3) -> IR field. Manual: "G02 X.. Y.. I..J.. or R.. [F..]"
ARC = {"I": "i", "J": "j", "K": "k", "R": "r"}

# Every word the manual lists for G81-G89 (so they stay with their cycle).
_CYCLE_WORDS = {"X", "Y", "Z", "ER", "EH", "EF", "P", "ES", "Q", "EP", "K", "EK", "EC", "EA", "F"}

CORNER = {"EB": CornerType.ROUND}

CODE_PARAMETERS = {
    "G4": {"F"},  # G4 F2 -> F is the dwell time, NOT a feed rate
    "G59": {"X", "Y", "Z", "U", "V", "W", "A", "B", "C", "I", "J", "K", "ED"},
    **{f"G{n}": _CYCLE_WORDS for n in range(81, 90)},
    "M6": {"T"},
    "G151": {"S", "EA", "EC", "EU", "T", "D"},  # "G151 S0" must NOT become spindle S0
    # Unmapped codes: listed only so their words are reported with them
    # (and "G5.1 Q1 R5" R is not read as an arc radius).
    "G5.1": {"Q", "R"},
    "G79": {"N"},
}
