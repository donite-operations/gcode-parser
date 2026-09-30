# dialects/num/parser.py
"""GRIMME NUM text -> IR. Everything NUM-specific lives here."""
import re

from core.ir import (
    ArcDirection, CircularMove, Dwell, FeedRate, LinearMove, RapidMove, ToolCompensation, ToolCompensationMode,
    LocalOffset, Corner, CornerType
    )
from dialects.base import Parser, IR_AXES
from dialects.num_grimme import mapping


class NumGrimmeParser(Parser):
    MAPPING = mapping
    BEGIN_MARKERS = ("( ------------- 5X BEGIN ----------- )",)
    END_MARKERS = ("( ------- 5x END ------- )",)  # the comma makes it a tuple
    # Two-letter addresses (EA, EC, EU, ER, EF, FL...) and "E60001= 0" style assignments.
    # The value is optional: in NUM "G1 X" means X0.
    TOKEN_PATTERN = re.compile(r"([A-Z]{1,2})(\d+\s*=\s*[-+]?[\d.]+|[-+]?(?:\d+\.?\d*|\.\d+))?")

    SAFETY_LINES = (
        "G52 G17 G90 G0 Z650",
        "G52 G17 G90 G0 X540",
        "G52 G17 G90 G0 X540 Y-600 Z650 A0 C0",
        "G52 G17 G90 G0 X540 Y-600 A0 C0",
        "G52 G17 G90 G0 Z500",                   # Plate_NUM_GRIMME.XPI
        "G52 G17 G90 G0 X500 Y-400 Z500 A0 C0",
    )

    # NUM-only syntax the IR cannot represent: kept whole as NotIdentify.
    RAW_LINE_PATTERNS = (
        *Parser.RAW_LINE_PATTERNS,    # "/" block skip
        re.compile(r"^(VAR|ENDV)$"),  # variable block markers
        re.compile(r"^\[\w+\]\s*="),  # [TOOL_L_T1]=E50001/1000
        re.compile(r"^G79\s*\["),     # G79 [TOOL_L_T1]< 20 N9980
        re.compile(r"^\$"),           # $ operator message
    )

    G_HANDLERS = {
        **Parser.G_HANDLERS,
        "TOOL_COMPENSATION": "_tcp",
        "DWELL": "_dwell",
    }
    ADDRESS_HANDLERS = {
        **Parser.ADDRESS_HANDLERS,
        "L": "_variable_assignment",
        "D": "_tool_correction",
        "FL": "_feed_from_variable",
    }

    def _number(self, raw, state):
        """An address without value is 0: 'G1 X EB-10' -> X0, 'G2 X Y I50 J' -> X0 Y0 J0."""
        return float(raw) if raw else 0.0

    def _corner(self, words, state):
        """EB20 -> rounding of radius 20 ; EB-10 -> chamfer of 10 (the sign gives the type)."""
        if len(words) != 1:
            return None
        size = self._number(words[0].value, state)
        if not size:  # EB0 / EB without value: nothing to round
            return None
        return Corner(type=CornerType.ROUND if size > 0 else CornerType.CHAMFER, size=abs(size))

    def _feed_from_variable(self, ctx, _):
        """FL<n>: feed = value of variable L<n> ('L1 = 2000' ... 'G1 Z-7 FL1' -> F2000)."""
        value = ctx.state.variables.get(int(ctx.value))
        if value is None:
            return None
        ctx.state.last_feed = value
        return FeedRate(value=value)

    def _motion(self, kind, axes, arc, state):
        if isinstance(kind, ArcDirection):
            if not arc:
                return None
            return CircularMove(direction=kind, **axes, **arc, feed=state.last_feed, wcs=state.wcs)
        if kind is LinearMove:
            return LinearMove(**axes, feed=state.last_feed, wcs=state.wcs)
        return RapidMove(**axes, wcs=state.wcs)

    def _local_offset(self, ctx, _):
        """G59: offset per axis added to the program origin (X Y Z A C -> IR).
        If it also carries a rotation (I/J/K centre + ED angle) or the U/V/W axes,
        the IR has no field for that -> NotIdentify rather than silently dropping it."""
        if any(ctx.param(a) is not None for a in ("I", "J", "K", "ED", "U", "V", "W")):
            return None
        axes = self._axis_values(ctx.params, ctx.state)
        return LocalOffset(**({axis: None for axis in IR_AXES} | axes))

    def _tcp(self, ctx, _):
        """G151: TCP on or off depending on its words.
            G151 EA0 EC0 EU0 T1 D1 -> ToolCompensation(TCP, offset="1")
            G151 S0                -> ToolCompensation(OFF)
        Anything else -> NotIdentify (e.g. EA/EC/EU not 0: the IR can't store angles)."""
        d, s = ctx.param("D"), ctx.param("S")

        if d is None and s is not None and float(s) == 0:
            return ToolCompensation(mode=ToolCompensationMode.OFF)

        angles = [ctx.param(a) for a in ("EA", "EC", "EU")]
        if d is not None and all(a is None or float(a) == 0 for a in angles):
            return ToolCompensation(mode=ToolCompensationMode.TCP, offset=d, tool=ctx.state.tool)

        return None

    def _dwell(self, ctx, _):
        """G4 F<seconds>."""
        seconds = ctx.param("F")
        return Dwell(time=float(seconds)) if seconds is not None else None

    def _tool_correction(self, ctx, _):
        """D<n>: NUM tool correction number. Inverse of what NumGrimmeWriter writes for LENGTH."""
        return ToolCompensation(mode=ToolCompensationMode.LENGTH, offset=ctx.value)
