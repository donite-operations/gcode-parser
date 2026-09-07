# core/ir.py
from dataclasses import dataclass, field
from typing import Union
from enum import Enum

#? Enum options

class AbsoluteMode(Enum):
    ABSOLUTE = True
    INCREMENTAL = False

class SpindleDirection(Enum):
    CLOCKWISE = "cw"
    COUNTERCLOCKWISE = "ccw"
    STOP = "stop"

class SpindleDirection(Enum):
    CLOCKWISE = "cw"
    COUNTERCLOCKWISE = "ccw"
    STOP = "stop"

class CoolantState(Enum):
    ON = "on"     # M8
    OFF = "off"   # M9

class CompensationMode(Enum):
    ON = "on"
    OFF = "off"

class RotationMode(Enum):
    ON = True
    OFF = False

@dataclass
class VariableRef:
    number: int

Expression = float | VariableRef

#? Syntax class

@dataclass
class Word:
    address: str
    value: Expression | float

@dataclass
class Block:
    line_number: int | None = None
    words: list[Word] = field(default_factory=list)
    comment: str | None = None
    adresses_list: list[str] | None = None

    def get(self, address: str) -> float | None:
        """Search the address and returns de G-Code Command Value -> 'G90' Return: 90"""
        for w in self.words:
            if w.address == address:
                return w.value
        return None

@dataclass
class Program:
    blocks: list[Block] = field(default_factory=list)

#? Actual state of the machine

@dataclass
class ModalState:
    active_g: int | None = None
    absolute_mode: bool = True
    units_mm: bool = True
    last_feed: float | None = None
    variables: dict[int, float] = field(default_factory=dict)

#? Machine Operations

@dataclass
class VariableAssignment:
    number: int
    value: float

@dataclass
class ToolChange:
    tool_number: int = 0

@dataclass
class SpindleControl:
    direction: SpindleDirection

@dataclass
class CoolantControl:
    state: CoolantState

class ToolCompensation:
    mode: CompensationMode
    offset: int | None

@dataclass
class SpindleSpeed:
    rpm: float = 0

@dataclass
class Dwell:
    time: float = 0
    
@dataclass
class LinearMove:
    x: float | None = None
    y: float | None = None
    z: float | None = None
    b: float | None = None
    c: float | None = None
    feed: float | None = None

@dataclass
class RapidMove:
    x: float | None = None
    y: float | None = None
    z: float | None = None
    b: float | None = None
    c: float | None = None
    # absolute_mode: AbsoluteMode = True

@dataclass
class CoordinateRotation:
    enabled: RotationMode

@dataclass
class ProgramEnd:
    pass

Operation = Union[LinearMove, RapidMove, ToolChange, SpindleSpeed, ProgramEnd, VariableAssignment]
