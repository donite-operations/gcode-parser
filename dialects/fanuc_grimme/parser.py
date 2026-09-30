# dialects/fanuc_grimme/parser.py
"""FANUC GRIMME text -> IR. Same FANUC syntax as ARES (inherited), only the machine changes."""
import re

from core.ir import ToolCompensation, ToolCompensationMode
from dialects.fanuc_ares.parser import FanucAresParser
from dialects.fanuc_grimme import mapping
from dialects.base import Parser


class FanucGrimmeParser(FanucAresParser):
    MAPPING = mapping
    BEGIN_MARKERS = ("( ------------- 5X BEGIN ----------- )",)
    END_MARKERS = ("( ------- 5x END ------- )",)

    # Safe positions of this machine (Platte_FANUC_GRIMME.nc)
    SAFETY_LINES = (
        "G53 Z665",
        "G53 X540 Y-800 A0 C0",
        "G53 X540 Y-800",
    )

    # FANUC syntax the IR cannot represent: kept whole as NotIdentify.
    RAW_LINE_PATTERNS = (
        *FanucAresParser.RAW_LINE_PATTERNS,        # "/" block skip
        re.compile(r"^<"),                         # <PROGRAM NAME>
        re.compile(r"^(IF|WHILE|END\d|GOTO)"),     # macro loops / jumps
    )

    ADDRESS_HANDLERS = {
        **FanucAresParser.ADDRESS_HANDLERS,
        "D": "_tool_correction",
    }

    # This machine always writes offset 99 (G43 H99 / D99) for the active tool.
    # The IR stores the tool number instead, so NUM gets D<tool> and ARES H<tool>.

    def _tool_compensation(self, ctx, mode):
        """G43 H99 / G43.4 H99 / G49."""
        tool = ctx.state.tool
        offset = None if mode is ToolCompensationMode.OFF else tool
        return ToolCompensation(mode=mode, offset=offset, tool=tool)

    def _tool_correction(self, ctx, _):
        """D99 (with G41/G42): correction of the active tool."""
        return ToolCompensation(mode=ToolCompensationMode.LENGTH, offset=ctx.state.tool)
