# dialects/base.py
from abc import ABC, abstractmethod
from core.ir import Operation


class Parser(ABC):
    @abstractmethod
    def parse(self, text: str) -> list[Operation]:
        """From G-Code text to an Operations list"""


class Writer(ABC):
    @abstractmethod
    def write(self, operations: list[Operation]) -> str:
        """From Operations list to a G-Code text"""
