# core/ir.py
from dataclasses import dataclass, field
from typing import Union


@dataclass
class Word:
    address: str
    value: float


@dataclass
class Block:
    line_number: int | None = None
    words: list[Word] = field(default_factory=list)
    comment: str | None = None

    def get(self, address: str) -> float | None:
        for w in self.words:
            if w.address == address:
                return w.value
        return None


@dataclass
class Program:
    blocks: list[Block] = field(default_factory=list)


@dataclass
class ModalState:
    active_g: int | None = None
    absolute_mode: bool = True
    units_mm: bool = True
    last_feed: float | None = None


@dataclass
class LinearMove:
    x: float | None = None
    y: float | None = None
    z: float | None = None
    feed: float | None = None


@dataclass
class RapidMove:
    x: float | None = None
    y: float | None = None
    z: float | None = None


@dataclass
class ToolChange:
    tool_number: int = 0


@dataclass
class SpindleSpeed:
    rpm: float = 0


@dataclass
class ProgramEnd:
    pass


Operation = Union[LinearMove, RapidMove, ToolChange, SpindleSpeed, ProgramEnd]
