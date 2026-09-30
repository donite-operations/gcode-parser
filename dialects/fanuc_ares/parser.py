# dialects/fanuc/parser.py
"""FANUC (ARES) text -> IR. Everything FANUC-specific lives here."""
import re

from core.ir import (
    ArcDirection, CircularMove, ContourControlMode, Dwell, LinearMove, ModalState, RapidMove,
    ToolCompensation,
)
from dialects.base import Parser
from dialects.fanuc_ares import mapping


class FanucAresParser(Parser):
    MAPPING = mapping
    BEGIN_MARKERS = ("(--- files_x/freeJob_begin_end_files/5X_begin.txt ---)",)
    END_MARKERS = ("(--- files_x/freeJob_begin_end_files/5X_end.txt ---)",)
    # G0G40G80G90 · #1=3000. · F#2 · Z-.5
    # TOKEN_PATTERN = re.compile(r"([A-Z#])(#\d+|\d+=-?[\d.]+|-?(?:\d+\.?\d*|\.\d+))")
    TOKEN_PATTERN = re.compile(r"(,?[A-Z#])(#\d+|\d+=-?[\d.]+|-?(?:\d+\.?\d*|\.\d+))")

    SAFETY_LINES = (
        "G53 G90 G00 Z-125 H0",  # new post (VT34 files)
        "G53 Z-100.",
        "G0 G53 Z-250",          # old post (fanuc_ares.nc)
        "G0 G53 B0",
        "G0 G53 Z0.",
    )

    G_HANDLERS = {
        **Parser.G_HANDLERS,
        "TOOL_COMPENSATION": "_tool_compensation",
        "DWELL": "_dwell",
        "CONTOUR_CONTROL": "_contour_control",
    }
    ADDRESS_HANDLERS = {
        **Parser.ADDRESS_HANDLERS,
        "#": "_variable_assignment",
    }

    def _number(self, raw: str, state: ModalState) -> float | None:
        """'12.5' -> 12.5 ; '#2' -> value of variable 2 (None if not defined)."""
        if raw.startswith("#"):
            return state.variables.get(int(raw[1:]))
        return float(raw)

    def _motion(self, kind, axes, arc, state):
        if isinstance(kind, ArcDirection):
            if not arc:
                return None  # an arc needs I/J/K or R
            return CircularMove(direction=kind, **axes, **arc, feed=state.last_feed, wcs=state.wcs)
        if kind is LinearMove:
            return LinearMove(**axes, feed=state.last_feed, wcs=state.wcs)
        return RapidMove(**axes, wcs=state.wcs)

    def _tool_compensation(self, ctx, mode):
        """G43 H3 / G43.4 H3 / G49."""
        return ToolCompensation(mode=mode, offset=ctx.param("H"), tool=ctx.state.tool)

    def _dwell(self, ctx, _):
        """G4 X<seconds> or G4 P<milliseconds>. IR Dwell.time is in seconds."""
        seconds, millis = ctx.param("X"), ctx.param("P")
        if seconds is not None:
            return Dwell(time=float(seconds))
        if millis is not None:
            return Dwell(time=float(millis) / 1000)
        return None

    def _contour_control(self, ctx, _):
        """G5.1 Q1 R5 / G5.1 Q0 (R is kept as the last tolerance)."""
        q, r = ctx.param("Q"), ctx.param("R")
        if q is None:
            return None
        if r is not None:
            ctx.state.last_contour_tolerance = int(float(r))
        return ContourControlMode(q=int(float(q)), tolerance=ctx.state.last_contour_tolerance)