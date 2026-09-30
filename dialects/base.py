# dialects/base.py
"""
Common logic shared by every dialect.

    text --Parser--> list[list[Operation]] --Writer--> text
                     (IR: one list per block)

A dialect only provides three files:
    mapping.py  code -> IR meaning (the writer uses the inverse automatically)
    parser.py   Parser subclass: MAPPING + what differs (token syntax, handlers)
    writer.py   Writer subclass: MAPPING + what differs (number format, handlers)

The base classes implement the ISO / FANUC-style behaviour most controls share.
Override a method only where your dialect really differs.

Unknown things are never guessed: anything the mapping does not cover becomes a
NotIdentifyOperation in the parser, or an "(UNMAPPED ...)" comment in the writer.
"""
import re
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from types import SimpleNamespace

from core.ir import (
    Absolute, AbsoluteMode, ArcDirection, Block, CancelOffset, CannedCycle, CoolantControl, CoolantState,
    CircularMove, CoordinateRotation, ContourControlMode, CutterCompensation, CycleType, Dwell,
    FeedRate, LinearMove, PlaneSelection, LocalOffset, ModalState, NotIdentifyOperation, Operation,
    Program, ProgramEnd, RapidMove, RotationMode, SpindleControl, SpindleDirection, SpindleSpeed,
    ToolChange, ToolCompensation, Unit, UnitMode, VariableAssignment, Word,
    WorkCoordinate, SafetyPoint, Corner, CornerType
)

IR_AXES = ("x", "y", "z", "b", "c")  # coordinate fields of LinearMove / RapidMove / LocalOffset
RAW = "RAW"                          # address of a whole line the IR cannot represent


# ---------------------------------------------------------------- helpers

def normalize_code(value: str) -> str:
    """'06' -> '6', '43.40' -> '43.4'. Makes 'M06' and 'M6' hit the same mapping entry."""
    try:
        number = float(value)
    except ValueError:
        return value
    return str(int(number)) if number.is_integer() else str(number)


def split_code(code: str) -> tuple[str, str]:
    """'G43.4' -> ('G', '43.4'), 'M06' -> ('M', '6')."""
    match = re.match(r"([A-Z#]+)(.*)", code)
    return match.group(1), normalize_code(match.group(2))


def invert(table: dict) -> dict:
    """{'90': ABSOLUTE, '91': INCREMENTAL} -> {ABSOLUTE: '90', ...}.
    If several codes share a meaning, the first one listed wins."""
    inverse = {}
    for code, meaning in table.items():
        inverse.setdefault(meaning, code)
    return inverse


def mapping_tables(codes_cls) -> dict[str, dict]:
    """The code tables (dict attributes) of a GCodes / MCodes class."""
    return {
        name: table for name, table in vars(codes_cls).items()
        if not name.startswith("_") and isinstance(table, dict)
    }

def word_text(words: list[Word]) -> str:
    return " ".join(f"{word.address}{word.value}" for word in words)

def normalize_marker(text: str) -> str:
    """'( ------- 5x END ------- )' -> '5X END'."""
    return " ".join(re.sub(r"[()\-]", " ", text).split()).upper()


@dataclass
class Sections:
    header: list[list[Operation]]
    body: list[list[Operation]]
    footer: list[list[Operation]]

# ================================================================ PARSER

@dataclass
class HandlerContext:
    """What a parser handler receives: the word being interpreted and its block."""
    command: str
    value: str
    state: ModalState
    block: Block
    line: int | None = None                           # source line (1-based)
    params: list[Word] = field(default_factory=list)  # words owned by this code (CODE_PARAMETERS)

    def param(self, address: str) -> str | None:
        for word in self.params:
            if word.address == address:
                return word.value
        return None


class Parser(ABC):
    """Generic engine: text -> list[list[Operation]].

    Only IR construction lives here. A dialect parser MUST define:
        MAPPING        its mapping module (GCodes, MCodes, AXES, ARC, CODE_PARAMETERS)
        TOKEN_PATTERN  how its words look
        _motion()      how its G0/G1/G2/G3 become IR moves
    and ADDS the handlers for its own tables/addresses to G_HANDLERS,
    M_HANDLERS and ADDRESS_HANDLERS.

    Step 1 (syntax):    each line -> Block(words)
    Step 2 (semantics): each Block -> list[Operation]
        1. words owned by a code (CODE_PARAMETERS) are handed to that code
        2. every other command word is dispatched to its handler
        3. motion goes last (explicit G0-G3, or modal: axes without G)
        4. whatever could not be interpreted -> one NotIdentifyOperation
    """

    MAPPING = None
    TOKEN_PATTERN: re.Pattern = None

    LINE_NUMBER_PATTERN = re.compile(r"^N(\d+)\s*")
    COMMENT_PATTERN = re.compile(r"\((.*?)\)")
    # Lines kept whole as NotIdentify. "/" = block skip (ISO): the IR can't mark a
    # block as optional, so it must not be converted as a normal block.
    RAW_LINE_PATTERNS: tuple[re.Pattern, ...] = (re.compile(r"^/"),)

    # Safety points: moves in MACHINE coordinates (FANUC G53 / NUM G52 = the
    # CANCEL_OFFSET table of the mapping). Machine coordinates are not portable
    # between machines, so they become SafetyPoint(axes) and the target writer
    # writes ITS OWN safe position. Each machine parser defines:
    SAFETY_LINES: tuple[str, ...] = ()

    # Generic handlers: they only turn a code into an IR operation, without
    # reading dialect-specific words. Dialects extend these dicts.
    # (MOTION is special: always interpreted last, see _motion_operation.)
    G_HANDLERS = {
        "ABSOLUTE": "_absolute_mode",
        "UNIT": "_unit",
        "PLANE": "_plane",
        "ROTATION": "_rotation",
        "CUTTER_COMPENSATION": "_cutter_compensation",
        "CANNED_CYCLE": "_canned_cycle",
        "WORK_COORDINATE_SYSTEM": "_work_coordinate_system",
        "CANCEL_OFFSET": "_cancel_offset",
        "LOCAL_OFFSET": "_local_offset",
    }
    M_HANDLERS = {
        "TOOL_CHANGE": "_tool_change",
        "SPINDLE_DIRECTION": "_spindle_control",
        "COOLANT": "_coolant_control",
        "PROGRAM_END": "_program_end",
    }
    ADDRESS_HANDLERS = {  # non G/M words that are commands on their own
        "F": "_feedrate",
        "S": "_spindle_speed",
    }

    def __init__(self):
        if self.MAPPING is None or self.TOKEN_PATTERN is None:
            raise TypeError(f"{type(self).__name__} must define MAPPING and TOKEN_PATTERN")
        g_codes, m_codes = self.MAPPING.GCodes, self.MAPPING.MCodes
        self._axes: dict[str, str] = self.MAPPING.AXES
        self._arc: dict[str, str] = getattr(self.MAPPING, "ARC", {})
        self._motion_codes = {normalize_code(c): op for c, op in g_codes.MOTION.items()}
        self._g = self._build_dispatch(g_codes, self.G_HANDLERS, skip={"MOTION"})
        self._m = self._build_dispatch(m_codes, self.M_HANDLERS)
        self._address = {a: (getattr(self, h), None) for a, h in self.ADDRESS_HANDLERS.items()}
        self._code_parameters = {
            split_code(code): set(addresses)
            for code, addresses in getattr(self.MAPPING, "CODE_PARAMETERS", {}).items()
        }
        self._begin_markers = {normalize_marker(m) for m in self.BEGIN_MARKERS}
        self._end_markers = {normalize_marker(m) for m in self.END_MARKERS}
        # Machine-coordinate codes: G53 on FANUC, G52 on NUM (both in CANCEL_OFFSET)
        self._machine_frame = {normalize_code(c) for c in getattr(g_codes, "CANCEL_OFFSET", {})}
        self._safety_keys = {self._words_key(self._parse_line(line)) for line in self.SAFETY_LINES}
        self._corner_types: dict[str, CornerType] = getattr(self.MAPPING, "CORNER", {})  # ",R" -> ROUND


    def _build_dispatch(self, codes_cls, handlers: dict, skip=()) -> dict:
        """{normalized code: (handler, IR meaning)} built from the mapping tables."""
        dispatch = {}
        for name, table in mapping_tables(codes_cls).items():
            if name in skip:
                continue
            if name not in handlers:
                raise TypeError(f"{type(self).__name__}: no handler for {codes_cls.__name__}.{name}")
            handler = getattr(self, handlers[name])
            for code, meaning in table.items():
                dispatch[normalize_code(code)] = (handler, meaning)
        return dispatch

    @staticmethod
    def _words_key(block: Block) -> frozenset:
        """Words of a line, ignoring order, N and comments: 'G0 G53 Z-250.' == 'G53 G0 Z-250'."""
        return frozenset((w.address, normalize_code(w.value)) for w in block.words)

    def _safety_override(self, block: Block, line: int) -> list[Operation] | None:
        """Known safety line -> [SafetyPoint].
        Any other move in machine coordinates (G53 / NUM G52) -> NotIdentify: never translated literally.
        None = normal line."""
        if block.words and self._words_key(block) in self._safety_keys:
            return [SafetyPoint()]

        machine_coords = any(w.address == "G" and normalize_code(w.value) in self._machine_frame for w in block.words)
        moves = any(w.address in self._axes for w in block.words)
        if machine_coords and moves:
            warnings.warn(f"L{line}: unknown machine-coordinate move, not translated: {word_text(block.words)}")
            return [NotIdentifyOperation(line_number=line, operation=word_text(block.words))]
        return None
    # -------------------------------------------------- public API

    def parse(self, text: str) -> list[list[Operation]]:
        return self.parse_sections(text).body

    def parse_sections(self, text: str) -> Sections:
        """Parse the whole program (the header may declare variables used by the body)
        and split it into header / body / footer."""
        program = self._parse_program(text)
        state = ModalState()
        blocks: list[list[Operation]] = []
        begin = end = None
        for line, block in enumerate(program.blocks, start=1):

            operations = self._interpret_block(block, state, line)  # keeps the modal state (G0, G90...)
            override = self._safety_override(block, line)
            if override is not None:
                operations = override

            repeated_safety = operations == [SafetyPoint()] and blocks and blocks[-1] == operations
            if operations and not repeated_safety:
                blocks.append(operations)

            marker = normalize_marker(block.comment) if block.comment else None
            # Operations on a marker line belong to the body
            if begin is None and marker in self._begin_markers:
                begin = len(blocks)
            # LAST end marker: with several operations the body must keep all of them
            if begin is not None and marker in self._end_markers:
                end = len(blocks)

        if begin is None or end is None:
            begin, end = self._frame_bounds(blocks)
        return Sections(blocks[:begin], blocks[begin:end], blocks[end:])

    def _frame_bounds(self, blocks: list[list[Operation]]) -> tuple[int, int]:
        """Fallback when the source has no markers:
        body = first tool change .. last spindle stop / coolant off."""
        def has(block, check):
            return any(check(op) for op in block)

        def is_tool_change(op):
            return isinstance(op, ToolChange)

        def ends_machining(op):
            return (isinstance(op, SpindleControl) and op.mode is SpindleDirection.STOP) or \
                   (isinstance(op, CoolantControl) and op.mode is CoolantState.OFF)

        first = next((i for i, b in enumerate(blocks) if has(b, is_tool_change)), 0)
        last = max((i for i, b in enumerate(blocks) if has(b, ends_machining)), default=len(blocks) - 1)
        if last < first:
            last = len(blocks) - 1
        return first, last + 1

    # -------------------------------------------------- step 1: syntax

    def _parse_program(self, text: str) -> Program:
        # Empty lines are kept (as empty blocks) so block index == source line.
        return Program(blocks=[self._parse_line(line) for line in text.splitlines()])

    def _parse_line(self, raw_line: str) -> Block:
        line = raw_line.strip()

        comment = None
        match = self.COMMENT_PATTERN.search(line)
        if match:
            comment = match.group(1)
            line = self.COMMENT_PATTERN.sub("", line).strip()

        line_number = None
        match = self.LINE_NUMBER_PATTERN.match(line)
        if match:
            line_number = int(match.group(1))
            line = line[match.end():]

        if any(pattern.match(line) for pattern in self.RAW_LINE_PATTERNS):
            return Block(line_number=line_number, words=[Word(RAW, line.strip())], comment=comment)

        words = [Word(address, value) for address, value in self.TOKEN_PATTERN.findall(line)]
        return Block(line_number=line_number, words=words, comment=comment)

    # -------------------------------------------------- step 2: semantics

    def _interpret_block(self, block: Block, state: ModalState, line: int) -> list[Operation]:
        words = block.words
        if not words:
            return []
        if words[0].address == RAW:
            return [NotIdentifyOperation(line_number=line, operation=words[0].value)]

        params = self._collect_params(words)
        owned = {index for indexes in params.values() for index in indexes}

        operations: list[Operation] = []
        unknown: list[str] = []
        axis_words: list[Word] = []
        arc_words: list[Word] = []
        corner_words: list[Word] = []
        motion_code = None

        for i, word in enumerate(words):
            if i in owned:
                continue
            if word.address in self._axes:
                axis_words.append(word)
                continue
            if word.address in self._arc:
                arc_words.append(word)  # I J K R: only valid if the motion is an arc
                continue
            if word.address in self._corner_types:
                corner_words.append(word)  # ,R ,C / EB: only valid on a linear move
                continue
            if word.address == "G" and normalize_code(word.value) in self._motion_codes:
                motion_code = normalize_code(word.value)
                continue

            ctx = HandlerContext(
                command=word.address, value=word.value, state=state, block=block,
                line=line, params=[words[j] for j in params.get(i, [])],
            )
            operation = self._dispatch(ctx)
            if operation is None:
                unknown.append(word_text([word, *ctx.params]))
                if word.address == "G":
                    state.active_g = None  # an unknown G may have changed the motion mode
            else:
                operations.append(operation)

        motion, unused = self._motion_operation(motion_code, axis_words, arc_words, corner_words, state)
        if motion is not None:
            operations.append(motion)
        if unused:
            unknown.append(word_text(unused))

        if unknown:
            operations.append(NotIdentifyOperation(line_number=line, operation=" ".join(unknown)))
        return operations

    def _collect_params(self, words: list[Word]) -> dict[int, list[int]]:
        """{index of a code word: indexes of the words that belong to it}.
        e.g. 'G43.4 H3' -> H belongs to G43.4; NUM 'G4 F2' -> F is the dwell, not a feed."""
        params = {}
        for i, word in enumerate(words):
            addresses = self._code_parameters.get((word.address, normalize_code(word.value)))
            if addresses:
                params[i] = [j for j, other in enumerate(words) if j != i and other.address in addresses]
        return params

    def _dispatch(self, ctx: HandlerContext) -> Operation | None:
        if ctx.command == "G":
            entry = self._g.get(normalize_code(ctx.value))
        elif ctx.command == "M":
            entry = self._m.get(normalize_code(ctx.value))
        else:
            entry = self._address.get(ctx.command)

        if entry is None:
            return None
        handler, meaning = entry
        return handler(ctx, meaning)

    def _number(self, raw: str, state: ModalState) -> float | None:
        """Numeric value of a word. Dialects with variable references override it."""
        return float(raw)

    def _values(self, words: list[Word], fields: dict[str, str], state: ModalState) -> dict[str, float | None]:
        """Words -> IR fields using an address table, e.g. NUM 'A5' with AXES -> {'b': 5.0}."""
        return {fields[w.address]: self._number(w.value, state) for w in words if w.address in fields}

    def _axis_values(self, words: list[Word], state: ModalState) -> dict[str, float | None]:
        return self._values(words, self._axes, state)

    # -------------------------------------------------- motion

    def _motion_operation(self, code, axis_words, arc_words, corner_words, state):
        """Modal bookkeeping (generic): which motion applies to this block.
        Building the IR move is up to the dialect (_motion).
        Returns (operation or None, words that could not be used)."""
        if code is not None:
            state.active_g = code
        elif not axis_words:
            return None, arc_words + corner_words  # e.g. a lone R5: nothing to move

        kind = self._motion_codes.get(state.active_g)  # RapidMove / LinearMove / ArcDirection.CW...
        is_arc = isinstance(kind, ArcDirection)
        axes = self._axis_values(axis_words, state)
        arc = self._values(arc_words, self._arc, state) if is_arc else {}
        unused_arc = [] if is_arc else arc_words  # I/J/K/R without an arc -> unknown

        if kind is None or None in axes.values() or None in arc.values():
            return None, axis_words + arc_words + corner_words
        motion = self._motion(kind, axes, arc, state)
        if motion is None:
            return None, axis_words + arc_words + corner_words

        # Corner (not modal: only this block). Only a linear move can carry it.
        unused_corner = []
        if corner_words:
            corner = self._corner(corner_words, state) if isinstance(motion, LinearMove) else None
            if corner is None:
                unused_corner = corner_words
            else:
                motion.corner = corner
        return motion, unused_arc + unused_corner

    def _corner(self, words: list[Word], state: ModalState) -> Corner | None:
        """FANUC ',R20' / ',C10' -> Corner. None = cannot be represented -> NotIdentify.
        Dialects with another syntax (NUM EB) override it."""
        if len(words) != 1:
            return None
        size = self._number(words[0].value, state)
        if size is None or size <= 0:
            return None
        return Corner(type=self._corner_types[words[0].address], size=size)

    @abstractmethod
    def _motion(self, kind, axes: dict[str, float], arc: dict[str, float], state: ModalState) -> Operation | None:
        """Build the IR move for this dialect.
        kind: RapidMove / LinearMove class, or ArcDirection (then arc has i/j/k/r)."""

    # -------------------------------------------------- generic G handlers
    # Signature: (ctx, meaning) -> Operation | None   (None = NotIdentify)

    def _absolute_mode(self, ctx, mode: AbsoluteMode):
        ctx.state.absolute_mode = mode is AbsoluteMode.ABSOLUTE
        return Absolute(mode=mode)

    def _unit(self, ctx, unit: Unit):
        ctx.state.units_mm = unit is Unit.MM
        return UnitMode(value=unit)

    def _plane(self, ctx, plane):
        return PlaneSelection(plane=plane)

    def _rotation(self, ctx, enabled: RotationMode):
        if enabled is RotationMode.ON and ctx.params:
            return None  # centre / angle cannot be stored in the IR
        return CoordinateRotation(enabled=enabled)

    def _cutter_compensation(self, ctx, mode):
        return CutterCompensation(mode=mode)

    def _canned_cycle(self, ctx, cycle: CycleType):
        if cycle is CycleType.CANCEL:
            return CannedCycle(cycle=cycle)
        return None  # the IR CannedCycle has no X/Y hole position -> NotIdentify

    def _work_coordinate_system(self, ctx, wcs):
        ctx.state.wcs = wcs
        return WorkCoordinate(wcs=wcs)

    def _cancel_offset(self, ctx, _):
        ctx.state.wcs = None
        return CancelOffset()

    def _local_offset(self, ctx, _):
        axes = self._axis_values(ctx.params, ctx.state)
        return LocalOffset(**({axis: None for axis in IR_AXES} | axes))

    # -------------------------------------------------- generic M handlers

    def _tool_change(self, ctx, _):
        tool = ctx.param("T")
        ctx.state.tool = tool
        return ToolChange(tool_number=tool)

    def _spindle_control(self, ctx, direction):
        return SpindleControl(mode=direction)

    def _coolant_control(self, ctx, coolant):
        return CoolantControl(mode=coolant)

    def _program_end(self, ctx, _):
        return ProgramEnd()

    # -------------------------------------------------- generic address handlers

    def _feedrate(self, ctx, _):
        value = self._number(ctx.value, ctx.state)
        if value is None:
            return None
        ctx.state.last_feed = value
        return FeedRate(value=value)

    def _spindle_speed(self, ctx, _):
        return SpindleSpeed(rpm=float(ctx.value))

    def _variable_assignment(self, ctx, _):
        """'<n>=<value>' -> VariableAssignment. Registered by each dialect with its
        own address (FANUC '#1=3000.', NUM 'L1=3000.')."""
        number, _, value = ctx.value.partition("=")
        try:
            number, value = int(number), float(value)
        except ValueError:
            return None  # e.g. '#5=#5-1': an expression, not a value -> NotIdentify
        ctx.state.variables[number] = value
        return VariableAssignment(number=number, value=value)


# ================================================================ WRITER

class UnsupportedOperation(Exception):
    """Raised by a writer handler when the dialect has no code for an IR value."""


def describe(op: Operation) -> str:
    """ToolCompensation(mode=TCP, offset='3') -> 'ToolCompensation mode=TCP offset=3'."""
    fields = [
        f"{name}={value.name if isinstance(value, Enum) else value}"
        for name, value in vars(op).items() if value is not None
    ]
    return " ".join([type(op).__name__, *fields])


class Writer(ABC):
    """list[list[Operation]] -> text. One output line per block.

    A dialect writer MUST define MAPPING and build its machine's start and end
    sequence: _program_header() and _program_footer()."""

    MAPPING = None  # dialect mapping module: GCodes, MCodes, AXES, ARC

    PRECISION_MM = 3
    PRECISION_INCH = 4
    LINE_NUMBERS = True
    OMIT: set[type] = set()

    # Order of words inside a line: N G <axes/params> F S T M (comment)
    WORD_ORDER = {"G": 0, "F": 2, "S": 3, "T": 4, "M": 5, "(": 6}

    # Safety points (see Parser.SAFE_POSITIONS). Each machine writer defines:
    SAFETY_LINES: tuple[str, ...] = ()
    SAFETY_LINES: list[str] = []
    TOOL_CHANGE_LINES: list[str] = []

    HANDLERS = {
        RapidMove: "_write_rapid_move",
        LinearMove: "_write_linear_move",
        CircularMove: "_write_circular_move",
        ToolChange: "_write_tool_change",
        SpindleControl: "_write_spindle_control",
        SpindleSpeed: "_write_spindle_speed",
        CoolantControl: "_write_coolant",
        CutterCompensation: "_write_cutter_comp",
        ToolCompensation: "_write_tool_comp",
        WorkCoordinate: "_write_wcs",
        LocalOffset: "_write_local_offset",
        CancelOffset: "_write_cancel_offset",
        Absolute: "_write_absolute",
        CoordinateRotation: "_write_rotation",
        ContourControlMode: "_write_contour_control",
        CannedCycle: "_write_canned_cycle",
        Dwell: "_write_dwell",
        FeedRate: "_write_feed_rate",
        UnitMode: "_write_unit_mode",
        PlaneSelection: "_write_plane",
        VariableAssignment: "_write_variable_assignment",
        ProgramEnd: "_write_program_end",
        NotIdentifyOperation: "_write_not_identified",
    }

    def __init__(self, line_numbers: bool | None = None, line_number_start: int = 1, line_number_step: int = 1):
        self.line_numbers = self.LINE_NUMBERS if line_numbers is None else line_numbers
        self.line_number_start = line_number_start
        self.line_number_step = line_number_step
        # IR -> code tables, e.g. self.G.ABSOLUTE[AbsoluteMode.ABSOLUTE] == "90"
        self.G = SimpleNamespace(**{n: invert(t) for n, t in mapping_tables(self.MAPPING.GCodes).items()})
        self.M = SimpleNamespace(**{n: invert(t) for n, t in mapping_tables(self.MAPPING.MCodes).items()})
        self.axes = invert(self.MAPPING.AXES)  # IR field -> address, e.g. 'b' -> 'A' on NUM
        self.arc = invert(getattr(self.MAPPING, "ARC", {}))  # 'i' -> 'I' ...
        self.reset()
        self.corner = invert(getattr(self.MAPPING, "CORNER", {}))  # CornerType.ROUND -> ',R'

    def reset(self) -> None:
        self.state = ModalState()
        self._next_n = self.line_number_start
        self._at_safe: set[str] = set()  # axes at their safe position since the last move

    # -------------------------------------------------- public API

    def write(self, program: list[list[Operation]]) -> str:
        self.reset()
        header = [self._frame_line(line) for line in self._program_header()]
        body = [line for block in program for line in self._write_body_block(block)]
        footer = [self._frame_line(line) for line in self._program_footer()]
        return "\n".join(line for line in header + body + footer if line)

    def _write_body_block(self, block: list[Operation]) -> list[str]:
        """One line per block. A SafetyPoint is replaced by this machine's SAFETY_LINES,
        and every tool change is preceded by its TOOL_CHANGE_LINES."""
        if block == [SafetyPoint()]:
            return self._safety_lines(self.SAFETY_LINES)
        lines = []
        if any(isinstance(op, ToolChange) for op in block):
            lines = self._safety_lines(self.TOOL_CHANGE_LINES)
        return lines + [self._write_block(block)]

    def _safety_lines(self, lines: list[str]) -> list[str]:
        if not lines:
            raise NotImplementedError(f"{type(self).__name__} defines no SAFETY_LINES / TOOL_CHANGE_LINES")
        self.state.active_g = None  # these lines contain G0: the next move must write its G again
        return [self._frame_line(line) for line in lines]

    # -------------------------------------------------- safety points

    def _write_safety_point(self, op: SafetyPoint) -> list[str]:
        """SafetyPoint(axes) -> this machine's own safe position for those axes.
        Axes without a safe position here are dropped (no line if none is left).
        Z goes first on its own line: never move XY / rotaries before retracting."""
        if not self.SAFE_POSITION:
            raise NotImplementedError(f"{type(self).__name__} defines no SAFE_POSITION")
        axes = [axis for axis in IR_AXES if axis in op.axes and axis in self.SAFE_POSITION]
        self._at_safe |= set(axes)
        groups = [["z"], [a for a in axes if a != "z"]] if "z" in axes else [axes]
        return [self._safety_line(group) for group in groups if group]

    def _safety_line(self, axes: list[str]) -> str:
        coordinates = " ".join(f"{self.axes[a]}{self._fmt(self.SAFE_POSITION[a])}" for a in axes)
        # The prefix contains G0: the next move must write its own G code again
        self.state.active_g = self._code(self.G, "MOTION", RapidMove)
        return self._frame_line(f"{self.SAFETY_PREFIX} {coordinates}")

    def _tool_change_safety(self) -> list[str]:
        """Safe axes this machine needs before a tool change that are not safe yet."""
        missing = self.TOOL_CHANGE_SAFE_AXES - self._at_safe
        return self._write_safety_point(SafetyPoint(axes=frozenset(missing))) if missing else []

    # -------------------------------------------------- machine start / end

    @abstractmethod
    def _program_header(self) -> list[str]:
        """Program start code + machine reset (literal lines, without N numbers)."""

    @abstractmethod
    def _program_footer(self) -> list[str]:
        """Return to home + program end (literal lines, without N numbers)."""

    def _frame_line(self, line: str) -> str:
        """Header/footer lines get N numbers like the body (except %, O and comments)."""
        if not self.line_numbers or not line or line[0] in "%O(":
            return line
        numbered = f"N{self._next_n} {line}"
        self._next_n += self.line_number_step
        return numbered

    # -------------------------------------------------- block assembly

    def _write_block(self, block: list[Operation]) -> str:
        words: list[Word] = []
        seen: set[tuple[str, str]] = set()
        for operation in block:
            for word in self._dispatch_words(operation):
                key = (word.address, word.value)
                if key not in seen:
                    seen.add(key)
                    words.append(word)
        words.sort(key=lambda word: self.WORD_ORDER.get(word.address, 1))  # stable
        return self._render_block(words)

    def _render_block(self, words: list[Word]) -> str:
        if not words:
            return ""
        parts = [f"{word.address}{word.value}" for word in words]
        if self.line_numbers:
            parts.insert(0, f"N{self._next_n}")
            self._next_n += self.line_number_step
        return " ".join(parts)

    def _dispatch_words(self, operation: Operation) -> list[Word]:
        if type(operation) in self.OMIT:
            return []

        name = self.HANDLERS.get(type(operation))
        if name is None:
            raise NotImplementedError(f"{type(self).__name__} has no handler for {type(operation).__name__}")
        try:
            return getattr(self, name)(operation)
        except UnsupportedOperation:
            return [self._comment(f"UNMAPPED {describe(operation)}")]

    # -------------------------------------------------- helpers

    @staticmethod
    def _code(tables: SimpleNamespace, table: str, meaning) -> str:
        """Code of an IR meaning, or UnsupportedOperation if the dialect lacks it."""
        try:
            return getattr(tables, table)[meaning]
        except (AttributeError, KeyError):
            raise UnsupportedOperation from None

    def _g(self, table: str, meaning) -> Word:
        return Word("G", self._code(self.G, table, meaning))

    def _m(self, table: str, meaning) -> Word:
        return Word("M", self._code(self.M, table, meaning))

    def _comment(self, text: str) -> Word:
        return Word("(", text.replace("(", "[").replace(")", "]") + ")")

    def _fmt(self, value: float) -> str:
        """FANUC style: always keep the decimal point (-250. / 0.)."""
        precision = self.PRECISION_MM if self.state.units_mm else self.PRECISION_INCH
        text = f"{value:.{precision}f}".rstrip("0")
        return "0." if text == "-0." else text

    def _coordinate_words(self, op) -> list[Word]:
        words = []
        for axis in IR_AXES:
            value = getattr(op, axis)
            if value is None:
                continue
            if axis not in self.axes:
                raise UnsupportedOperation
            words.append(Word(self.axes[axis], self._fmt(value)))
        return words

    def _axis_words(self, op) -> list[Word]:
        words = []
        if op.wcs is not None and op.wcs != self.state.wcs:
            words.append(self._g("WORK_COORDINATE_SYSTEM", op.wcs))
            self.state.wcs = op.wcs
        return words + self._coordinate_words(op)

    def _motion_words(self, op, meaning) -> list[Word]:
        """meaning = the MOTION table value: RapidMove, LinearMove or ArcDirection.CW/CCW."""
        code = self._code(self.G, "MOTION", meaning)
        words = []
        if self.state.active_g != code:  # G0 / G1 are modal
            words.append(Word("G", code))
            self.state.active_g = code
        return words + self._axis_words(op)

    # -------------------------------------------------- handlers per operation
    # Look up codes BEFORE touching self.state (lookup may raise UnsupportedOperation).

    def _feed_words(self, feed: float | None) -> list[Word]:
        if feed is None or feed == self.state.last_feed:
            return []
        self.state.last_feed = feed
        return [Word("F", self._fmt(feed))]

    def _write_rapid_move(self, op: RapidMove) -> list[Word]:
        return self._motion_words(op, RapidMove)

    def _write_linear_move(self, op: LinearMove) -> list[Word]:
        return self._motion_words(op, LinearMove) + self._corner_words(op.corner) + self._feed_words(op.feed)

    def _corner_words(self, corner: Corner | None) -> list[Word]:
        """FANUC ',R20.' / ',C10.'. If this machine has no code for it, the move is kept
        and the corner is flagged in a comment (the corner would be lost silently otherwise)."""
        if corner is None:
            return []
        address = self.corner.get(corner.type)
        if address is None:
            return [self._comment(f"UNMAPPED Corner {corner.type.name} {self._fmt(corner.size)}")]
        return [Word(address, self._fmt(corner.size))]

    def _write_circular_move(self, op: CircularMove) -> list[Word]:
        words = self._motion_words(op, op.direction)
        for field, address in self.arc.items():  # I J K R
            value = getattr(op, field)
            if value is not None:
                words.append(Word(address, self._fmt(value)))
        return words + self._feed_words(op.feed)

    def _write_tool_change(self, op: ToolChange) -> list[Word]:
        change = self._m("TOOL_CHANGE", ToolChange)
        tool = [] if op.tool_number is None else [Word("T", str(op.tool_number))]

        return tool + [change]

    def _write_spindle_control(self, op: SpindleControl) -> list[Word]:
        return [self._m("SPINDLE_DIRECTION", op.mode)]

    def _write_spindle_speed(self, op: SpindleSpeed) -> list[Word]:
        return [Word("S", str(int(op.rpm)))]

    def _write_coolant(self, op: CoolantControl) -> list[Word]:
        return [self._m("COOLANT", op.mode)]

    def _write_cutter_comp(self, op: CutterCompensation) -> list[Word]:
        return [self._g("CUTTER_COMPENSATION", op.mode)]

    def _write_tool_comp(self, op: ToolCompensation) -> list[Word]:
        words = [self._g("TOOL_COMPENSATION", op.mode)]
        if op.offset is not None:
            words.append(Word("H", str(op.offset)))
        return words

    def _write_wcs(self, op: WorkCoordinate) -> list[Word]:
        word = self._g("WORK_COORDINATE_SYSTEM", op.wcs)
        self.state.wcs = op.wcs
        return [word]

    def _write_local_offset(self, op: LocalOffset) -> list[Word]:
        return [self._g("LOCAL_OFFSET", LocalOffset), *self._coordinate_words(op)]

    def _write_cancel_offset(self, op: CancelOffset) -> list[Word]:
        return [self._g("CANCEL_OFFSET", CancelOffset)]

    def _write_absolute(self, op: Absolute) -> list[Word]:
        word = self._g("ABSOLUTE", op.mode)
        self.state.absolute_mode = op.mode is AbsoluteMode.ABSOLUTE
        return [word]

    def _write_plane(self, op: PlaneSelection) -> list[Word]:
        return [self._g("PLANE", op.plane)]

    def _write_rotation(self, op: CoordinateRotation) -> list[Word]:
        return [self._g("ROTATION", op.enabled)]

    def _write_contour_control(self, op: ContourControlMode) -> list[Word]:
        words = [self._g("CONTOUR_CONTROL", ContourControlMode), Word("Q", str(op.q))]
        if op.tolerance is not None:
            words.append(Word("R", self._fmt(op.tolerance)))
        self.state.last_contour_tolerance = op.tolerance
        return words

    def _write_canned_cycle(self, op: CannedCycle) -> list[Word]:
        words = [self._g("CANNED_CYCLE", op.cycle)]
        for address, value in (("Z", op.z), ("R", op.r), ("Q", op.peck)):
            if value is not None:
                words.append(Word(address, self._fmt(value)))
        if op.dwell is not None:
            words.append(Word("P", str(round(op.dwell * 1000))))  # seconds -> ms
        if op.feed is not None and op.feed != self.state.last_feed:
            words.append(Word("F", self._fmt(op.feed)))
            self.state.last_feed = op.feed
        return words

    def _write_dwell(self, op: Dwell) -> list[Word]:
        return [self._g("DWELL", Dwell), Word("P", str(round(op.time * 1000)))]  # seconds -> ms

    def _write_feed_rate(self, op: FeedRate) -> list[Word]:
        self.state.last_feed = op.value
        return [Word("F", self._fmt(op.value))]

    def _write_unit_mode(self, op: UnitMode) -> list[Word]:
        word = self._g("UNIT", op.value)
        self.state.units_mm = op.value is Unit.MM
        return [word]

    def _write_variable_assignment(self, op: VariableAssignment) -> list[Word]:
        return [Word(f"#{op.number}", f"={self._fmt(op.value)}")]

    def _write_program_end(self, op: ProgramEnd) -> list[Word]:
        return [self._m("PROGRAM_END", ProgramEnd)]

    def _write_not_identified(self, op: NotIdentifyOperation) -> list[Word]:
        where = f" L{op.line_number}" if op.line_number is not None else ""
        return [self._comment(f"UNMAPPED{where}: {op.operation}")]
