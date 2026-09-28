# dialects/num/parser.py
"""GRIMME NUM text -> IR. Everything NUM-specific lives here."""
import re

from core.ir import (
    ArcDirection, CircularMove, Dwell, LinearMove, RapidMove, ToolCompensation, ToolCompensationMode,
    LocalOffset
    )
from dialects.base import Parser, IR_AXES
from dialects.num_grimme import mapping


class NumGrimmeParser(Parser):
    MAPPING = mapping
    BEGIN_MARKERS = ("( ------------- 5X BEGIN ----------- )",)
    END_MARKERS = ("( ------- 5x END ------- )",)  # the comma makes it a tuple
    # Two-letter addresses (EA, EC, EU, ER, EF...) and "E60001= 0" style assignments.
    TOKEN_PATTERN = re.compile(r"([A-Z]{1,2})(\d+\s*=\s*-?[\d.]+|-?(?:\d+\.?\d*|\.\d+))")

    # G52 moves recognised as SafetyPoint (any other G52 move -> NotIdentify)
    # "G52 G17 G90 G0 Z650" / "... X540 Y-600 Z650 A0 C0" / "... X540" / "... X540 Y-600 A0 C0"
    SAFE_POSITIONS = {
        "x": {540},
        "y": {-600},
        "z": {650},
        "b": {0},  # Grimme A axis (IR 'b')
        "c": {0},
    }

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
    }

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
